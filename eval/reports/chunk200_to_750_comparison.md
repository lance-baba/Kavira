# 分块 200 → 750 召回影响复测报告

- 生成时间：2026-10-22
- 运行器：`./runtime/python-3.11-embed/python.exe`（sqlite_vec / onnxruntime / tokenizers）
- 环境：`KAVIRA_EMBEDDING_DIR=<repo>/vendor/cache/embedding`
- 范围：只重跑评测；`app/core/search.py`、`app/core/chunker.py` **一行未改**；未提交。
- 本轮代码的分块参数：`CHILD_SIZE=750, CHILD_OVERLAP=90, PARENT_SIZE=2400`（`app/core/chunker.py:19-21`）
- 旧值口径的分块参数：`200/30/800`（`git show 999f623:app/core/chunker.py`，2026-10-16 时点）

---

## 0. Harness 改动（唯一改动的代码）

**问题**：`eval/run_eval.py` 历史上在 `build_library()` 里固定用 `HashEmbedder(512)` 伪向量，报告 `meta.embedder` 也硬编码 `local_hash(512)`。DEV72 因此从未测过真实语义通道。

**修法**（对齐 `eval/holdout_b_run.py` / `eval/paraphrase/run_probe.py`）：

1. 文件顶部、**任何 `app.core` 导入之前**设置 `KAVIRA_EMBEDDING_DIR`（默认 `<repo>/vendor/cache/embedding`）。`paths.py` 是模块级求值，晚一步会静默退回 `resources/embedding`（只有契约模板）。
2. 新增 `resolve_real_embedder()`：走生产 `embedder.resolve(config.get)` 全链路，不做特殊照顾。
3. `run_baseline()` 现在**强制**使用真实嵌入器；生效源不是 `local_onnx` 时打印诊断并 `return 5`，**不产出任何数字**（已实测：缺失 artifact 时 exit=5、无报告写入）。
4. 新增 `--out <基名>`（本轮用它把结果写到新文件，未触达冻结报告）和 `--allow-hash-baseline`（仅历史对照，需显式开启）。
5. 报告 `meta` 增加 `embedder_meta`（tier/model/dim/signature/资源目录）与 `chunking`（实际 child/overlap/parent 参数），便于事后核对口径。

> 说明：`build_library()` 不传 embedder 时仍保留 `HashEmbedder` 兜底，仅为兼容旧调用方；`run_baseline` 一定显式传入真实嵌入器。`holdout_b_run.py` 仍显式传自己的 embedder，未受影响。
>
> 已知小瑕疵：`run_eval.py` 结尾的 `print_summary` 仍把输出路径硬编码打印成 `eval/reports/baseline.md`；**实际写入文件以上面的 `--out` 为准**（本轮为 `baseline.after_chunk750.*`）。

**实际生效嵌入器（本轮三套一致）**：
`local_onnx / multilingual-e5-small-int8 / 384 维 / int8`，`embedding_dir = F:/项目/USB-WIKI/vendor/cache/embedding`，`fallback_reason` 为空。

### 本轮产出（均为新增文件，未覆盖任何旧报告）

| 套件 | 文件 |
|---|---|
| DEV72 | `eval/reports/baseline.after_chunk750.json` / `.md` |
| Holdout B | `eval/reports/holdout_b.after_chunk750.json` / `.md` |
| 中文改写 32 题 | `eval/reports/paraphrase_probe.after_chunk750.json` / `.md` |
| 英文改写 24 题 | `eval/reports/paraphrase_probe_en.after_chunk750.json` / `.md` |

复现命令：

```bash
export KAVIRA_EMBEDDING_DIR="$(pwd)/vendor/cache/embedding"
./runtime/python-3.11-embed/python.exe eval/run_eval.py baseline --out baseline.after_chunk750
./runtime/python-3.11-embed/python.exe eval/holdout_b_run.py --no-llm --out holdout_b.after_chunk750
./runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py \
    --out eval/reports/paraphrase_probe.after_chunk750
./runtime/python-3.11-embed/python.exe eval/paraphrase/run_probe.py \
    --queries eval/paraphrase_en/queries_en.json \
    --fixtures eval/fixtures_paraphrase_en \
    --out eval/reports/paraphrase_probe_en.after_chunk750
```

---

## 1. 先看一个决定性事实：本轮语料几乎“测不到”分块粒度

