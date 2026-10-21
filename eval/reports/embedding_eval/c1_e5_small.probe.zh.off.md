# Kavira · 改写查询探针报告（Paraphrase Probe）

- 生成时间：2026-10-16 20:58:06
- 题量：**32** 条人工撰写的中文改写查询（top_k=5）
- 语料：Holdout B 的 8 篇文档（`<repo>/eval/fixtures_holdout_b`）；**只复用文档，不复用其已冻结的 57 道题**
- 隔离库：`C:\Users\huqih\AppData\Local\Temp\kavira-paraphrase-p_c80hm_`（TEMP，未触碰真实 Library）
- 耗时：1.81s

## 头条数字

> **46.9% 的改写查询，在 top-5 里拿不到正确文档。**

也就是说：用户换一种说法提问时，约 **每 2.1 次就有 1 次**在候选项里根本找不到那篇资料。

## 有效性声明（先看这个，再看分数）

| 项 | 值 |
| --- | --- |
| 嵌入器 tier | **local_onnx** |
| 模型 id | `multilingual-e5-small-int8` |
| base model | `intfloat/multilingual-e5-small` |
| 精度 / 维度 | int8 / **384** |
| 签名 | `local_onnx:multilingual-e5-small-int8:384` |
| 向量路是否启用 | **是**（chunks_vec 行数=52，维度冲突=无） |
| 嵌入资源目录 | `<repo>/vendor/cache/embedding_candidates/c1_e5_small` |
| 降级原因 | 无（未降级） |

> ⚠ 现有 `eval/run_eval.py` 用的是 `HashEmbedder`（哈希伪向量，无语义），
> 它**永远测不出**同义改写问题。本报告的数字只有在 tier=`local_onnx`、
> 且 `chunks_vec` 真有向量时才成立；否则探针会直接报错退出，不会产出数字。

## 总指标

| 指标 | 值 |
| --- | --- |
| **失败率（top-5 拿不到正确文档）** | **46.9%** |
| Recall@1 | 46.9% |
| Recall@3 | 46.9% |
| Recall@5 | 53.1% |
| MRR | 0.481 |
| **空结果率（一条引用都没有）** | **31.2%** |
| route 含 `no-lexical-hit` 的比例 | 31.2% |
| accepted=0 的查询比例 | 31.2% |
| 字面候选=0 的查询比例 | 31.2% |
| 平均字面候选数 / 向量候选数 | 1.69 / 20.0 |

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
| `vector-only(no-lexical-overlap)` | 593 | 100.0% |

## 零字面重合子集（最硬的那一组）

共 **10** 条查询在语料里一个字面候选都没有（占全部 31.2%）：

| 指标 | 该子集 | 全集 |
| --- | --- | --- |
| 失败率@5 | 100.0% | 46.9% |
| 空结果率 | 100.0% | 31.2% |
| Recall@1 | 0.0% | 46.9% |

## 语义够近也进不来：rule B/C 的结构性缺口

有 **32** 条查询，被拒候选里的最高语义相似度已经 **≥ SEM_FLOOR（0.6）**，其中 10 条最终仍返回空结果。

原因写在 `_is_grounded()` 里：rule B/C 都要求 **scope 词命中章节路径或文档标题**。
当 query 的实词在语料里一个都锚不上（scope/target 皆为空列表）时，
`hit_s` 为空，**相似度再高也没有通道可走**，只能落到
`vector-only(no-lexical-overlap)`。也就是说这不是「嵌入不够好」，
而是「闸门没有为『纯语义命中』留出口」。

> ⚠ 这句话**只描述闸门当前的状态**，不能读成「模型选型无所谓」。
> 闸门一旦开放，模型立刻变成决定性变量 —— 见下面
> 「对照：换成 HashEmbedder」里的**闸门打开前的上限**小节。

## 失败案例（可人工复核）

### `pp_wh_short_a` —— A 库那批十二口径的螺丝少了几个？

- 失败类型：**空结果（一条引用都没有）**
- 正确文档：`hb_warehouse.md`；答案位置：「A 库物料」表第一行 + 「盘亏处理」第一条：A-1001 六角螺栓 M12，账面 2400 / 实盘 2396，盘亏 4 个
- route：`like+no-lexical-hit`；返回引用数：**0**
- 字面候选 0 / 向量候选 20 → accepted 0、rejected 20
- 主要拒绝原因：`vector-only(no-lexical-overlap)`
- 被拒切片里最高的语义相似度：0.9062（门槛 SEM_FLOOR=0.6）
- 系统提示：`未找到字面匹配：知识库中没有出现查询实词的内容（已避免用语义相近但无关的文档冒充引用来源）`
- 实际 top-5：**（空）**

### `pp_bridge_mid_cause` —— 中间那跨的垫块被剪歪了，根子在什么地方？

