# Kavira 增量设计：改写查询召回（A+B 语义通道）

> 状态：**待老胡确认 Q1–Q5**（§6）。本文件是架构师（高见远）的设计提案 + 团队 lead 的方法论修正。
> 关联 PRD：`docs/paraphrase-recall-PRD.md`；探针：`eval/paraphrase/run_probe.py`。

---

## 0. 关键事实校准（先对齐口径）

| 事实 | 证据 | 对设计的影响 |
|---|---|---|
| `question_type` 运行时枚举 = `{coverage, quantity, person, datetime, model, location, general}` | `search.py:328-344` | PRD §9-Q3 举例的 `negative_no_answer` / `attribution` **不是运行时类型**（是 eval 用例标签），Q3 不能按这两个名字做 denylist。 |
| `allow_semantic_only` 配置已存在 | `config.py:74`（`=0`，`[SEARCH]` 段）、`app.js:1772`（UI 桩） | 后端门控不用新建 key，只需把默认翻成 `1` 并接上真实逻辑。 |
| **Holdout B（及 DEV 72）当前跑在 `HashEmbedder` 上，不是真实模型** | `run_eval.py:66 emb=HashEmbedder(DIM)`；`holdout_b_run.py:391 R.build_library(...)`；`reports/baseline_holdout.json` embedder=`local_hash(512)` | **PRD 的 'before' 基线不存在**。P0-5 Step 0 必须先建 `local_onnx` 基线条，再开通道、再比对。现有 `holdout_b.md` 的 "97.5%/0%" 是词法基线，不是真实模型保证。 |

---

## 1. A. 语义专用通道：**二次放行循环（在 `_is_grounded` 之上），不塞 rule D**

**决策**：在 `hybrid_search` 的 grounded 循环**之后**、`if not accepted:`（1458）**之前**做二次放行，**不修改 `_is_grounded`**。

- N3「只在其上开有约束出口」= on top of，正是二次放行。
- `_is_grounded` 是纯函数、无词法候选池上限上下文；塞 rule D 要改签名 + 唯一调用点（1438）+ 动 A/B/C 三条分支，风险高、难守「A/B/C 不动」验收。二次放行把池上限比较留在 `hybrid_search`（本就有 `fused/lex_ids/accepted/rejected` 全部上下文），`_is_grounded` 字节级不变 → P0-3「闸门未动」可逐字兑现。

**`lex_pool_max_sim` 计算点**（紧接 `search.py:1421` 之后）：

```python
lex_pool_max_sim = None
for _cid in lex_ids:
    _d = fused.get(_cid, {}).get("distance")
    _s = _sim_from_distance(_d)
    if _s is not None and (lex_pool_max_sim is None or _s > lex_pool_max_sim):
        lex_pool_max_sim = _s
```

**二次放行循环**（插入 search.py:1447 之后、1449 之前；`search.py` 当前未 import config，21 行附近加 `from . import config`）：

```python
# ---- A. 语义专用通道（_is_grounded 之上的约束出口，N3）----
_released: list[str] = []
try:
    _sem_on = config.get_bool("SEARCH", "allow_semantic_only", False)
    if _sem_on and ana.question_type not in SEMANTIC_EXCLUDE_QTYPES:
        _thr = max(SEM_FLOOR, (lex_pool_max_sim or 0.0) + SEMANTIC_MARGIN)
        _new_rej = []
        for _item in rejected:                       # 仅检视零字面重合被拒者
            if _item["reason"] != "vector-only(no-lexical-overlap)":
                _new_rej.append(_item); continue
            _cid = _item["chunk_id"]; _sim = _item.get("similarity")
            if _sim is None or _sim < _thr:
                _new_rej.append(_item); continue
            _ent = fused[_cid]
            _ent["_reason"] = "semantic-only"
            _ent["_match_mode"] = "semantic-only"
            accepted.append((_cid, _ent)); _released.append(_cid)
        rejected[:] = _new_rej
        if debug is not None:
            debug["semantic"] = {"enabled": True,
                                 "lex_pool_max_sim": lex_pool_max_sim,
                                 "threshold": round(_thr, 4),
                                 "released": [{"chunk_id": c,
                                               "similarity": fused[c].get("_sim")}
                                              for c in _released]}
            debug["semantic_released_count"] = len(_released)
except Exception as _exc:   # noqa: BLE001
    log.warning("语义通道异常，按现状降级: %s", _exc)
```