用当前 `chunker.parse()` 分别以 `200/30/800` 与 `750/90/2400` 解析同一批 fixture（**只读统计，不改代码**）：

| 语料 | 分块 | 文档数 | 子块数 | 父块数 | 平均子块长度 | 最长子块 |
|---|---|---:|---:|---:|---:|---:|
| DEV72 (`eval/fixtures`) | 200/30 | 6 | 49 | 48 | 63.2 | 200 |
| DEV72 | 750/90 | 6 | **48** | **48** | 63.9 | 243 |
| Holdout B (`eval/fixtures_holdout_b`) | 200/30 | 8 | 52 | 52 | 65.9 | 178 |
| Holdout B | 750/90 | 8 | **52** | **52** | 65.9 | 178 |
| 英文改写 (`eval/fixtures_paraphrase_en`) | 200/30 | 8 | 40 | 39 | 102.2 | 229 |
| 英文改写 | 750/90 | 8 | **39** | **39** | 104.0 | 229 |

原因：这些 fixture 的**自然章节/段落本身就短于 200 字**，切片主要发生在标题与段落边界，滑窗大小从 200 提到 750 只合并了极少数碎片。**子块总数 49→48、52→52、40→39**，父块数不变。

因此：**这批评测语料在结构上无法体现 200→750 的差异**。分块真正要解决的 253KB 资讯日报、长正文文档，并不在 DEV72 / Holdout B / 改写探针里。

---

## 2. 同口径隔离对照（同模型、同语义闸门，只差分块 200 vs 750）

这一组才是「分块」的净效应。旧值选用**同为 `multilingual-e5-small-int8 / 384`、同为 200 分块**的既有报告，避免把模型升级混进来。

### 2.1 DEV72（72 题，可答 66 题；top-5 父块）

| 指标 | 旧：200 分块 | 新：750 分块 | Δ |
|---|---:|---:|---:|
| R@1 | 66.67% (44/66) | **68.18% (45/66)** | **+1.52pp** |
| R@3 | 89.39% (59/66) | **90.91% (60/66)** | **+1.52pp** |
| R@5 | 90.91% (60/66) | **92.42% (61/66)** | **+1.52pp** |
| MRR | 0.7803 | **0.7939** | **+0.0136** |
| coverage_group_recall | 77.14% | 82.86% | +5.71pp |
| coverage_full_rate | 71.43% | 71.43% | 0 |
| wrong_document_rate | 1.52% | 1.52% | 0 |
| citation_intersection_rate | 90.91% | 92.42% | +1.52pp |

- 旧值来源：`eval/reports/embedding_eval/t07.dev72.json`（2026-10-16 21:25:37；e5-small-384；`note` 明确写着“指标聚合逐字复用 run_eval.run_baseline 口径”）。
- 新值来源：`eval/reports/baseline.after_chunk750.json`（2026-10-22 20:44:00）。
- 变化仅 1 个题位的命中位置（子块 49→48 导致的边界位移），属于噪声量级；**不能据此宣称分块带来稳定增益**。
- 分类上主要变化：`section_overview` R@5 0.40→0.60；`person` 0.80→0.80；`location` 0.75→0.75；其余持平。

### 2.2 中文改写探针（32 题）

| 指标 | 旧：200 分块 | 新：750 分块 | Δ |
|---|---:|---:|---:|
| failure@5 | 15.62% (5/32) | **15.62% (5/32)** | **0** |
| R@1 | 71.88% | 71.88% | 0 |
| R@3 | 78.12% | 78.12% | 0 |
| R@5 | 84.38% | 84.38% | 0 |
| MRR | 0.7625 | 0.7625 | 0 |
| 空结果率 | 3.12% (1/32) | 3.12% (1/32) | 0 |
| 拒因分布 | vector-only 443 | vector-only 444 | +1 切片 |

- 旧值来源：`eval/reports/embedding_eval/t07.probe.zh.on.json`（2026-10-16 21:25:19；e5-384；`semantic_floor=0.84`、`allow_semantic_only=true`，与本轮完全一致）。
- 新值来源：`eval/reports/paraphrase_probe.after_chunk750.json`（2026-10-22 20:44:35）。
- **32 题逐题结果完全一致**；唯一差异是被拒切片数 +1（443→444），来自子块边界变化。
- 拒因分布：两轮都只有一种拒因 `vector-only(no-lexical-overlap)`，即“向量路召回但词法零重叠 → 被 grounded 闸门拒绝”。