- 失败类型：**空结果（一条引用都没有）**
- 正确文档：`hb_bridge2.md`；答案位置：「病害成因」一节第二条：ZZ-07 的病害由温度变化引起（位置为中跨）
- route：`like+no-lexical-hit`；返回引用数：**0**
- 字面候选 0 / 向量候选 20 → accepted 0、rejected 20
- 主要拒绝原因：`vector-only(no-lexical-overlap)`
- 被拒切片里最高的语义相似度：0.8842（门槛 SEM_FLOOR=0.6）
- 系统提示：`未找到字面匹配：知识库中没有出现查询实词的内容（已避免用语义相近但无关的文档冒充引用来源）`
- 实际 top-5：**（空）**

### `pp_flood_drain` —— 城里淹了以后往外抽水这事儿由哪个单位牵头？

- 失败类型：**空结果（一条引用都没有）**
- 正确文档：`hb_flood.md`；答案位置：「应急处置分工」第一条：城市排涝由排水管理处负责
- route：`like+no-lexical-hit`；返回引用数：**0**
- 字面候选 0 / 向量候选 20 → accepted 0、rejected 20
- 主要拒绝原因：`vector-only(no-lexical-overlap)`
- 被拒切片里最高的语义相似度：0.884（门槛 SEM_FLOOR=0.6）
- 系统提示：`未找到字面匹配：知识库中没有出现查询实词的内容（已避免用语义相近但无关的文档冒充引用来源）`
- 实际 top-5：**（空）**

### `pp_clinic_fasting` —— 抽血化验之前得饿多长时间？

- 失败类型：**非空，但 top-5 全是别的文档**
- 正确文档：`hb_clinic.md`；答案位置：「质量要求」第一条：空腹采血要求禁食 8 小时以上
- route：`like`；返回引用数：**1**
- 字面候选 1 / 向量候选 20 → accepted 1、rejected 19
- 主要拒绝原因：`vector-only(no-lexical-overlap)`
- 被拒切片里最高的语义相似度：0.8891（门槛 SEM_FLOOR=0.6）
- 系统提示：（无）
- 实际 top-5：hb_software.md

### `pp_lab_cycle` —— 这些机器多长时间要重新校对一次？

- 失败类型：**非空，但 top-5 全是别的文档**
- 正确文档：`hb_lab.md`；答案位置：「仪器台账」表校准周期列：三台机器均为 12 个月
- route：`like`；返回引用数：**1**
- 字面候选 1 / 向量候选 20 → accepted 1、rejected 19
- 主要拒绝原因：`vector-only(no-lexical-overlap)`
- 被拒切片里最高的语义相似度：0.8858（门槛 SEM_FLOOR=0.6）
- 系统提示：（无）
- 实际 top-5：hb_software.md

## 对照：换成 HashEmbedder（现有评测口径）

| 指标 | 真实模型 local_onnx | HashEmbedder（现有 eval 口径） | 差 |
| --- | --- | --- | --- |
| 失败率@5 | 46.9% | 46.9% | +0.0pp |
| Recall@1 | 46.9% | 46.9% | +0.0pp |
| Recall@3 | 46.9% | 46.9% | +0.0pp |
| Recall@5 | 53.1% | 53.1% | +0.0pp |
| MRR | 0.481 | 0.481 | +0.000 |
| 空结果率 | 31.2% | 31.2% | +0.0pp |

> 两组跑的是**同一批改写查询、同一套生产检索**，唯一差别是嵌入器。
> HashEmbedder 那一栏就是「现有评测口径看到的成绩」。

### 闸门打开**之前**的上限（金标文档有没有被向量路捞到）

| 嵌入器 | 金标文档出现在向量候选中的题数 | 其中 sim ≥ SEM_FLOOR | 最高相似度 |
| --- | --- | --- | --- |
| local_onnx（bge-small-zh-v1.5-int8） | 32/32 | **32/32** | **0.9081** |
| HashEmbedder（现有 eval 口径） | 32/32 | **0/32** | **0.3374** |

（SEM_FLOOR = 0.6；该上限由探针只读复算一次 `search._vec_search()` 得到，可复现）

> **读数：** **在现有闸门下**换嵌入器无差别（失败率差 0.0pp）：所有纯向量候选都被 `_is_grounded()` 判为 `vector-only(no-lexical-overlap)`，向量路的语义根本没机会进入排序，两组自然一模一样。但**闸门打开前的上限**两组天差地别 —— ONNX 已在 **32/32** 题把金标文档捞进向量候选且 sim ≥ SEM_FLOOR(0.6)（最高 0.9081），HashEmbedder 只有 **0/32** 题（最高 0.3374）。→ **闸门一旦开放，模型选型立刻成为决定性变量。**正确顺序是：**先开通道，再评估模型；开闸门前后各测一次。**

## 逐题明细

