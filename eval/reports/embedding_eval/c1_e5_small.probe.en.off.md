# Kavira · 改写查询探针报告（Paraphrase Probe）

- 生成时间：2026-10-16 20:58:11
- 题量：**24** 条人工撰写的中文改写查询（top_k=5）
- 语料：Holdout B 的 8 篇文档（`eval/fixtures_paraphrase_en`）；**只复用文档，不复用其已冻结的 57 道题**
- 隔离库：`C:\Users\huqih\AppData\Local\Temp\kavira-paraphrase-2aysiycx`（TEMP，未触碰真实 Library）
- 耗时：1.64s

## 头条数字

> **8.3% 的改写查询，在 top-5 里拿不到正确文档。**

也就是说：用户换一种说法提问时，约 **每 12.0 次就有 1 次**在候选项里根本找不到那篇资料。

## 有效性声明（先看这个，再看分数）

| 项 | 值 |
| --- | --- |
| 嵌入器 tier | **local_onnx** |
| 模型 id | `multilingual-e5-small-int8` |
| base model | `intfloat/multilingual-e5-small` |
| 精度 / 维度 | int8 / **384** |
| 签名 | `local_onnx:multilingual-e5-small-int8:384` |
| 向量路是否启用 | **是**（chunks_vec 行数=40，维度冲突=无） |
| 嵌入资源目录 | `<repo>/vendor/cache/embedding_candidates/c1_e5_small` |
| 降级原因 | 无（未降级） |

> ⚠ 现有 `eval/run_eval.py` 用的是 `HashEmbedder`（哈希伪向量，无语义），
> 它**永远测不出**同义改写问题。本报告的数字只有在 tier=`local_onnx`、
> 且 `chunks_vec` 真有向量时才成立；否则探针会直接报错退出，不会产出数字。

## 总指标

| 指标 | 值 |
| --- | --- |
| **失败率（top-5 拿不到正确文档）** | **8.3%** |
| Recall@1 | 70.8% |
| Recall@3 | 87.5% |
| Recall@5 | 91.7% |
| MRR | 0.793 |
| **空结果率（一条引用都没有）** | **4.2%** |
| route 含 `no-lexical-hit` 的比例 | 4.2% |
| accepted=0 的查询比例 | 4.2% |
| 字面候选=0 的查询比例 | 4.2% |
| 平均字面候选数 / 向量候选数 | 5.08 / 20.0 |

## 语义通道放行数（A/B，P1-3 可观测性）

| 项 | 值 |
| --- | --- |
| 通道开关 `allow_semantic_only` | **关** |
| 固定 floor / 相对 margin / 排序惩罚 | 0.6 / 0.05 / 0.04 |
| 排除的 `question_type` | coverage |
| --- | --- |
| 语义通道放行的切片总数 | **0** |
| 有放行的查询数 | 0（0.0%） |
| 进入引用的 `semantic-only` 条数 | 0 |

> 放行门槛 = `max(SEMANTIC_FLOOR, 词法候选池最高 sim + SEMANTIC_MARGIN)`；
> 每条被放行候选的来源分类见 `debug["semantic"]`（lexical / scope+semantic / semantic-only）。

## 拒绝原因分布（哪个规则在拒绝）

| reason | 被拒切片数 | 占比 |
| --- | --- | --- |
| `vector-only(no-lexical-overlap)` | 381 | 100.0% |

## 零字面重合子集（最硬的那一组）

共 **1** 条查询在语料里一个字面候选都没有（占全部 4.2%）：

| 指标 | 该子集 | 全集 |
| --- | --- | --- |
| 失败率@5 | 100.0% | 8.3% |
| 空结果率 | 100.0% | 4.2% |
| Recall@1 | 0.0% | 70.8% |

## 语义够近也进不来：rule B/C 的结构性缺口

有 **24** 条查询，被拒候选里的最高语义相似度已经 **≥ SEM_FLOOR（0.6）**，其中 1 条最终仍返回空结果。

原因写在 `_is_grounded()` 里：rule B/C 都要求 **scope 词命中章节路径或文档标题**。
当 query 的实词在语料里一个都锚不上（scope/target 皆为空列表）时，
`hit_s` 为空，**相似度再高也没有通道可走**，只能落到
`vector-only(no-lexical-overlap)`。也就是说这不是「嵌入不够好」，
而是「闸门没有为『纯语义命中』留出口」。

