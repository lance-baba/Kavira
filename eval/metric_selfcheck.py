"""关系指标口径（A′）自证 —— 纯确定性、零依赖、无模型、无网络、**零副作用**。

为什么需要它：`relation_metrics()` 的分桶语义（尤其 `answered` 桶）决定了
「False Association」到底在度量什么。口径一旦被悄悄改回「把 answered 塞进
abstention」，同一个 Guard 行为会从 `FA 0%` 变成 `FA 12.5%` —— 这类回归不会
被任何产品测试抓到，只能靠本脚本。**已接入 `tests/test_suite.py`（全量套件默认跑）。**

覆盖（A–D）：
  A. 五桶语义（合成 per_case）：答对不计 FA / **答错人名计 FA** / **YES 但无 owner 计 FA** /
     该答未答只记 `answered_miss` / 负例与弃答被放行计 FA / 未知 state 单列且 YES 计 FA。
  B. **分母恒等式**：`fa_denominator == n_no + n_ins + n_answered + n_unknown == n_guard − n_yes`
     —— 防「靠缩分母把 FA 做成 0」。
  C. 真实报告重算：直接读 `eval/reports/*.json` 的 `per_case`（**不重跑检索/嵌入算法**）。
     冻结基线 `holdout_b.json` 是不可变资产，故对其数值做**硬断言**；
     `holdout_b.a_prime.json` 可重新生成，只校验结构 + 打印现值。
  D. owner 匹配方向：双向子串（「市应急管理局」vs「应急管理局」算对）；**不同的人不算对**。

⚠ 本脚本从 `eval/holdout_b_run.py` **源码用 AST 抽取真实函数**执行，
  不 import 该模块（避免 `test_env` 激活 / 建 TEMP 库等副作用），因此抽取的函数
  一旦改名，本脚本会立刻报错 —— 这正是我们想要的「口径漂移哨兵」。

用法：
    runtime/python-3.11-embed/python.exe eval/metric_selfcheck.py   # 独立跑，exit 0/1
    python3 eval/metric_selfcheck.py                                 # 纯标准库，任意外部 Python 也能跑
    tests/test_suite.py 内：`from eval.metric_selfcheck import run as _run_msc`
"""
from __future__ import annotations

import ast
import json
import types
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNNER = HERE / "holdout_b_run.py"
GOLD = HERE / "datasets" / "holdout_b" / "holdout_b_gold.jsonl"
REPORTS = HERE / "reports"

# 与 app/core/relation_guard.py 的常量逐字一致（本脚本刻意不 import 生产模块）
ROUTE_GUARD = "ATTRIBUTION_GUARD"
ROUTE_PASS = "PASS_THROUGH"
YES, NO, INSUFFICIENT = "YES", "NO", "INSUFFICIENT_RELATION"

#: 独立运行时的记账（接入 test_suite 时改由套件的 check/section 记账）
_TALLY = {"ok": 0, "fail": 0}

CheckFn = Callable[..., bool]
SectionFn = Callable[[str], None]


# --------------------------------------------------------------------------
# 0) 从源码抽取真实实现（不 import runner）
# --------------------------------------------------------------------------
def load_real_functions() -> dict:
    """AST 抽取 `_owner_matches_gold` / `relation_metrics` 的真实源码并执行。

    Returns:
        namespace dict，至少含这两个函数。

    Raises:
        AssertionError: 函数被改名 / 删除（口径哨兵）。
    """
    want = {"_owner_matches_gold", "relation_metrics"}
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want]
    missing = want - {n.name for n in nodes}
    assert not missing, f"{RUNNER.name} 里找不到函数：{sorted(missing)}（口径实现被改名/删除？）"
    ns: dict = {"RG": types.SimpleNamespace(
        ROUTE_GUARD=ROUTE_GUARD, ROUTE_PASS=ROUTE_PASS,
        VERDICT_YES=YES, VERDICT_NO=NO, VERDICT_INSUFFICIENT=INSUFFICIENT)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), f"{RUNNER}(extracted)", "exec"), ns)  # noqa: S102
    return ns


# --------------------------------------------------------------------------
# 1) 合成场景
# --------------------------------------------------------------------------
def _case(cid: str, state: str, must: list[str], *, guard: str | None,
          owner: str | None = None, reason: str = "", route: str = ROUTE_GUARD):
    """构造 (gold case, per_case) 一对，形状与 `holdout_b_run.run_eval_all()` 一致。"""
    case = {"id": cid, "expected": {"answer_state": state, "must_contain": must}}
    pc = {"id": cid, "route": route, "guard": guard, "owner": owner, "reason": reason}
    return case, pc