| id | query | gold | R@1 | R@5 | 空? | route | 字面/向量候选 | accepted | 主要拒绝原因 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `pp_bridge_year` | 这座桥是哪一年落成的？ | hb_bridge2.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_bridge_joint` | 桥面上留的那几道接缝一共设了多少处？ | hb_bridge2.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_bridge_mid_cause` | 中间那跨的垫块被剪歪了，根子在什么地方？ | hb_bridge2.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_bridge_device_expiry` | 测混凝土开裂大小的那台仪器，标定证书哪天到期？ | hb_bridge2.md | ❌ | ✅ |  | `fts` | 6/20 | 6 | `vector-only(no-lexical-overlap)` |
| `pp_clinic_fasting` | 抽血化验之前得饿多长时间？ | hb_clinic.md | ❌ | ❌ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_clinic_urine` | 尿的标本取好以后，多久之内必须拿去化验？ | hb_clinic.md | ✅ | ✅ |  | `like` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pp_clinic_reagent` | 做化验用的那些药水归谁管进货？ | hb_clinic.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_clinic_flow` | 一份标本从接进来到最后发出结果，中间要走几步？ | hb_clinic.md | ✅ | ✅ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_flood_rainfall` | 六月初那场大雨一共下了多少毫米？ | hb_flood.md | ✅ | ✅ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_flood_inflow` | 上游下来的水最多的时候每秒到了多少方？ | hb_flood.md | ✅ | ✅ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_flood_gate` | 水库那天把几个口子打开放水了？ | hb_flood.md | ✅ | ✅ |  | `like` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pp_flood_drain` | 城里淹了以后往外抽水这事儿由哪个单位牵头？ | hb_flood.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_lab_owner` | 做材料拉伸的大机器里，三百型的那台平时归谁管？ | hb_lab.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_lab_cycle` | 这些机器多长时间要重新校对一次？ | hb_lab.md | ❌ | ❌ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_lab_org` | 测力之类的设备是送到外面哪家单位去标定的？ | hb_lab.md | ❌ | ✅ |  | `like` | 5/20 | 5 | `vector-only(no-lexical-overlap)` |
| `pp_lab_fail` | 要是校下来不合格，这台设备该怎么处理？ | hb_lab.md | ✅ | ✅ |  | `fts` | 7/20 | 7 | `vector-only(no-lexical-overlap)` |
| `pp_sw_position` | 这个软件是给谁用的，能自己架服务器吗？ | hb_software.md | ✅ | ✅ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_sw_current` | 现在线上跑的是哪一版，什么时候发的？ | hb_software.md | ❌ | ❌ |  | `like` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |
| `pp_sw_size` | 单个文件最大能放多大？ | hb_software.md | ✅ | ✅ |  | `like` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |
| `pp_sw_known` | 现在还有哪些地方做得不太好用？ | hb_software.md | ❌ | ❌ |  | `like` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |
| `pp_sub_capacity` | 站里那两台变压器各自能带多少负荷？ | hb_substation.md | ✅ | ✅ |  | `fts` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_sub_breaker` | 那种能切断故障电流的设备一共装了几台？ | hb_substation.md | ✅ | ✅ |  | `like` | 5/20 | 5 | `vector-only(no-lexical-overlap)` |
| `pp_sub_relay_owner` | 站里那些保护类的设备归到哪个人头上？ | hb_substation.md | ✅ | ✅ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_sub_overhaul` | 变压器多久要彻底拆开修一次？ | hb_substation.md | ✅ | ✅ |  | `fts` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |
| `pp_subway_depth` | 这个坑挖了多深？ | hb_subway.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_subway_items` | 这个工程都盯着哪些方面的数据？ | hb_subway.md | ✅ | ✅ |  | `like` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |
| `pp_subway_freq` | 挖土的时候多久测一次？ | hb_subway.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_subway_alarm` | 墙顶往旁边挪到多少就要报警了？ | hb_subway.md | ✅ | ✅ |  | `like` | 3/20 | 3 | `vector-only(no-lexical-overlap)` |
| `pp_wh_scope` | 这次清点一共查了多少种东西？ | hb_warehouse.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_wh_short_a` | A 库那批十二口径的螺丝少了几个？ | hb_warehouse.md | ❌ | ❌ | ⚠️ | `like+no-lexical-hit` | 0/20 | 0 | `vector-only(no-lexical-overlap)` |
| `pp_wh_handle` | 查出来少的东西后来是怎么处理的？ | hb_warehouse.md | ✅ | ✅ |  | `like` | 2/20 | 2 | `vector-only(no-lexical-overlap)` |
| `pp_wh_recheck` | 最后谁来对这次清点的结果把关？ | hb_warehouse.md | ❌ | ❌ |  | `like` | 1/20 | 1 | `vector-only(no-lexical-overlap)` |

---

> 本报告**只测量**：`hybrid_search()` 仅经官方 `debug` 通道取数，未绕过 `_is_grounded()` 闸门。
> 闸门 rule A/B/C 未改动 —— A/B 语义通道是在其**之上**新增的有约束二次放行出口；
> 放行数/阈值见上表，逐条来源分类见 `debug["semantic"]`（P1-3）。