> ⚠ 这句话**只描述闸门当前的状态**，不能读成「模型选型无所谓」。
> 闸门一旦开放，模型立刻变成决定性变量 —— 见下面
> 「对照：换成 HashEmbedder」里的**闸门打开前的上限**小节。

## 失败案例（可人工复核）

### `pe_en_sw_known` —— What problems are currently acknowledged?

- 失败类型：**空结果（一条引用都没有）**
- 正确文档：`en_software.md`；答案位置：Known Issues: large files sync slowly on first download; offline conflict merging lacks spreadsheet support
- route：`like+no-lexical-hit`；返回引用数：**0**
- 字面候选 0 / 向量候选 20 → accepted 0、rejected 20
- 主要拒绝原因：`vector-only(no-lexical-overlap)`
- 被拒切片里最高的语义相似度：0.7954（门槛 SEM_FLOOR=0.6）
- 系统提示：`未找到字面匹配：知识库中没有出现查询实词的内容（已避免用语义相近但无关的文档冒充引用来源）`
- 实际 top-5：**（空）**

### `pe_en_lab_cycle` —— How often must these devices be recalibrated?

- 失败类型：**非空，但 top-5 全是别的文档**
- 正确文档：`en_lab.md`；答案位置：Instrument Ledger: share a calibration cycle of 12 months
- route：`fts`；返回引用数：**2**
- 字面候选 2 / 向量候选 20 → accepted 2、rejected 18
- 主要拒绝原因：`vector-only(no-lexical-overlap)`
- 被拒切片里最高的语义相似度：0.8046（门槛 SEM_FLOOR=0.6）
- 系统提示：（无）
- 实际 top-5：en_substation.md, en_clinic.md

## 对照：换成 HashEmbedder（现有评测口径）

| 指标 | 真实模型 local_onnx | HashEmbedder（现有 eval 口径） | 差 |
| --- | --- | --- | --- |
| 失败率@5 | 8.3% | 8.3% | +0.0pp |
| Recall@1 | 70.8% | 66.7% | -4.2pp |
| Recall@3 | 87.5% | 83.3% | -4.2pp |
| Recall@5 | 91.7% | 91.7% | +0.0pp |
| MRR | 0.793 | 0.769 | -0.024 |
| 空结果率 | 4.2% | 4.2% | +0.0pp |

> 两组跑的是**同一批改写查询、同一套生产检索**，唯一差别是嵌入器。
> HashEmbedder 那一栏就是「现有评测口径看到的成绩」。

### 闸门打开**之前**的上限（金标文档有没有被向量路捞到）

| 嵌入器 | 金标文档出现在向量候选中的题数 | 其中 sim ≥ SEM_FLOOR | 最高相似度 |
| --- | --- | --- | --- |
| local_onnx（bge-small-zh-v1.5-int8） | 24/24 | **24/24** | **0.8871** |
| HashEmbedder（现有 eval 口径） | 24/24 | **24/24** | **0.9018** |

（SEM_FLOOR = 0.6；该上限由探针只读复算一次 `search._vec_search()` 得到，可复现）

> **读数：** **在现有闸门下**换嵌入器无差别（失败率差 0.0pp）：所有纯向量候选都被 `_is_grounded()` 判为 `vector-only(no-lexical-overlap)`，向量路的语义根本没机会进入排序，两组自然一模一样。但**闸门打开前的上限**两组天差地别 —— ONNX 已在 **24/24** 题把金标文档捞进向量候选且 sim ≥ SEM_FLOOR(0.6)（最高 0.8871），HashEmbedder 只有 **24/24** 题（最高 0.9018）。→ **闸门一旦开放，模型选型立刻成为决定性变量。**正确顺序是：**先开通道，再评估模型；开闸门前后各测一次。**

## 逐题明细