**debug 契约零破坏**：`debug["rejected"]`/`debug["grounded"]` 仍是 `list[dict]`，键不变。`gold_vec_ceiling()` 只读 `_vec_search`，不受影响。P1-3 来源分类天然落在 `_reason`：`lexical` / `scope+semantic:*` / `semantic-only`。

---

## 2. B. 词法桥：真实词回灌 + 锚点逐字可匹配（守 P0-2 / N6）

1. 新增 `_real_anchor_terms(text)`（放 `_snippet` 附近 ~664 行）：用 `_TERM_RE` 切词，剔除 `_STOPWORDS`（`search.py:84`）+ `_GENRE_TERMS`（`search.py:108`）+ **时间类通用词集**（`时间/时长/多久/周期/日期/年限` 等，专门封死 §7 的"时间"污染）。
2. snippet 锚点：默认 `_snippet(pr["content"], query)`（664）对语义-only 回退到 `content` 前缀——**本来就是笔记真实文本**，已满足 P0-2。加强项（可选、零额外 I/O）：`_semantic_snippet(content, real_terms)` 取含最多 `real_terms` 的真实句子。
3. 引用身份：`source_start_line/end_line` 来自 `parent_blocks` 真实元数据（`_parent_rows:1223`），snippet ⊂ content → **引用区间与原文逐字可匹配**（P0-2 结构性成立）。
4. **不引入"时间"类通用词**：B 回灌词只来自块内真实词并经三重过滤，绝不把 query 的"时间"泛词带进 grounding → N6 边界守住，不会"借语义通道放行掩盖 §7 次级问题"。

---

## 3. `Reference` 新增字段 + 前端消费

`Reference` dataclass（`search.py:44-59`）加：

```python
match_mode: str = "lexical"   # "lexical" | "semantic-only"
```

- 构造点：`search.py:1583-1589` `Reference(...)` 加 `match_mode=("semantic-only" if acc.get("semantic") else "lexical")`；同步 `parents.append`（1590-1602）加 `"match_mode": ...`。
- 后端透传：grep `Reference(` 与 references 帧序列化点（`app/core/llm.py` / `app/api/*` 的 `similarity=` 同位置），把 `match_mode` 一并 emit 进 inline `[N]` cite 与底部 refs 帧。
- 前端消费：
  - 底部来源 chips：`app.js:348-369 refsHtml()`，在 `<span class="ref" ...>` 加 `data-match-mode="..."`（用既有 `attr()` 工厂），并在 `esc(r.display_source...)` 前插徽标 `<span class="ref-tag semantic">semantic-only</span>`（仅当 `match_mode==="semantic-only"` 且 `show_semantic_label` 开）。
  - inline cite spans：`mdToHtml` 内构造 `.cite` 处（点击逻辑 `app.js:2173-2181` 读 `data-parent-id/snippet/src-start/src-end`）补 `data-match-mode`；tooltip（`app.js:88-95` 已读 `snippet`/`source_start_line`）附加"这条引用来自语义相似匹配，原文未出现你的原话"。
  - 设置页：`app.js:1772-1774` 把 `allow_semantic_only` tip 改成"默认开启：允许语义通道召回，引用会标注 semantic-only"；可选新增 `show_semantic_label` 行（仅控徽标显隐）。

---

## 4. 排序权益（Q4）：永远在字面命中之后

父块聚合（1469-1480）给 `acc` 记 `acc["semantic"]`，`final` 计算（`search.py:1509`）对语义-only 父块减固定惩罚：

```python
sem_pen = SEMANTIC_PENALTY if acc.get("semantic") else 0.0
final = round(float(acc["max"]) - sem_pen + lex + ans + multi, 6)
```

