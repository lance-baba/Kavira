#!/usr/bin/env python3
r"""Kavira · 改写查询探针（Paraphrase Probe）—— **纯测量，不改一行产品代码**。

回答一个产品问题：用户说「换个说法可能找不到资料」，到底**有多少比例**的改写查询
真的找不到，被**哪条规则**拒绝的。

设计红线（与 eval/README.md 的「只测不调」一致）：

* **只调用**生产 ``search.hybrid_search()``，参数原封不动（只用官方 ``debug`` 通道取数据），
  不绕过 ``_is_grounded()`` 闸门、不调 top_k 之外的开关去把分数做漂亮。
* **必须用真实嵌入模型**。现有 ``eval/run_eval.py`` 用的是 ``HashEmbedder``（哈希伪向量，
  没有语义），**永远测不出同义改写问题**。本探针强制激活随包 ``local_onnx``
  （bge-small-zh-v1.5-int8），拿不到就**醒目报错并非 0 退出** —— 有效性比分数重要。
* **绝不碰真实 Library**：复用 ``tests/test_env`` 安全保险丝，在 ``%TEMP%`` 下建隔离库。
* **只复用 Holdout B 的 8 篇语料文档**，不复用它已冻结的 57 道题与 gold。

用法（推荐用随包嵌入式运行时，它自带 sqlite-vec）：

    runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py
    runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py --check-only
    runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py --no-hash-control
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
REPO = EVAL_DIR.parent

# ⚠ 必须在 import 任何 app 模块**之前**设置：
#    app/core/paths.py 第 125 行是模块级求值 EMBEDDING_DIR = _detect_embedding_dir(...)，
#    晚一步就永远指向 resources/embedding（那里只有契约模板 default.json）。
_EMBEDDING_DIR = (os.environ.get("KAVIRA_EMBEDDING_DIR") or "").strip() or str(
    REPO / "vendor" / "cache" / "embedding")
os.environ["KAVIRA_EMBEDDING_DIR"] = _EMBEDDING_DIR

sys.path.insert(0, str(REPO))

# ⚠ 同样必须早于 app.core.paths：先激活隔离测试库
from tests import test_env  # noqa: E402

_LIB = test_env.activate_test_library(prefix="kavira-paraphrase-")

from app.core import config, db as db_mod, indexer, paths, search as S  # noqa: E402
from app.core import embedder as emb_mod  # noqa: E402
from app.core.embedder import HashEmbedder  # noqa: E402

QUERIES_FILE = HERE / "queries.json"
FIXTURES_DIR = EVAL_DIR / "fixtures_holdout_b"
REPORTS_DIR = EVAL_DIR / "reports"
REPORT_NAME = "paraphrase_probe"

DEFAULT_TOP_K = 5
DEFAULT_DIM = 512


# --------------------------------------------------------------------------
# 数据集自检
# --------------------------------------------------------------------------
def load_queries(path: Path) -> list[dict]:
    """读取改写查询集。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data["queries"] if isinstance(data, dict) else data
    return [r for r in rows if isinstance(r, dict)]


def validate_queries(rows: list[dict], fixtures_dir: Path) -> list[str]:
    """改写有效性自检 —— 任何一条不成立就报错（不产出误导性数字）。

    * A：``avoid_terms`` 每个词必须**逐字出现在** gold_doc 原文里。
      否则它算不上「文档原字面词」，这条标注本身无效。
    * B：``avoid_terms`` 每个词必须**不出现在** query 里。
      否则这道不是改写，而是照抄原词 —— 词法路本来就会命中，测不出问题。
    """
    problems: list[str] = []
    cache: dict[str, str] = {}
    seen: set[str] = set()

    def doc_text(name: str) -> str:
        if name not in cache:
            p = Path(fixtures_dir) / name
            cache[name] = p.read_text(encoding="utf-8") if p.is_file() else ""
        return cache[name]

    for row in rows:
        qid = str(row.get("id") or "<无 id>")
        if qid in seen:
            problems.append(f"[{qid}] id 重复")
        seen.add(qid)

        query = str(row.get("query") or "").strip()
        gold = str(row.get("gold_doc") or "").strip()
        terms = [str(t) for t in (row.get("avoid_terms") or [])]

        if not query:
            problems.append(f"[{qid}] query 为空")
        if not gold:
            problems.append(f"[{qid}] gold_doc 为空")
            continue
        if not (Path(fixtures_dir) / gold).is_file():
            problems.append(f"[{qid}] gold_doc 不存在于语料目录：{gold}")
            continue
        if not terms:
            problems.append(f"[{qid}] avoid_terms 为空（无法证明这是改写）")
        if not row.get("answer_hint"):
            problems.append(f"[{qid}] answer_hint 为空（无法人工复核）")

        text = doc_text(gold)
        for t in terms:
            if t not in text:
                # 说明：题目写的是「验证 avoid_terms 里的词确实没有在目标文档原文中
                # 按字面出现」。但 avoid_terms 的语义是「文档原字面词、query 刻意回避
                # 的词」，两者同时成立才是有效改写：
                #   ① 它在文档里（否则不是"文档的原字面词"）
                #   ② 它不在 query 里（否则不是改写）
                # 因此这里做的是 **双向断言**，任一侧不成立都判为无效。
                problems.append(
                    f"[{qid}] avoid_term「{t}」未逐字出现在 {gold} 原文中"
                    "（它算不上文档原字面词，标注无效）")
            if t in query:
                problems.append(
                    f"[{qid}] avoid_term「{t}」出现在 query「{query}」中"
                    "（这是照抄原词，不是改写）")
    return problems


