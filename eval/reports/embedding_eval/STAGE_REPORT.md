# 嵌入模型评估 · 前置(P0-0)+基础设施(T02)+速度(T03) 交付报告

> 作者：寇豆码（Engineer） ｜ 阶段：换字节 + 修 pooling 前置
> **未动** chunker / `_is_grounded()` / A+B 通道逻辑 / Holdout B 冻结 gold / eval fixtures。
> 报告全部落在 `eval/reports/embedding_eval/`（新子目录），**未覆盖任何冻结报告**。

---

## 0. 结论速览

| 任务 | 结论 |
|---|---|
| **T01** pooling 修复 + 零回归自证 | ✅ 完成。现役 CLS 模型**向量逐位一致（84/84）**；探针+Holdout 报告**逐字段一致**；单测 22/22 通过 |
| **T02** 评测基础设施 + 门槛0 | ✅ 完成。`eval/embedding_eval/` 五件套；现役基线存档；**C1 metadata 已核实** |
| **T03** 门槛1 速度（C1） | ✅ **通过**（四项均 ≤3×/≤1.0s，见 §4） |
| **C1 需要 `query:`/`passage:` 前缀** | ⚠ **是**。本阶段仅记录，未纳入 manifest 协议（待老胡拍板） |
| **C1 维度** | **384（≠512）** → 换此 artifact **需重建 vec0 表**（PRD §8-R3，待拍板） |
| **Blocker** | 无阻塞。C1 质量/安全（门槛2/3）**刻意未测**——见 §5「为何不测」 |

---

## 1. 改动文件清单（含行号）

| 文件 | 改动 |
|---|---|
| `app/core/embedder.py` | **+40 行**：<br>• `load_embedding_resource()` 解析默认值 `pooling=data.get("pooling") or ""`（原为 `or "cls"`）——漏声明→"未知→降级"，现役显式 `cls` 零影响；<br>• 新增 `OnnxEmbedder._pool(self, last_hidden, mask)`：`cls`→原样 `last_hidden[:,0,:]`；`mean`→按 `attention_mask` 加权、排除 padding（`(h*m).sum(1)/clip(m.sum(1),1e-9)`）；未知→`raise`；<br>• `embed()` 原 `pooled = last_hidden[:,0,:]` 改为 `pooled = self._pool(last_hidden, mask)`；<br>• `probe()` 前置校验 `pooling ∈ {cls,mean}`，否则 `return False, "未知 pooling=...，按不可用降级"` |
| `eval/paraphrase/run_probe.py` | 加 `--semantic {on,off}`；parse 后 `config.update({"SEARCH":{"allow_semantic_only":"1"/"0"}}, persist=False)`（**仅内存，不写 config.ini**） |
| `eval/holdout_b_run.py` | 同上加 `--semantic {on,off}` |
| `tests/test_pooling.py` | **新增** P0-0 单测（合成数组段恒跑；真实模型段缺件时 SKIP） |
| `tests/test_suite.py` | **+7 行**：注册 `run_pooling_tests`（与 A4.1 同级，任何模式都跑） |
| `eval/embedding_eval/` | **新增** `candidates.json` / `pooling_regression.py` / `inspect_artifact.py` / `bench_speed.py` / `run_matrix.py` / `README.md` |

---

## 2. T01 零回归证据（四条独立证据）

### 2.1 golden 逐位一致（`pooling_golden.cls.json`）
固定有序文本集 = 32 条探针 query（文件顺序）+ 8 篇 holdout_b 文档的 parent `retrieval_text`（文档名升序→parent.ord 升序），共 **84** 条。改动**前** `capture`、改动**后** `verify`：

```
比对条数    : 84
逐位一致    : 84/84  (100.0%)
✅ 逐位一致 100% —— CLS 修复前后向量字节级相同，零回归成立
```
（逐元素 `np.float32(v).tobytes().hex()` 比对；文本集 sha256 防漂移。）