- `SEMANTIC_PENALTY = 0.04`（> 典型 RRF 单 rank 差 ~0.0003、> 词法/向量命中分差 ~0.004-0.016）→ **语义-only 永不在字面命中之前**；存在字面命中时它沉到第 6 被 `ranked[:5]`（1556）截掉（"仅作补充引用"）。
- 唯一例外：`accepted` 全为语义-only（零字面重合子集，原本空结果）→ 自然排第 1 进 top-5，正是"空结果→有结果"的救援场景（P0-1 空结果率下降来源）。

---

## 5. 作用域排除（Q3）+ 降级（🔒3）+ 性能（R4）

- **Q3 denylist（runtime）**：`SEMANTIC_EXCLUDE_QTYPES = frozenset({"coverage"})`。`coverage` 走 B2/B3 整节聚合（1520-1553），注入外部语义文档会污染"功能有哪些"；且 coverage 词法路本稳。其余 `general/quantity/person/datetime/model/location` 全放行。负例/归因保护靠保守阈值 + 总开关 + Holdout B 红线（非 `question_type` denylist）。
- **🔒3 降级**：二次放行整段包 `try/except`；embedder 返回 None / 余弦异常 / DB 错 → 记 warning、不释放、保留原空结果 + 原案。向量路未启用时 `lex_pool_max_sim=None`、候选 sim 全 None → 阈值 `max(0.6,0+0.05)=0.65` 但 `sim is None` 不释放 → 结构性降级。`_sim_from_distance` 对坏距离返回 `None`（1157-1160）→ 条件天然不释放。
- **R4 性能**：0 额外 DB 查询（复用内存 `fused/info/lex_set`）；0 额外 embedder 调用（句级选锚点用 IDF/词频非向量）；候选上限沿用 `candidates=20`；检索/端到端 p95 **+10% 封顶**（基线 `reports/depth_control.json:110` = 972.2ms）。预期 Δ≈0。

---

## 6. Q1–Q5 推荐落地（待老胡拍板）

| # | 推荐默认值 | 默认值如何被基线数据支撑 |
|---|---|---|
| **Q1** 阈值 | **相对+固定双条件**：`thr = max(SEM_FLOOR(0.6), lex_pool_max_sim + 0.05)`；零字面子集 `lex_pool_max_sim=None` → `thr=0.6`。 | 探针实测 13/32 金标 sim≥0.6（最高 0.7320）；597 被拒切片 sim 分布上 0.6 是既有 rule B 已验证安全下限。相对项 `+0.05` 防"postgrey 型近邻"在 lex 池本就高 sim 时偷渡。零字面 10 题子集落到 0.6 固定 floor，足以救回 ≥5/10 命中"≤50%"目标。 |
| **Q2** 开关 | 两个 key 分离：`allow_semantic_only=1`（后端通道门，默认 ON，改 `config.py:74`）+ **新增** `show_semantic_label=1`（仅控徽标显隐，默认 ON）。 | P0-1 通道 ON 才能 46.9%→≤25%；P0-4 标注 100% 可见 → 两默认都 ON。现有 UI 桩 `app.js:1772` 直接接逻辑。 |
| **Q3** 排除 | denylist = `["coverage"]`（runtime）；其余全放行。 | `coverage` 走整节聚合，语义-only 外部文档污染"功能有哪些"；且 coverage 词法路本稳。`negative_no_answer`/`attribution` 非运行时类型，不能做 denylist。 |
| **Q4** 排序 | 永远在字面命中之后（penalty 0.04）；仅当全为语义-only 时才 first。 | "先保证不错，再谈找到"——零字面子集（原本空结果）被救回时自然 first（P0-1 空结果率下降来源）；一旦有字面命中，语义-only 沉到第 6 被截，绝不挤真文档。 |
| **Q5** 次级问题 | **严格隔离 §7**：不改查询词拆分/过滤；B 词法桥三重过滤确保"时间"泛词不进 grounding；两验收各自独立。 | §7 是词法路 `is_lex=True` 直接 grounded 问题，与语义通道正交；借通道放行掩盖会污染"非空但错文档"计数。 |

---

