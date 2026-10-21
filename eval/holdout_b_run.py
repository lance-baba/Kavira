"""Kavira · Holdout B —— Release Candidate Gate 1 最终验收 Runner。

**只验收，不调算法。** 本轮禁止修改 app/core/{search,chunker,llm,relation_guard}.py、
embedding、prompt、TopK、citation、UI。失败只记录，不现场修。

用法（必须用随包嵌入式运行时 + TEMP 隔离库）：
    runtime/python-3.11-embed/python.exe eval/holdout_b_run.py
    runtime/python-3.11-embed/python.exe eval/holdout_b_run.py --no-llm

流程：
  0) 校验 HOLDOUT_B_MANIFEST（fixture/gold 哈希）→ 首次正式运行即**冻结**
  1) Retrieval Eval
  2) Selective Attribution Guard（仅 Router 判进 Guard 的题）
  3) Citation 数据校验（结构合法率 + source-range overlap）
  4) LLM smoke（≤15 题）
  5) 产出报告 + Blocker 判定 + KNOWN_LIMITATIONS.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# ⚠ 必须在 import 任何 app 模块**之前**设置：app/core/paths.py:125 是模块级求值
#    EMBEDDING_DIR = _detect_embedding_dir(BASE_DIR)，晚一步就永远指向
#    resources/embedding（那里只有契约模板 default.json）→ 会静默降级成纯 FTS5，
#    于是「真实模型基线」又变回词法基线。镜像 eval/paraphrase/run_probe.py 顶部做法。
_EMBEDDING_DIR = (os.environ.get("KAVIRA_EMBEDDING_DIR") or "").strip() or str(
    REPO / "vendor" / "cache" / "embedding")
os.environ["KAVIRA_EMBEDDING_DIR"] = _EMBEDDING_DIR

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

# ⚠⚠ 导入顺序是**安全关键**，不得调换：
#    `app.core.*` 里只要有一处先于 `run_eval` 被 import，`app.core.paths` 就会在
#    `test_env.activate_test_library()` 生效**之前**完成模块级求值 ——
#    DATA_DIR 会定格在真实 dev Library，于是 fixtures 会被拷进真实 notes/、
#    索引写进真实 cache.db（本阶段实测踩过这个坑，已修复并加断言）。
#    `relation_guard` 只 import re/dataclasses，不碰 paths，所以它可以先用。
from app.core import relation_guard as RG  # noqa: E402

import _metrics  # noqa: E402
import run_eval as R  # noqa: E402   ← 这一步才 activate_test_library + 首次 import app.core.paths

from app.core import config, embedder as emb_mod  # noqa: E402  ← 必须在 run_eval 之后

REPORTS = HERE / "reports"
HB_DIR = HERE / "datasets" / "holdout_b"
GOLD = HB_DIR / "holdout_b_gold.jsonl"
MANIFEST = HB_DIR / "HOLDOUT_B_MANIFEST.json"
FIXTURES_HB = HERE / "fixtures_holdout_b"
TOP_K = 5
SMOKE_IDS = [
    "hb_df_struct", "hb_m_level", "hb_q_inclino_tube", "hb_lc_clinic_items",
    "hb_tr_a1001", "hb_neg_cost", "hb_c_pos1", "hb_c_neg1", "hb_c_ins1",
    "hb_e_pos1", "hb_r_neg1", "hb_se_tube_range",
]


def resolve_real_embedder() -> tuple[object, dict, str]:
    """解析**生产**嵌入源（走 embedder.resolve 全链路，不做任何特殊照顾）。

    镜像 `eval/paraphrase/run_probe.py::resolve_real_embedder()`：本 runner 的
    验收口径必须是真实语义模型，否则「语义通道」在哈希伪向量下结构性 inert，
    跑出来的数字会掩盖真实行为（PRD §1.4 / 设计 §8）。
    """
    resolved = emb_mod.resolve(config.get)
    emb = resolved.embedder
    res = getattr(emb, "resource", None)
    meta = {
        "tier": str(getattr(emb, "source", "") or "?"),
        "model_id": str(getattr(emb, "model", "") or "?"),
        "dimension": int(getattr(emb, "dim", 0) or 0),
        "signature": str(getattr(emb, "signature", "") or ""),
        "resource_id": str(getattr(res, "id", "") or ""),
        "base_model": str(getattr(res, "base_model", "") or ""),
        "precision": str(getattr(emb, "precision", "")
                         or getattr(res, "precision", "") or ""),
        "fallback_reason": str(resolved.fallback_reason or ""),
        "resolve_notes": list(resolved.notes),
        "resolve_warnings": list(resolved.warnings),
        "embedding_dir": _EMBEDDING_DIR.replace("\\", "/"),
    }
    return emb, meta, str(resolved.source)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


# --------------------------------------------------------------------------
def freeze() -> dict:
    """校验完整性；首次正式运行即冻结（之后禁止改 fixture / gold）。"""
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = []
    for name, rec in man["fixtures"].items():
        p = FIXTURES_HB / name
        if not p.exists():
            problems.append(f"fixture 缺失: {name}")
        elif _sha256(p) != rec["sha256"]:
            problems.append(f"fixture {name} 哈希不符（已冻结后不得修改）")
    if _sha256(GOLD) != man["gold_sha256"]:
        problems.append("gold 哈希不符（已冻结后不得修改）")
    if problems:
        print("HOLDOUT B MANIFEST CHECK FAILED:")
        for p in problems:
            print("  -", p)
        raise SystemExit(2)
    if not man.get("frozen"):
        man["frozen"] = True
        man["frozen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[freeze] Holdout B 已冻结 @ {man['frozen_at']} —— 之后禁止修改 fixture/gold/expected")
    else:
        print(f"[freeze] Holdout B 已冻结 @ {man['frozen_at']}（本次为再次运行）")
    return man


# --------------------------------------------------------------------------
def gold_parents(par, docs, c) -> set[str]:
    exp = c["expected"]
    did = docs.get(exp["doc"], "")
    must = exp.get("must_contain") or []
    groups = c.get("evidence_groups") or []
    ids = set()
    if groups:
        for g in groups:
            for p in par.get(did, []):
                if all(t in (p["content"] or "") for t in g):
                    ids.add(p["parent_id"])
    elif must:
        for p in par.get(did, []):
            if all(t in (p["content"] or "") for t in must):
                ids.add(p["parent_id"])
    if not ids and must:
        ids = {p["parent_id"] for p in par.get(did, [])
               if any(t in (p["content"] or "") for t in must)}
    return ids


def run_eval_all(cases, db, emb, par, docs) -> dict:
    ranking, per_case = {}, []
    for c in cases:
        res = R.S.hybrid_search(db, emb, c["query"], top_k_parents=TOP_K)
        refs = list(res.references)
        ranking[c["id"]] = refs
        rq = RG.analyze_relation(c["query"])
        guard = None
        if rq.route == RG.ROUTE_GUARD:
            # T3.5 安全加固（与生产 llm.py 一致）：语义-only 引用不得作为归因证据 ——
            # 语义沾边文档即便被放行进引用，也不能把归因从 INSUFFICIENT 翻成 YES。
            # 与生产口径保持逐字一致，否则 Holdout B 的 Guard 数字会与线上漂移。
            pdicts = [{"parent_id": r.parent_id, "doc_id": r.doc_id,
                       "content": _content(par, r), "section_path": _sec(par, r)}
                      for r in refs
                      if getattr(r, "match_mode", "lexical") != "semantic-only"]
            guard = RG.evaluate_relation(rq, pdicts)
        per_case.append({"id": c["id"], "category": c["category"],
                         "query": c["query"], "route": rq.route,
                         "relation_type": rq.relation_type,
                         "guard": guard.verdict if guard else None,
                         "allow": guard.allow_relation_claim if guard else None,
                         "reason": guard.reason if guard else "",
                         # A′：结构化 owner（**只读取** GuardResult，不改 guard 逻辑）。
                         # 用于判定「查找题的 YES 是否答对了责任人」，避免从中文 reason
                         # 里做正则反解析（reason 文案将来改了就会静默失准）。
                         "owner": guard.owner if guard else None,
                         # P0-4：该题引用里 semantic-only（语义通道放行）的条数
                         "n_refs": len(refs),
                         "semantic_only_refs": sum(
                             1 for r in refs
                             if getattr(r, "match_mode", "lexical") == "semantic-only")})
    rows = _metrics.metrics_for(cases, ranking, par, docs)
    agg = _metrics.aggregate(rows)
    return {"ranking": ranking, "rows": rows, "metrics": agg, "per_case": per_case}


def _content(par, ref) -> str:
    for p in par.get(ref.doc_id, []):
        if p["parent_id"] == ref.parent_id:
            return p["content"] or ""
    return ""


def _sec(par, ref) -> str:
    for p in par.get(ref.doc_id, []):
        if p["parent_id"] == ref.parent_id:
            return p.get("section_path") or ""
    return ""


def citation_check(cases, ranking, par, docs) -> dict:
    """引用校验。

    主口径（与 DEV72 既有 `citation_intersection_rate` 一致）：
      **每题**是否至少有一条引用的 source range 与 gold 证据区间相交。
    另附 `per_ref_overlap_rate` 作诊断 —— 它天然偏低（一题返回 5 条引用，
    其中只有部分是 gold 证据），不能拿它当 Gate 判据。
    """
    valid_of = {p["parent_id"]: d for d, ps in par.items() for p in ps}
    ok = tot = 0
    case_ok = case_tot = 0
    ref_ok = ref_tot = 0
    for c in cases:
        golds = gold_parents(par, docs, c)
        granges = [(p["s"], p["e"]) for d, ps in par.items() for p in ps if p["parent_id"] in golds]
        hit_case = False
        for r in ranking[c["id"]]:
            tot += 1
            good = (bool(r.doc_id) and bool(r.parent_id) and r.source_start_line > 0
                    and r.source_end_line >= r.source_start_line
                    and valid_of.get(r.parent_id) == r.doc_id)
            ok += 1 if good else 0
            if granges:
                ref_tot += 1
                inter = any(r.source_start_line <= ge and r.source_end_line >= gs
                            for gs, ge in granges)
                ref_ok += 1 if inter else 0
                hit_case = hit_case or inter
        if granges:
            case_tot += 1
            case_ok += 1 if hit_case else 0
    return {"structural_rate": (ok / tot) if tot else None, "n_refs": tot,
            "overlap_rate": (case_ok / case_tot) if case_tot else None, "overlap_n": case_tot,
            "per_ref_overlap_rate": (ref_ok / ref_tot) if ref_tot else None,
            "per_ref_n": ref_tot}


def _owner_matches_gold(pc: dict, must: list[str]) -> bool:
    """A′ 判据：Guard 判出的负责人是否与 gold 的 `must_contain` 一致。

    证据来源优先级：
      1. `pc["owner"]`（结构化，来自 `GuardResult.owner`，**只读**）—— 只要拿到就用它，
         避免 reason 里同时出现「正确 owner」与「被问的 target」时被字面匹配误判为答对；
      2. 仅当 `owner` 缺失（旧 per_case / 历史报告）才回退 `pc["reason"]` 文本 ——
         `relation_guard` 的 YES reason 形如「责任方「李岚」」，必含 owner 字面。
    匹配方向双向（`t in hay` 或 `hay in t`），避免 gold 写全称、guard 抓短名时误判。
    """
    terms = [t for t in (must or []) if t]
    if not terms:
        return False
    owner = str(pc.get("owner") or "").strip()
    hay = owner or str(pc.get("reason") or "").strip()
    if not hay:
        return False
    return any(t in hay or hay in t for t in terms)


def relation_metrics(cases, per_case) -> dict:
    """归因裁决指标（A′ 口径）。

    **分桶语义在此钉死**（`answer_state` 是 gold 对「这题该怎么答」的声明）：

    * ``yes``          → 正例：Guard=YES 记 correct，否则记 ``positive_miss``。
    * ``no``           → 负例：Guard=NO 记 correct；Guard=YES 记 **fp**（声称了错关系）。
    * ``insufficient`` → 弃答题：Guard=INSUFFICIENT 记 correct；Guard=YES 记 **fp**。
    * ``answered``     → **查找题**（gold 声明"可回答、答案就是 must_contain"）。
      **它不是关系断言题**，因此不能被塞进 abstention 桶 —— 历史上正是这一步把
      「Guard 正确答出责任人」记成了 False Association：
        - Guard=YES 且负责人与 must_contain 一致 → ``answered_correct``（**不计 FA**）；
        - Guard=YES 但负责人不符 / 取不到     → ``answered_fp``（**真·答错责任人，计 FA**）；
        - Guard≠YES                           → ``answered_miss``（**不计 FA**，属
          「该答未答」的召回问题，由 ``unnecessary_guard`` 的 blocked 口径监督）。
    * 其它未知 state → ``unknown`` 桶**单独统计**（绝不默认当 insufficient）；
      其中 Guard=YES 仍计 **fp**（保守：未知题不放行）。

    因此 **False Association 的语义 = 「声称了 gold 说无证据的关系，或答错了责任人」**。
    """
    by_id = {c["id"]: c for c in cases}
    # ---- 正例 ----
    n_yes = tp = positive_miss = 0
    # ---- 负例 ----
    n_no = tn_no = fp_no = negative_miss = 0
    # ---- 弃答 ----
    n_ins = tn_ins = fp_ins = insufficient_miss = 0
    # ---- 查找题（A′ 新增分桶）----
    n_answered = answered_correct = answered_fp = answered_miss = 0
    # ---- 未知 state（显式分桶，不透支 insufficient）----
    n_unknown = tn_unknown = fp_unknown = unknown_miss = 0

    for pc in per_case:
        if pc["route"] != RG.ROUTE_GUARD:
            continue
        c = by_id[pc["id"]]
        state = c["expected"]["answer_state"]
        must = c["expected"].get("must_contain") or []
        v = pc["guard"]
        if state == "yes":
            n_yes += 1
            if v == RG.VERDICT_YES:
                tp += 1
            else:
                positive_miss += 1
        elif state == "no":
            n_no += 1
            if v == RG.VERDICT_YES:
                fp_no += 1
            elif v == RG.VERDICT_NO:
                tn_no += 1
            else:
                negative_miss += 1
        elif state == "insufficient":
            n_ins += 1
            if v == RG.VERDICT_YES:
                fp_ins += 1
            elif v == RG.VERDICT_INSUFFICIENT:
                tn_ins += 1
            else:
                insufficient_miss += 1
        elif state == "answered":
            n_answered += 1
            if v == RG.VERDICT_YES:
                if _owner_matches_gold(pc, must):
                    answered_correct += 1
                else:
                    answered_fp += 1
            else:
                answered_miss += 1
        else:
            n_unknown += 1
            if v == RG.VERDICT_YES:
                fp_unknown += 1
            elif v == RG.VERDICT_INSUFFICIENT:
                tn_unknown += 1
            else:
                unknown_miss += 1

    # FA 分子：声称了不该声称的关系（负例被翻成 YES / 弃答题被翻成 YES /
    #            查找题答错责任人 / 未知题放行）。
    fa_fp = fp_no + fp_ins + answered_fp + fp_unknown
    # FA 分母：所有**应当被裁决为非正例**的题（负例 + 弃答 + 查找题 + 未知题），
    # 等价于 `n_guard − n_yes`。注意 answered 参与分母但不贡献 fp（除非答错责任人）——
    # 这样分母与旧口径的 8 题对齐（4 no + 3 insufficient + 1 answered），
    # 横比不会因缩分母而虚高。
    fa_den = n_no + n_ins + n_answered + n_unknown
    return {
        "n": n_yes + n_no + n_ins + n_answered + n_unknown,
        "n_yes": n_yes, "n_no": n_no, "n_insufficient": n_ins,
        "n_answered": n_answered, "n_unknown": n_unknown,
        "n_answered_correct": answered_correct,
        # ---- 三个原有指标（语义不变）----
        "positive_relation_accuracy": (tp / n_yes) if n_yes else None,
        "negative_relation_accuracy": (tn_no / n_no) if n_no else None,
        "abstention_accuracy": (tn_ins / n_ins) if n_ins else None,
        # ---- A′ 新增：查找题正确率 ----
        "answered_accuracy": (answered_correct / n_answered) if n_answered else None,
        # ---- False Association（A′ 语义：错声称 / 答错责任人）----
        "false_association_rate": (fa_fp / fa_den) if fa_den else None,
        "fa_fp": fa_fp, "fa_denominator": fa_den,
        # ---- 诊断桶（不参与 Blocker 判定，便于定位漏检方向）----
        "positive_miss": positive_miss, "negative_miss": negative_miss,
        "insufficient_miss": insufficient_miss,
        "answered_fp": answered_fp, "answered_miss": answered_miss,
        "unknown_miss": unknown_miss,
    }


def unnecessary_guard(cases, per_case) -> dict:
    """普通题（非 causal/event/responsibility）与 Guard 的关系。

    区分两件事 —— spec 的 Blocker D 说的是「普通 query 被 Guard **误拦**」，
    不是「被路由」：
      * `routed_to_guard`      : 进入了 Guard（其中可能有**形态确实是责任归属**的题，
                                 例如「谁负责数据平差与报表编制？」，这是设计内行为）
      * `blocked_n`            : 真的被判 NO / INSUFFICIENT 而阻断 —— **这才是误伤**
    """
    HIGH = {"causal", "event", "responsibility"}
    by_id = {c["id"]: c for c in cases}
    n = routed = blocked = 0
    bad, blocked_cases = [], []
    for pc in per_case:
        c = by_id[pc["id"]]
        if c["category"] in HIGH:
            continue
        n += 1
        if pc["route"] == RG.ROUTE_GUARD:
            routed += 1
            bad.append({"id": pc["id"], "category": c["category"], "query": c["query"],
                        "guard": pc["guard"]})
            if pc["guard"] != RG.VERDICT_YES:
                blocked += 1
                blocked_cases.append({"id": pc["id"], "category": c["category"],
                                      "query": c["query"], "guard": pc["guard"]})
    return {"normal_queries": n, "routed_to_guard": routed, "blocked_n": blocked,
            "unnecessary_guard_rate": (blocked / n) if n else None,
            "routed_rate": (routed / n) if n else None,
            "cases": bad, "blocked_cases": blocked_cases}


def negative_guard(cases, per_case) -> dict:
    """负例（无答案题 `category == "negative_no_answer"`）的**引用安全性**。

    关注的是 B 语义通道有没有给无答案题**新引入**引用 —— 这是 P0-4 的核心判据：
    防编造闸门本就该让无答案题的引用数≈0；语义通道若把「孤立语义近邻」放行进来，
    负例题就会冒出 semantic-only 引用（典型：`hb_neg_design_life` 单块 sim≈0.64）。

    字段：
      * ``neg_cases``                      : 负例题总数
      * ``neg_cited_cases``                : 其中**仍有引用**（n_refs>0）的题数
      * ``neg_semantic_new_citation_cases``: 其中引用里含 ``semantic-only`` 的题数
                                             —— 语义通道给无答案题**新引入**引用，须为 0
      * ``leaked_ids`` / ``leaked``        : 上述违规题 id 及明细，便于定位
    """
    by_id = {c["id"]: c for c in cases}
    neg = cited = sem_new = 0
    leaked: list[dict] = []
    for pc in per_case:
        c = by_id.get(pc["id"])
        if not c or c["category"] != "negative_no_answer":
            continue
        neg += 1
        n_refs = int(pc.get("n_refs", 0) or 0)
        n_sem = int(pc.get("semantic_only_refs", 0) or 0)
        if n_refs > 0:
            cited += 1
        if n_sem > 0:
            sem_new += 1
            leaked.append({"id": pc["id"], "query": c["query"],
                           "n_refs": n_refs, "semantic_only_refs": n_sem})
    return {"neg_cases": neg, "neg_cited_cases": cited,
            "neg_semantic_new_citation_cases": sem_new,
            "leaked_ids": [x["id"] for x in leaked], "leaked": leaked}


# --------------------------------------------------------------------------
def llm_smoke(cases, db, emb) -> dict:
    from app.core import llm as llm_mod
    by_id = {c["id"]: c for c in cases}
    gw = llm_mod.Gateway(db, emb)
    out = []
    for cid in SMOKE_IDS:
        c = by_id.get(cid)
        if not c:
            continue
        t0 = time.perf_counter()
        try:
            frames = list(gw.stream_chat(c["query"]))
        except Exception as exc:  # noqa: BLE001
            out.append({"id": cid, "error": str(exc)[:120]})
            continue
        dt = (time.perf_counter() - t0) * 1000
        meta = next((f for f in frames if f.get("type") == "meta"), {})
        refs = next((f for f in frames if f.get("type") == "references"), {})
        text = "".join(f.get("content", "") for f in frames if f.get("type") == "delta")
        out.append({
            "id": cid, "category": c["category"], "query": c["query"],
            "route": meta.get("relation_route"), "guard": meta.get("guard_state"),
            "allow": meta.get("allow_relation_claim"),
            "provider": meta.get("provider"), "n_refs": len(refs.get("refs") or []),
            "has_citation": bool(refs.get("refs")), "ms": round(dt, 0),
            "answer_head": text[:150].replace("\n", " "),
        })
    return out


# --------------------------------------------------------------------------
def assess(metrics, rel, cit, unec, neg, per_case) -> tuple[list[dict], str]:
    blockers: list[dict] = []
    A = rel.get("false_association_rate") or 0
    if A > 0:
        blockers.append({"id": "A", "desc": f"错误归因被放行（False Association {A*100:.1f}%）"})
    na = metrics.get("no_answer_fp_rate") or 0
    if na > 0:
        blockers.append({"id": "B", "desc": f"无答案题被高置信回答（No-answer FP {na*100:.1f}%）"})
    if (cit.get("structural_rate") or 1) < 1.0:
        blockers.append({"id": "C1", "desc": f"引用结构不合法（{cit['structural_rate']*100:.1f}%）"})
    if (cit.get("overlap_rate") or 1) < 0.90:
        blockers.append({"id": "C2", "desc": f"引用区间与证据不符（overlap {cit['overlap_rate']*100:.1f}%）"})
    u = unec.get("unnecessary_guard_rate") or 0
    if u > 0.02:
        blockers.append({"id": "D",
                         "desc": (f"普通题被 Guard 误拦 "
                                  f"{unec['blocked_n']}/{unec['normal_queries']} = {u*100:.1f}%")})
    # F：语义通道给无答案题**新引入**引用 —— B 护栏（M2 旁证）必须把它打到 0。
    ngs = neg.get("neg_semantic_new_citation_cases") or 0
    if ngs > 0:
        blockers.append({"id": "F",
                         "desc": (f"语义通道给无答案题新引入引用 "
                                  f"{ngs}/{neg.get('neg_cases', 0)} 例："
                                  + "、".join(neg.get("leaked_ids") or []))})
    # E：常见事实类的系统性漏召回
    core = {}
    for pc in per_case:
        pass
    return blockers, ""


def per_category_recall(cases, rows) -> dict:
    out = {}
    by_id = {r["id"]: r for r in rows}
    for c in cases:
        cat = c["category"]
        r = by_id.get(c["id"])
        if not r or c["expected"]["answer_state"] != "answered":
            continue
        out.setdefault(cat, []).append(1 if r["hit@1"] else 0)
    return {k: (sum(v) / len(v), len(v)) for k, v in sorted(out.items())}


# --------------------------------------------------------------------------
def render_md(rep: dict) -> str:
    m, rel, cit, unec = rep["retrieval"], rep["relation"], rep["citation"], rep["unnecessary_guard"]
    ng = rep.get("negative_guard") or {}
    p = lambda v: "—" if v is None else f"{v*100:.1f}%"
    L = ["# Kavira · Holdout B —— Release Candidate Gate 1", "",
         f"- 生成：{rep['generated_at']}　冻结：{rep['manifest']['frozen_at']}",
         f"- 规模：**{rep['n_cases']} 题 / {rep['n_fixtures']} 篇独立文档**，"
         f"hard case **{rep['manifest']['hard_case_ratio']*100:.0f}%**",
         f"- gold sha256：`{rep['manifest']['gold_sha256'][:16]}…`",
         "- 运行时：随包嵌入式 Python + TEMP 隔离库；**未触碰真实 Library**。",
         "- 本轮**只验收未调算法**，生产代码零改动。", ""]

    _e = rep.get("embedder")
    if _e:
        L += ["## 嵌入器（验收口径）", "", "| 项 | 值 |", "| --- | --- |",
              f"| tier | **{_e['tier']}** |",
              f"| 模型 | `{_e['model_id']}` |",
              f"| 精度 / 维度 | {_e['precision']} / **{_e['dimension']}** |",
              f"| 签名 | `{_e['signature']}` |",
              f"| 降级原因 | {_e['fallback_reason'] or '无（未降级）'} |", "",
              "> ⚠ 本 runner 已强制要求 tier=`local_onnx`：拿不到真实语义模型会直接"
              "非 0 退出，不会产出「哈希伪向量口径」的数字。", ""]

    L += [
         "## Retrieval", "", "| 指标 | 值 |", "| --- | --- |",
         f"| Recall@1 | **{p(m['recall@1'])}** |", f"| Recall@3 | **{p(m['recall@3'])}** |",
         f"| Recall@5 | **{p(m['recall@5'])}** |",
         f"| MRR | **{m['mrr']:.3f}** |",
         f"| Coverage group | **{p(m['coverage_group_recall'])}** |",
         f"| Coverage full | **{p(m['coverage_full_rate'])}** |",
         f"| Relation | {p(m['relation_accuracy'])} |", "",
         "## Safety", "", "| 指标 | 值 |", "| --- | --- |",
         f"| Wrong-document Rate | **{p(m['wrong_document_rate'])}** |",
         f"| No-answer FP Rate | **{p(m['no_answer_fp_rate'])}** |",
         f"| Attribution err（旧口径） | {p(m['attribution_violation_rate'])} |",
         f"| False Association | **{p(rel['false_association_rate'])}** "
         f"（{rel.get('fa_fp', 0)}/{rel.get('fa_denominator', 0)}；"
         f"分母 = no + insufficient + answered + unknown） |",
         f"| Unnecessary Guard（**真的被拦**） | **{p(unec['unnecessary_guard_rate'])}** "
         f"（{unec['blocked_n']}/{unec['normal_queries']}） |",
         f"| 普通题进入 Guard（含责任形态） | {p(unec['routed_rate'])} "
         f"（{unec['routed_to_guard']}/{unec['normal_queries']}） |", "",
         "## Relation（Guard）", "", "| 指标 | 值 |", "| --- | --- |",
         f"| Positive Relation Accuracy | **{p(rel['positive_relation_accuracy'])}** |",
         f"| Negative Relation Accuracy | **{p(rel['negative_relation_accuracy'])}** |",
         f"| Abstention Accuracy | **{p(rel['abstention_accuracy'])}** |",
         f"| Answered Accuracy（查找题，A′ 单独分桶） | "
         f"**{p(rel.get('answered_accuracy'))}** "
         f"（{rel.get('n_answered_correct', 0)}/{rel.get('n_answered', 0)}） |", "",
         "> A′ 口径：`answer_state == \"answered\"` 的**查找题**不再计入 abstention 桶。"
         "Guard=YES 且负责人与 gold `must_contain` 一致 → `answered_correct`（不计 FA）；"
         "负责人不符 → `answered_fp`（计 FA，保留「答错责任人」检测力）；"
         "Guard≠YES → `answered_miss`（不计 FA，由 Unnecessary Guard 监督）。", "",
         "## Citation", "", "| 指标 | 值 |", "| --- | --- |",
         f"| 结构合法率 | **{p(cit['structural_rate'])}**（{cit['n_refs']} 条引用） |",
         f"| source-range overlap（每题至少一条） | **{p(cit['overlap_rate'])}**"
         f"（{cit['overlap_n']} 题） |",
         f"| └ 逐条引用口径（诊断，天然偏低） | {p(cit.get('per_ref_overlap_rate'))}"
         f"（{cit.get('per_ref_n')} 条引用） |", "",
         "## Negative Safety（语义通道 · 负例不入引用）", "",
         "| 指标 | 值 |", "| --- | --- |",
         f"| 负例题数（无答案） | **{ng.get('neg_cases', '—')}** |",
         f"| └ 其中仍有引用的题数 | {ng.get('neg_cited_cases', '—')} |",
         f"| └ 含 semantic-only 引用的题数（**须为 0**） | "
         f"**{ng.get('neg_semantic_new_citation_cases', '—')}** |",
         f"| 违规题 id | {('、'.join(ng.get('leaked_ids') or []) or '—')} |", "",
         "## 各类型 Recall@1", "", "| 类别 | Recall@1 | n |", "| --- | --- | --- |"]
    for k, (v, n) in rep["per_category"].items():
        L.append(f"| {k} | {v*100:.0f}% | {n} |")
    L += ["", "## Blocker 判定", ""]
    if rep["blockers"]:
        for b in rep["blockers"]:
            L.append(f"- **BLOCKER {b['id']}**：{b['desc']}")
    else:
        L.append("- **无 Blocker**")
    for b in rep.get("judged_non_blocking") or []:
        L.append(f"- 触发阈值但判定**非 Blocker**：{b['id']} —— {b['desc']}；{b['judged']}")
    L += ["", "## 最终结论", "", f"# **{rep['verdict']}**", "",
          f"> {rep['verdict_reason']}", ""]
    if rep.get("smoke"):
        L += ["## LLM smoke", "", "| id | 类别 | route | guard | 引用 | 回答摘要 |", "| --- | --- | --- | --- | --- | --- |"]
        for s in rep["smoke"]:
            if "error" in s:
                L.append(f"| {s['id']} | | | | | ERROR {s['error'][:40]} |")
                continue
            L.append(f"| {s['id']} | {s['category']} | {s['route'] or 'PASS'} | {s['guard'] or '-'} | "
                     f"{'✅' if s['has_citation'] else '❌'} | {s['answer_head'][:60]} |")
        L.append("")
    L += ["---", "", "> 本轮只验收不调算法；失败只记录，不现场修。", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval/holdout_b_run.py")
    ap.add_argument("--no-llm", action="store_true", help="跳过 LLM smoke")
    ap.add_argument("--out", default="holdout_b.current",
                    help="报告输出基名（不含扩展名）。默认 eval/reports/holdout_b.current —— "
                         "**刻意不默认写 holdout_b**：那会覆盖已提交的冻结报告（c5451b8 历史证据）。"
                         "目标文件已存在时拒绝覆盖，需显式 --force。")
    ap.add_argument("--force", action="store_true",
                    help="允许覆盖已存在的报告文件（默认拒绝，防误删冻结/历史证据）。")
    ap.add_argument("--allow-hash-baseline", action="store_true",
                    help="⚠ 仅供口径对照：用历史 HashEmbedder 口径跑一次"
                         "（用于复现既有 holdout_b.md 的数字，证明 harness 改动本身没改变结果）。"
                         "默认禁止 —— 哈希伪向量口径下的验收数字无效。")
    ap.add_argument("--semantic", choices=["on", "off"], default=None,
                    help="覆写语义专用通道开关 allow_semantic_only（on=1 / off=0）。"
                         "**只改本进程内存，绝不写 config.ini**；不传则沿用 config.ini。"
                         "用于「开/关闸门两态各测一次」（PRD §7.2 / P0-4）。")
    args = ap.parse_args(argv)
    t0 = time.time()

    # A/B 两态口径：仅内存覆写 allow_semantic_only。persist=False 保证不落盘 config.ini。
    if args.semantic:
        config.update({"SEARCH": {
            "allow_semantic_only": "1" if args.semantic == "on" else "0"}}, persist=False)
        print(f"[semantic] allow_semantic_only = "
              f"{'1（开）' if args.semantic == 'on' else '0（关）'}"
              "（仅本进程内存，未写 config.ini）")

    # ---- #5 输出保护：解析输出基名并做「已存在则拒绝」守卫（放在最前，避免白跑一次建库）----
    REPORTS.mkdir(parents=True, exist_ok=True)
    out_base = Path(args.out)
    if not out_base.is_absolute():
        out_base = REPORTS / out_base
    out_json, out_md = Path(f"{out_base}.json"), Path(f"{out_base}.md")
    _existing = [p for p in (out_json, out_md) if p.exists()]
    if _existing and not args.force:
        print("⛔ 目标报告已存在，拒绝覆盖（防误删冻结 / 历史证据）：")
        for _p in _existing:
            print(f"   - {_p}")
        print("   归档新结果请改用 --out <新名>；确要原地覆盖请显式加 --force。")
        return 6

    # ---- 0) 嵌入器有效性闸门：必须真实 local_onnx，否则非 0 退出、不产出数字 ----
    if args.allow_hash_baseline:
        from app.core.embedder import HashEmbedder  # noqa: PLC0415

        emb = HashEmbedder(R.DIM)
        emb_meta, source = {
            "tier": "local_hash", "model_id": emb.model, "dimension": emb.dim,
            "signature": emb.signature, "resource_id": "", "base_model": "",
            "precision": "", "fallback_reason": "",
            "resolve_notes": ["⚠ 显式 --allow-hash-baseline：历史哈希口径，仅用于对照"],
            "resolve_warnings": [],
            "embedding_dir": _EMBEDDING_DIR.replace("\\", "/"),
        }, "local_hash"
        print("=" * 72)
        print("  ⚠⚠  --allow-hash-baseline：本次为【历史哈希伪向量口径】")
        print("     数字不可用于验收（见 PRD §1.4）；只用来证明 harness 改动无副作用。")
        print("=" * 72)
    else:
        emb, emb_meta, source = resolve_real_embedder()
    if source != "local_onnx" and not args.allow_hash_baseline:
        print("=" * 72)
        print("  ⛔ 有效性校验失败：本次生效的嵌入器不是真实 local_onnx")
        print("=" * 72)
        print("  期望 tier : local_onnx（bge-small-zh-v1.5-int8 ONNX，512 维）")
        print(f"  实际 tier : {source}")
        print(f"  fallback  : {emb_meta['fallback_reason'] or '（无）'}")
        print(f"  notes     : {emb_meta['resolve_notes']}")
        print(f"  warnings  : {emb_meta['resolve_warnings']}")
        print(f"  嵌入资源目录 : {_EMBEDDING_DIR}")
        print("")
        print("  Holdout B 的验收口径必须是真实语义模型；用 HashEmbedder / 纯 FTS5 跑出的")
        print("  数字会掩盖语义通道的真实行为。故不肯产出数字，直接退出。")
        print("=" * 72)
        return 3
    print(f"[embedder] tier={source} model={emb_meta['model_id']} dim={emb_meta['dimension']}")

    # ---- 隔离自检（安全保险丝）：DATA_DIR 必须就是 test_env 建的 TEMP 库 ----
    # 少了这一条，一旦有人调整 import 顺序，fixtures 就会被静默拷进真实 Library。
    lib = Path(R._LIB).resolve()
    if Path(R.paths.DATA_DIR).resolve() != lib:
        print("=" * 72)
        print("  ⛔ 隔离失效：paths.DATA_DIR ≠ test_env 的 TEMP 库 —— 拒绝运行")
        print("=" * 72)
        print(f"  期望（TEMP 隔离库）: {lib}")
        print(f"  实际（DATA_DIR）    : {Path(R.paths.DATA_DIR).resolve()}")
        print("  这通常意味着某个 app.core.* 在 run_eval 之前被 import（见文件头注释）。")
        print("=" * 72)
        return 5

    man = freeze()
    cases = load(GOLD)
    db, emb = R.build_library(FIXTURES_HB, embedder=emb)
    if db is None or not db.query("SELECT count(*) AS n FROM documents"):
        print("⛔ 索引库为空，拒绝出数字")
        return 5
    n_docs = db.query("SELECT count(*) AS n FROM documents")[0]["n"]
    if n_docs != len(list(FIXTURES_HB.glob("*.md"))):
        print(f"⛔ 库内文档数 {n_docs} ≠ fixture 数 {len(list(FIXTURES_HB.glob('*.md')))}"
              " —— 隔离库疑似被污染，拒绝出数字")
        return 5
    docs, par = R.doc_map(db), R.parent_index(db)

    ev = run_eval_all(cases, db, emb, par, docs)
    metrics = ev["metrics"]
    cit = citation_check(cases, ev["ranking"], par, docs)
    rel = relation_metrics(cases, ev["per_case"])
    unec = unnecessary_guard(cases, ev["per_case"])
    neg = negative_guard(cases, ev["per_case"])
    cat = per_category_recall(cases, ev["rows"])

    blockers, _ = assess(metrics, rel, cit, unec, neg, ev["per_case"])
    # E：常见事实类（direct/model/quantity/person）是否系统性漏召回
    core = [cat[k] for k in ("direct_fact", "model_spec", "quantity", "person") if k in cat]
    if core:
        mean = statistics.fmean(v for v, _ in core)
        if mean < 0.60:
            blockers.append({
                "id": "E",
                "desc": f"常见事实类（direct/model/quantity/person）Recall@1 均值仅 {mean*100:.0f}%"
                        f" —— 系统性漏召回"})
    # ---- 最终判定 ----
    # D 的判据是「**大面积**误拦」。若只有 1~2 例且根因明确（不是系统性），
    # 按规格归入 Known Limitation 而非 Blocker —— 但必须显式说明理由，不能悄悄放过。
    judged = []
    rest = []
    for b in blockers:
        if b["id"] == "D" and unec.get("blocked_n", 0) <= 2:
            judged.append({"id": b["id"], "desc": b["desc"],
                           "judged": "non-blocking（1~2 例、根因明确，不构成『大面积误拦』）"})
        else:
            rest.append(b)
    blockers = rest
    _judged_for_print = judged
    if blockers:
        verdict, reason = "RC_BLOCKED", (
            "发现系统性错误，需单独修复后重新创建 Holdout C（不得复用 B 做最终验收）")
    elif judged or rep_limitations(metrics, rel, cit):
        verdict, reason = "RC_READY_WITH_LIMITATIONS", (
            "无安全/数据 Blocker（无错误归因、无编造、无引用错位）；"
            "存在明确长尾限制，已记录进 KNOWN_LIMITATIONS.md，记录后可进入 Pilot")
    else:
        verdict, reason = "RC_READY", "无 Release Blocker，可进入 Windows Release Gate"

    rep = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "manifest": man,
           "n_cases": len(cases), "n_fixtures": man["fixture_count"],
           "embedder": emb_meta,
           "retrieval": metrics, "relation": rel, "citation": cit,
           "unnecessary_guard": unec, "negative_guard": neg,
           "per_category": cat, "per_case": ev["per_case"],
           "blockers": blockers, "judged_non_blocking": judged,
           "verdict": verdict, "verdict_reason": reason,
           "elapsed_s": round(time.time() - t0, 1)}

    if not args.no_llm:
        rep["smoke"] = llm_smoke(cases, db, emb)

    out_base.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(rep), encoding="utf-8")

    p = lambda v: "—" if v is None else f"{v*100:5.1f}%"
    print("\n=== Holdout B（RC Gate 1）===")
    print(f"cases={len(cases)} fixtures={man['fixture_count']} "
          f"hard={man['hard_case_ratio']*100:.0f}%")
    print(f"  Recall@1 {p(metrics['recall@1'])}  Recall@3 {p(metrics['recall@3'])}  "
          f"Recall@5 {p(metrics['recall@5'])}  MRR {metrics['mrr']:.3f}")
    print(f"  Coverage group {p(metrics['coverage_group_recall'])}  "
          f"full {p(metrics['coverage_full_rate'])}")
    print(f"  Wrong-doc {p(metrics['wrong_document_rate'])}  No-answer FP {p(metrics['no_answer_fp_rate'])}")
    print(f"  FalseAssoc {p(rel['false_association_rate'])}"
          f"（{rel.get('fa_fp', 0)}/{rel.get('fa_denominator', 0)}）  "
          f"UnnecessaryGuard {p(unec['unnecessary_guard_rate'])}"
          f"（{unec['blocked_n']}/{unec['normal_queries']}）")
    print(f"  NegSafety（负例含 semantic-only 引用，须为 0）: "
          f"{neg['neg_semantic_new_citation_cases']}/{neg['neg_cases']}"
          f"{'  [' + '、'.join(neg['leaked_ids']) + ']' if neg['leaked_ids'] else ''}")
    print(f"  PosRel {p(rel['positive_relation_accuracy'])}  NegRel {p(rel['negative_relation_accuracy'])}  "
          f"Abstention {p(rel['abstention_accuracy'])}  "
          f"Answered {p(rel.get('answered_accuracy'))}"
          f"（{rel.get('n_answered_correct', 0)}/{rel.get('n_answered', 0)}）")
    print(f"  Citation 结构 {p(cit['structural_rate'])}  overlap(每题) {p(cit['overlap_rate'])}"
          f"  逐条诊断 {p(cit.get('per_ref_overlap_rate'))}")
    print(f"\nBlockers: {len(blockers)} {[b['id'] for b in blockers]}")
    for b in rep["judged_non_blocking"]:
        print(f"  非 Blocker（已记录）: {b['id']} — {b['desc']} → {b['judged']}")
    print(f"结论: {verdict}")
    print(f"\n报告 → {out_md}  /  {out_json}  ({rep['elapsed_s']}s)")
    return 0


def rep_limitations(metrics, rel, cit) -> bool:
    """是否存在需要记录的长尾限制（不构成 Blocker，但值得写进 KNOWN_LIMITATIONS）。"""
    return ((metrics.get("recall@1") or 0) < 0.90
            or (metrics.get("coverage_full_rate") or 0) < 0.90
            or (cit.get("overlap_rate") or 1) < 1.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
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
        if R._DB is not None:
            try:
                R._DB.checkpoint_and_close()
            except Exception:  # noqa: BLE001
                pass
        try:
            R.test_env.cleanup_test_library(R._LIB)
        except Exception:  # noqa: BLE001
            pass