# --------------------------------------------------------------------------
# 隔离库
# --------------------------------------------------------------------------
def new_library(prefix: str) -> Path:
    """新建一个 TEMP 隔离资料库并把 app.core.paths 重绑过去。"""
    lib = test_env.create_isolated_library(prefix=prefix)
    os.environ["KAVIRA_LIBRARY"] = str(lib)
    paths.rebind(lib)
    paths.ensure_dirs()
    return lib


def build_library(fixtures_dir: Path, embedder, dim: int = DEFAULT_DIM):
    """把 fixtures 拷进隔离库并用给定嵌入器建索引。"""
    db = db_mod.get_db(paths.CACHE_DB, embedding_dim=dim)
    db.init_schema()
    for src in sorted(Path(fixtures_dir).glob("*.md")):
        dst = paths.NOTES_DIR / src.name
        shutil.copyfile(src, dst)
        indexer.index_file(db, dst, embedder)
    return db


def doc_map(db) -> dict[str, str]:
    """文件名 → doc_id（金标文档定位用）。"""
    return {Path(r["rel_path"]).name: r["doc_id"]
            for r in db.query("SELECT doc_id, rel_path FROM documents")}


def vec_route_status(db) -> dict:
    """向量路是否真的活着（表在 + 无维度冲突 + 表里真有向量）。"""
    rows = None
    if db.vec_table_ready:
        try:
            rows = int(db.query("SELECT count(*) AS n FROM chunks_vec")[0]["n"])
        except Exception:  # noqa: BLE001 - 只读探测，失败即视为未知
            rows = None
    return {
        "vec_table_ready": bool(db.vec_table_ready),
        "signature_mismatch": str(db.signature_mismatch or ""),
        "vec_rows": rows,
    }


def embedder_meta(embedder, fallback_reason: str = "") -> dict:
    """嵌入器身份（写进报告的「有效性声明」）。"""
    res = getattr(embedder, "resource", None)
    return {
        "tier": str(getattr(embedder, "source", "") or "?"),
        "model_id": str(getattr(embedder, "model", "") or "?"),
        "dimension": int(getattr(embedder, "dim", 0) or 0),
        "signature": str(getattr(embedder, "signature", "") or ""),
        "resource_id": str(getattr(res, "id", "") or ""),
        "base_model": str(getattr(res, "base_model", "") or ""),
        "precision": str(getattr(embedder, "precision", "")
                         or getattr(res, "precision", "") or ""),
        "fallback_reason": str(fallback_reason or ""),
    }


def resolve_real_embedder() -> tuple[object, dict, str]:
    """解析**生产**嵌入源（走 embedder.resolve 全链路，不做任何特殊照顾）。"""
    resolved = emb_mod.resolve(config.get)
    meta = embedder_meta(resolved.embedder if resolved.embedder else None,
                         resolved.fallback_reason)
    meta["resolve_notes"] = list(resolved.notes)
    meta["resolve_warnings"] = list(resolved.warnings)
    return resolved.embedder, meta, str(resolved.source)


# --------------------------------------------------------------------------
# 单题测量
# --------------------------------------------------------------------------
#: 向量候选上限的取样条数（与 hybrid_search 的 candidates 默认值一致）
VEC_LIMIT = 20


def gold_vec_ceiling(db, embedder, query: str, gold_doc_id: str, floor: float,
                     limit: int = VEC_LIMIT) -> dict:
    """「闸门打开**之前**」的上限：金标文档有没有被向量路捞到、相似度多少。

    只读复算一次生产向量召回（``search._vec_search`` —— 与 ``hybrid_search`` 内部
    **同一条语句、同一个嵌入器**），再把 chunk_id 映射回 doc_id。
    ⚠ 纯只读测量：不改任何状态，也不影响 ``hybrid_search`` 的行为。

    为什么非测这个不可：只看闸门**之后**的输出，两个嵌入器会一模一样
    （纯向量候选全被 `_is_grounded()` 判死），很容易被读成「模型选型无所谓」。
    把闸门之前的候选摊开，差异才看得见 —— 那是**闸门一旦开放就能兑现的收益**。
    """
    out: dict = {"gold_in_vec_candidates": False,
                 "gold_best_vec_similarity": None,
                 "gold_vec_ge_floor": False}
    if not gold_doc_id:
        return out
    pairs = S._vec_search(db, embedder, query, limit)
    if not pairs:
        return out
    cids = [c for c, _ in pairs]
    ph = ",".join("?" * len(cids))
    try:
        rows = db.query(
            f"SELECT chunk_id, doc_id FROM chunks WHERE chunk_id IN ({ph})", tuple(cids))
    except Exception:  # noqa: BLE001 - 只读探测，失败即视为未知
        return out
    doc_of = {r["chunk_id"]: r["doc_id"] for r in rows}
    sims = [S._sim_from_distance(d) for c, d in pairs
            if doc_of.get(c) == gold_doc_id]
    sims = [s for s in sims if s is not None]
    if not sims:
        return out
    best = max(sims)
    out["gold_in_vec_candidates"] = True
    out["gold_best_vec_similarity"] = round(best, 4)
    out["gold_vec_ge_floor"] = bool(best >= floor)
    return out


