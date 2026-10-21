# 改写查询探针（Paraphrase Probe）

把用户那句「换个说法可能找不到资料」变成**可复现的硬数据**。

**本探针自身只测量，不改产品代码。** `hybrid_search()` 原封不动调用，只用官方
`debug` 通道取数，不绕过 `_is_grounded()` 闸门、不调任何隐藏开关。

> ⚠ 状态更新（A+B 语义通道实施后）：探针已用于**开闸门前/后各测一次**——
> `paraphrase_probe.baseline_local_onnx.*`（`allow_semantic_only=0` 基线）与
> `paraphrase_probe.*`（=1，实施后）。产品代码的改动（`app/core/search.py` 的
> 语义专用通道、`config.py` 默认值、前端标注）由设计文档 §7 的 T1–T5 负责，
> **不是本探针做的**；探针只负责把「闸门开/关」两种状态的分数测出来并留档（P0-5）。

## 目录

```text
eval/paraphrase/
├─ README.md          # 本文件（复现说明）
├─ queries.json       # 32 条人工撰写的中文改写查询（含 avoid_terms + 自检约定）
├─ run_probe.py       # 探针执行器（自检 → 建隔离库 → 校验嵌入器 → 逐题测量 → 出报告）
└─ (产出)
   eval/reports/paraphrase_probe.json   # 机器可读
   eval/reports/paraphrase_probe.md     # 人读
```

## 为什么必须重新做一套题，而不能直接看 `run_eval.py` 的成绩

`eval/run_eval.py:40` 用的是 `HashEmbedder` —— **确定性的哈希伪向量，没有真实语义**。
现有评测跑出的 Recall@1 97.5%，实质是在测一个「接近词法的系统」，
**永远测不出「同义改写」问题**：哈希向量对同义词照样不相似。

所以本探针强制激活随包的真实 ONNX 嵌入模型：

| 项 | 值 |
| --- | --- |
| tier | `local_onnx` |
| 模型 | `bge-small-zh-v1.5-int8`（base: `BAAI/bge-small-zh-v1.5`，int8，512 维） |
| 权重位置 | `vendor/cache/embedding/`（`model.onnx` + `tokenizer.json` + `artifact.json`） |

### 关键坑：必须在 import `app` 之前设环境变量

`app/core/paths.py:125` 是**模块级求值**：

```python
EMBEDDING_DIR: Path = _detect_embedding_dir(BASE_DIR)
```

而产品默认目录 `resources/embedding/` 下只有契约模板 `default.json`，没有运行时要的
`artifact.json` → 会静默降级成纯 FTS5。因此 `run_probe.py` 在**任何 app import 之前**
就写好 `KAVIRA_EMBEDDING_DIR`（见 `app/core/paths.py:115-119`，官方支持的覆盖点）。

**有效性闸门**：拿不到 `local_onnx`（降级成 HashEmbedder / 纯 FTS5）时，
探针打印醒目错误并 **以退出码 3 退出**，绝不产出误导性数字。这一步比分数本身重要。

## 运行

```bash
# 推荐：随包嵌入式运行时（自带 sqlite-vec，向量路可用；托管的 Python 3.13 缺 sqlite_vec）
runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py

# 只跑数据集自检（不建库、不检索）
runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py --check-only

# 跳过 HashEmbedder 对照组
runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py --no-hash-control

# 换 top_k
runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py --top-k 10

# 探索性实验：换查询集时**务必**用 --out 另存，否则会覆盖规范报告
runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py \
    --queries /tmp/exp.json --out /tmp/exp_report
```

退出码：`0` 成功 · `2` 查询集自检失败 · `3` 嵌入器不是真实 `local_onnx` · `4` 向量路未启用。

**安全**：启动第一步就 `tests/test_env.activate_test_library()`（复用测试安全保险丝），
在 `%TEMP%/kavira-paraphrase-*` 建独立库，fixtures 拷进去索引，跑完关库 + 删目录。
**绝不触碰真实 Library / Documents / LOCALAPPDATA，不读真实 API Key。**

## 数据集契约（`queries.json`）

语料 = Holdout B 的 8 篇文档 `eval/fixtures_holdout_b/`。
**只复用文档，不复用它已冻结的 57 道题与 gold** —— 本探针是全新题面 + 新 gold。

每篇 4 题 × 8 篇 = **32 题**，全部人工撰写（未用模型生成、未套模板）。
每题刻意用**中文同义 / 口语 / 上位说法**替换文档里的原字面词，例如：

| 文档原词 | 改写后的说法 |
| --- | --- |
| 检定有效期 | 标定证书哪天到期 |
| 禁食 8 小时 | 得饿多长时间 |
| 城市排涝 | 淹了以后往外抽水 |
| 开挖深度 | 这个坑挖了多深 |
| 单文件上限 2GB | 单个文件最大能放多大 |

字段：

```jsonc
{
  "id": "pp_bridge_year",
  "query": "这座桥是哪一年落成的？",
  "gold_doc": "hb_bridge2.md",
  "answer_hint": "「桥梁概况」一节末尾：建成于 2011 年",
  "avoid_terms": ["建成于"]        // 文档原字面词，query 刻意回避它
}
```

### 自检（双向断言，任一不成立即报错退出）

`run_probe.py::validate_queries()`：

* **A**：`avoid_terms` 每个词必须**逐字出现在** `gold_doc` 原文中。
  否则它算不上「文档原字面词」，这条标注本身无效。
* **B**：`avoid_terms` 每个词必须**不出现在** `query` 中。
  否则这道是照抄原词（词法路本来就会命中），**不是改写**。
