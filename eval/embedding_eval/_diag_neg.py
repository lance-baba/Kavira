#!/usr/bin/env python3
"""一次性诊断：hb_neg_design_life 在 C1 下的语义通道放行细节（不入交付链）。

看三件事：① 放行候选的 sim；② 词法池最高分（决定 `_thr`）；③ 泄漏文档达各 floor
的候选数（决定旁证 N）。据此判断「调 N / 调 floor」到底有没有杠杆。
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO / "eval"
C1 = REPO / "vendor" / "cache" / "embedding_candidates" / "c1_e5_small"
os.environ["KAVIRA_EMBEDDING_DIR"] = str(C1)
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(EVAL_DIR))

import holdout_b_run as H  # noqa: E402
from app.core import config, search as S  # noqa: E402

emb, meta, source = H.resolve_real_embedder()
db, emb = H.R.build_library(H.FIXTURES_HB, embedder=emb)
cases = H.load(H.GOLD)
c = next(x for x in cases if x["id"] == "hb_neg_design_life")
print("query:", c["query"])
print("answer_state:", c["expected"].get("answer_state"))

for floor in (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
    config.update({"SEARCH": {"semantic_floor": str(floor)}}, persist=False)
    dbg = {}
    S.hybrid_search(db, emb, c["query"], top_k_parents=5, debug=dbg)
    sem = dbg.get("semantic", {})
    print(f"\nfloor={floor}: threshold={sem.get('threshold')} "
          f"lex_pool_max_sim={sem.get('lex_pool_max_sim')} "
          f"released={sem.get('released')} doc_floor_n={sem.get('doc_floor_n')}")

# 原始（闸门 floor 未动）确认
assert S.SEM_FLOOR == 0.6
try:
    H.R._DB.checkpoint_and_close()
except Exception:
    pass
try:
    import logging
    lg = logging.getLogger("wikiusb")
    for h in list(lg.handlers):
        try:
            h.close()
        except Exception:
            pass
        lg.removeHandler(h)
except Exception:
    pass
try:
    H.R.test_env.cleanup_test_library(H.R._LIB)
except Exception:
    pass