## 7. 任务分解（给 Engineer，线性依赖）

- **T1 基础设施/配置**：`search.py`(加 `from . import config`、加 `SEMANTIC_MARGIN/SEMANTIC_PENALTY/SEMANTIC_EXCLUDE_QTYPES`)、`config.py`(`allow_semantic_only=1` + 加 `show_semantic_label=1`)、`app.js`(1772 tip)。验证：`allow_semantic_only=0` 时行为与基线逐字节一致。
- **T2 核心 A**：`search.py`(1421 后算 `lex_pool_max_sim`；1447-1449 插二次放行 + try/except + `debug["semantic"]`)。验证：探针 32 题失败率 46.9%→≤25%、空结果率 ≤12%、零字面子集 ≤50%；DEV 72 零回退（HashEmbedder 下通道 inert）。
- **T3 核心 B + `match_mode` + 排序惩罚**：`search.py`(`Reference` 加字段；`_real_anchor_terms`/`_semantic_snippet`；父块记 `semantic`；final 减 `sem_pen`；构造写 `match_mode`)。验证：Holdout B（**local_onnx**）引用结构合法率 100%、overlap ≥98.1%、**误归因/Wrong-doc/No-answer FP 全 0%**；语义-only 锚点逐字可匹配；排序惩罚生效。
- **T3.5 安全加固**：语义-only 不作归因证据 —— 在每处 `relation_guard.evaluate_relation()` 调用点（`app/core/llm.py` + `eval/holdout_b_run.py:122-125`）过滤 `match_mode=="semantic-only"` 的引用。验证：Holdout B FA 不高于 T0 基线（≤1 例）。
- **T4 前端标注**：`app.js`(`refsHtml` 加 `data-match-mode`+徽标；cite spans 补 `data-match-mode`；tooltip 补人话；`show_semantic_label` UI)、`app/core/llm.py`(透传 `match_mode`)。验证：离线 UI 语义-only 100% 显示徽标+人话；字面命中零误标；`show_semantic_label=0` 时徽标隐藏但内部标记仍在。
- **T5 评测闭环**：`run_probe.py`(取 `semantic_released_count`、aggregate 加放行统计、render_md 加"语义通道放行数")；**修正 `holdout_b_run.py` 改用真实 `local_onnx`**（见 §8）；基线存档/重跑对比。验证：P0-1~P0-5 + P0-3 红线全过 → 解锁模型评估（N2）。

依赖图：T1 → T2 → T3 → T3.5 → T4 → T5（T3.5 可与 T3 同批交付；线性，便于逐步验收与回滚）。

---

## 8. 方法论修正（影响 P0-5，必须执行）

**现状**：Holdout B 与 DEV 72 均经 `run_eval.build_library` 用 `HashEmbedder`（无真实语义）运行。现有 `holdout_b.md` 的 "Recall@1 ≥97.5% / False Assoc 0%" 是**词法基线**，未验证真实模型下的语义通道行为。

**修正后的 P0-5 流程**：

```
Step 0a  先建 Holdout B 的 local_onnx 基线（修正 holdout_b_run.py 用真实嵌入器）
          → 这是 PRD 假设的 'before' 基线，目前不存在
Step 0b  存档探针 local_onnx 基线（已存在：paraphrase_probe.json，tier=local_onnx）
Step 1   实施 A + B + semantic-only 标注
Step 2   重跑：Holdout B(local_onnx) + 探针(local_onnx) + DEV 72
Step 3   判定：§5 P0 AC 通过 + 与 Step 0a/0b 的【真实模型】基线对比不回退 → 通过
Step 4   （后续独立）嵌入模型评估：开/关闸门两种状态各测一次
```

- `holdout_b_run.py` 须改为自建库 + `resolve_real_embedder()`（镜像 `run_probe.py:196`），不走 `R.build_library`。属 harness 改动，不碰冻结 gold（`HOLDOUT_B_MANIFEST.json` / fixtures / datasets），符合 N5。
- DEV 72 在 HashEmbedder 下通道结构性 inert（sim<0.6 不触发），作零风险 smoke；但为完整验证，应在 local_onnx 下也跑一次（T5）。
- 验收「不回退」的对照基准 = Step 0a/0b 的真实模型基线，**不是**现有 `holdout_b.md` 的词法基线。