### 2.3 英文改写探针（24 题）

| 指标 | 旧：200 分块 | 新：750 分块 | Δ |
|---|---:|---:|---:|
| failure@5 | 8.33% (2/24) | **8.33% (2/24)** | **0** |
| R@1 | 70.83% | 70.83% | 0 |
| R@3 | 87.50% | 87.50% | 0 |
| R@5 | 91.67% | 91.67% | 0 |
| MRR | 0.7931 | 0.7931 | 0 |
| 空结果率 | 4.17% (1/24) | 4.17% (1/24) | 0 |
| 拒因分布 | vector-only 381 | vector-only 382 | +1 切片 |

- 旧值来源：`eval/reports/embedding_eval/t07.probe.en.on.json`（2026-10-16 21:25:26；e5-384；`semantic_floor=0.84`、`allow_semantic_only=true`）。
- 新值来源：`eval/reports/paraphrase_probe_en.after_chunk750.json`（2026-10-22 20:45:35）。
- 同样逐题一致；被拒切片 381→382。

### 2.4 Holdout B（57 题，检索指标分母为 40 道可答）

| 指标 | 旧：200 分块 | 新：750 分块 | Δ |
|---|---:|---:|---:|
| R@1 | 97.50% (39/40) | **97.50% (39/40)** | **0** |
| R@3 | 100.00% (40/40) | 100.00% (40/40) | 0 |
| R@5 | 100.00% (40/40) | 100.00% (40/40) | 0 |
| MRR | 0.9875 | 0.9875 | 0 |
| Wrong-doc | 0.00% | 0.00% | 0 |
| No-answer FP | 0.00% | 0.00% | 0 |
| False Association | 0.00% (0/8) | 0.00% (0/8) | 0 |
| Abstention | 100% | 100% | 0 |
| Citation 结构合法率 | 100.00% | 100.00% | 0 |
| Citation 逐题 overlap | 98.11% (52/53) | 98.11% (52/53) | 0 |
| Citation 逐条 overlap | 55.56% (65/117) | 55.56% (65/117) | 0 |
| Unnecessary Guard | 0.00% (0/44) | 0.00% (0/44) | 0 |
| Blockers | [] | [] | — |

- 旧值来源：`eval/reports/holdout_b.a_prime.json`（2026-10-19 08:21:46；e5-384；200 分块；与新版同为 guard 修复后的代码）。
- 新值来源：`eval/reports/holdout_b.after_chunk750.json`（2026-10-22 20:44:23）。
- **所有指标逐项完全相同**，包括 citation 的三个口径（125 refs / 53 题 / 117 条），说明这批 8 篇小文档上分块没有可测影响。

---

## 3. 与冻结发布基线的对照（不同口径，仅作“用户当下 vs 旧发布”参考）

这一组**不是**分块净效应：旧发布基线同时差在 ①嵌入模型（bge-small-zh-512 → e5-small-384）②分块（200→750）③语义闸门（floor 0.6→0.84）④guard 代码。列出来是为了防止把模型收益误记到分块头上。

### 3.1 DEV72

| 指标 | 旧（hash 512，200） | 新（e5-384，750） | Δ |
|---|---:|---:|---:|
| R@1 | 71.21% | 68.18% | **-3.03pp** |
| R@3 | 92.42% | 90.91% | -1.52pp |
| R@5 | 93.94% | 92.42% | -1.52pp |
| MRR | 0.8123 | 0.7939 | -0.0184 |

- 旧值来源：`eval/reports/baseline.dev72.current.json`（2026-10-12 21:22:06，`meta.embedder = local_hash(512)`，200 分块）。
- 另一份冻结值 `baseline.dev72.frozen.json`（2026-09-23，同为 hash）为 R@1 69.70% / R@3 92.42% / R@5 93.94% / MRR 0.8072，结论相同。
- **真实语义模型的 DEV72 指标低于历史哈希伪向量**（68.18% < 71.21%）。这说明旧 hash 数字不可作为“真实能力”引用，也说明该 dev 集上语义通道并没有把分数抬高。

### 3.2 中文改写探针（对照旧发布基线）