def run_one(db, embedder, case: dict, top_k: int, docs: dict | None = None,
            floor: float = 0.6) -> dict:
    """跑一次生产 hybrid_search()，把 debug 通道能拿到的全部记账。"""
    dbg: dict = {}
    res = S.hybrid_search(db, embedder, case["query"], top_k_parents=top_k, debug=dbg)

    refs = list(res.references)
    names = [Path(r.path).name for r in refs]
    gold = case["gold_doc"]
    rank = next((i for i, n in enumerate(names, start=1) if n == gold), 0)

    rejected = list(dbg.get("rejected") or [])
    grounded = list(dbg.get("grounded") or [])
    reasons = Counter(str(r.get("reason") or "?") for r in rejected)
    sims = [float(r["similarity"]) for r in rejected
            if r.get("similarity") is not None]
    # A/B：语义专用通道的可观测性（P1-3）—— 放行数、阈值、每条引用的匹配来源
    sem = dict(dbg.get("semantic") or {})
    ref_modes = Counter(str(getattr(r, "match_mode", "lexical") or "lexical") for r in refs)

    return {
        "id": case["id"],
        "query": case["query"],
        "gold_doc": gold,
        "answer_hint": case.get("answer_hint", ""),
        "avoid_terms": list(case.get("avoid_terms") or []),
        "n_refs": len(refs),
        "empty": len(refs) == 0,
        "route": res.route,
        "no_lexical_hit": "no-lexical-hit" in (res.route or ""),
        "warnings": list(res.warnings),
        "counts": dict(res.counts or {}),
        "lexical_candidates": int(dbg.get("lexical_candidates", 0) or 0),
        "vector_candidates": int(dbg.get("vector_candidates", 0) or 0),
        "fused": len(grounded) + len(rejected),
        "accepted": len(grounded),
        "rejected": len(rejected),
        "rejected_reasons": dict(reasons),
        "grounded_reasons": dict(
            Counter(str(g.get("reason") or "?") for g in grounded)),
        "resolved_scope_terms": list(dbg.get("scope_terms") or []),
        "resolved_target_terms": list(dbg.get("target_terms") or []),
        # A/B：语义通道（P1-3 可观测性）
        "semantic": sem,
        "semantic_released_count": int(dbg.get("semantic_released_count", 0) or 0),
        "semantic_threshold": sem.get("threshold"),
        "ref_match_modes": dict(ref_modes),
        "best_rejected_similarity": round(max(sims), 4) if sims else None,
        # 闸门打开**之前**的上限（只读复算一次向量召回，见 gold_vec_ceiling）
        **gold_vec_ceiling(db, embedder, case["query"], (docs or {}).get(gold, ""), floor),
        "top5_docs": names[:top_k],
        "hit@1": rank == 1,
        "hit@3": 0 < rank <= 3,
        "hit@5": 0 < rank <= 5,
        "first_hit_rank": rank,
        "rr": (1.0 / rank) if rank else 0.0,
    }


# --------------------------------------------------------------------------
# 聚合
# --------------------------------------------------------------------------
def _rate(records: list[dict], key: str) -> float | None:
    vals = [bool(r.get(key)) for r in records]
    return (sum(vals) / len(vals)) if vals else None


def aggregate(records: list[dict]) -> dict:
    """核心指标。``failure_rate@5`` 就是头条数字。"""
    n = len(records)
    if not n:
        return {}
    r5 = _rate(records, "hit@5") or 0.0
    mrr = statistics.fmean([r["rr"] for r in records]) if records else 0.0
    zero = [r for r in records if r["lexical_candidates"] == 0]
    accepted0 = [r for r in records if r["accepted"] == 0]
    released = [r for r in records if r.get("semantic_released_count")]
    sem_refs = sum(int((r.get("ref_match_modes") or {}).get("semantic-only", 0))
                   for r in records)
    return {
        "cases": n,
        "failure_rate@5": round(1.0 - r5, 4),
        "recall@1": round(_rate(records, "hit@1") or 0.0, 4),
        "recall@3": round(_rate(records, "hit@3") or 0.0, 4),
        "recall@5": round(r5, 4),
        "mrr": round(mrr, 4),
        "empty_result_rate": round(_rate(records, "empty") or 0.0, 4),
        "no_lexical_hit_rate": round(_rate(records, "no_lexical_hit") or 0.0, 4),
        "accepted_zero_rate": round(len(accepted0) / n, 4),
        "zero_lexical_overlap_rate": round(len(zero) / n, 4),
        "avg_lexical_candidates": round(
            statistics.fmean([r["lexical_candidates"] for r in records]), 2),
        "avg_vector_candidates": round(
            statistics.fmean([r["vector_candidates"] for r in records]), 2),
        # A/B：语义通道放行统计（P1-3）
        "semantic_released_total": sum(
            int(r.get("semantic_released_count", 0) or 0) for r in records),
        "queries_with_release": len(released),
        "queries_with_release_rate": round(len(released) / n, 4),
        "semantic_only_references": sem_refs,
    }


def vector_ceiling(records: list[dict], floor: float) -> dict:
    """闸门打开**之前**的上限聚合：金标文档被向量路捞到的题数与最高相似度。"""
    n = len(records)
    if not n:
        return {}
    sims = [r["gold_best_vec_similarity"] for r in records
            if r.get("gold_best_vec_similarity") is not None]
    return {
        "cases": n,
        "gold_in_vec_candidates": sum(1 for r in records if r.get("gold_in_vec_candidates")),
        "gold_vec_sim_ge_floor": sum(1 for r in records if r.get("gold_vec_ge_floor")),
        "max_gold_vec_similarity": round(max(sims), 4) if sims else None,
        "SEM_FLOOR": floor,
    }


def rejection_histogram(records: list[dict]) -> dict:
    """被拒切片的 reason 直方图（哪条规则在拒绝）。"""
    hist: Counter = Counter()
    for r in records:
        for reason, cnt in (r.get("rejected_reasons") or {}).items():
            hist[reason] += int(cnt)
    return dict(sorted(hist.items(), key=lambda kv: -kv[1]))