### 2.2 pool 语义单测（`tests/test_pooling.py`）
```
P0-0 TOTAL=22 PASS=22 SKIP=0 FAIL=0
```
含：`cls==last_hidden[:,0,:]`；`mean` 与 numpy 手算 `<1e-6` 且排除 padding；`mean!=cls`；未知 pooling `raise`；`probe()` 对未知/漏声明判不可用。真实模型段：`max|mean-numpy|=0`、`max|cls-numpy|=0`、`max|mean-cls|=0.121`、L2≈1。

### 2.3 报告级零回归（改动前 vs 改动后，开/关闸门各一次）
```
probe.on     before==after : True
probe.off    before==after : True
holdout.on   before==after : True
holdout.off  before==after : True
ZERO-REGRESSION ALL EQUAL: True
```
（忽略 `generated_at/elapsed_s/library/embedding_dir/corpus_dir/queries_file`。）

### 2.4 关键数字（现役口径，存档 `incumbent.*`）
| 报告 | 关键数字 |
|---|---|
| `incumbent.probe.on`（开闸门） | failure@5 **40.6%**、空结果 **25.0%**（＝PRD §1.2 现况） |
| `incumbent.probe.off`（关闸门） | failure@5 **46.9%**、空结果 **31.2%** |
| `incumbent.holdout.on` | Recall@1 **97.5%**、Wrong-doc 0%、No-answer FP 0%、FA **12.5%**、citation 结构 100%、overlap **98.1%** |
| `incumbent.holdout.off` | 同上（当前 config 下开/关一致） |

---

## 3. harness 改动零副作用 + 冻结报告复现

加了 `--semantic` 后，直接证据：
- **`--semantic on` ≡ 不传 flag**（同 config 下逐字段一致）→ flag 本身零副作用。
- `holdout_b_run.py --semantic on` 复现冻结 `holdout_b.after_local_onnx.json`：**metrics 全等**（Recall@1 97.5% / FA 12.5% / Wrong-doc 0 / No-answer FP 0 / NegSafety 0）。

**重要发现（如实报告）：committed 的 `paraphrase_probe.json`(31.25%) 与现况(40.6%) 不一致，根因不是本次 harness 改动，而是 M2 加固 `semantic_min_corroboration=2`。**
- 在**内存**里把 `semantic_min_corroboration` 覆写为 1（persist=False）后：
  - probe 复现冻结数字 **31.2% / 18.8%**（＝frozen 31.25%/18.75%）；
  - holdout 复现冻结报告 **逐字段全等**（`citation.n_refs` 126==126、`per_case` 全等）。
- 剩余差异仅为后续 A+B 工作新增的 2 个 debug 子字段（`doc_floor_n`、`min_corroboration`）。
- 佐证：corroboration=1 时负例题 `hb_neg_design_life` 出现 semantic-only 泄漏（Blocker F）——这正是加上 `=2` 的原因。

> 诊断脚本（一次性，未入交付链）：`eval/reports/embedding_eval/temp/_diag_frozen*.py`；复现产物 `temp/probe.corrob1.json`、`temp/holdout.corrob1.json`。

---

## 4. T02 基础设施 + 门槛0 + 现役基线

新增 `eval/embedding_eval/`：`candidates.json`、`inspect_artifact.py`（**不 import app**）、`bench_speed.py`、`run_matrix.py`、`README.md`、`pooling_regression.py`。候选字节目录 `vendor/cache/embedding_candidates/<id>/`（gitignore）。

### 4.1 门槛0 体检（`inspect_artifact.py`，9/9 checks）
| 候选 | size 匹配 | SHA256 重算 | ORT 前向 | 真实维度 | pooling | 交叉核对 |
|---|:--:|:--:|:--:|:--:|---|---|
| **incumbent** `bge-small-zh-v1.5-int8` | ✅ | ✅ | ✅ | 512 | cls | — |
| **c1_e5_small** `multilingual-e5-small-int8` | ✅ | ✅ | ✅ | **384** | **mean** | ✅ 与 `1_Pooling/config.json` 一致 |