* **C（运行期）**：另外统计每条 query 的 `lexical_candidates`，
  用真实召回数证明「字面重合」到底有没有断。

> 说明：主理人的原始要求是「验证 avoid_terms 里的词确实没有在目标文档原文中按字面出现」。
> 但 `avoid_terms` 的语义是「文档原字面词、query 刻意回避的词」——这两个说法互相矛盾
> （若它不在文档里，它就不是"文档的原字面词"）。这里按**双向断言**实现，
> 两侧都验，更严格也更自洽。

## 测量口径

对每条 query 只做一次调用：

```python
res = search.hybrid_search(db, embedder, query, top_k_parents=5, debug=dbg)
```

从 `SearchResult` 取 `route` / `counts` / `warnings` / `references`；
从 `dbg` 取 `lexical_candidates` / `vector_candidates` / `grounded` / `rejected`。
gold 判定用 `Path(reference.path).name == gold_doc`（文档级，非证据块级）。

| 指标 | 定义 |
| --- | --- |
| **失败率@5** | top-5 引用里没有 gold 文档的查询占比（**头条数字**） |
| Recall@1 / @3 / @5 | top-k 出现 gold 文档的占比 |
| 空结果率 | `len(res.references) == 0` 的占比 |
| `no-lexical-hit` 率 | `route` 含 `no-lexical-hit` 的占比 |
| accepted=0 率 | 没有一个候选通过 `_is_grounded()` 的占比 |
| 拒绝原因分布 | 全部被拒切片的 `reason` 直方图 |
| 零字面重合子集 | `lexical_candidates == 0` 的那组题单独出指标 |
| **闸门打开前的上限** | 金标文档出现在向量候选中的题数 / 其中 `sim ≥ SEM_FLOOR` 的题数 / 最高相似度 |

「闸门打开前的上限」由 `gold_vec_ceiling()` 只读复算一次 `search._vec_search()` 得到
（同一条语句、同一嵌入器），**不改任何状态、不影响 `hybrid_search()` 行为**，
落在报告的 `vector_ceiling` 块与逐题的 `gold_best_vec_similarity` / `gold_vec_ge_floor` 字段。

额外跑一遍 `HashEmbedder`（`--no-hash-control` 可跳过）作对照，用来暴露
「现有评测口径 vs 真实模型」的差距 —— 两个口径都各出一份 `vector_ceiling`。

## 当前结论（2026-10-12，32 题 / top_k=5 / local_onnx）

| 指标 | 值 |
| --- | --- |
| **失败率@5** | **46.9%**（15/32） |
| Recall@1 | 46.9% |
| Recall@5 | 53.1% |
| MRR | 0.481 |
| **空结果率** | **31.2%**（10/32） |
| 拒绝原因 | `vector-only(no-lexical-overlap)` **100%**（597/597） |

三条可直接引用的结论：

1. **字面候选 = 0 的 10 道题，失败率 100%、空结果率 100%。**
   只要 query 的实词在语料里一个都锚不上，就必然返回空结果 —— 这就是用户说的「找不到」。
2. **在现有闸门下**换嵌入器无差别，但**这不等于模型选型无所谓**。
   换成 `HashEmbedder` 后所有指标一模一样（失败率 Δ 0.0pp、MRR Δ 0.000），
   原因是所有纯向量候选都被 `_is_grounded()` 判为 `vector-only(no-lexical-overlap)`，
   向量路的语义**根本没机会进入排序** —— 差异是被闸门抹平的，不是不存在。
   把闸门**之前**的候选摊开看，两组天差地别（见下）。
3. **语义够近也进不来。** 有 9 道题被拒候选的最高相似度已 ≥ `SEM_FLOOR`（0.6），
   最高达 0.6737，仍然返回空。因为 rule B/C 都要求 **scope 词命中章节路径或文档标题**，
   而 scope 为空时 `hit_s` 必空 —— **闸门没有为「纯语义命中」留出口**。

### 闸门打开**之前**的上限（决定了「开通道」值不值）

探针会**只读复算一次**生产向量召回（`search._vec_search()`，与 `hybrid_search` 内部
同一条语句、同一嵌入器），统计「金标文档有没有被向量路捞到」：

| 嵌入器 | 金标文档出现在向量候选的题数 | 其中 sim ≥ SEM_FLOOR(0.6) | 最高相似度 |
| --- | --- | --- | --- |
| `local_onnx`（bge-small-zh-v1.5-int8） | 31/32 | **13/32** | **0.7320** |
| `HashEmbedder`（现有 eval 口径） | 31/32 | **0/32** | 0.2852 |

（该数字与 QA 的独立取证 `temp/qa_paraphrase/v1_hash_control_audit.py` L5 完全一致，
两边互证。）

**读数：闸门一旦开放，模型选型立刻成为决定性变量（13 题 vs 0 题）。
因此正确顺序是：先开通道，再评估模型；开闸门前后各测一次。**
若只做「换更强的嵌入模型」或「加 reranker」，都会排在闸门之后，
对这一类改写查询大概率无效。

## 已知边界

* 语料只有 8 篇小文档，绝对分数会被小规模抬高/压低；有意义的是**结构**（哪条规则在拒绝）
  与**同一批题上的相对差异**。
* gold 是**文档级**，不是证据块级：top-5 里有正确文档就算过，不保证引用的是正确段落。
* 中文改写很难做到 100% 零字面重合（「报告」「检测」这类通用词仍会命中）；
  因此报告额外给出 `lexical_candidates == 0` 的硬子集，避免把「部分命中」混进结论。
