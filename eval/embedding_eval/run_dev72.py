#!/usr/bin/env python3
r"""Kavira · DEV72 **真实模型口径** 跑分器（复用 run_eval 的题目/建库/指标。

背景：`eval/run_eval.py baseline` 固定用 `HashEmbedder`（local_hash），**测不出**
真实语义差异（PRD §1.5-F7）。holdout_b_run 已用真实 local_onnx 口径；DEV72 缺同口径
跑分器，本脚本补上——**指标聚合与 run_eval.run_baseline 逐字一致**，只换嵌入器。

用法::

    runtime/python-3.11-embed/python.exe eval/embedding_eval/run_dev72.py \
        --embedding-dir vendor/cache/embedding --id incumbent
    runtime/python-3.11-embed/python.exe eval/embedding_eval/run_dev72.py \
        --embedding-dir vendor/cache/embedding_candidates/c1_e5_small --id c1_e5_small
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
REPO = EVAL_DIR.parent
REPORTS_DIR = EVAL_DIR / "reports" / "embedding_eval"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval/embedding_eval/run_dev72.py")
    ap.add_argument("--embedding-dir", required=True)
    ap.add_argument("--id", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    root = Path(args.embedding_dir)
    if not root.is_absolute():
        root = REPO / root
    cid = args.id or root.name
    out_base = Path(args.out) if args.out else (REPORTS_DIR / f"{cid}.dev72")
    if not out_base.is_absolute():
        out_base = REPO / out_base

    # ⚠ 必须早于 import app（paths.py 模块级求值）
    os.environ["KAVIRA_EMBEDDING_DIR"] = str(root)
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(EVAL_DIR))

    import run_eval as R  # noqa: E402  —— import 即激活 TEMP 隔离库 + import app.core.paths
    from app.core import config, embedder as emb_mod  # noqa: E402

    # 真实嵌入源（走生产 resolve 全链路）
    resolved = emb_mod.resolve(config.get)
    emb = resolved.embedder
    if str(resolved.source) != "local_onnx" or not isinstance(emb, emb_mod.OnnxEmbedder):
        print("⛔ 未解析到真实 local_onnx 嵌入器："
              f"source={resolved.source} fallback={resolved.fallback_reason}")
        return 3
    res = getattr(emb, "resource", None)
    emb_meta = {
        "tier": str(getattr(emb, "source", "")), "model_id": str(getattr(emb, "model", "")),
        "dimension": int(getattr(emb, "dim", 0) or 0), "signature": str(emb.signature),
        "resource_id": str(getattr(res, "id", "")), "base_model": str(getattr(res, "base_model", "")),
        "precision": str(getattr(emb, "precision", "")),
        "query_prefix": str(getattr(res, "query_prefix", "")),
        "document_prefix": str(getattr(res, "document_prefix", "")),
        "fallback_reason": str(resolved.fallback_reason or ""),
        "embedding_dir": str(root).replace("\\", "/"),
    }
    print(f"[dev72] id={cid} tier={emb_meta['tier']} model={emb_meta['model_id']} "
          f"dim={emb_meta['dimension']} prefixes={emb_meta['query_prefix']!r}/"
          f"{emb_meta['document_prefix']!r}")

    t0 = time.time()
    cases = R.load_gold(R.GOLD)
    db, emb = R.build_library(R.FIXTURES, embedder=emb)
    docs = R.doc_map(db)
    parents = R.parent_index(db)
    rows = [R.eval_case(c, db, emb, docs, parents) for c in cases]

    answered = [r for r in rows if r["answer_state"] == "answered"]
    negatives = [r for r in rows if r["category"] == "negative_no_answer"]
    attribution = [r for r in rows if r["category"] == "attribution"]
    cov_rows = [r for r in rows if "coverage_group_recall" in r]
    rel_rows = [r for r in rows if "relation_ok" in r]
    cit_rows = [r for r in rows if r.get("citation_intersect") is not None]
    cit_ok, cit_tot = R.citation_structural(db, parents, cases)

    def rate(items, key):
        vals = [bool(i.get(key)) for i in items if i.get(key) is not None]
        return (sum(vals) / len(vals)) if vals else None

    metrics = {
        "recall@1": rate(answered, "hit@1"),
        "recall@3": rate(answered, "hit@3"),
        "recall@5": rate(answered, "hit@5"),
        "mrr": (statistics.fmean([r["rr"] for r in answered]) if answered else None),
        "coverage_group_recall": (statistics.fmean([r["coverage_group_recall"] for r in cov_rows])
                                  if cov_rows else None),
        "coverage_full_rate": rate(cov_rows, "coverage_full"),
        "relation_accuracy": rate(rel_rows, "relation_ok"),
        "wrong_document_rate": rate(answered, "wrong_doc"),
        "no_answer_fp_rate": rate(negatives, "trap_hit"),
        "attribution_violation_rate": rate(attribution, "trap_hit"),
        "citation_structural_rate": (cit_ok / cit_tot) if cit_tot else None,
        "citation_intersection_rate": rate(cit_rows, "citation_intersect"),
    }

    per_cat: dict[str, dict] = {}
    for cat in sorted({c["category"] for c in cases}):
        rs = [r for r in rows if r["category"] == cat]
        ann = [r for r in rs if r["answer_state"] == "answered"]
        per_cat[cat] = {"n": len(rs), "recall@1": rate(ann, "hit@1"),
                        "recall@5": rate(ann, "hit@5")}

    per_query = [{"id": r["id"], "category": r["category"], "answer_state": r["answer_state"],
                  "hit@1": r["hit@1"], "hit@3": r["hit@3"], "hit@5": r["hit@5"],
                  "rr": round(r["rr"], 4), "route": r.get("route"),
                  "coverage_full": r.get("coverage_full"), "relation_ok": r.get("relation_ok"),
                  "trap_hit": r.get("trap_hit")} for r in rows]

    report = {
        "meta": {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "split": "dev",
                 "cases": len(cases), "top_k": R.TOP_K, "embedder": emb_meta,
                 "elapsed_s": round(time.time() - t0, 2),
                 "note": "DEV72 真实模型口径；指标聚合逐字复用 run_eval.run_baseline 口径"},
        "counts_by_category": dict(sorted(Counter(c["category"] for c in cases).items())),
        "metrics": metrics, "per_category": per_cat, "per_query": per_query,
    }
    out_base.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{out_base}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print("\n=== DEV72（真实模型口径）===")
    print(f"  cases={len(cases)}  embedder={emb_meta['model_id']} dim={emb_meta['dimension']}")
    for k, v in metrics.items():
        print(f"  {k:28s}: {'—' if v is None else round(v, 4)}")
    print(f"  → {out_base}.json")
    # 关闭隔离库
    try:
        R._DB.checkpoint_and_close()
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
    try:
        R.test_env.cleanup_test_library(R._LIB)
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
