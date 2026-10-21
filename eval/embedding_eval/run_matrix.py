#!/usr/bin/env python3
r"""Kavira · 嵌入评估 **矩阵编排器**（逐候选 × 逐闸门，全部走子进程）。

三门槛顺序固定、不可跳步（PRD §4.2）：
  门槛0 资源可行   → inspect_artifact.py
  门槛1 速度       → bench_speed.py（对照 incumbent.speed.json，**每项 ≤3× 现役**）
  门槛2 质量       → run_probe.py（中文 32 题，开/关闸门）
  门槛3 安全       → holdout_b_run.py（开/关闸门）

铁律：**门槛1 不过 → 直接否决候选，不跑质量/安全**（F4，省评测预算）。

每个候选的每一闸门都是**独立子进程**（各自 ``KAVIRA_EMBEDDING_DIR``），
保证候选之间、候选与 harness 之间互不串味。

用法::

    # 现役基线（门槛0+1）
    runtime/python-3.11-embed/python.exe eval/embedding_eval/run_matrix.py --id incumbent
    # 全候选 门槛0+1
    runtime/python-3.11-embed/python.exe eval/embedding_eval/run_matrix.py
    # 通过速度门槛后再跑质量/安全（显式 opt-in）
    runtime/python-3.11-embed/python.exe eval/embedding_eval/run_matrix.py --id c1_e5_small --quality
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
REPO = EVAL_DIR.parent
REPORTS_DIR = EVAL_DIR / "reports" / "embedding_eval"
CANDIDATES = HERE / "candidates.json"

# 门槛1 阈值（PRD §4.3）
SPEED_FACTOR = 3.0          # 单条 / 批量 / 重建 每项 ≤ 3× 现役
LOAD_ABS_MAX_S = 1.0        # session 加载 ≤ 1.0 s

# 门槛2 / 门槛3 阈值（PRD §4.3）
GATE2 = {"failure_rate@5": 0.25, "empty_result_rate": 0.12}
GATE2_ZERO = {"failure_rate@5": 0.50}
GATE3 = {"recall@1": 0.975, "wrong_document_rate": 0.0, "no_answer_fp_rate": 0.0}
GATE3_FA_MAX = 0.125


def _run(cmd: list[str], env_extra: dict) -> tuple[int, str]:
    env = {**os.environ, **env_extra}
    proc = subprocess.run(cmd, cwd=str(REPO), env=env,
                          capture_output=True, text=True)
    tail = (proc.stdout or "")[-1500:] + (proc.stderr or "")[-1500:]
    return proc.returncode, tail


def _read_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def gate0(cand: dict, py: str) -> dict:
    out = REPORTS_DIR / "candidates" / f"{cand['id']}.json"
    cmd = [py, str(HERE / "inspect_artifact.py"),
           "--embedding-dir", cand["embedding_dir"], "--id", cand["id"],
           "--out", str(out)]
    rc, tail = _run(cmd, {})
    prov = _read_json(out) or {}
    return {"gate": 0, "passed": bool(rc == 0 and prov.get("ok")),
            "report": str(out).replace("\\", "/"), "detail": tail[-400:],
            "dimension": prov.get("real_dimension"),
            "pooling": prov.get("pooling")}


def gate1(cand: dict, py: str, incumbent_speed: dict | None) -> dict:
    out = REPORTS_DIR / f"{cand['id']}.speed.json"
    cmd = [py, str(HERE / "bench_speed.py"),
           "--embedding-dir", cand["embedding_dir"], "--id", cand["id"],
           "--out", str(out)]
    rc, tail = _run(cmd, {})
    speed = _read_json(out) or {}
    res: dict = {"gate": 1, "passed": False, "report": str(out).replace("\\", "/"),
                 "detail": tail[-400:], "speed": speed.get("single_ms_median")}

    if rc != 0 or not speed.get("ok"):
        res["reason"] = "速度基准失败：" + "; ".join(speed.get("problems") or [tail[-200:]])
        return res

    if cand.get("is_baseline") or incumbent_speed is None:
        res["passed"] = True
        res["reason"] = "基线自身（无对照）；作为后续候选的比较基准"
        return res

    rows = []
    checks = [
        ("single_ms_median", "单条延迟", SPEED_FACTOR),
        ("batch_ms_per_item_median", "批量吞吐/条", SPEED_FACTOR),
        ("rebuild_s", "全量重建", SPEED_FACTOR),
    ]
    ok = True
    for key, label, factor in checks:
        base = incumbent_speed.get(key)
        cur = speed.get(key)
        if cur is None:
            rows.append({"item": label, "base": base, "candidate": cur,
                         "ratio": None, "pass": False})
            ok = False
            continue
        if base in (None, 0):
            rows.append({"item": label, "base": base, "candidate": cur, "ratio": None,
                         "pass": None})
            continue
        ratio = cur / base
        p = ratio <= factor
        ok = ok and p
        rows.append({"item": label, "base": base, "candidate": cur,
                     "ratio": round(ratio, 3), "pass": p})
    # session 加载另按绝对上限
    load = speed.get("load_s")
    load_ok = (load is not None) and (load <= LOAD_ABS_MAX_S)
    ok = ok and load_ok
    rows.append({"item": "session 加载", "base": None, "candidate": load,
                 "abs_max": LOAD_ABS_MAX_S, "pass": load_ok})

    res["passed"] = bool(ok)
    res["rows"] = rows
    res["reason"] = "全部 ≤3× 且加载 ≤1.0s" if ok else "存在超阈值项 → 否决（不测质量）"
    return res


def gate2(cand: dict, py: str) -> dict:
    """质量：probe 开/关闸门。"""
    res: dict = {"gate": 2, "passed": False, "runs": {}}
    for state in ("on", "off"):
        base = REPORTS_DIR / f"{cand['id']}.probe.{state}"
        cmd = [py, str(EVAL_DIR / "paraphrase" / "run_probe.py"),
               "--semantic", state, "--no-hash-control", "--force", "--out", str(base)]
        rc, tail = _run(cmd, {"KAVIRA_EMBEDDING_DIR": cand["embedding_dir"]})
        rep = _read_json(Path(f"{base}.json")) or {}
        m = rep.get("metrics") or {}
        z = rep.get("zero_lexical_subset") or {}
        res["runs"][state] = {
            "rc": rc, "report": f"{base}.json",
            "failure_rate@5": m.get("failure_rate@5"),
            "empty_result_rate": m.get("empty_result_rate"),
            "zero_lexical_failure@5": z.get("failure_rate@5"),
        }
    on = res["runs"].get("on") or {}
    passed = (on.get("failure_rate@5") is not None
              and on["failure_rate@5"] <= GATE2["failure_rate@5"]
              and (on.get("empty_result_rate") or 1) <= GATE2["empty_result_rate"]
              and (on.get("zero_lexical_failure@5") is None
                   or on["zero_lexical_failure@5"] <= GATE2_ZERO["failure_rate@5"]))
    res["passed"] = bool(passed)
    res["thresholds"] = {**GATE2, "zero_lexical_failure@5": GATE2_ZERO["failure_rate@5"]}
    return res


def gate3(cand: dict, py: str, incumbent_fa: float | None) -> dict:
    """安全：Holdout B 开/关闸门。"""
    res: dict = {"gate": 3, "passed": False, "runs": {}}
    for state in ("on", "off"):
        out = f"embedding_eval/{cand['id']}.holdout.{state}"
        cmd = [py, str(EVAL_DIR / "holdout_b_run.py"),
               "--semantic", state, "--no-llm", "--force", "--out", out]
        rc, tail = _run(cmd, {"KAVIRA_EMBEDDING_DIR": cand["embedding_dir"]})
        rep = _read_json(REPORTS_DIR / f"{cand['id']}.holdout.{state}.json") or {}
        m = rep.get("retrieval") or {}
        cit = rep.get("citation") or {}
        rel = rep.get("relation") or {}
        res["runs"][state] = {
            "rc": rc, "report": str(REPORTS_DIR / f"{cand['id']}.holdout.{state}.json"),
            "recall@1": m.get("recall@1"), "wrong_document_rate": m.get("wrong_document_rate"),
            "no_answer_fp_rate": m.get("no_answer_fp_rate"),
            "false_association_rate": rel.get("false_association_rate"),
            "structural_rate": cit.get("structural_rate"), "overlap_rate": cit.get("overlap_rate"),
        }
    ok = True
    for state, r in res["runs"].items():
        if (r.get("recall@1") is None or r["recall@1"] < GATE3["recall@1"]
                or r.get("wrong_document_rate") != 0.0
                or r.get("no_answer_fp_rate") != 0.0
                or (r.get("false_association_rate") or 0) > GATE3_FA_MAX
                or (r.get("structural_rate") or 0) < 1.0
                or (r.get("overlap_rate") or 0) < 0.981):
            ok = False
        # FA 不新增
        if incumbent_fa is not None and (r.get("false_association_rate") or 0) > incumbent_fa:
            ok = False
    res["passed"] = bool(ok)
    res["thresholds"] = {**GATE3, "false_association_rate_max": GATE3_FA_MAX,
                         "incumbent_fa": incumbent_fa, "overlap_min": 0.981}
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval/embedding_eval/run_matrix.py")
    ap.add_argument("--candidates", default=str(CANDIDATES))
    ap.add_argument("--id", default=None, help="只跑某个候选 id")
    ap.add_argument("--gates", default="0,1", help="要跑的闸门（逗号分隔，如 0,1 或 0,1,2,3）")
    ap.add_argument("--quality", action="store_true",
                    help="显式开启门槛2/3（质量/安全）。默认只跑 0/1，避免对不过速度的候选白测。")
    ap.add_argument("--python", default=sys.executable, help="子进程解释器（默认当前解释器）")
    ap.add_argument("--out", default=str(REPORTS_DIR / "summary.json"))
    args = ap.parse_args(argv)

    cand_path = Path(args.candidates)
    if not cand_path.is_absolute():
        cand_path = REPO / cand_path
    spec = json.loads(cand_path.read_text(encoding="utf-8"))
    cands = spec["candidates"]
    if args.id:
        cands = [c for c in cands if c["id"] == args.id]
        if not cands:
            print(f"⛔ 未找到候选 id={args.id}")
            return 2

    gates = {int(x) for x in args.gates.split(",") if x.strip()}
    if args.quality:
        gates |= {2, 3}

    incumbent = next((c for c in spec["candidates"] if c.get("is_baseline")), None)
    incumbent_speed = _read_json(REPORTS_DIR / f"{incumbent['id']}.speed.json") if incumbent else None
    incumbent_fa = None
    if incumbent:
        irep = _read_json(REPORTS_DIR / f"{incumbent['id']}.holdout.on.json")
        if irep:
            incumbent_fa = (irep.get("relation") or {}).get("false_association_rate")

    summary = {"generated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
               "gates_run": sorted(gates), "candidates": {}}

    for c in cands:
        rec: dict = {"id": c["id"], "embedding_dir": c["embedding_dir"],
                     "expected_dimension": c.get("expected_dimension"),
                     "expected_pooling": c.get("expected_pooling"), "gates": {}}
        print(f"\n===== 候选 {c['id']} =====")

        if 0 in gates:
            g0 = gate0(c, args.python)
            rec["gates"]["0"] = g0
            print(f"  门槛0 资源可行 : {'✅' if g0['passed'] else '❌'} "
                  f"(dim={g0.get('dimension')} pooling={g0.get('pooling')})")

        speed_ok = True
        if 1 in gates:
            g1 = gate1(c, args.python, incumbent_speed)
            rec["gates"]["1"] = g1
            speed_ok = g1["passed"]
            # 刚跑完基线 → 立即用**本次实测**刷新对照基准，供后续候选使用（避免用旧文件）
            if c.get("is_baseline"):
                incumbent_speed = _read_json(REPORTS_DIR / f"{c['id']}.speed.json") or incumbent_speed
            print(f"  门槛1 速度     : {'✅' if speed_ok else '❌'}  {g1.get('reason','')}")

        if speed_ok and (2 in gates):
            rec["gates"]["2"] = gate2(c, args.python)
            print(f"  门槛2 质量     : {'✅' if rec['gates']['2']['passed'] else '❌'}")
        elif 2 in gates and not speed_ok:
            rec["gates"]["2"] = {"gate": 2, "passed": False,
                                 "reason": "门槛1 未过 → 铁律不测质量"}
            print("  门槛2 质量     : ⏹ 跳过（门槛1 未过）")

        if speed_ok and rec.get("gates", {}).get("2", {}).get("passed") and (3 in gates):
            rec["gates"]["3"] = gate3(c, args.python, incumbent_fa)
            print(f"  门槛3 安全     : {'✅' if rec['gates']['3']['passed'] else '❌'}")
        elif 3 in gates:
            rec["gates"]["3"] = {"gate": 3, "passed": False, "reason": "前置闸门未过 → 跳过"}

        rec["verdict"] = _verdict(rec, gates)
        summary["candidates"][c["id"]] = rec

    out = Path(args.out)
    if not out.is_absolute():
        out = REPO / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n汇总 → {out}")
    return 0


def _verdict(rec: dict, gates: set) -> str:
    g = rec["gates"]
    if rec.get("_stop"):
        return "REJECTED"
    for k in sorted(gates):
        r = g.get(str(k))
        if r is None:
            return "INCOMPLETE"
        if not r.get("passed"):
            return "REJECTED"
    return "PASS"


if __name__ == "__main__":
    raise SystemExit(main())