| 指标 | 旧（bge-512，200，floor 0.6） | 新（e5-384，750，floor 0.84） | Δ |
|---|---:|---:|---:|
| failure@5 | 40.62% (13/32) | **15.62% (5/32)** | **-25.00pp** |
| R@1 | 53.12% | 71.88% | +18.76pp |
| R@3 | 53.12% | 78.12% | +25.00pp |
| R@5 | 59.38% | 84.38% | +25.00pp |
| MRR | 0.5437 | 0.7625 | +0.2188 |
| 空结果率 | 25.00% (8/32) | 3.12% (1/32) | -21.88pp |
| 拒因分布 | vector-only 593 | vector-only 444 | -149 (-25.1%) |

- 旧值来源：`eval/reports/paraphrase_probe.json`（2026-10-16 20:54:06；bge-512；200 分块；`semantic_floor=0.6`）。
- 另一份 `paraphrase_probe.baseline_local_onnx.json`（2026-10-12，bge-512）更差：failure 46.88%、R@1 46.88%、空结果 31.25%。
- **这 25pp 的改善几乎全部来自嵌入模型升级**：同为 e5-384、floor 0.84 的 200 分块旧报告已经是 15.62%。分块贡献为 0；floor 从 0.6 收紧到 0.84 反而使 e5 的 failure 从 12.5% 回到 15.6%（`c1_e5_small.probe.zh.on.json` → `t07.probe.zh.on.json`）。

### 3.3 Holdout B（对照冻结文件）

| 指标 | 旧冻结 `holdout_b.json`（bge 时代，200） | 新（e5，750） | Δ |
|---|---:|---:|---:|
| R@1 / R@3 / R@5 | 97.50% / 100% / 100% | 97.50% / 100% / 100% | 0 |
| MRR | 0.9875 | 0.9875 | 0 |
| Wrong-doc | 0.00% | 0.00% | 0 |
| No-answer FP | 0.00% | 0.00% | 0 |
| False Association | 0.00% | 0.00% (0/8) | 0 |
| Citation 结构 / 逐题 / 逐条 | 100% / 98.11% / 55.56% | 100% / 98.11% / 55.56% | 0 |

- 旧值来源：`eval/reports/holdout_b.json`（2026-09-23 07:50:34，**冻结原件未动**，无 `embedder` 字段）。
- 冻结文件的 FA 也记为 0.0%，但它没有 `fa_fp` / `fa_denominator` 字段，算法不可逐位复核；`holdout_b.baseline_local_onnx.json`（bge-512，200 分块）则记录 FA=12.5%、Blockers=[A]。
- **12.5%→0% 不能归功于分块**：同为 e5-384、同为 200 分块，2026-10-19 08:05 的 `holdout_b.regress_check.json` 仍是 12.5%（Blocker A），同日 08:21 的 `holdout_b.a_prime.json` 已降到 0%。变化发生在两次同模型同分块的运行之间，属于 guard 代码修复，不是 750 分块。

---

## 4. 结论

### 4.1 升/降清单

**分块 200→750 的净效应（同模型、同闸门对照）**

- DEV72：R@1/R@3/R@5 各 **+1.52pp**，MRR **+0.0136**，coverage_group **+5.71pp**；仅相当于 1 个题位变化，**在噪声范围内**。
- 中文改写：failure@5 / R@1 / R@3 / R@5 / MRR / 空结果率 **全部不变**（32 题逐题一致）。
- 英文改写：同上，**全部不变**（24 题逐题一致）。
- Holdout B：检索、Wrong-doc、No-answer FP、False Association、citation 三口径 **全部不变**。
- 结构性原因：本轮语料子块数 49→48 / 52→52 / 40→39，分块参数几乎没改变索引结构（见 §1）。

**结论：在本轮全部评测语料上，分块 200→750 对召回没有可测影响（≈0）。**

**相对旧发布口径的变化（多因素，不可归因于分块）**

- 中文改写 failure@5 **40.62% → 15.62%**（-25pp），空结果 25%→3.1%，主因是嵌入模型 bge-512 → e5-384。
- DEV72 R@1 **71.21% → 68.18%**（-3.03pp），真实模型反而低于历史哈希伪向量；这提醒旧 hash 数字不能当能力基线。
- Holdout B 各项持平；若与 10-12 / 10-19 08:05 的 FA=12.5% 相比，降到 0% 来自 guard 修复，不是分块。
- 语义闸门 floor 0.6→0.84 使 e5 的中文改写 failure 从 12.5% 回升到 15.6%（-3.1pp 的代价）。

### 4.2 能不能对外宣称「R@1 = x%」？

**不建议宣称任何单一 R@1 数字作为产品指标。** 如果必须披露，只能这样限定：

