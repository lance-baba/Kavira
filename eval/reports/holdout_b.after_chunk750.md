# Kavira · Holdout B —— Release Candidate Gate 1

- 生成：2026-10-22 20:44:23　冻结：2026-09-23 07:46:54
- 规模：**57 题 / 8 篇独立文档**，hard case **32%**
- gold sha256：`a244cd8693c9fe9d…`
- 运行时：随包嵌入式 Python + TEMP 隔离库；**未触碰真实 Library**。
- 本轮**只验收未调算法**，生产代码零改动。

## 嵌入器（验收口径）

| 项 | 值 |
| --- | --- |
| tier | **local_onnx** |
| 模型 | `multilingual-e5-small-int8` |
| 精度 / 维度 | int8 / **384** |
| 签名 | `local_onnx:multilingual-e5-small-int8:384` |
| 降级原因 | 无（未降级） |

> ⚠ 本 runner 已强制要求 tier=`local_onnx`：拿不到真实语义模型会直接非 0 退出，不会产出「哈希伪向量口径」的数字。

## Retrieval

| 指标 | 值 |
| --- | --- |
| Recall@1 | **97.5%** |
| Recall@3 | **100.0%** |
| Recall@5 | **100.0%** |
| MRR | **0.988** |
| Coverage group | **100.0%** |
| Coverage full | **100.0%** |
| Relation | 71.4% |

## Safety

| 指标 | 值 |
| --- | --- |
| Wrong-document Rate | **0.0%** |
| No-answer FP Rate | **0.0%** |
| Attribution err（旧口径） | — |
| False Association | **0.0%** （0/8；分母 = no + insufficient + answered + unknown） |
| Unnecessary Guard（**真的被拦**） | **0.0%** （0/44） |
| 普通题进入 Guard（含责任形态） | 2.3% （1/44） |

## Relation（Guard）

| 指标 | 值 |
| --- | --- |
| Positive Relation Accuracy | **100.0%** |
| Negative Relation Accuracy | **100.0%** |
| Abstention Accuracy | **100.0%** |
| Answered Accuracy（查找题，A′ 单独分桶） | **100.0%** （1/1） |

> A′ 口径：`answer_state == "answered"` 的**查找题**不再计入 abstention 桶。Guard=YES 且负责人与 gold `must_contain` 一致 → `answered_correct`（不计 FA）；负责人不符 → `answered_fp`（计 FA，保留「答错责任人」检测力）；Guard≠YES → `answered_miss`（不计 FA，由 Unnecessary Guard 监督）。

## Citation

| 指标 | 值 |
| --- | --- |
| 结构合法率 | **100.0%**（125 条引用） |
| source-range overlap（每题至少一条） | **98.1%**（53 题） |
| └ 逐条引用口径（诊断，天然偏低） | 55.6%（117 条引用） |

## Negative Safety（语义通道 · 负例不入引用）

| 指标 | 值 |
| --- | --- |
| 负例题数（无答案） | **4** |
| └ 其中仍有引用的题数 | 3 |
| └ 含 semantic-only 引用的题数（**须为 0**） | **0** |
| 违规题 id | — |

## 各类型 Recall@1

| 类别 | Recall@1 | n |
| --- | --- | --- |
| citation | 100% | 3 |
| direct_fact | 100% | 5 |
| list_coverage | 100% | 4 |
| model_spec | 100% | 5 |
| person | 100% | 4 |
| quantity | 100% | 5 |
| section_overview | 100% | 4 |
| similar_entity | 100% | 5 |
| table_relation | 80% | 5 |

## Blocker 判定

- **无 Blocker**

## 最终结论

# **RC_READY_WITH_LIMITATIONS**

> 无安全/数据 Blocker（无错误归因、无编造、无引用错位）；存在明确长尾限制，已记录进 KNOWN_LIMITATIONS.md，记录后可进入 Pilot

---

> 本轮只验收不调算法；失败只记录，不现场修。