| id | query | gold | R@1 | R@5 | 空? | route | 字面/向量候选 | accepted | 主要拒绝原因 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `pe_en_bridge_year` | When did the Riverside Viaduct start carrying traffic? | en_bridge.md | ✅ | ✅ |  | `fts` | 7/20 | 7 | `vector-only(no-lexical-overlap)` |
| `pe_en_bridge_joints` | How many gaps are laid out across the road surface of the viaduct? | en_bridge.md | ✅ | ✅ |  | `fts` | 12/20 | 12 | `vector-only(no-lexical-overlap)` |
| `pe_en_bridge_device` | Until what date is the certificate for the instrument that gauges concrete cracking valid? | en_bridge.md | ❌ | ✅ |  | `fts` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |
| `pe_en_wh_scope` | How many different kinds of goods were checked during the audit? | en_warehouse.md | ✅ | ✅ |  | `fts` | 7/20 | 7 | `vector-only(no-lexical-overlap)` |
| `pe_en_wh_short` | For the M12 fasteners in warehouse A, how many pieces went missing? | en_warehouse.md | ✅ | ✅ |  | `fts` | 5/20 | 5 | `vector-only(no-lexical-overlap)` |
| `pe_en_wh_review` | Who performed the final sign-off on the audit result? | en_warehouse.md | ✅ | ✅ |  | `fts` | 8/20 | 8 | `vector-only(no-lexical-overlap)` |
| `pe_en_flood_rain` | How much rain fell during the June storm? | en_flood.md | ✅ | ✅ |  | `fts` | 6/20 | 6 | `vector-only(no-lexical-overlap)` |
| `pe_en_flood_gate` | How many openings did the reservoir use to release water? | en_flood.md | ✅ | ✅ |  | `fts` | 13/20 | 13 | `vector-only(no-lexical-overlap)` |
| `pe_en_flood_drain` | Which office is responsible for draining the city? | en_flood.md | ❌ | ✅ |  | `fts` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pe_en_clinic_fast` | How long must a person go without food before a blood draw? | en_clinic.md | ❌ | ✅ |  | `fts` | 5/20 | 5 | `vector-only(no-lexical-overlap)` |
| `pe_en_clinic_reagent` | Which department buys the chemicals used for testing? | en_clinic.md | ❌ | ✅ |  | `fts` | 7/20 | 7 | `vector-only(no-lexical-overlap)` |
| `pe_en_clinic_flow` | How many stages does a sample pass through from intake to result? | en_clinic.md | ✅ | ✅ |  | `fts` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pe_en_lab_owner` | Who is responsible for the 300-series tensile machine? | en_lab.md | ✅ | ✅ |  | `fts` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pe_en_lab_cycle` | How often must these devices be recalibrated? | en_lab.md | ❌ | ❌ |  | `fts` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pe_en_lab_org` | Which body verifies the force-measuring equipment? | en_lab.md | ❌ | ✅ |  | `fts` | 12/20 | 12 | `vector-only(no-lexical-overlap)` |
| `pe_en_sw_position` | Can this tool be hosted on our own servers? | en_software.md | ✅ | ✅ |  | `fts` | 8/20 | 8 | `vector-only(no-lexical-overlap)` |
| `pe_en_sw_size` | What is the largest file the service accepts? | en_software.md | ✅ | ✅ |  | `fts` | 4/20 | 4 | `vector-only(no-lexical-overlap)` |
| `pe_en_sw_known` | What problems are currently acknowledged? | en_software.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pe_en_sub_cap` | How much load can each of the two transformers carry? | en_substation.md | ✅ | ✅ |  | `fts` | 5/20 | 5 | `vector-only(no-lexical-overlap)` |
| `pe_en_sub_brk` | How many devices are fitted that can interrupt fault current? | en_substation.md | ✅ | ✅ |  | `fts` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pe_en_sub_overhaul` | How often are the transformers completely stripped down and repaired? | en_substation.md | ✅ | ✅ |  | `fts` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |
| `pe_en_subway_depth` | How deep is the pit? | en_subway.md | ✅ | ✅ |  | `fts` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pe_en_subway_freq` | How often are measurements taken while digging? | en_subway.md | ✅ | ✅ |  | `fts` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pe_en_subway_alarm` | At what movement does the wall top trigger a warning? | en_subway.md | ✅ | ✅ |  | `fts` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |

---

> 本报告**只测量**：`hybrid_search()` 仅经官方 `debug` 通道取数，未绕过 `_is_grounded()` 闸门。
> 闸门 rule A/B/C 未改动 —— A/B 语义通道是在其**之上**新增的有约束二次放行出口；
> 放行数/阈值见上表，逐条来源分类见 `debug["semantic"]`（P1-3）。