---

## 9. T0 实测结果（2026-10-12 21:20，HEAD=48b6473）与验收重写

### 9.1 真实模型基线（local_onnx）

**Holdout B（57题/8篇，hard 32%），报告 `eval/reports/holdout_b.baseline_local_onnx.{json,md}`：**

| 指标 | 值 |
|---|---|
| Recall@1 / @3 / @5 | 97.5% / 100% / 100% |
| MRR | 0.988 |
| Coverage group / full | 100% / 100% |
| **Wrong-document Rate** | **0%** |
| **No-answer FP Rate** | **0%** |
| **False Association** | **12.5%** ← 既有回归（非本次改动） |
| Unnecessary Guard（真的被拦） | 0%（0/44） |
| 普通题进 Guard | 2.3%（1/44） |
| Citation 结构合法率 | 100%（125 条） |
| source-range overlap（每题） | 98.1%（53 题） |
| 各类型 Recall@1 | 仅 table_relation 80%（4/5），其余 100% |

**探针（32题），报告 `eval/reports/paraphrase_probe.baseline_local_onnx.*`：** failure@5 46.9% / 空结果率 31.2% / 零字面子集 100%（重跑 0 漂移）。

**DEV 72（HashEmbedder 口径不变）：** R@1 71.2%（frozen 69.7%，+1.5pp）/ @3 92.4% / @5 93.9% / MRR 0.812。

### 9.2 ★ 关键发现：冻结 `holdout_b.json` 的 Guard 数字已 stale

- 冻结报告 `eval/reports/holdout_b.json` 由 **`c5451b8`（2026-09-23 07:52，"RC Gate 1 只验收"）** 生成，Guard 系数字为 FA 0% / Abstention 100%。
- 此后**唯一**动 `app/core/relation_guard.py` 的提交是 **`21ab749`（2026-09-23 20:42，"补齐责任归属句式与责任类阻断文案"）**，且为 `c5451b8` 的后代。
- ⇒ 当前 HEAD（无任何本次改动）下 FA = **12.5%**（仅 1 例漂移：`hb_p_data`「谁负责数据平差与报表编制？」裁决 INSUFFICIENT_RELATION → YES）。**hash 与 local_onnx 两种口径一致**（非模型相关，是 relation_guard 代码变更所致）。
- RC Gate 1 的 `RC_READY_WITH_LIMITATIONS` 结论基于 stale 数据 → 需重新评估。

### 9.3 据此对验收的重写（替换 PRD 原 P0-3）

| 项 | 重写后判据（对照 T0 真实基线） |
|---|---|
| 探针 failure@5 | 46.9% → **≤25%** |
| 探针空结果率 | 31.2% → **≤12%** |
| 探针零字面子集 | 100% → **≤50%** |
| Holdout B Recall@1 | **≥97.5%** |
| Wrong-doc / No-answer FP | **0% / 0%** |
| Unnecessary Guard | **≤2.3%** |
| Citation 结构率 / overlap | **100% / ≥98.1%** |
| **False Association** | **≤ T0 基线（12.5%，≤1 例），不得新增任何 FA**（绝对 0% 在 HEAD 不可达；既有 12.5% 为独立问题，不在 A+B 范围） |

### 9.4 追加安全加固（T3.5）：语义-only 不作归因证据

**语义-only 引用不得作为 `relation_guard.evaluate_relation()` 的证据。** 在每处 Guard 调用点（生产 `app/core/llm.py` guard 路径 + `eval/holdout_b_run.py:122-125` 构造 `pdicts`）过滤 `match_mode == "semantic-only"` 的引用。理由：这是 R1「误归因回潮」的结构性防线——语义沾边文档即便被放行，也永远无法把归因裁决从 INSUFFICIENT 翻成 YES；若某查询全部引用都是 semantic-only，Guard 证据为空 → 自然 INSUFFICIENT（安全）。

