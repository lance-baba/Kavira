#!/usr/bin/env python3
r"""Kavira · C1 语义通道**参数扫点**（找「消泄漏 + 保召回」的最小代价配置）。

扫点变量（**只动语义通道**，绝不动 `_is_grounded()` 的 `SEM_FLOOR`）：
  * ``semantic_min_corroboration`` ∈ {2, 3, 4}
  * 语义通道 floor ``SEMANTIC_FLOOR`` ∈ {0.60, 0.65}

每个组合（TEMP 隔离库、``KAVIRA_EMBEDDING_DIR`` 指向 C1、开闸门）跑：
  1. 门槛3 Holdout B → ``negative_guard.neg_semantic_new_citation_cases``（须 0）+ 8 红线；
  2. 门槛2 中文探针 32 → failure@5 / 空结果率 / 零字面子集（≤25% / ≤12% / ≤50%）。

覆写全在**子进程内存**（`_sweep_runner.py`），进程退出即还原，**不改产品默认值**。

用法::

    runtime/python-3.11-embed/python.exe eval/embedding_eval/sweep_channel.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
REPO = EVAL_DIR.parent
REPORTS = EVAL_DIR / "reports" / "embedding_eval"
SWEEP_DIR = REPORTS / "sweep"
RUNNER = HERE / "_sweep_runner.py"

C1_DIR = REPO / "vendor" / "cache" / "embedding_candidates" / "c1_e5_small"
INCUMBENT_FA = 0.125   # 现役 Holdout B FA（问题二既有；门槛3 要求「不新增」）

# 门槛2 / 门槛3
ZH_FAIL_MAX, ZH_EMPTY_MAX, ZH_ZERO_MAX = 0.25, 0.12, 0.50
RED = {
    "recall@1": ("retrieval.recall@1", ">=", 0.975),
    "recall@3": ("retrieval.recall@3", "==", 1.0),
    "recall@5": ("retrieval.recall@5", "==", 1.0),
    "wrong_document": ("retrieval.wrong_document_rate", "==", 0.0),
    "no_answer_fp": ("retrieval.no_answer_fp_rate", "==", 0.0),
    "false_assoc": ("relation.false_association_rate", "<=", 0.125),
    "unnecessary_guard": ("unnecessary_guard.unnecessary_guard_rate", "<=", 0.023),
    "citation_struct": ("citation.structural_rate", "==", 1.0),
    "overlap": ("citation.overlap_rate", ">=", 0.981),
}


def _g(d, dotted, default=None):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


def _cmp(val, op, thr):
    if val is None:
        return False
    return {">=": val >= thr, "<=": val <= thr, "==": abs(val - thr) < 1e-9}[op]


def run_one(mode: str, corrob: int, floor: float, base: Path, py: str) -> dict:
    cmd = [py, str(RUNNER), "--mode", mode, "--embedding-dir", str(C1_DIR),
           "--corrob", str(corrob), "--floor", str(floor), "--out", str(base)]
    env = {**os.environ}
    proc = subprocess.run(cmd, cwd=str(REPO), env=env, capture_output=True, text=True)
    rep = {}
    p = Path(f"{base}.json")
    if p.exists():
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            rep = {}
    return {"rc": proc.returncode, "report": rep,
            "tail": (proc.stdout or "")[-600:] + (proc.stderr or "")[-400:]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval/embedding_eval/sweep_channel.py")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--corrob", default="2,3,4")
    ap.add_argument("--floors", default="0.60,0.65")
    args = ap.parse_args(argv)

    corobs = [int(x) for x in args.corrob.split(",")]
    floors = [float(x) for x in args.floors.split(",")]
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for corrob, floor in itertools.product(corobs, floors):
        name = f"c1_N{corrob}_f{int(round(floor * 100))}"
        print(f"\n===== sweep {name} (corrob={corrob}, floor={floor}) =====")
        hb = run_one("holdout", corrob, floor, SWEEP_DIR / f"{name}.holdout", args.python)
        pr = run_one("probe", corrob, floor, SWEEP_DIR / f"{name}.probe", args.python)

        h, p = hb["report"], pr["report"]
        leak = _g(h, "negative_guard.neg_semantic_new_citation_cases")
        red_ok = {}
        for label, (dotted, op, thr) in RED.items():
            red_ok[label] = _cmp(_g(h, dotted), op, thr)
        # FA 不新增（不得 > 现役）
        fa = _g(h, "relation.false_association_rate")
        fa_ok = (fa is not None) and fa <= INCUMBENT_FA + 1e-9 and red_ok["false_assoc"]
        red_ok["false_assoc_no_increase"] = fa_ok
        leak_ok = (leak == 0)
        all_red = all(red_ok.values()) and leak_ok

        zh_fail = _g(p, "metrics.failure_rate@5")
        zh_empty = _g(p, "metrics.empty_result_rate")
        zh_zero = _g(p, "zero_lexical_subset.failure_rate@5")
        zh_ok = (zh_fail is not None and zh_fail <= ZH_FAIL_MAX
                 and zh_empty is not None and zh_empty <= ZH_EMPTY_MAX
                 and (zh_zero is None or zh_zero <= ZH_ZERO_MAX))

        row = {
            "corrob": corrob, "floor": floor, "name": name,
            "leak": leak, "leak_ok": leak_ok,
            "red_ok": red_ok, "all_red": all_red,
            "zh_failure@5": zh_fail, "zh_empty": zh_empty, "zh_zero_subset": zh_zero,
            "zh_ok": zh_ok,
            "feasible": bool(leak_ok and all_red and zh_ok),
            "holdout_rc": hb["rc"], "probe_rc": pr["rc"],
            "fa": fa,
        }
        rows.append(row)
        print(f"  leak={leak} all_red={all_red} zh_fail@5={zh_fail} zh_empty={zh_empty} "
              f"zh_zero={zh_zero} -> feasible={row['feasible']}")

    feasible = [r for r in rows if r["feasible"]]

    # —— 与已有 channel_sweep.json 合并（支持分批扫、避免重跑）——
    prev = {}
    prev_p = REPORTS / "channel_sweep.json"
    if prev_p.exists():
        try:
            for r in json.loads(prev_p.read_text(encoding="utf-8")).get("rows", []):
                prev[r["name"]] = r
        except ValueError:
            pass
    for r in rows:
        prev[r["name"]] = r
    rows = sorted(prev.values(), key=lambda r: (r["corrob"], r["floor"]))
    feasible = [r for r in rows if r["feasible"]]

    # 最小代价：优先保中文召回 → 取满足条件的最小 N、再最小 floor
    best = None
    if feasible:
        best = sorted(feasible, key=lambda r: (r["corrob"], r["floor"]))[0]

    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "candidate": "c1_e5_small", "vars": {"corrob": corobs, "floors": floors},
           "incumbent_fa": INCUMBENT_FA, "rows": rows,
           "feasible_count": len(feasible),
           "recommended": ({"corrob": best["corrob"], "floor": best["floor"]}
                           if best else None)}
    (REPORTS / "channel_sweep.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORTS / "channel_sweep.md").write_text(_render(out), encoding="utf-8")
    print(f"\n扫点表 → {REPORTS / 'channel_sweep.md'}")
    return 0


def _render(out: dict) -> str:
    L = ["# C1 语义通道参数扫点（消泄漏 + 保召回）", "",
         f"- 候选：`multilingual-e5-small`（384/mean/前缀）｜生成：{out['generated_at']}",
         f"- 变量：`semantic_min_corroboration` ∈ {out['vars']['corrob']}；"
         f"`SEMANTIC_FLOOR` ∈ {out['vars']['floors']}（**闸门 `SEM_FLOOR` 未动**）",
         f"- 口径：TEMP 隔离库、开闸门、真实模型；**内存级覆写，未改产品默认值**", "",
         "| N | floor | 泄漏例数 | 中文 failure@5 | 空结果率 | 零字面子集 | 红线全过 | 可行性 |",
         "|--:|--:|--:|--:|--:|--:|:--:|:--:|"]
    for r in out["rows"]:
        L.append(
            f"| {r['corrob']} | {r['floor']:.2f} | {r['leak']} | "
            f"{'—' if r['zh_failure@5'] is None else format(r['zh_failure@5'], '.4f')} | "
            f"{'—' if r['zh_empty'] is None else format(r['zh_empty'], '.4f')} | "
            f"{'—' if r['zh_zero_subset'] is None else format(r['zh_zero_subset'], '.4f')} | "
            f"{'✅' if r['all_red'] else '❌'} | {'✅' if r['feasible'] else '❌'} |")
    L += ["", "目标：泄漏=0 且 中文 failure@5 ≤25% / 空结果 ≤12% / 零字面子集 ≤50% 且 8 红线全过。",
          "", "## 结论", ""]
    rec = out.get("recommended")
    if rec:
        L.append(f"✅ **存在可行配置**：`semantic_min_corroboration={rec['corrob']}`、"
                 f"`SEMANTIC_FLOOR={rec['floor']:.2f}`（满足条件的**最小代价**，优先保中文召回）。")
    else:
        L.append("❌ **无解**：所有组合要么泄漏>0、要么中文跌出目标。"
                 "详见上表最好的一档（供「召回 vs 负例安全」权衡）。")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
