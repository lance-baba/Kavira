#!/usr/bin/env python3
r"""Kavira · 嵌入 artifact **速度基准**（门槛1 · F4 铁律「先测速度」）。

在**产品配置（2 线程）**下测四项（PRD §4.3 门槛1）：
  1. 单条延迟（batch=1，ms，取中位数）
  2. 批量吞吐（batch=32，ms/条）
  3. session 加载（s，冷加载一次）
  4. 全量重建（换 artifact 后首次索引，s；8 篇 holdout_b → 隔离库）

对照现役基线（``incumbent.speed.json``），**每项 ≤3× 现役**为过（阈值由 run_matrix 判定）。
不过关即 STOP、不测质量（铁律留痕）。

关键实现约束（与 run_probe / holdout_b_run 顶部同源）
====================================================
* ``--embedding-dir`` 由 ``KAVIRA_EMBEDDING_DIR`` 传入，且**必须早于 import app.core.paths**
  （paths.py:125 模块级求值）。故本脚本用**延迟 import**：先 parse + setenv，再 import app。
* 全程 **TEMP 隔离库**（tests.test_env），绝不碰 repo/data。
* 线程数：``OnnxEmbedder._lazy`` 固定 ``intra_op_num_threads = 2``（产品口径），此处不改。

用法::

    runtime/python-3.11-embed/python.exe eval/embedding_eval/bench_speed.py \
        --embedding-dir vendor/cache/embedding --id incumbent
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
REPO = EVAL_DIR.parent
REPORTS_DIR = EVAL_DIR / "reports" / "embedding_eval"

sys.path.insert(0, str(REPO))
from tests import test_env  # noqa: E402  （stdlib-only，安全在 env 之前 import）

QUERIES_FILE = EVAL_DIR / "paraphrase" / "queries.json"
HB_FIXTURES = EVAL_DIR / "fixtures_holdout_b"


def _load_texts() -> list[str]:
    try:
        data = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
        rows = data["queries"] if isinstance(data, dict) else data
        texts = [str(r.get("query") or "") for r in rows if isinstance(r, dict)]
        texts = [t for t in texts if t]
        if texts:
            return texts
    except (OSError, ValueError):
        pass
    return ["这是一条用于速度基准的中文测试文本。"]


def _time_call(fn, repeat: int) -> list[float]:
    out: list[float] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval/embedding_eval/bench_speed.py")
    ap.add_argument("--embedding-dir", required=True, help="含 artifact.json 的资源目录")
    ap.add_argument("--id", default=None, help="候选 id")
    ap.add_argument("--out", default=None, help="speed 报告输出路径")
    ap.add_argument("--n-single", type=int, default=20, help="单条测量重复次数")
    ap.add_argument("--n-batch", type=int, default=10, help="batch=32 重复次数")
    ap.add_argument("--batch", type=int, default=32, help="批大小")
    ap.add_argument("--fixtures", default=str(HB_FIXTURES), help="全量重建语料目录")
    ap.add_argument("--warmup", type=int, default=3, help="预热次数")
    args = ap.parse_args(argv)

    root = Path(args.embedding_dir)
    if not root.is_absolute():
        root = (REPO / root)
    cid = args.id or root.name
    out = Path(args.out) if args.out else (REPORTS_DIR / f"{cid}.speed.json")
    if not out.is_absolute():
        out = REPO / out

    # ⚠ 必须早于 import app.core.*
    os.environ["KAVIRA_EMBEDDING_DIR"] = str(root)
    _LIB = test_env.activate_test_library(prefix=f"kavira-bench-{cid}-"[:32])

    from app.core import config, db as db_mod, indexer, paths  # noqa: E402
    from app.core import embedder as emb_mod  # noqa: E402

    report: dict = {
        "id": cid,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "embedding_dir": str(root).replace("\\", "/"),
        "threads": 2,
        "ok": False,
        "problems": [],
    }

    try:
        resource, code, why = emb_mod.load_embedding_resource()
        if resource is None:
            report["problems"].append(f"资源不可用（{code}：{why}）")
            _write(out, report)
            print(f"⛔ 资源不可用（{code}：{why}）；目录={root}")
            return 3

        # ---- ③ session 加载（冷加载一次）----
        emb = emb_mod.OnnxEmbedder(resource)
        t0 = time.perf_counter()
        emb._lazy()                                            # noqa: SLF001
        load_s = time.perf_counter() - t0

        ok, why = emb.probe()
        if not ok:
            report["problems"].append(f"probe 失败：{why}")
            _write(out, report)
            print(f"⛔ probe 失败：{why}")
            return 3

        texts = _load_texts()
        single_text = texts[0]
        batch_texts = (texts * ((args.batch // len(texts)) + 1))[:args.batch]

        # 预热
        for _ in range(args.warmup):
            emb.embed([single_text])
            emb.embed(batch_texts)

        # ---- ① 单条延迟 ----
        single_ms = _time_call(lambda: emb.embed([single_text]), args.n_single)
        # ---- ② 批量/索引吞吐 ----
        batch_ms = _time_call(lambda: emb.embed(batch_texts), args.n_batch)
        batch_per_item = [x / args.batch for x in batch_ms]

        # ---- ④ 全量重建（隔离库）----
        rebuild = _measure_rebuild(emb, Path(args.fixtures),
                                   int(getattr(emb, "dim", 0) or resource.dimension))

        report.update({
            "ok": True,
            "resource_id": resource.id,
            "precision": resource.precision,
            "declared_pooling": resource.pooling,
            "dimension": int(getattr(emb, "dim", 0) or resource.dimension),
            "normalize": resource.normalize,
            "n_single": args.n_single,
            "n_batch": args.n_batch,
            "batch_size": args.batch,
            "single_ms_median": round(statistics.median(single_ms), 3),
            "single_ms_mean": round(statistics.fmean(single_ms), 3),
            "single_ms_min": round(min(single_ms), 3),
            "batch_ms_median": round(statistics.median(batch_ms), 3),
            "batch_ms_per_item_median": round(statistics.median(batch_per_item), 3),
            "load_s": round(load_s, 3),
            "rebuild_s": rebuild["seconds"],
            "rebuild_docs": rebuild["docs"],
            "rebuild_chunks": rebuild["chunks"],
            "rebuild_error": rebuild.get("error", ""),
        })
    except BaseException as exc:  # noqa: BLE001
        report["problems"].append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            test_env.cleanup_test_library(_LIB)
        except Exception:  # noqa: BLE001
            pass

    _write(out, report)

    if report["ok"]:
        print("=" * 72)
        print(f"  门槛1 · 速度基准：{cid}（{report['threads']} 线程）")
        print("=" * 72)
        print(f"  单条延迟(batch=1)     : {report['single_ms_median']} ms  (median)")
        print(f"  批量吞吐(batch={report['batch_size']})   : {report['batch_ms_per_item_median']} ms/条")
        print(f"  session 加载          : {report['load_s']} s")
        print(f"  全量重建({report['rebuild_docs']} 篇)    : {report['rebuild_s']} s"
              f"  ({report['rebuild_chunks']} chunks)")
        print(f"  → {out}")
        print("=" * 72)
        return 0
    print("⛔ 速度基准失败：" + "; ".join(report["problems"]))
    return 3


def _measure_rebuild(emb, fixtures: Path, dim: int) -> dict:
    """在隔离库内用给定嵌入器全量索引 fixtures，返回耗时/规模。"""
    from app.core import db as db_mod, indexer, paths  # noqa: PLC0415

    out: dict = {"seconds": None, "docs": 0, "chunks": 0, "error": ""}
    lib = None
    db = None
    try:
        lib = test_env.create_isolated_library(prefix="kavira-bench-rebuild-")
        os.environ["KAVIRA_LIBRARY"] = str(lib)
        paths.rebind(lib)
        paths.ensure_dirs()
        db = db_mod.get_db(paths.CACHE_DB, embedding_dim=dim)
        db.init_schema()
        srcs = sorted(Path(fixtures).glob("*.md"))
        t0 = time.perf_counter()
        for src in srcs:
            dst = paths.NOTES_DIR / src.name
            shutil.copyfile(src, dst)
            indexer.index_file(db, dst, emb)
        out["seconds"] = round(time.perf_counter() - t0, 3)
        out["docs"] = len(srcs)
        out["chunks"] = int(db.query("SELECT count(*) AS n FROM chunks")[0]["n"])
    except BaseException as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if db is not None:
            try:
                db.checkpoint_and_close()
            except Exception:  # noqa: BLE001
                pass
        try:
            import logging
            lg = logging.getLogger("wikiusb")
            for h in list(lg.handlers):
                try:
                    h.close()
                except Exception:  # noqa: BLE001
                    pass
                lg.removeHandler(h)
        except Exception:  # noqa: BLE001
            pass
        if lib is not None:
            try:
                test_env.cleanup_test_library(lib)
            except Exception:  # noqa: BLE001
                pass
    return out


def _write(out: Path, report: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