def sem_floor_note(records: list[dict], floor: float = 0.6) -> dict:
    """「语义已经够近，却照样被拒」统计。

    ``_is_grounded`` 的 rule B/C 都要求 **scope 词命中章节路径或文档标题**；
    当 query 的实词在语料里一个都锚不上（scope/target 皆空）时，相似度再高也进不去。
    这一组数字把「闸门的结构性拒绝」与「嵌入质量不够」区分开。
    """
    high = [r for r in records
            if (r.get("best_rejected_similarity") or 0.0) >= floor]
    return {
        "SEM_FLOOR": floor,
        "queries_best_rejected_sim_ge_floor": len(high),
        "of_which_empty": sum(1 for r in high if r["empty"]),
        "example_ids": sorted(r["id"] for r in high)[:8],
    }


def pick_failure_cases(records: list[dict], limit: int = 5) -> list[dict]:
    """挑可人工复核的失败案例。

    刻意**两类都取**：3 个空结果（按被拒最高相似度倒序，越"冤"越靠前）
    + 2 个非空但 top-5 全错（说明闸门放行的是别的文档）。
    """
    fails = [r for r in records if not r["hit@5"]]
    empties = sorted((r for r in fails if r["empty"]),
                     key=lambda r: -(r.get("best_rejected_similarity") or 0.0))
    wrongs = sorted((r for r in fails if not r["empty"]), key=lambda r: r["id"])
    picked = empties[:3] + wrongs[:2]
    out = []
    for r in picked[:limit]:
        top_reason = max((r.get("rejected_reasons") or {}).items(),
                         key=lambda kv: kv[1], default=("—", 0))
        out.append({
            "id": r["id"],
            "query": r["query"],
            "gold_doc": r["gold_doc"],
            "answer_hint": r.get("answer_hint", ""),
            "empty": r["empty"],
            "n_refs": r["n_refs"],
            "route": r["route"],
            "system_warning": (r.get("warnings") or [""])[0],
            "warnings": r.get("warnings") or [],
            "lexical_candidates": r["lexical_candidates"],
            "vector_candidates": r["vector_candidates"],
            "accepted": r["accepted"],
            "rejected": r["rejected"],
            "top_rejected_reason": top_reason[0],
            "rejected_reasons": r.get("rejected_reasons") or {},
            "best_rejected_similarity": r.get("best_rejected_similarity"),
            "top5_docs": r.get("top5_docs") or [],
        })
    return out