> 「在自建 Holdout B（8 篇文档、40 道可答、top-5 父块、e5-small-384）上，R@1 = 97.5%（39/40），R@3/R@5 = 100%。该结果不代表真实资料库或长文档场景。」

理由：

1. **样本与语料太小**：Holdout B 只有 8 篇、每篇 0.8–1.7KB；DEV72 只有 6 篇 22KB；改写探针复用同一批 8 篇。它们测的是“文档级区分”，不是长文档内的块级定位。
2. **指标已饱和且对改动不敏感**：Holdout B 的 97.5% 在 bge-512、e5-384、200 分块、750 分块下**逐位相同**，没有区分度，不能用来证明任何优化（包括本次分块）有效。
3. **DEV72 低于历史哈希值**（68.18% < 71.21%），把它包装成“真实 R@1”会被旧报告直接反驳。
4. **改写探针的 84.4% R@5 与 15.6% failure@5 是更诚实的能力描述**，但它是 32 题人工改写集，也不适合外推为产品召回率。

### 4.3 若要真正量化分块，需要补的实验（本轮未做，未改代码）

1. 构造/截取**长正文语料**（单章节 > 1500 字，例如 253KB 资讯日报、DOCX 长报告），确保 200 与 750 产生显著不同的子块数（如 1976 → 数百）。
2. 用同一嵌入器（e5-384）、同一闸门，只切换 `CHILD_SIZE/OVERLAP/PARENT_SIZE` 跑 A/B；报告需同时给出子块数、平均块长、索引耗时、库体积。
3. 关注跨段证据题（答案跨两个子块）与 `citation` 行范围 overlap，而不只是 R@1——分块变大最可能先影响的是引用精度与长答案覆盖度。

---

## 5. 数据来源索引（逐项可追溯）

| 用途 | 文件 | 生成时间 | 口径 |
|---|---|---|---|
| DEV72 新 | `eval/reports/baseline.after_chunk750.json` | 2026-10-22 20:44 | e5-384 / 750 |
| DEV72 旧（同模型） | `eval/reports/embedding_eval/t07.dev72.json` | 2026-10-16 21:25 | e5-384 / 200 |
| DEV72 旧（hash） | `eval/reports/baseline.dev72.current.json` | 2026-10-12 21:22 | hash-512 / 200 |
| DEV72 冻结 | `eval/reports/baseline.dev72.frozen.json` | 2026-09-23 07:29 | hash-512 / 200 |
| Holdout B 新 | `eval/reports/holdout_b.after_chunk750.json` | 2026-10-22 20:44 | e5-384 / 750 |
| Holdout B 旧（同模型） | `eval/reports/holdout_b.a_prime.json` | 2026-10-19 08:21 | e5-384 / 200 |
| Holdout B 旧（guard 前） | `eval/reports/holdout_b.regress_check.json` | 2026-10-19 08:05 | e5-384 / 200 |
| Holdout B 冻结 | `eval/reports/holdout_b.json` | 2026-09-23 07:50 | 无 embedder 字段 / 200 |
| 中文改写 新 | `eval/reports/paraphrase_probe.after_chunk750.json` | 2026-10-22 20:44 | e5-384 / 750 / floor .84 |
| 中文改写 旧（同模型） | `eval/reports/embedding_eval/t07.probe.zh.on.json` | 2026-10-16 21:25 | e5-384 / 200 / floor .84 |
| 中文改写 旧（bge） | `eval/reports/paraphrase_probe.json` | 2026-10-16 20:54 | bge-512 / 200 / floor .6 |
| 英文改写 新 | `eval/reports/paraphrase_probe_en.after_chunk750.json` | 2026-10-22 20:45 | e5-384 / 750 / floor .84 |
| 英文改写 旧（同模型） | `eval/reports/embedding_eval/t07.probe.en.on.json` | 2026-10-16 21:25 | e5-384 / 200 / floor .84 |
| 英文改写 旧（另一次） | `eval/reports/embedding_eval/c1_e5_small.probe.en.off.json` | 2026-10-16 20:58 | e5-384 / 200 / 语义关 |

> 未提交（`git status`）：仅 `eval/run_eval.py` 被修改；四套 `*.after_chunk750.*` 为新增未跟踪文件；`holdout_b.json`、`baseline.dev72.frozen.json`、`paraphrase_probe.json` 等冻结文件内容与修改时间均未变。
