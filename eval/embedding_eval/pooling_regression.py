#!/usr/bin/env python3
r"""Kavira · P0-0 pooling 修复的**零回归自证**（golden 逐位比对）。

背景
====
`app/core/embedder.py` 历史上把 pooling 硬编码成 CLS（`last_hidden[:, 0, :]`），
`artifact.json` 里的 `pooling` 字段被解析却从未生效（PRD §5 / 设计债 F5）。修复后
`OnnxEmbedder._pool()` 会按声明选择 `cls` / `mean`；**未知值按不可用降级**。

对现役 `bge-small-zh-v1.5-int8`（声明 `pooling=cls`）的硬红线是：
**修复前后向量逐位一致**（PRD §5.2 / R7）。本脚本用「改动前先照相、改动后逐位比对」
把这条红线变成可复现的证据。

子命令
======
* ``capture``  —— **Step 0（改动前）**：现役 local_onnx 上对固定有序文本集算向量，
  逐元素 ``np.float32(v).tobytes().hex()`` 落盘为 golden（默认
  ``eval/reports/embedding_eval/pooling_golden.cls.json``）。**已存在默认拒绝覆盖**。
* ``verify``   —— **Step A（改动后）**：重算并**逐位比对**（要求 100% 相等）。
* ``selftest`` —— 同一模型上 ``mean != cls``，且 ``mean`` 与 numpy 手算 ``< 1e-6``。

固定有序文本集（deterministic）
===============================
1. `eval/paraphrase/queries.json` 的 **32 条**探针 query（按文件顺序）；
2. `eval/fixtures_holdout_b/` 的 **8 篇**文档，每篇的 parent ``retrieval_text``
   （``retrieval_text_of(section_path, content)``；文档按文件名升序、父块按 ``ord`` 升序）。

> 文本集本身**只在改动前固定一次**；capture 会把每条文本的 sha256 一并落盘，
> verify 会先校验文本集未漂移（否则 golden 无意义）。
>
> ⚠ **复现注意（QA caveat，2026-10-16）**：两条都满足才可逐位复现 ——
> ① **同一 artifact**：golden 是 **bge-small-zh-v1.5（CLS）** 的基线。现役发布位置
>    (`vendor/cache/embedding`) 在 T07 已换成 **multilingual-e5-small（mean/384）** ⇒
>    **须把 `KAVIRA_EMBEDDING_DIR` 指向 bge 备份**
>    `vendor/cache/embedding_bge_small_zh_v1.5_backup`（本脚本未显式设 env 时**已默认**指向它）。
>    对 e5 跑 golden 会得到 0/84 —— 那是 **artifact 不匹配**，不是回归（`verify` 会前置报错）。
> ② **同一 84 条批**：INT8 的 CLS 输出对 **padding 后的序列长度**敏感 —— 同一文本单独跑 vs
>    在批内（被 padding 到批内最长）跑，逐元素 `max|Δ|` 实测可达 **~1e-2**、cosine≈0.997
>    （语义影响可忽略，但**逐位**复现必须同批）。`verify` 用与 `capture` 相同的批才有意义。

安全：全程 TEMP 隔离库；不触碰真实 Library；不写任何产品数据。

用法（随包嵌入式运行时，自带 onnxruntime / tokenizers）::

    runtime/python-3.11-embed/python.exe eval/embedding_eval/pooling_regression.py capture
    runtime/python-3.11-embed/python.exe eval/embedding_eval/pooling_regression.py verify
    runtime/python-3.11-embed/python.exe eval/embedding_eval/pooling_regression.py selftest
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
REPO = EVAL_DIR.parent
REPORTS_DIR = EVAL_DIR / "reports" / "embedding_eval"

# ⚠ 必须在 import 任何 app 模块**之前**设置：app/core/paths.py:125 是模块级求值。
def _default_embedding_dir() -> str:
    """golden 是 bge-small-zh(CLS) 的基线；现役发布位置可能已换成别的 artifact
    （T07 已换成 multilingual-e5-small/mean）。存在 bge 备份目录时默认指向它，
    使 `capture`/`verify` 开箱即可复现/自证。"""
    env = (os.environ.get("KAVIRA_EMBEDDING_DIR") or "").strip()
    if env:
        return env
    backup = REPO / "vendor" / "cache" / "embedding_bge_small_zh_v1.5_backup"
    if backup.is_dir():
        return str(backup)
    return str(REPO / "vendor" / "cache" / "embedding")

_EMBEDDING_DIR = _default_embedding_dir()
os.environ["KAVIRA_EMBEDDING_DIR"] = _EMBEDDING_DIR

sys.path.insert(0, str(REPO))

# ⚠ 同样早于 app.core.paths：激活 TEMP 隔离测试库（本脚本不建库，但保持「永不碰真实
#   Library」的一致纪律；同时也避免 config.load() 之外的任何意外落盘）。
from tests import test_env  # noqa: E402

_LIB = test_env.activate_test_library(prefix="kavira-pooling-")

from app.core import chunker  # noqa: E402
from app.core import embedder as emb_mod  # noqa: E402

QUERIES_FILE = EVAL_DIR / "paraphrase" / "queries.json"
HB_FIXTURES = EVAL_DIR / "fixtures_holdout_b"
GOLDEN_NAME = "pooling_golden.cls.json"


# --------------------------------------------------------------------------
# 固定有序文本集
# --------------------------------------------------------------------------
def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_text_set() -> list[dict]:
    """构造**固定有序**文本集：(32 探针 query) + (8 篇 holdout_b 的 parent retrieval_text)。

    顺序严格确定：query 按文件顺序；父块按「文档名升序 → parent.ord 升序」。
    """
    items: list[dict] = []

    data = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    rows = data["queries"] if isinstance(data, dict) else data
    for i, q in enumerate(rows):
        if not isinstance(q, dict):
            continue
        text = str(q.get("query") or "")
        items.append({
            "kind": "probe_query", "key": str(q.get("id") or f"q{i}"),
            "ord": i, "text": text,
        })

    for name in sorted(p.name for p in HB_FIXTURES.glob("*.md")):
        text_md = (HB_FIXTURES / name).read_text(encoding="utf-8")
        parsed = chunker.parse(text_md, name)
        for p in sorted(parsed.parents, key=lambda x: x.ord):
            items.append({
                "kind": "hb_parent", "key": f"{name}:p{p.ord}", "ord": p.ord,
                "text": chunker.retrieval_text_of(p.section_path, p.content),
            })
    return items


def _load_embedder(pooling_override: str | None = None):
    """按随包资源构建 OnnxEmbedder（可选覆写 pooling，仅供 selftest）。"""
    resource, code, why = emb_mod.load_embedding_resource()
    if resource is None:
        raise SystemExit(f"⛔ 随包嵌入资源不可用（{code}：{why}）；目录={_EMBEDDING_DIR}")
    if pooling_override is not None:
        resource = dataclasses.replace(resource, pooling=pooling_override)
    return resource, emb_mod.OnnxEmbedder(resource)


def _hex_of_vector(vec) -> str:
    """逐元素 np.float32(v).tobytes().hex() 拼接（= 该 float32 向量的字节级快照）。"""
    import numpy as np

    return "".join(np.float32(x).tobytes().hex() for x in vec)


# --------------------------------------------------------------------------
# Step 0：capture
# --------------------------------------------------------------------------
def cmd_capture(args) -> int:
    out = Path(args.out) if args.out else (REPORTS_DIR / GOLDEN_NAME)
    if out.exists() and not args.force:
        print(f"⛔ golden 已存在，拒绝覆盖（防误改基准）：{out}\n"
              "   确要重拍请显式加 --force。")
        return 6

    resource, emb = _load_embedder()
    ok, why = emb.probe()
    if not ok:
        print(f"⛔ 现役 local_onnx 探针失败：{why}")
        return 3

    items = build_text_set()
    texts = [it["text"] for it in items]
    t0 = time.time()
    vecs = emb.embed(texts)
    elapsed = time.time() - t0

    records = []
    for it, vec in zip(items, vecs):
        records.append({
            "kind": it["kind"], "key": it["key"], "ord": it["ord"],
            "text_sha256": _sha256_text(it["text"]),
            "dim": len(vec),
            "hex": _hex_of_vector(vec),
        })

    payload = {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "purpose": "P0-0 pooling 修复的「改动前」基线；改动后逐位比对（要求 100% 相等）",
            "embedding_dir": _EMBEDDING_DIR.replace("\\", "/"),
            "resource_id": resource.id,
            "base_model": resource.base_model,
            "precision": resource.precision,
            "declared_pooling": resource.pooling,
            "normalize": resource.normalize,
            "max_length": resource.max_length,
            "dimension": int(getattr(emb, "dim", 0) or resource.dimension),
            "count": len(records),
            "elapsed_s": round(elapsed, 3),
            "text_set_rule": ("32 条探针 query（文件顺序） + 8 篇 holdout_b 文档的 "
                              "parent retrieval_text（文档名升序 → parent.ord 升序）"),
            "hex_encoding": "逐元素 np.float32(v).tobytes().hex() 拼接",
        },
        "vectors": records,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[capture] {len(records)} 条向量已落盘：{out}")
    print(f"[capture] resource={resource.id} pooling={resource.pooling} "
          f"dim={payload['meta']['dimension']} elapsed={elapsed:.3f}s")
    return 0


# --------------------------------------------------------------------------
# Step A：verify（逐位比对）
# --------------------------------------------------------------------------
def cmd_verify(args) -> int:
    golden_path = Path(args.golden) if args.golden else (REPORTS_DIR / GOLDEN_NAME)
    if not golden_path.exists():
        print(f"⛔ golden 不存在：{golden_path}（请先运行 capture）")
        return 2
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    gvecs = {r["key"]: r for r in golden["vectors"]}

    items = build_text_set()
    resource, emb = _load_embedder()

    # 前置：golden 只对「同一 artifact（id / pooling）」有意义（T07 后现役位置已换 e5/mean）
    gmeta = golden.get("meta", {})
    if ((gmeta.get("resource_id") and resource.id != gmeta["resource_id"])
            or (gmeta.get("declared_pooling")
                and resource.pooling != gmeta["declared_pooling"])):
        print("=" * 72)
        print("  ⛔ golden 与当前嵌入资源不匹配 —— 比对无意义（artifact 不匹配，非回归）")
        print("=" * 72)
        print(f"  golden 针对 : {gmeta.get('resource_id')} / pooling={gmeta.get('declared_pooling')}")
        print(f"  当前资源    : {resource.id} / pooling={resource.pooling}")
        print("  请把 KAVIRA_EMBEDDING_DIR 指向该 artifact（bge 备份）：")
        print("    vendor/cache/embedding_bge_small_zh_v1.5_backup")
        return 4

    ok, why = emb.probe()
    if not ok:
        print(f"⛔ 现役 local_onnx 探针失败：{why}")
        return 3

    # 文本集漂移检查：capture 时的 sha256 必须与现在一致，否则 golden 无意义。
    drift = []
    for it in items:
        g = gvecs.get(it["key"])
        if g is None:
            drift.append(f"{it['key']}：golden 缺失")
        elif g["text_sha256"] != _sha256_text(it["text"]):
            drift.append(f"{it['key']}：文本 sha256 漂移")
    if drift or len(items) != len(golden["vectors"]):
        print("=" * 72)
        print("  ⛔ 文本集漂移 —— golden 与当前文本集不一致，比对无意义")
        print("=" * 72)
        for d in drift[:20]:
            print("   - " + d)
        print(f"   golden 条数={len(golden['vectors'])} 当前条数={len(items)}")
        return 4

    vecs = emb.embed([it["text"] for it in items])
    mismatches: list[dict] = []
    for it, vec in zip(items, vecs):
        g = gvecs[it["key"]]
        h = _hex_of_vector(vec)
        if h != g["hex"]:
            # 定位第一个不同的 float32 元素，便于诊断
            first = None
            for idx in range(0, min(len(g["hex"]), len(h)), 8):
                if g["hex"][idx:idx + 8] != h[idx:idx + 8]:
                    first = idx // 8
                    break
            mismatches.append({"key": it["key"], "dim": len(vec),
                               "first_diff_index": first})

    total = len(items)
    equal = total - len(mismatches)
    print("=" * 72)
    print("  P0-0 · Step A —— golden 逐位比对（现役 CLS 模型，要求 100% 相等）")
    print("=" * 72)
    print(f"  golden      : {golden_path}")
    print("  ⚠ 复现注意   : golden 须按同一 84 条批重放（INT8 [CLS] 依赖 padding 后序列长度）")
    print(f"  resource    : {golden['meta']['resource_id']} "
          f"(pooling={golden['meta']['declared_pooling']}, "
          f"dim={golden['meta']['dimension']})")
    print(f"  比对条数    : {total}")
    print(f"  逐位一致    : {equal}/{total}  ({equal / total * 100:.1f}%)")
    if mismatches:
        print(f"  逐位不一致  : {len(mismatches)}")
        for m in mismatches[:10]:
            print(f"     - {m['key']}  首个不同元素 index={m['first_diff_index']}")
        print("  ⛔ 零回归红线不达（向量非逐位一致）")
        print("=" * 72)
        return 1
    print("  ✅ 逐位一致 100% —— CLS 修复前后向量字节级相同，零回归成立")
    print("=" * 72)
    return 0


# --------------------------------------------------------------------------
# selftest：mean != cls 且 mean 与 numpy 手算 < 1e-6
# --------------------------------------------------------------------------
def _reference_pool(emb, texts: list[str], mode: str):
    """用同一 session 手算参考向量（独立于 _pool 实现）。"""
    import numpy as np

    np_mod = emb._np
    encs = emb._tok.encode_batch(list(texts))
    ids = np_mod.array([e.ids for e in encs], dtype=np_mod.int64)
    mask = np_mod.array([e.attention_mask for e in encs], dtype=np_mod.int64)
    feed: dict = {}
    names = set(emb.io_names["inputs"])
    if "input_ids" in names:
        feed["input_ids"] = ids
    if "attention_mask" in names:
        feed["attention_mask"] = mask
    if "token_type_ids" in names:
        feed["token_type_ids"] = np_mod.zeros_like(ids)
    outputs = emb._session.run(None, feed)
    last_hidden = None
    for name, arr in zip(emb.io_names["outputs"], outputs):
        if "last_hidden_state" in name.lower():
            last_hidden = arr
            break
    if last_hidden is None:
        last_hidden = [a for a in outputs if getattr(a, "ndim", 0) == 3][0]

    if mode == "cls":
        pooled = last_hidden[:, 0, :]
    else:
        m = mask.astype(np_mod.float32)[:, :, None]
        pooled = (last_hidden * m).sum(axis=1) / np_mod.clip(m.sum(axis=1), 1e-9, None)
    if emb.resource.normalize:
        norms = np_mod.linalg.norm(pooled, axis=1, keepdims=True)
        pooled = pooled / np_mod.clip(norms, 1e-9, None)
    return np_mod.asarray(pooled, dtype=np_mod.float32)


def cmd_selftest(args) -> int:
    import numpy as np

    texts = ["抽血化验之前得饿多长时间？",
             "基坑开挖深度约 17.6 米，监测频率为开挖阶段 1 次/天。",
             "这台万能材料试验机的责任人是谁？"]

    res_cls, emb_cls = _load_embedder(pooling_override="cls")
    res_mean, emb_mean = _load_embedder(pooling_override="mean")
    ok1, why1 = emb_cls.probe()
    ok2, why2 = emb_mean.probe()
    if not (ok1 and ok2):
        print(f"⛔ 探针失败：cls={why1} mean={why2}")
        return 3

    v_cls = np.asarray(emb_cls.embed(texts), dtype=np.float32)
    v_mean = np.asarray(emb_mean.embed(texts), dtype=np.float32)

    # ① mean 与 numpy 手算一致（<1e-6）
    ref_mean = _reference_pool(emb_mean, texts, "mean")
    ref_cls = _reference_pool(emb_cls, texts, "cls")
    err_mean = float(np.max(np.abs(v_mean - ref_mean)))
    err_cls = float(np.max(np.abs(v_cls - ref_cls)))

    # ② mean != cls（同一模型、同一输入）
    max_abs_diff = float(np.max(np.abs(v_mean - v_cls)))

    print("=" * 72)
    print("  P0-0 · selftest —— cls/mean 正确性")
    print("=" * 72)
    print(f"  max|mean - numpy手算| : {err_mean:.3e}   (要求 < 1e-6)")
    print(f"  max|cls  - numpy手算| : {err_cls:.3e}   (要求 < 1e-6)")
    print(f"  max|mean - cls|       : {max_abs_diff:.3e}   (要求 > 0，即两者不同)")
    ok = (err_mean < 1e-6) and (err_cls < 1e-6) and (max_abs_diff > 0.0)
    print(f"  结论：{'✅ PASS' if ok else '⛔ FAIL'}")
    print("=" * 72)
    return 0 if ok else 1


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval/embedding_eval/pooling_regression.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_cap = sub.add_parser("capture", help="Step 0：改动前拍 golden（默认拒绝覆盖）")
    p_cap.add_argument("--out", default=None, help="golden 输出路径")
    p_cap.add_argument("--force", action="store_true", help="允许覆盖已存在的 golden")
    p_cap.set_defaults(func=cmd_capture)

    p_ver = sub.add_parser("verify", help="Step A：改动后逐位比对")
    p_ver.add_argument("--golden", default=None, help="golden 路径")
    p_ver.set_defaults(func=cmd_verify)

    p_st = sub.add_parser("selftest", help="cls/mean 正确性自检")
    p_st.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    try:
        return int(args.func(args))
    finally:
        try:
            test_env.cleanup_test_library(_LIB)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