### 9.5 Q3 措辞修正（Q1/Q2/Q4/Q5 不变）

`responsibility`（及 `causal` / `event`）是 `relation_guard` 的运行时 **relation_type**（Guard in-scope），与 search 的 `question_type`（`coverage/quantity/person/datetime/model/location/general`）是**两套分类**。Q3 的 denylist 仍按 search `question_type` 排除 `coverage`；归因安全改由 §9.4 的结构性保障兜底（不再依赖"负例非运行时类型"这一错误前提）。

### 9.6 隔离事故与永久保险丝（如实记录）

工程师 T0 首版改 `holdout_b_run.py` 时把 `from app.core import ... embedder` 置于 `test_env.activate_test_library()` 之前 → `paths.DATA_DIR` 被定死指向真实 dev 库 `<repo>/data`，8 个 fixture 被索引进真实库。已处置：校验 8 文件逐字节相同 → `indexer.purge_orphans()` 清孤儿 → 删 8 文件 → 修 import 顺序 → **新增永久保险丝（`paths.DATA_DIR != test_env._LIB` 或文档数 ≠ fixture 数则 exit 5）**。Lead 只读复核：`repo/data` 现为 **21 文档**、与 21 个 note 文件一一对应、`hb_` 零残留、`git status` 仅两处 eval 改动。**最终一致性由 QA 独立复验。**

---

## 10. B 护栏最终方案（M2 旁证）与验收（实测）

**决策**：老胡授权主理人拍板 → 采用 **M2**。依据：负例 `hb_neg_design_life`（sim 0.642 / 单块 / zero-lex）与救回题 `pp_wh_scope`（sim 0.6225 / 单块 / zero-lex）在检索层**同构且负例更强** ⇒ 阈值类方案无法区分（M1 过拟合且丢更多召回；M3 更差；M4 不改变引用计数）。M2 用"孤块不足以成源"这一普适规则做最小代价护栏。

**机制**：二次放行块追加条件「同一文档内 ≥N 个候选自身 `sim ≥ SEMANTIC_FLOOR(0.6)`」；N = `config [SEARCH] semantic_min_corroboration`（默认 **2**，N=1 回退旧行为）。新增负例题指标 `neg_semantic_new_citation_cases`（Holdout B **BLOCKER F**，before 值取绝对 0）。

| 指标 | OFF 基线 | ON·N=1（无护栏） | ON·N=2（M2） |
|---|---|---|---|
| 探针 failure@5 | 46.9% | 31.2% | **40.6%** |
| 探针空结果率 | 31.2% | 18.8% | **25.0%** |
| 探针 zero-lex 子集失败率 | 100% | 60% | **80%** |
| 探针放行切片 | 0 | 10 | **4** |
| Holdout B `neg_semantic_new_citation_cases` | 0 | **1** | **0** |
| Holdout B `citation.n_refs` | 125 | 126 | **125** |
| Holdout B R@1 / FA / Wrong-doc / No-answer FP / UnnecessaryGuard | 97.5% / 12.5% / 0% / 0% / 0% | 同 | 同（与 T0 逐字段一致） |

**代价**：M2 只拿到 46.9→40.6 的 **6.3pp**（撤回 3 道单块零字面救援题：`pp_wh_scope`/`pp_flood_drain`/`pp_clinic_fasting`）。**取舍依据**：负例题给引用会抬高 LLM 顺着语义沾边引用**编造答案**的风险，撞产品"不编造"核心承诺；且召回三目标已顺延模型阶段。**回退**：`semantic_min_corroboration=1`。

**QA 独立复验 8/8 PASS**（含 N=1 必要性反证：泄漏回 1、探针回 31.2%，坐实代价恰为那 3 题；闸门 `_is_grounded` 字节级未动；双向开关惰性；边界 10/10；回归全绿）。

⚠ **指标口径偏窄（已记录）**：`negative_guard` 只统计 semantic-only **新增**引用；4 道无答案题中仍有 3 道带**词法**引用（`hb_neg_cost`/`hb_neg_price`/`hb_neg_lab_env`，与基线一致），属既有盲点，非本次回归。
