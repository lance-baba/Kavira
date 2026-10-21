#!/usr/bin/env python3
r"""Kavira · 嵌入 artifact **独立**体检器（门槛0 · 资源可行性 / §12 provenance）。

设计红线
========
* **不 import app**：本工具刻意与产品代码解耦。它只认 ``artifact.json`` 与目录里的
  字节，用 ``onnxruntime`` 自己把模型跑一遍 —— 这样即便 `embedder.py` 有 bug，
  体检结论也不会被同一段有 bug 的代码污染（"独立"是本工具存在的全部意义）。
* **只读**：不写任何目录里的字节（provenance 报告写到 ``--out``）。
* **不联网**：只读本地文件。

它做什么
========
1. 读 ``artifact.json``，校验必需字段；
2. 校验模型文件存在、大小 == ``artifact_size``；
3. **重算** model / tokenizer 每个文件的 SHA256，与清单声明比对；
4. ``ort.InferenceSession`` 打印每个输入/输出的 **name / shape / type**；
5. 跑一次（dummy 输入）拿到**真实输出维度**（``last_hidden_state`` 的末维）；
6. 读清单声明的 pooling；若目录内有 ``1_Pooling/config.json`` 则**交叉核对**；
7. 产出 §14 格式的 provenance 到 ``--out``（默认 ``eval/reports/embedding_eval/candidates/<id>.json``）。

用法::

    runtime/python-3.11-embed/python.exe eval/embedding_eval/inspect_artifact.py \
        --embedding-dir vendor/cache/embedding --id incumbent
    runtime/python-3.11-embed/python.exe eval/embedding_eval/inspect_artifact.py \
        --embedding-dir vendor/cache/embedding_candidates/c1_e5_small --id c1_e5_small
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_REPORTS = HERE.parent / "reports" / "embedding_eval" / "candidates"


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _read_pooling_config(root: Path) -> dict | None:
    """若目录内有 ``1_Pooling/config.json``（sentence-transformers 规范）则返回其内容。"""
    p = root / "1_Pooling" / "config.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pooling_from_st_config(cfg: dict) -> str | None:
    if cfg.get("pooling_mode_cls_token"):
        return "cls"
    if cfg.get("pooling_mode_mean_tokens"):
        return "mean"
    if cfg.get("pooling_mode_max_tokens"):
        return "max"
    if cfg.get("pooling_mode_mean_sqrt_len_tokens"):
        return "mean_sqrt_len"
    return None


def inspect(embedding_dir: Path, candidate_id: str) -> dict:
    import numpy as np
    import onnxruntime as ort

    problems: list[str] = []
    checks: list[dict] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(cond), "detail": str(detail)})
        if not cond:
            problems.append(f"{name}: {detail}")

    manifest_path = embedding_dir / "artifact.json"
    if not manifest_path.is_file():
        return {
            "id": candidate_id, "embedding_dir": str(embedding_dir).replace("\\", "/"),
            "ok": False, "problems": [f"缺少 artifact.json"],
            "checks": checks,
        }
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    local = data.get("local_files") or {}
    model_name = Path(str(local.get("model") or "model.onnx")).name
    tok_name = Path(str(local.get("tokenizer") or "tokenizer.json")).name
    model_path = embedding_dir / model_name

    # ---- 1) 模型文件 ----
    chk("模型文件存在", model_path.is_file(), str(model_path))
    declared_size = int(data.get("artifact_size") or 0)
    real_size = model_path.stat().st_size if model_path.is_file() else 0
    chk("模型大小 == artifact_size", real_size == declared_size,
        f"declared={declared_size} real={real_size}")

    # ---- 2) SHA256 重算 ----
    declared_sha = str(data.get("artifact_sha256") or "").lower()
    real_sha = _sha256(model_path) if model_path.is_file() else ""
    chk("模型 SHA256 == artifact_sha256", bool(real_sha) and real_sha == declared_sha,
        f"declared={declared_sha[:16]}… real={real_sha[:16]}…")

    tok_files: dict[str, dict] = {}
    for name, rec in (data.get("tokenizer_files") or {}).items():
        fname = Path(name).name
        fp = embedding_dir / fname
        if not fp.is_file():
            chk(f"tokenizer 文件存在 {fname}", False, str(fp))
            continue
        got = _sha256(fp)
        want = str((rec or {}).get("sha256") or "").lower()
        tok_files[fname] = {"size": fp.stat().st_size, "sha256": got,
                            "declared_sha256": want, "match": got == want}
        chk(f"tokenizer SHA256 匹配 {fname}", got == want,
            f"declared={want[:16]}… real={got[:16]}…")

    # ---- 3) onnxruntime 体检 ----
    io: dict = {"inputs": [], "outputs": []}
    real_dim: int | None = None
    if model_path.is_file():
        try:
            so = ort.SessionOptions()
            so.intra_op_num_threads = 2
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess = ort.InferenceSession(str(model_path), sess_options=so,
                                        providers=["CPUExecutionProvider"])
            for i in sess.get_inputs():
                io["inputs"].append({"name": i.name, "shape": i.shape, "type": i.type})
            for o in sess.get_outputs():
                io["outputs"].append({"name": o.name, "shape": o.shape, "type": o.type})

            # dummy 输入跑一次，拿真实输出维度
            in_names = {i["name"] for i in io["inputs"]}
            feed: dict = {}
            if "input_ids" in in_names:
                feed["input_ids"] = np.zeros((1, 8), dtype=np.int64)
            if "attention_mask" in in_names:
                feed["attention_mask"] = np.ones((1, 8), dtype=np.int64)
            if "token_type_ids" in in_names:
                feed["token_type_ids"] = np.zeros((1, 8), dtype=np.int64)
            if feed:
                outs = sess.run(None, feed)
                for name, arr in zip([o["name"] for o in io["outputs"]], outs):
                    if "last_hidden_state" in name.lower() and getattr(arr, "ndim", 0) == 3:
                        real_dim = int(arr.shape[-1])
                        break
                if real_dim is None:
                    cand = [a for a in outs if getattr(a, "ndim", 0) == 3]
                    if cand:
                        real_dim = int(cand[0].shape[-1])
            chk("onnxruntime 前向成功", True, f"real_dim={real_dim}")
        except BaseException as exc:  # noqa: BLE001
            chk("onnxruntime 前向成功", False, f"{type(exc).__name__}: {exc}")

    declared_dim = int(data.get("dimension") or 0)
    if real_dim is not None:
        chk("真实维度 == 清单 declared dimension", real_dim == declared_dim,
            f"declared={declared_dim} real={real_dim}")

    # ---- 4) pooling + 交叉核对 ----
    declared_pooling = str(data.get("pooling") or "").lower()
    st_cfg = _read_pooling_config(embedding_dir)
    st_pooling = _pooling_from_st_config(st_cfg) if st_cfg else None
    if st_pooling is not None:
        chk("清单 pooling 与 1_Pooling/config.json 一致", declared_pooling == st_pooling,
            f"manifest={declared_pooling} st={st_pooling}")

    provenance = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "id": candidate_id,
        "embedding_dir": str(embedding_dir).replace("\\", "/"),
        "ok": not problems,
        # §14 / §12 格式
        "model_id": data.get("id"),
        "artifact_source": data.get("artifact_source"),
        "artifact_revision": data.get("artifact_revision"),
        "base_model": data.get("base_model"),
        "base_model_revision": data.get("base_model_revision"),
        "filename": data.get("artifact_file") or model_name,
        "precision": data.get("precision"),
        "size": real_size,
        "declared_size": declared_size,
        "sha256": real_sha,
        "declared_sha256": declared_sha,
        "license": data.get("license"),
        "tokenizer": {"files": tok_files},
        "pooling": declared_pooling,
        "pooling_config_file": st_cfg,
        "pooling_from_config_file": st_pooling,
        "query_prefix": str(data.get("query_prefix") or ""),
        "document_prefix": str(data.get("document_prefix") or ""),
        "normalization": "l2" if data.get("normalize", True) else "none",
        "dimension": declared_dim,
        "real_dimension": real_dim,
        "max_length": int(data.get("max_length") or 512),
        "onnx_io": io,
        "checks": checks,
        "problems": problems,
    }
    return provenance


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval/embedding_eval/inspect_artifact.py")
    ap.add_argument("--embedding-dir", required=True, help="含 artifact.json 的资源目录")
    ap.add_argument("--id", default=None, help="候选 id（默认取目录名）")
    ap.add_argument("--out", default=None, help="provenance 输出路径（默认 reports/.../candidates/<id>.json）")
    args = ap.parse_args(argv)

    root = Path(args.embedding_dir)
    if not root.is_absolute():
        root = (REPO / root)
    cid = args.id or root.name
    out = Path(args.out) if args.out else (DEFAULT_REPORTS / f"{cid}.json")
    if not out.is_absolute():
        out = REPO / out

    prov = inspect(root, cid)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 72)
    print(f"  门槛0 · artifact 体检：{cid}")
    print("=" * 72)
    print(f"  dir        : {root}")
    print(f"  model      : {prov.get('filename')}  precision={prov.get('precision')}")
    print(f"  size       : {prov.get('size')} (declared {prov.get('declared_size')})")
    print(f"  sha256     : {str(prov.get('sha256'))[:24]}…")
    print(f"  dimension  : declared={prov.get('dimension')} real={prov.get('real_dimension')}")
    print(f"  pooling    : declared={prov.get('pooling')} "
          f"from_config={prov.get('pooling_from_config_file')}")
    print(f"  onnx IO    : "
          + "; ".join(i["name"] + str(i["shape"]) for i in prov.get("onnx_io", {}).get("inputs", [])))
    print(f"  checks     : {sum(1 for c in prov['checks'] if c['ok'])}/{len(prov['checks'])} ok")
    for c in prov["checks"]:
        print(("   ✅ " if c["ok"] else "   ❌ ") + c["name"] + ("" if c["ok"] else f"  [{c['detail']}]"))
    print(f"  → {out}")
    print("=" * 72)
    return 0 if prov["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