def synth_cases() -> tuple[list[dict], list[dict]]:
    """14 例合成 per_case（13 道进 Guard + 1 道 PASS），覆盖五桶每一个分支。"""
    scen = [
        # ---- answered（查找题）----
        _case("ans_hit",   "answered", ["李岚"], guard=YES, owner="李岚"),            # 答对
        _case("ans_wrong", "answered", ["李岚"], guard=YES, owner="王强"),            # 答错人名
        _case("ans_none",  "answered", ["李岚"], guard=YES, owner=None,
              reason="同一 line 内共现"),                                            # YES 但无 owner
        _case("ans_miss",  "answered", ["李岚"], guard=INSUFFICIENT),                 # 该答未答
        # ---- no（负例）----
        _case("no_fp",     "no", [], guard=YES),                                     # 负例被放行
        _case("no_ok",     "no", [], guard=NO),
        _case("no_miss",   "no", [], guard=INSUFFICIENT),                             # 弃答而非否定
        # ---- insufficient（弃答）----
        _case("ins_fp",    "insufficient", ["X"], guard=YES, owner="Y"),              # 弃答被放行
        _case("ins_ok",    "insufficient", ["X"], guard=INSUFFICIENT),
        _case("ins_miss",  "insufficient", ["X"], guard=NO),                          # 判了否定
        # ---- yes（正例）----
        _case("yes_ok",    "yes", ["赵鹏"], guard=YES, owner="赵鹏"),
        _case("yes_miss",  "yes", ["赵鹏"], guard=INSUFFICIENT),
        # ---- 未知 state ----
        _case("unk_yes",   "legacy_state", [], guard=YES),                            # 未知 → 保守 fp
    ]
    cases = [c for c, _ in scen]
    per_case = [p for _, p in scen]
    # 未进入 Guard 的题不得被计入任何桶
    c, p = _case("not_guard", "answered", ["李岚"], guard=None, route=ROUTE_PASS)
    cases.append(c)
    per_case.append(p)
    return cases, per_case


# --------------------------------------------------------------------------
# 2) 各区
# --------------------------------------------------------------------------
def part_a_buckets(rm, check: CheckFn, section: SectionFn) -> None:
    """五桶语义：逐条隔离断言（每条分支互不干扰）。"""
    section("关系指标口径 A′ · 五桶语义")

    def one(cid: str, state: str, must: list[str], *, guard: str | None,
            owner: str | None = None, reason: str = "", route: str = ROUTE_GUARD) -> dict:
        c, p = _case(cid, state, must, guard=guard, owner=owner, reason=reason, route=route)
        return rm([c], [p])

    # ---- answered 桶的四条分支 ----
    m = one("ans_hit", "answered", ["李岚"], guard=YES, owner="李岚")
    check("A′ answered 答对 → answered_correct=1 且 **fa_fp=0**（不计 FA）",
          m["answered_accuracy"] == 1.0 and m["fa_fp"] == 0,
          f"answered=1.0 fa_fp={m['fa_fp']}")
    m = one("ans_wrong", "answered", ["李岚"], guard=YES, owner="王强")
    check("A′ answered **答错人名** → fa_fp=1（**计入** FA，检测力保留）",
          m["fa_fp"] == 1 and m["answered_fp"] == 1 and m["false_association_rate"] == 1.0)
    m = one("ans_none", "answered", ["李岚"], guard=YES, owner=None, reason="同一 line 内共现")
    check("A′ answered 判 YES 但**取不到 owner** → fa_fp=1（保守计 FA）",
          m["fa_fp"] == 1 and m["answered_fp"] == 1)
    m = one("ans_miss", "answered", ["李岚"], guard=INSUFFICIENT)
    check("A′ answered 该答未答 → answered_miss=1 且 **fa_fp=0**（不计 FA）",
          m["answered_miss"] == 1 and m["fa_fp"] == 0
          and m["answered_accuracy"] == 0.0)

    # ---- no / insufficient / unknown 的放行与漏检 ----
    m = one("no_fp", "no", [], guard=YES)
    check("A′ 负例被放行 → fa_fp=1", m["fa_fp"] == 1)
    m = one("ins_fp", "insufficient", ["X"], guard=YES, owner="Y")
    check("A′ 弃答题被放行 → fa_fp=1", m["fa_fp"] == 1)
    m = one("ins_miss", "insufficient", ["X"], guard=NO)
    check("A′ 弃答题判了否定 → insufficient_miss=1 且 **fa_fp=0**（单列，不混进负例）",
          m["insufficient_miss"] == 1 and m["fa_fp"] == 0 and m["negative_relation_accuracy"] is None)
    m = one("unk_yes", "legacy_state", [], guard=YES)
    check("A′ 未知 state 单列 unknown 桶（**绝不默认当 insufficient**）且 YES → fa_fp=1（保守）",
          m["n_unknown"] == 1 and m["n_insufficient"] == 0 and m["fa_fp"] == 1)
    m = one("pass_route", "answered", ["李岚"], guard=None, route=ROUTE_PASS)
    check("A′ 未进 Guard 的题不计入任何桶", m["n"] == 0 and m["fa_denominator"] == 0)

    # ---- 全量聚合（13 道 guard 题 + 1 道 PASS）----
    cases, per_case = synth_cases()
    m = rm(cases, per_case)
    check("A′ 全量：未进 Guard 的题被排除（14 例中只统计 13 例 guard 题）",
          m["n"] == 13, f"n={m['n']}")
    check("A′ 全量：answered 桶 4 例 = 答对1 / 答错1 / 无owner1 / 未答1",
          m["n_answered"] == 4 and m["n_answered_correct"] == 1
          and m["answered_fp"] == 2 and m["answered_miss"] == 1)
    check("A′ 全量：FA 分子 = 四类 fp 之和（no 1 + insufficient 1 + answered 2 + unknown 1 = 5）",
          m["fa_fp"] == 5, f"fa_fp={m['fa_fp']}")
    check("A′ 全量：answered_accuracy = 1/4 = 25%", abs((m["answered_accuracy"] or 0) - 0.25) < 1e-9)
    # 三个原指标语义不变
    check("A′ positive_relation_accuracy 语义不变（1/2=50%）",
          abs((m["positive_relation_accuracy"] or 0) - 0.5) < 1e-9)
    check("A′ negative_relation_accuracy 语义不变（1/3≈33.3%）",
          abs((m["negative_relation_accuracy"] or 0) - 1 / 3) < 1e-9)
    check("A′ abstention_accuracy 语义不变（1/3≈33.3%）",
          abs((m["abstention_accuracy"] or 0) - 1 / 3) < 1e-9)