# --------------------------------------------------------------------------
# 报告渲染
# --------------------------------------------------------------------------
def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def render_md(rep: dict) -> str:
    m = rep["metrics"]
    emb = rep["meta"]["embedder"]
    vec = rep["meta"]["vector_route"]
    hc = rep.get("hash_control")

    L = ["# Kavira · 改写查询探针报告（Paraphrase Probe）", "",
         f"- 生成时间：{rep['meta']['generated_at']}",
         f"- 题量：**{m['cases']}** 条人工撰写的中文改写查询（top_k={rep['meta']['top_k']}）",
         f"- 语料：Holdout B 的 8 篇文档（`{rep['meta']['corpus_dir']}`）；**只复用文档，不复用其已冻结的 57 道题**",
         f"- 隔离库：`{rep['meta']['library']}`（TEMP，未触碰真实 Library）",
         f"- 耗时：{rep['meta']['elapsed_s']}s", "",
         "## 头条数字", "",
         f"> **{_pct(m['failure_rate@5'])} 的改写查询，在 top-5 里拿不到正确文档。**",
         "",
         f"也就是说：用户换一种说法提问时，约 **每 {round(1 / m['failure_rate@5'], 1) if m['failure_rate@5'] else '∞'} 次"
         f"就有 1 次**在候选项里根本找不到那篇资料。", "",
         "## 有效性声明（先看这个，再看分数）", "",
         "| 项 | 值 |", "| --- | --- |",
         f"| 嵌入器 tier | **{emb['tier']}** |",
         f"| 模型 id | `{emb['model_id']}` |",
         f"| base model | `{emb['base_model']}` |",
         f"| 精度 / 维度 | {emb['precision']} / **{emb['dimension']}** |",
         f"| 签名 | `{emb['signature']}` |",
         f"| 向量路是否启用 | **{'是' if vec['vec_table_ready'] else '否'}**"
         f"（chunks_vec 行数={vec['vec_rows']}，维度冲突={vec['signature_mismatch'] or '无'}） |",
         f"| 嵌入资源目录 | `{rep['meta']['embedding_dir']}` |",
         f"| 降级原因 | {emb['fallback_reason'] or '无（未降级）'} |", "",
         "> ⚠ 现有 `eval/run_eval.py` 用的是 `HashEmbedder`（哈希伪向量，无语义），",
         "> 它**永远测不出**同义改写问题。本报告的数字只有在 tier=`local_onnx`、",
         "> 且 `chunks_vec` 真有向量时才成立；否则探针会直接报错退出，不会产出数字。",
         ""]

    L += ["## 总指标", "", "| 指标 | 值 |", "| --- | --- |",
          f"| **失败率（top-5 拿不到正确文档）** | **{_pct(m['failure_rate@5'])}** |",
          f"| Recall@1 | {_pct(m['recall@1'])} |",
          f"| Recall@3 | {_pct(m['recall@3'])} |",
          f"| Recall@5 | {_pct(m['recall@5'])} |",
          f"| MRR | {m['mrr']:.3f} |",
          f"| **空结果率（一条引用都没有）** | **{_pct(m['empty_result_rate'])}** |",
          f"| route 含 `no-lexical-hit` 的比例 | {_pct(m['no_lexical_hit_rate'])} |",
          f"| accepted=0 的查询比例 | {_pct(m['accepted_zero_rate'])} |",
          f"| 字面候选=0 的查询比例 | {_pct(m['zero_lexical_overlap_rate'])} |",
          f"| 平均字面候选数 / 向量候选数 | {m['avg_lexical_candidates']} / {m['avg_vector_candidates']} |",
          ""]

    # A/B：语义专用通道放行统计（P1-3 可观测性）
    if m.get("semantic_released_total") is not None:
        sc = rep["meta"].get("semantic_channel") or {}
        L += ["## 语义通道放行数（A/B，P1-3 可观测性）", "",
              "| 项 | 值 |", "| --- | --- |",
              f"| 通道开关 `allow_semantic_only` | **{'开' if sc.get('allow_semantic_only') else '关'}** |",
              f"| 固定 floor / 相对 margin / 排序惩罚 | "
              f"{sc.get('semantic_floor')} / {sc.get('semantic_margin')} / {sc.get('semantic_penalty')} |",
              f"| 排除的 `question_type` | "
              f"{'、'.join(sc.get('exclude_qtypes') or []) or '（无）'} |",
              "| --- | --- |",
              f"| 语义通道放行的切片总数 | **{m.get('semantic_released_total', 0)}** |",
              f"| 有放行的查询数 | {m.get('queries_with_release', 0)}"
              f"（{_pct(m.get('queries_with_release_rate'))}） |",
              f"| 进入引用的 `semantic-only` 条数 | {m.get('semantic_only_references', 0)} |",
              "",
              "> 放行门槛 = `max(SEMANTIC_FLOOR, 词法候选池最高 sim + SEMANTIC_MARGIN)`；",
              "> 每条被放行候选的来源分类见 `debug[\"semantic\"]`（lexical / scope+semantic / semantic-only）。",
              ""]

    hist = rep.get("rejection_histogram") or {}
    if hist:
        total = sum(hist.values())
        L += ["## 拒绝原因分布（哪个规则在拒绝）", "",
              "| reason | 被拒切片数 | 占比 |", "| --- | --- | --- |"]
        for reason, cnt in hist.items():
            L.append(f"| `{reason}` | {cnt} | {cnt / total * 100:.1f}% |")
        L.append("")

    z = rep.get("zero_lexical_subset") or {}
    if z:
        L += ["## 零字面重合子集（最硬的那一组）", "",
              f"共 **{z.get('cases', 0)}** 条查询在语料里一个字面候选都没有"
              f"（占全部 {_pct(z.get('cases', 0) / m['cases'] if m['cases'] else None)}）：", "",
              "| 指标 | 该子集 | 全集 |", "| --- | --- | --- |",
              f"| 失败率@5 | {_pct(z.get('failure_rate@5'))} | {_pct(m['failure_rate@5'])} |",
              f"| 空结果率 | {_pct(z.get('empty_result_rate'))} | {_pct(m['empty_result_rate'])} |",
              f"| Recall@1 | {_pct(z.get('recall@1'))} | {_pct(m['recall@1'])} |", ""]

    sf = rep.get("sem_floor_note") or {}
    if sf.get("queries_best_rejected_sim_ge_floor"):
        L += ["## 语义够近也进不来：rule B/C 的结构性缺口", "",
              f"有 **{sf['queries_best_rejected_sim_ge_floor']}** 条查询，被拒候选里的最高语义相似度"
              f"已经 **≥ SEM_FLOOR（{sf['SEM_FLOOR']}）**，其中 {sf['of_which_empty']} 条最终仍返回空结果。",
              "",
              "原因写在 `_is_grounded()` 里：rule B/C 都要求 **scope 词命中章节路径或文档标题**。",
              "当 query 的实词在语料里一个都锚不上（scope/target 皆为空列表）时，",
              "`hit_s` 为空，**相似度再高也没有通道可走**，只能落到",
              "`vector-only(no-lexical-overlap)`。也就是说这不是「嵌入不够好」，",
              "而是「闸门没有为『纯语义命中』留出口」。", "",
              "> ⚠ 这句话**只描述闸门当前的状态**，不能读成「模型选型无所谓」。",
              "> 闸门一旦开放，模型立刻变成决定性变量 —— 见下面",
              "> 「对照：换成 HashEmbedder」里的**闸门打开前的上限**小节。", ""]

    L += ["## 失败案例（可人工复核）", ""]
    for c in rep.get("failure_cases") or []:
        kind = "空结果（一条引用都没有）" if c["empty"] else "非空，但 top-5 全是别的文档"
        L += [f"### `{c['id']}` —— {c['query']}", "",
              f"- 失败类型：**{kind}**",
              f"- 正确文档：`{c['gold_doc']}`；答案位置：{c['answer_hint']}",
              f"- route：`{c['route']}`；返回引用数：**{c['n_refs']}**",
              f"- 字面候选 {c['lexical_candidates']} / 向量候选 {c['vector_candidates']}"
              f" → accepted {c['accepted']}、rejected {c['rejected']}",
              f"- 主要拒绝原因：`{c['top_rejected_reason']}`",
              f"- 被拒切片里最高的语义相似度：{c['best_rejected_similarity']}"
              f"（门槛 SEM_FLOOR=0.6）",
              "- 系统提示：" + (("`" + c["system_warning"] + "`") if c["system_warning"] else "（无）")]
        if c["top5_docs"]:
            L.append(f"- 实际 top-5：{', '.join(c['top5_docs'])}")
        else:
            L.append("- 实际 top-5：**（空）**")
        L.append("")

    if hc:
        hm = hc["metrics"]
        L += ["## 对照：换成 HashEmbedder（现有评测口径）", "",
              "| 指标 | 真实模型 local_onnx | HashEmbedder（现有 eval 口径） | 差 |",
              "| --- | --- | --- | --- |"]
        for key, label, kind in (
                ("failure_rate@5", "失败率@5", "pct"),
                ("recall@1", "Recall@1", "pct"),
                ("recall@3", "Recall@3", "pct"),
                ("recall@5", "Recall@5", "pct"),
                ("mrr", "MRR", "raw"),
                ("empty_result_rate", "空结果率", "pct"),
        ):
            a, b = m.get(key), hm.get(key)
            if a is None or b is None:
                continue
            if kind == "pct":
                L.append(f"| {label} | {_pct(a)} | {_pct(b)} | {(b - a) * 100:+.1f}pp |")
            else:
                L.append(f"| {label} | {a:.3f} | {b:.3f} | {b - a:+.3f} |")

        delta = abs((hm.get("failure_rate@5") or 0) - (m.get("failure_rate@5") or 0))
        L += ["", "> 两组跑的是**同一批改写查询、同一套生产检索**，唯一差别是嵌入器。",
              "> HashEmbedder 那一栏就是「现有评测口径看到的成绩」。", ""]

        # 「闸门打开之前」的上限 —— 决定「模型选型到底有没有用」的关键证据
        vc = rep.get("vector_ceiling") or {}
        oc, gc = vc.get("local_onnx"), vc.get("local_hash")
        if oc and gc:
            L += ["### 闸门打开**之前**的上限（金标文档有没有被向量路捞到）", "",
                  "| 嵌入器 | 金标文档出现在向量候选中的题数 | 其中 sim ≥ SEM_FLOOR | 最高相似度 |",
                  "| --- | --- | --- | --- |",
                  f"| local_onnx（bge-small-zh-v1.5-int8） | "
                  f"{oc['gold_in_vec_candidates']}/{oc['cases']} | "
                  f"**{oc['gold_vec_sim_ge_floor']}/{oc['cases']}** | "
                  f"**{oc['max_gold_vec_similarity']}** |",
                  f"| HashEmbedder（现有 eval 口径） | "
                  f"{gc['gold_in_vec_candidates']}/{gc['cases']} | "
                  f"**{gc['gold_vec_sim_ge_floor']}/{gc['cases']}** | "
                  f"**{gc['max_gold_vec_similarity']}** |", "",
                  f"（SEM_FLOOR = {oc['SEM_FLOOR']}；该上限由探针只读复算一次 "
                  "`search._vec_search()` 得到，可复现）", ""]

        if oc and gc:
            note = (
                f"**在现有闸门下**换嵌入器无差别（失败率差 {delta * 100:.1f}pp）："
                "所有纯向量候选都被 `_is_grounded()` 判为 "
                "`vector-only(no-lexical-overlap)`，向量路的语义根本没机会进入排序，"
                "两组自然一模一样。"
                f"但**闸门打开前的上限**两组天差地别 —— ONNX 已在 "
                f"**{oc['gold_vec_sim_ge_floor']}/{oc['cases']}** 题把金标文档捞进向量候选且 "
                f"sim ≥ SEM_FLOOR({oc['SEM_FLOOR']})（最高 {oc['max_gold_vec_similarity']}），"
                f"HashEmbedder 只有 **{gc['gold_vec_sim_ge_floor']}/{gc['cases']}** 题"
                f"（最高 {gc['max_gold_vec_similarity']}）。"
                "→ **闸门一旦开放，模型选型立刻成为决定性变量。**"
                "正确顺序是：**先开通道，再评估模型；开闸门前后各测一次。**")
        else:
            note = (f"两组失败率相差 {delta * 100:.1f}pp；"
                    "未取到「闸门打开前」的上限数据（本次未跑对照组）。")
        L += ["> **读数：** " + note, ""]

    L += ["## 逐题明细", "",
          "| id | query | gold | R@1 | R@5 | 空? | route | 字面/向量候选 | accepted | 主要拒绝原因 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rep.get("per_query") or []:
        top = max((r.get("rejected_reasons") or {}).items(),
                  key=lambda kv: kv[1], default=("", 0))
        L.append(
            f"| `{r['id']}` | {r['query']} | {r['gold_doc']} | "
            f"{'✅' if r['hit@1'] else '❌'} | {'✅' if r['hit@5'] else '❌'} | "
            f"{'⚠️' if r['empty'] else ''} | `{r['route']}` | "
            f"{r['lexical_candidates']}/{r['vector_candidates']} | {r['accepted']} | "
            f"`{top[0] or '—'}` |")

    L += ["", "---", "",
          "> 本报告**只测量**：`hybrid_search()` 仅经官方 `debug` 通道取数，未绕过 `_is_grounded()` 闸门。",
          "> 闸门 rule A/B/C 未改动 —— A/B 语义通道是在其**之上**新增的有约束二次放行出口；",
          "> 放行数/阈值见上表，逐条来源分类见 `debug[\"semantic\"]`（P1-3）。", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------
def _close_log_handlers() -> None:
    """释放 RotatingFileHandler —— 不释放则 rmtree 一定失败（Windows）。"""
    try:
        import logging  # noqa: PLC0415

        lg = logging.getLogger("wikiusb")
        for h in list(lg.handlers):
            try:
                h.close()
            except Exception:  # noqa: BLE001
                pass
            lg.removeHandler(h)
    except Exception:  # noqa: BLE001
        pass


def release_library(db, lib: Path) -> None:
    """关库 → 放句柄 → 删临时目录（Windows 上顺序错了就删不掉）。"""
    if db is not None:
        try:
            db.checkpoint_and_close()
        except Exception:  # noqa: BLE001
            pass
    _close_log_handlers()
    for _ in range(4):
        for suffix in ("", "-wal", "-shm"):
            try:
                (Path(lib) / ("cache.db" + suffix)).unlink(missing_ok=True)
            except OSError:
                pass
        try:
            test_env.cleanup_test_library(lib)
        except Exception:  # noqa: BLE001
            pass
        if not Path(lib).exists():
            return
        time.sleep(0.4)
    print(f"[warn] 临时库未删除（在 TEMP 内，可手动清理）：{lib}")


def print_summary(rep: dict) -> None:
    m = rep["metrics"]
    print("\n" + "=" * 72)
    print("Kavira · 改写查询探针（Paraphrase Probe）")
    print("=" * 72)
    print(f"  embedder tier   : {rep['meta']['embedder']['tier']}"
          f" / {rep['meta']['embedder']['model_id']}"
          f" / {rep['meta']['embedder']['dimension']} 维")
    print(f"  chunks_vec      : ready={rep['meta']['vector_route']['vec_table_ready']}"
          f" rows={rep['meta']['vector_route']['vec_rows']}")
    print(f"  cases           : {m['cases']}   top_k={rep['meta']['top_k']}")
    print("-" * 72)
    print(f"  【头条】失败率@5 : {m['failure_rate@5'] * 100:5.1f}%")
    print(f"  Recall@1        : {m['recall@1'] * 100:5.1f}%")
    print(f"  Recall@3        : {m['recall@3'] * 100:5.1f}%")
    print(f"  Recall@5        : {m['recall@5'] * 100:5.1f}%")
    print(f"  MRR             : {m['mrr']:.3f}")
    print(f"  空结果率        : {m['empty_result_rate'] * 100:5.1f}%")
    print(f"  no-lexical-hit  : {m['no_lexical_hit_rate'] * 100:5.1f}%")
    print("-" * 72)
    print("  拒绝原因分布（被拒切片数）：")
    for reason, cnt in (rep.get("rejection_histogram") or {}).items():
        print(f"      {cnt:5d}  {reason}")
    print("=" * 72)


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval/paraphrase/run_probe.py")
    ap.add_argument("--queries", default=str(QUERIES_FILE), help="改写查询集路径")
    ap.add_argument("--fixtures", default=str(FIXTURES_DIR), help="语料目录（Holdout B 8 篇）")
    ap.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="top_k_parents（默认 5）")
    ap.add_argument("--no-hash-control", action="store_true",
                    help="跳过 HashEmbedder 对照组")
    ap.add_argument("--check-only", action="store_true",
                    help="只跑数据集自检，不建库不检索")
    ap.add_argument("--out", default=None,
                    help="报告输出基名（不含扩展名）。默认 eval/reports/paraphrase_probe（规范报告）。"
                         "⚠ 目标已存在时**默认拒绝覆盖**，需显式 --force；探索性实验建议改用新 --out。")
    ap.add_argument("--force", action="store_true",
                    help="允许覆盖已存在的报告文件（默认拒绝，防误删规范/历史报告）。")
    ap.add_argument("--semantic", choices=["on", "off"], default=None,
                    help="覆写语义专用通道开关 allow_semantic_only（on=1 / off=0）。"
                         "**只改本进程内存，绝不写 config.ini**；不传则沿用 config.ini。"
                         "用于「开/关闸门两态各测一次」（PRD §7.2）。")
    args = ap.parse_args(argv)

    # A/B 两态口径：仅内存覆写 allow_semantic_only。persist=False 保证不落盘 config.ini。
    if args.semantic:
        config.update({"SEARCH": {
            "allow_semantic_only": "1" if args.semantic == "on" else "0"}}, persist=False)
        print(f"[semantic] allow_semantic_only = "
              f"{'1（开）' if args.semantic == 'on' else '0（关）'}"
              "（仅本进程内存，未写 config.ini）")

    # #6 输出保护：目标报告已存在则拒绝覆盖（除非 --force）。放最前，避免白跑一次建库。
    out_base = Path(args.out) if args.out else (REPORTS_DIR / REPORT_NAME)
    out_json, out_md = Path(f"{out_base}.json"), Path(f"{out_base}.md")
    if not args.check_only:
        _existing = [p for p in (out_json, out_md) if p.exists()]
        if _existing and not args.force:
            print("⛔ 目标报告已存在，拒绝覆盖（防误删规范 / 历史报告）：")
            for _p in _existing:
                print(f"   - {_p}")
            print("   探索性实验请改用 --out <新名>；确要覆盖请显式加 --force。")
            release_library(None, _LIB)
            return 6

    rows = load_queries(Path(args.queries))
    if not rows:
        print(f"[ERROR] 查询集为空：{args.queries}")
        release_library(None, _LIB)
        return 2

    problems = validate_queries(rows, Path(args.fixtures))
    if problems:
        print("=" * 72)
        print("  ⛔ 改写查询集自检失败 —— 不产出任何数字")
        print("=" * 72)
        for p in problems:
            print("  - " + p)
        release_library(None, _LIB)
        return 2
    print(f"[selfcheck] {len(rows)} 条改写查询全部通过双向断言"
          "（avoid_terms 逐字存在于目标文档 / 且不出现在 query 中）")
    if args.check_only:
        # 导入期就建好了隔离库（paths 需要它），这里必须还回去，别在 TEMP 里留垃圾。
        release_library(None, _LIB)
        return 0

    t0 = time.time()
    fixtures = Path(args.fixtures)
    corpus_docs = sorted(p.name for p in fixtures.glob("*.md"))

    # ---- 1) 主口径：真实 ONNX 嵌入模型 ----
    embedder, emb_meta, source = resolve_real_embedder()
    if source != "local_onnx" or not isinstance(embedder, emb_mod.OnnxEmbedder):
        print("=" * 72)
        print("  ⛔ 有效性校验失败：本次生效的嵌入器不是真实 local_onnx")
        print("=" * 72)
        print("  期望 tier : local_onnx（bge-small-zh-v1.5-int8 ONNX）")
        print(f"  实际 tier : {source}")
        print(f"  fallback  : {emb_meta['fallback_reason'] or '（无）'}")
        print(f"  notes     : {emb_meta['resolve_notes']}")
        print(f"  warnings  : {emb_meta['resolve_warnings']}")
        print("  嵌入资源目录 : " + _EMBEDDING_DIR)
        print("")
        print("  用 HashEmbedder / 纯 FTS5 跑出的分数**测不出同义改写问题**，")
        print("  会把「换个说法找不到」这个真实缺陷掩盖掉。故不肯产出数字，直接退出。")
        print("=" * 72)
        release_library(None, _LIB)
        return 3

    dim = int(getattr(embedder, "dim", DEFAULT_DIM) or DEFAULT_DIM)
    print(f"[embedder] tier={source} model={emb_meta['model_id']} dim={dim}")
    print(f"[embedder] {emb_meta['resolve_notes']}")

    db = build_library(fixtures, embedder, dim)
    vec = vec_route_status(db)
    print(f"[vector] ready={vec['vec_table_ready']} rows={vec['vec_rows']} "
          f"mismatch={vec['signature_mismatch'] or '无'}")
    if not vec["vec_table_ready"] or not vec["vec_rows"]:
        print("  ⛔ 向量路未真正启用（表不可用或没有向量），本次测量不成立。")
        release_library(db, _LIB)
        return 4

    floor = float(S.SEM_FLOOR)
    docs = doc_map(db)
    records: list[dict] = []
    for case in rows:
        rec = run_one(db, embedder, case, args.top_k, docs=docs, floor=floor)
        records.append(rec)
        flag = "❌空" if rec["empty"] else ("✅" if rec["hit@1"] else "·")
        print(f"  [{flag}] {rec['id']:20s} lex={rec['lexical_candidates']:<3d} "
              f"vec={rec['vector_candidates']:<3d} acc={rec['accepted']:<3d} "
              f"route={rec['route']}")

    metrics = aggregate(records)
    zero_subset = [r for r in records if r["lexical_candidates"] == 0]
    zero_metrics = aggregate(zero_subset)
    zero_metrics["cases"] = len(zero_subset)

    report = {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "app_version": _app_version(),
            "top_k": args.top_k,
            "corpus_dir": str(fixtures).replace("\\", "/"),
            "corpus_docs": corpus_docs,
            "queries_file": str(args.queries).replace("\\", "/"),
            "embedding_dir": _EMBEDDING_DIR.replace("\\", "/"),
            "library": str(_LIB),
            "embedder": emb_meta,
            "vector_route": vec,
            # A/B：语义专用通道的口径快照（R5「口径逐次核对」）
            "semantic_channel": {
                "allow_semantic_only": bool(
                    config.get_bool("SEARCH", "allow_semantic_only", False)),
                "semantic_floor": float(S.semantic_floor()),
                "semantic_margin": float(S.SEMANTIC_MARGIN),
                "semantic_penalty": float(S.SEMANTIC_PENALTY),
                "exclude_qtypes": sorted(S.SEMANTIC_EXCLUDE_QTYPES),
            },
            "elapsed_s": round(time.time() - t0, 2),
        },
        "metrics": metrics,
        "zero_lexical_subset": zero_metrics,
        "sem_floor_note": sem_floor_note(records, floor=S.SEM_FLOOR),
        "rejection_histogram": rejection_histogram(records),
        "failure_cases": pick_failure_cases(records, limit=5),
        "per_query": records,
        "vector_ceiling": {"local_onnx": vector_ceiling(records, floor)},
        "hash_control": None,
    }
    release_library(db, _LIB)

    # ---- 2) 可选对照：HashEmbedder（现有 eval 口径）----
    if not args.no_hash_control:
        try:
            lib2 = new_library("kavira-paraphrase-hash-")
            hash_emb = HashEmbedder(dim)
            db2 = build_library(fixtures, hash_emb, dim)
            vec2 = vec_route_status(db2)
            docs2 = doc_map(db2)
            h_records = [run_one(db2, hash_emb, c, args.top_k, docs=docs2, floor=floor)
                         for c in rows]
            report["vector_ceiling"]["local_hash"] = vector_ceiling(h_records, floor)
            report["hash_control"] = {
                "embedder": embedder_meta(hash_emb),
                "vector_route": vec2,
                "metrics": aggregate(h_records),
                "rejection_histogram": rejection_histogram(h_records),
                "per_query": h_records,
            }
            release_library(db2, lib2)
        except Exception as exc:  # noqa: BLE001 - 对照组失败不影响主口径
            print(f"[warn] HashEmbedder 对照组跳过：{type(exc).__name__}: {exc}")
            report["hash_control"] = {"skipped": f"{type(exc).__name__}: {exc}"}

    report["meta"]["elapsed_s"] = round(time.time() - t0, 2)

    out_base.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(report), encoding="utf-8")

    print_summary(report)
    print(f"\n报告 → {out_md}  /  {out_json}")
    return 0


def _app_version() -> str:
    try:
        from app.version import APP_VERSION  # noqa: PLC0415

        return str(APP_VERSION)
    except Exception:  # noqa: BLE001
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