### 4.2 C1 metadata（已获取并核实）
| 项 | 值 |
|---|---|
| artifact_source / revision | `Xenova/multilingual-e5-small` @ `761b726dd34fb83930e26aab4e9ac3899aa1fa78` |
| base_model / revision | `intfloat/multilingual-e5-small` @ `614241f622f53c4eeff9890bdc4f31cfecc418b3` |
| filename / precision | `onnx/model_quantized.onnx` / int8 |
| size / SHA256 | `118,308,185` B / `f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193`（下载后重算**逐字节一致**） |
| tokenizer.json | size `17,082,730` / sha256 `0b44a9d7…90f…`（重算一致） |
| dimension / pooling / max_length | **384** / **mean** / 512 |
| license | base **MIT (显式)**；转换仓库未声明，按 MIT 溯源记录 |
| **e5 前缀** | **需要**：query 加 `query: `、passage 加 `passage: `（本阶段仅记录，**未纳入协议**） |
| 体积 | 模型 118.3MB + tokenizer 17.1MB ≈ **135MB**（PRD 建议 ≤150MB ✅） |

> `onnx-community/multilingual-e5-small-ONNX` 返回 **HTTP 401**（不可匿名访问），故采用 `Xenova/multilingual-e5-small`（PRD §4.1 已列的 ONNX-community/Xenova 转换路径之一）。

---

## 5. T03 门槛1 速度（C1）—— ✅ 通过

`bench_speed.py`，产品口径 **2 线程**，8 篇 holdout_b 全量重建：

| 项 | 现役 incumbent | C1 e5-small | 比值 | 门槛 | 判定 |
|---|---:|---:|---:|---:|:--:|
| 单条延迟 batch=1 | 1.448 ms | 3.060 ms | **2.11×** | ≤3× | ✅ |
| 批量吞吐 batch=32 | 1.425 ms/条 | 2.068 ms/条 | **1.45×** | ≤3× | ✅ |
| 全量重建（8 篇） | 0.343 s | 0.586 s | **1.71×** | ≤3× | ✅ |
| session 加载 | 0.356 s | **0.871 s** | — | ≤1.0 s | ✅ |

> 参照：EmbeddingGemma-2 q4 会被此门槛**直接否决**（单条 35.6×、批量 150×）。C1 远在门内。
> 说明：本门槛用**同一 harness 实测的现役基线**做比值（自洽）。PRD §4.3 列的绝对基线（8.6ms/11.1ms/0.21s）与本次实测绝对值不同（机器/口径差异），但**比值判据不受影响**——这正是"对照现役基线"的意义。
> ⚠ 加载 0.871–0.946 s 贴近 1.0s 上限，多轮测量有波动；建议集成前复测确认冷启动预算。

**为何不测质量/安全（门槛2/3）**：团队指令明确本阶段"e5 前缀机制先不做，等老胡拍板"；而 e5 **必须**加 `query:`/`passage:` 前缀才是正确向量空间，此刻测质量/安全会产出**失真数字**。故按铁律留痕：**门槛1 已过，质量/安全待前缀协议拍板后再测**。（`run_matrix.py --quality` 已就绪，可一键跑 2/3。）

---

## 6. git status 摘要

新增（untracked）：`eval/embedding_eval/`、`eval/reports/embedding_eval/`、`tests/test_pooling.py`。
本次我改动：`app/core/embedder.py`(+40)、`tests/test_suite.py`(+7)、`eval/holdout_b_run.py`(+~13，其余为既有 M)、`eval/paraphrase/run_probe.py`。
（其余 `M` 文件 config.py/llm.py/relation_guard.py/search.py/app.js 等为**本阶段之前**的既有改动，非本次所动。）
**冻结资产未动**：`paraphrase_probe.json`(10-12)、`holdout_b.after_local_onnx.json`(10-12)、`HOLDOUT_B_MANIFEST.json`(09-23) mtime 均未变；`config.ini` 未被写入。

## 7. 待办 / 待拍板（交主理人）
1. **e5 前缀**：是否纳入 artifact manifest 协议（`query:`/`passage:`）——决定后才能测 C1 质量/安全。
2. **384 维**：C1 为 384≠512，换 artifact 需重建 vec0 表（PRD §9-Q2）。
3. 现役 `paraphrase_probe.json` 口径已漂移（corroboration=2），PRD 应以其为现况（40.6%）基准。