def part_b_denominator(rm, check: CheckFn, section: SectionFn) -> None:
    """分母恒等式：防「靠缩分母把 FA 做成 0」。"""
    section("关系指标口径 A′ · FA 分母恒等式")
    cases, per_case = synth_cases()
    m = rm(cases, per_case)
    guard_n = sum(1 for p in per_case if p["route"] == ROUTE_GUARD)
    check("A′ fa_denominator == n_no + n_ins + n_answered + n_unknown",
          m["fa_denominator"] == m["n_no"] + m["n_insufficient"] + m["n_answered"] + m["n_unknown"],
          f"{m['fa_denominator']}")
    check("A′ fa_denominator == n_guard − n_yes（结构性，与题量无关）",
          m["fa_denominator"] == guard_n - m["n_yes"],
          f"{m['fa_denominator']} == {guard_n} − {m['n_yes']}")
    check("A′ FA 分母确实包含 answered 题（answered 参与分母，不是缩分母得到的 0）",
          m["fa_denominator"] > m["n_no"] + m["n_insufficient"])


def _load_cases() -> dict:
    rows = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {c["id"]: c for c in rows}


def part_c_reports(rm, check: CheckFn, section: SectionFn) -> None:
    """真实报告重算（读 per_case，**不重跑检索/嵌入算法**）。"""
    section("关系指标口径 A′ · 真实报告重算（不重跑算法）")
    if not GOLD.exists():
        check("A′ gold 数据集存在", False, str(GOLD))
        return
    by_id = _load_cases()

    frozen = REPORTS / "holdout_b.json"
    if frozen.exists():
        rep = json.loads(frozen.read_text(encoding="utf-8"))
        m = rm([by_id[p["id"]] for p in rep["per_case"]], rep["per_case"])
        check("A′ 冻结基线 holdout_b.json（c5451b8）FA 仍为 0%（0/8）",
              m["fa_fp"] == 0 and m["fa_denominator"] == 8,
              f"{m['fa_fp']}/{m['fa_denominator']}")
        check("A′ 冻结基线 answered 桶 n=1、answered_accuracy=0%（该答却阻断）",
              m["n_answered"] == 1 and m["answered_miss"] == 1
              and (m["answered_accuracy"] == 0.0))
        check("A′ 冻结基线 abstention = 100%（3/3，不含 answered）",
              m["n_insufficient"] == 3 and m["abstention_accuracy"] == 1.0)
        check("A′ 冻结基线 正/负例准确率 100%",
              m["positive_relation_accuracy"] == 1.0 and m["negative_relation_accuracy"] == 1.0)
    else:
        print(f"  ⏭  冻结基线报告不存在，跳过：{frozen}")

    current = REPORTS / "holdout_b.a_prime.json"
    if current.exists():
        rep = json.loads(current.read_text(encoding="utf-8"))
        m = rm([by_id[p["id"]] for p in rep["per_case"]], rep["per_case"])
        guard_n = sum(1 for p in rep["per_case"] if p["route"] == ROUTE_GUARD)
        # a_prime 可重新生成（换嵌入器/换 guard 都会合理变动），故只校验结构不校验数值
        check("A′ holdout_b.a_prime.json 结构恒等式成立",
              m["fa_denominator"] == guard_n - m["n_yes"]
              and m["fa_denominator"] == (m["n_no"] + m["n_insufficient"]
                                          + m["n_answered"] + m["n_unknown"]))
        check("A′ holdout_b.a_prime.json 的 FA 分子 ≤ 分母", m["fa_fp"] <= m["fa_denominator"])
        print(f"        现值：FA={m['fa_fp']}/{m['fa_denominator']} "
              f"pos={m['positive_relation_accuracy']} neg={m['negative_relation_accuracy']} "
              f"abstention={m['abstention_accuracy']} answered={m['answered_accuracy']} "
              f"answered_fp={m['answered_fp']} answered_miss={m['answered_miss']}")
    else:
        print(f"  ⏭  未找到 {current.name}（先跑 eval/holdout_b_run.py 生成），跳过")


