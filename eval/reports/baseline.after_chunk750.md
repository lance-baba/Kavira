# Kavira · RAG Eval Lab V1 — Baseline Report

- 生成时间：2026-10-22 20:44:00
- 题量：**72**（top_k=5，embedder=local_onnx(multilingual-e5-small-int8,384d)）
- 隔离库：`C:\Users\huqih\AppData\Local\Temp\kavira-eval-992zo2b8`（TEMP，未触碰真实 Library）
- 耗时：4.91s

## 总指标

| 指标 | 值 |
| --- | --- |
| Evidence Recall@1 | 68.2% |
| Evidence Recall@3 | 90.9% |
| Evidence Recall@5 | 92.4% |
| MRR | 0.794 |
| Coverage Evidence Recall（证据组覆盖） | 82.9% |
| Coverage 全覆盖率 | 71.4% |
| Relation Accuracy（同行共现） | 100.0% |
| Wrong-document Rate | 1.5% |
| No-answer False-positive Rate | 0.0% |
| Attribution 误归因率 | 0.0% |
| Citation 结构合法率 | 100.0% |
| Citation 与证据区间相交率 | 92.4% |

## 各类别

| category | n | Recall@5 | 通过 |
| --- | --- | --- | --- |
| attribution | 5 | 100.0% | 5/5 |
| citation | 5 | 100.0% | 5/5 |
| cross_section | 4 | 100.0% | 4/4 |
| date_time | 5 | 100.0% | 5/5 |
| direct_fact | 8 | 87.5% | 7/8 |
| list_coverage | 5 | 100.0% | 5/5 |
| location | 4 | 75.0% | 3/4 |
| model_spec | 5 | 100.0% | 5/5 |
| negative_no_answer | 5 | — | 5/5 |
| person | 5 | 80.0% | 4/5 |
| quantity | 6 | 100.0% | 6/6 |
| section_overview | 5 | 60.0% | 3/5 |
| similar_entity | 4 | 100.0% | 4/4 |
| table_relation | 6 | 100.0% | 6/6 |

## 三个点名 Baseline

- **level_model_query**：`水准仪是什么型号的？` → Recall@1=❌ Recall@3=✅ Recall@5=✅ RR=0.333 route=like
- **qwen_features**：`Qwen-Image-2.1 的功能有哪些？` → Recall@1=❌ Recall@3=✅ Recall@5=✅ RR=0.5 route=fts
- **typhoon_attribution**：`冷空气影响了哪些地区？` → Recall@1=✅ Recall@3=✅ Recall@5=✅ RR=1.0 route=like

## 最差失败 case（共 6）

| id | category | 归因层 | 查询 |
| --- | --- | --- | --- |
| jkj_l_point_layout | location | `RECALL` | 观测点沿什么布设、间距多少？ |
| jkj_df_purpose | direct_fact | `RERANK` | 监测的目的是什么？ |
| jkj_p_list | person | `RERANK` | 观测人员有哪些？ |
| jkj_so_device | section_overview | `RERANK` | 监测设备情况怎么样？ |
| jkj_so_person | section_overview | `RERANK` | 人员配置情况怎么样？ |
| jkj_so_freq | section_overview | `COVERAGE` | 监测频率是怎么样的？ |

---

> 本报告仅**测量**，未对 search.py / chunker / prompt / embedding / top_k 做任何改动。Baseline 越真实越有价值。