def part_d_owner_match(owner_ok, check: CheckFn, section: SectionFn) -> None:
    """owner 匹配方向：双向子串；不同的人不算对；owner 优先于 reason。"""
    section("关系指标口径 A′ · owner 匹配方向")
    check("A′ 全称 vs 短名 → 算对（市应急管理局 / 应急管理局）",
          owner_ok({"owner": "应急管理局", "reason": ""}, ["市应急管理局"]))
    check("A′ 完全相同 → 算对", owner_ok({"owner": "李岚", "reason": ""}, ["李岚"]))
    check("A′ **不同的人不算对**（王强 vs 李岚）",
          not owner_ok({"owner": "王强", "reason": ""}, ["李岚"]))
    check("A′ owner 缺失 + reason 含 gold 词 → 回退算对（旧报告兼容）",
          owner_ok({"owner": None, "reason": "责任方「李岚」"}, ["李岚"]))
    check("A′ owner 缺失 + reason 不含 gold 词 → 不算对",
          not owner_ok({"owner": None, "reason": "分别找到 anchor / target"}, ["李岚"]))
    check("A′ gold 无 must_contain → 不算对（拿不准就不给分）",
          not owner_ok({"owner": "李岚", "reason": ""}, []))
    check("A′ owner 优先于 reason（owner 不符时，reason 里出现 gold 词也**不得**算对）",
          not owner_ok({"owner": "王强", "reason": "不是「李岚」"}, ["李岚"]))


# --------------------------------------------------------------------------
def run(ctx, check: CheckFn, section: SectionFn, skip=None) -> None:
    """套件入口（与 `tests/test_*.py` 的 `run(ctx, check, section, skip)` 同签名）。

    Args:
        ctx: 套件上下文（本检查不需要，保留以对齐签名）。
        check: `check(name, cond, detail="") -> bool`。
        section: `section(title)` 打印分组。
        skip: 未使用（本检查全部可在任意模式跑，无网络/无模型依赖）。
    """
    ns = load_real_functions()
    rm = ns["relation_metrics"]
    owner_ok = ns["_owner_matches_gold"]
    part_a_buckets(rm, check, section)
    part_b_denominator(rm, check, section)
    part_c_reports(rm, check, section)
    part_d_owner_match(owner_ok, check, section)


def main() -> int:
    """独立运行（不依赖 tests/ 套件）。"""
    def _check(name: str, cond: bool, detail: str = "") -> bool:
        if cond:
            _TALLY["ok"] += 1
            print(f"  PASS  {name}" + (f"   [{detail}]" if detail else ""))
        else:
            _TALLY["fail"] += 1
            print(f"  FAIL  {name}" + (f"   [{detail}]" if detail else ""))
        return bool(cond)

    def _section(title: str) -> None:
        print(f"\n=== {title} ===")

    print("关系指标口径（A′）自证 —— 抽取自 eval/holdout_b_run.py 的真实实现")
    run(None, _check, _section, None)
    ok, fail = _TALLY["ok"], _TALLY["fail"]
    print(f"\nPASS {ok}  FAIL {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
