# Kavira · EmbeddingGemma 2 适用性评估报告

- 初版：2026-10-07（文献调研）
- **实测补录：2026-10-08（三项实测已完成，见 §5）**
- 评估对象：Google DeepMind `google/embeddinggemma-2`（2026-10-06 发布）
- 范围：**只做研究与实测，不改任何产品代码**
- 结论：从"建议暂缓"升级为**明确否决**——实测构成三重否决。

---

## 0. 一句话结论

实测结果比事先估算更糟：**速度慢 12–150 倍**（事先估 3–8 倍）、**中文质量略降**、**英文质量没有显著改善**，集成上还要求改 4 处协议。

在 V1.3 发布窗口内引入它，是用确定的性能灾难去换一个测不出来的收益。**明确否决。**

需要保留的是它暴露出的真问题：**我们的嵌入层是中文 only 的，而出海路线需要多语言**。这个需求成立，但应走更便宜的方案（§7-P2 方案 C）。

---

## 1. 决策速览表（★ = 本次实测数据）

| 维度 | 现状（bge-small-zh-v1.5 INT8） | EmbeddingGemma 2（q4） | 判定 |
|---|---|---|---|
| ★ 单条延迟（产品 2 线程） | **8.6 ms** | **304.4 ms** | ❌ **35.6×** |
| ★ 单条延迟（最佳 8 线程） | 4.3 ms | 102.9 ms | ❌ **12.0×** |
| ★ 批 32（产品 2 线程） | 11.1 ms/条 | 1674.9 ms/条 | ❌ **150.4×** |
| ★ 批 32（最佳 8 线程） | 23.4 ms/条 | 141.6 ms/条 | ❌ **12.7×** |
| ★ session 加载 | 0.16–0.27 s | **1.41–4.09 s** | ❌ 撞 PRD 冷启动 ≤3.5 s |
| ★ 中文 R@1 | **93.4 %** | 91.7 % | ❌ **−1.7 pp** |
| ★ 中文 MRR@10 | **95.8 %** | 94.9 % | ❌ **−1.0 pp** |
| ★ 英文 R@1 | 87.5 % | 86.2 % | ❌ −1.2 pp |
| ★ 英文 MRR@10 | 91.3 % | 91.2 % | ⚪ 持平 |
| ★ 英文主题 R@5 | 20.0 % | 40.0 % | ⚠ 仅 5 个 query，不可采信 |
| 模型体积 | 22.8 MB | 166 MB + 32 MB tokenizer | ❌ **×9** |
| 发布包体积 | 92.2 MB ZIP | 估算 ≈ 280–300 MB | ❌ |
| ★ 图输入 | 2 个 | **5 个**（3 个多模态占位为必需） | ❌ 需改代码 |
| ★ 图输出 | last_hidden_state | 另有 **`sentence_embedding`（已池化）** | ✅ 省掉自实现 pooling |
| 池化 | CLS | mean | ❌ 需改（`pooling` 字段现未被使用） |
| 任务前缀 | 无 | **强制** | ❌ 需拆 query/doc 两条路径 |
| 上下文 | 512 | 8192 | ❌ 完全浪费（切片 200 字 = 149 token） |
| 许可证 | MIT | Apache 2.0，**已取消门禁** | ✅ 商用友好 |
| ONNX 官方版 | 官方 | **Google 未提供** | ⚠ 仅社区版 |

---

## 2. EmbeddingGemma 2 是什么（文献事实）

来源：Google 官方博客、HF 模型卡、本次 HF API 实测拉取。

| 项 | 值 |
|---|---|
| 发布日期 / 架构 | 2026-10-06 / Gemma 4 |
| 参数 | 740M（文本 270M = 130M transformer + **140M embedding 表**；视觉 170M；音频 300M），可按需加载 |
| 输出维度 | 768，MRL 可截 512 / 256 / 128 |
| 上下文 | 8,192 token；图像 280 token/张、音频 25 token/秒 |
| ★ 池化 | `1_Pooling/config.json` 实测 **mean**，`include_prompt: true` |
| 训练数据 | 140+ 语言，2025-01 截止 |
| ★ 许可证 | **Apache 2.0，HF `gated=false`**（v1 是 `gated=manual` + Gemma 条款，需人工审批） |

**Google 自报基准（全精度 768d）**

| 基准 | EG2 | EG1 | 变化 |
|---|---|---|---|
| MTEB multilingual v2 | 61.36 | 61.15 | **+0.21** |
| MTEB Code v1 | 78.68 | 68.76 | **+9.92** |
| MMEB v2（多模态） | 59.01 | n/a | — |
| MAEB（音频） | 49.39 | n/a | — |

> 多语言文本几乎没进步，真正的跃迁在**代码**和**多模态**——这是本次判断的支点。

**体积实测（HF API 字节数）**

| 来源 | 文件 | 大小 |
|---|---|---|
| `google/embeddinggemma-2` | `model.safetensors` | 1,488.9 MB（bf16 全模态） |
| 同上 | `tokenizer.json` | 32.17 MB |
| 同上 | — | **无任何 `onnx/` 文件** |
| `onnx-community/...-ONNX` | `model_q4.onnx_data` | **174.03 MB**（落盘 166 MiB） |
| 同上 | `model_quantized.onnx_data` | 313.72 MB（落盘 299 MiB） |
| 同上 | `vision_encoder_q4` / `audio_encoder_q4` | 108.96 / 189.08 MB |
| `litert-community/...-text-270m` | `.litertlm` | 164.63 MB |

> ⚠ **ONNX 不在 Google 官方支持列表**。Google 的端侧形态是 `.litertlm`（LiteRT-LM / MediaPipe），**不是 onnxruntime**。我们测的 `onnx-community` 版是第三方转换产物（同为 Apache 2.0）。

---

## 3. 我们现在的嵌入层（对照基线）

读自 `resources/embedding/default.json` 与 `app/core/embedder.py`：

| 项 | 值 |
|---|---|
| id / 基座 | `bge-small-zh-v1.5-int8` / `BAAI/bge-small-zh-v1.5`（MIT） |
| 模型 + tokenizer | **22.8 MB** + 439 KB |
| 维度 / 最大长度 / 池化 | 512 / 512 / **CLS**（`last_hidden[:, 0, :]`） |
| 降级链 | `local_onnx` → `ollama` → `api` → 纯 FTS5 |
| 切片规格 | `CHILD_SIZE=200` 字符、`OVERLAP=30`、`PARENT_SIZE=800` |
| 非文本资源 | **PDF 已转文本入库**（pypdf/pdfminer）；**图片仅存 asset 不索引**；扫描件需 OCR，明确不支持 |

---

## 4. 实测环境

| 项 | 值 |
|---|---|
| CPU | Intel Family 6 Model 183，24 逻辑核（有 AVX2/VNNI） |
| 运行时 | `runtime/python-3.11-embed/python.exe`（3.11.9） |
| 版本 | onnxruntime **1.30.0** / numpy 2.4.6 / tokenizers 0.23.2 |
| 语料 | **`data/notes` 真实切片**，200 字符档（与 `CHILD_SIZE` 一致），不造假 |
| 线程 | 2（产品现行配置）与 8（对照） |
| 临时目录 | `temp/eg2bench/`（项目内，未落系统 TEMP） |

> ⚠ 测量期间系统负载有波动，单次结果噪声偏大（如基线 batch=32 在 8 线程下反而更慢）。**但 12× 到 150× 的量级差距远超噪声范围，结论稳健。**

---

## 5. 实测结果

### 5.1 速度（决定性）★

| 模型 | 线程 | 加载 s | 单条 ms | 倍率 | 批32 ms/条 | 倍率 |
|---|---|---|---|---|---|---|
| baseline bge-zh INT8 | **2** | 0.21 | **8.6** | 1.0x | **11.1** | 1.0x |
| baseline bge-zh INT8 | 8 | 0.16 | 4.3 | 0.5x | 23.4 | 2.1x |
| EG2 q4 | **2** | 1.41 | **304.4** | **35.6×** | **1674.9** | **150.4×** |
| EG2 q4 | 8 | 0.30 | 102.9 | 12.0× | 141.6 | 12.7× |
| EG2 INT8 | 2 | 0.19 | 515.2 | 60.2× | 910.4 | 81.8× |
| EG2 INT8 | 8 | 1.30 | 773.1 | 90.3× | 770.5 | 69.2× |

倍率以「baseline @2 线程」= 1.0x 为基准。

**独立复测**（另一轮，语料不同）：EG2 q4 @2 线程 batch=1 = **1425.9 ms** vs 基线 9.5 ms → **150×**。

要点：

1. **产品现行配置（2 线程）下单条慢 35.6×、批量慢 150×**；最乐观的 8 线程批量配置仍慢 **12.7×**。
2. **INT8 比 q4 更慢，不是更快**——299 MB 权重的内存带宽压力更大。"换 INT8 就好了"这条路是堵的。
3. 加线程有帮助（35.6× → 12.0×）但杯水车薪，且产品固定 2 线程是有意为之（避免与 UI 抢核）。
4. **session 加载 1.41–4.09 s**（基线 0.16–0.27 s）。4.09 s 那次已**超过 PRD 冷启动 ≤3.5 s 预算**，且这是 SSD 上的数字，U 盘上更糟。
5. **首次推理 5,590 ms**（预热开销）。

> 与事先估算（3–8×）对比：实测 **12–150×**。低估的原因是只算了参数量之比（11×），没算 INT4/INT8 在 ORT CPU 上的实际执行效率损失，以及 166–299 MB 权重的内存带宽压力。

### 5.2 图签名（影响集成成本）★

```
IN   input_ids          [B, T]
IN   attention_mask     [B, T]
IN   image_features     [n, 512]   ← 纯文本推理也必须喂，否则 ORT 报 missing input
IN   video_features     [n, 512]   ← 同上
IN   audio_features     [n, 512]   ← 同上
OUT  last_hidden_state  [B, T, 768]
OUT  sentence_embedding [B, 768]   ← 已池化 + 已归一化（absmax 0.357），可直接用
```

- tokenizer：vocab **262,144**；`<pad>`=0、`<bos>`=2、`<eos>`=1；encode 自动加 BOS/EOS。
- **200 字中文切片 = 149 token**（不是 200），8K 上下文对我们 100% 浪费。
- `last_hidden_state` absmax = **2564.7** —— 印证模型卡"FP16 会 NaN"的警告，跑 fp32 无碍。

两个集成结论：

- ✅ 好消息：池化**已 bake 进图**（`sentence_embedding`），不需要自己实现 mean pooling。
- ❌ 坏消息：图**强制 5 个输入**。我们 `OnnxEmbedder.embed()` 只按名字喂 `input_ids/attention_mask/token_type_ids`，遇到这三个必需输入会**直接抛异常**。

### 5.3 质量 A/B ★

**中文**（241 切片 / 18 文档 / 14 个主题级 query）

| 模型 | R@1 | R@5 | MRR@10 | 主题 R@5 |
|---|---|---|---|---|
| baseline 512d | **93.4 %** | 98.8 % | **95.8 %** | 14.3 % |
| EG2 q4 768d | 91.7 % | **99.2 %** | 94.9 % | 14.3 % |
| EG2 q4 512d | 91.3 % | 98.8 % | 94.5 % | 14.3 % |

**英文**（160 切片 / 5 文档 / 5 个主题级 query）

| 模型 | R@1 | R@5 | MRR@10 | 主题 R@5 |
|---|---|---|---|---|
| baseline 512d | **87.5 %** | 96.9 % | **91.3 %** | 20.0 % |
| EG2 q4 768d | 86.2 % | **97.5 %** | 91.2 % | **40.0 %** |
| EG2 q4 512d | 86.9 % | 96.9 % | 91.3 % | 40.0 % |

判读：

1. **中文略降**：R@1 −1.7 pp、MRR −1.0 pp。方向是负的。
2. **英文没有显著改善**：R@1 −1.2 pp、MRR −0.1 pp。唯一正收益是主题级 R@5 20% → 40%，但**只有 5 个 query，统计上不可采信**。
3. **评测方法本身的局限要如实说明**：方案 A（切片首句 → 该切片）主要测词汇重叠，两边都在 87–93% 的天花板上，区分度低；方案 B（主题级）区分度更高但样本太小。
4. 结论：**没有任何证据表明 EG2 在质量上值得换。**

---

## 6. 三重否决

| # | 否决项 | 证据 |
|---|---|---|
| 1 | **速度** | 产品配置下单条慢 35.6×、批量慢 150×；最乐观配置仍慢 12.7×（§5.1） |
| 2 | **质量** | 中文略降、英文无显著改善（§5.3） |
| 3 | **集成** | 图强制 5 输入 + 强制 prompt 前缀 + 现有 `pooling` 字段未生效 + 换模型必触发全量重建（§5.2、§7-P1） |

**任何一条单独成立就足以否决。三条同时成立，无需再权衡。**

---

## 7. 后续建议

| 优先级 | 动作 | 时机 |
|---|---|---|
| **P0** | **维持 bge-small-zh-v1.5 不动**。本报告不触发任何产品代码变更 | 现在 |
| **P1** | 修既有设计债：让 `EmbeddingResource.pooling` 字段真正生效——现在解析了但 `embed()` 硬编码 CLS。换任何非 CLS 模型都会**静默产出错误的向量空间** | V1.4，与换模型解耦 |
| **P1** | **"英文/多语言嵌入"作为独立需求立项**。需求成立（出海必需），但别绑死在 EG2 上 | V1.4 规划 |
| **P2** | 若要做多语言，优先评估**方案 C**：`multilingual-e5-small` INT8（118.1 MB + 17.1 MB tokenizer）等比 EG2 小一个数量级的多语言模型，走同一套实测流程（**先测速度，速度不过就不用测质量**） | V1.4 |
| **P2** | "扫描件/截图可搜"单独立项为 V2 feature。EG2 视觉编码器理论上能绕过 OCR，但那是完整 feature，不是换模型 | V2 |

---

## 8. 未验证项（请勿当既成事实引用）

1. **测量噪声**：本机负载波动明显（基线 batch=32 在 8 线程下反而更慢）。量级结论稳健，具体倍数请取区间而非点值。
2. **质量评测区分度不足**：方案 A 受词汇重叠主导（87–93% 天花板），方案 B 样本仅 5–14 个 query。**"英文无改善"受评测方法限制，不等于"EG2 英文一定不比基线好"**——只能说本次测不出收益。
3. **社区 ONNX 版的转换正确性**：`sentence_embedding` 输出看着合理（cos 抽查 0.8966），但**未与官方 safetensors 版本做过向量级对齐验证**。
4. **Google 全部基准分数均为自报**，无第三方独立复现。
5. 未测 LiteRT / MediaPipe 路径（Google 官方端侧方案），也**未测 GPU / NPU**。本结论仅适用于「Windows + onnxruntime CPU」这一我们实际所处的形态。
6. 未测视觉 / 音频编码器。

---

## 9. 复现方式

脚本保留在 `temp/eg2bench/`（48 KB，权重已清理）：

| 脚本 | 用途 |
|---|---|
| `probe.py` | 图 IO 签名、tokenizer 行为、加载耗时 |
| `quick.py` | 极简量级探针（逐档实时打印） |
| `final.py` | **主速度基准**：基线 / q4 / INT8 × 2/8 线程 × batch 1/32 |
| `bench_quality.py` | **质量 A/B**：中英文，R@1/R@5/MRR@10/主题 R@5，768d 与 512d 复用向量 |
| `bench_speed.py` | 含 RSS 与吞吐的完整版（较慢，跑一次 10 min+） |

复跑（权重需重新下载，约 465 MB）：

```bash
cd <repo>/temp/eg2bench
B=https://huggingface.co/onnx-community/embeddinggemma-2-ONNX/resolve/main
curl -sL -o onnx/model_q4.onnx      $B/onnx/model_q4.onnx
curl -sL -o onnx/model_q4.onnx_data $B/onnx/model_q4.onnx_data
curl -sL -o tokenizer.json          $B/tokenizer.json
<repo>/runtime/python-3.11-embed/python.exe -u final.py
<repo>/runtime/python-3.11-embed/python.exe -u bench_quality.py
```

---

## 10. 数据来源

- Google 官方博客（2026-10-06）与 Google Developers Blog（LiteRT 延迟 / 量化）
- Hugging Face API 实测：`google/embeddinggemma-2`、`onnx-community/embeddinggemma-2-ONNX`、`litert-community/*`、`Xenova/multilingual-e5-small`、`Xenova/bge-small-zh-v1.5`
- 原始配置文件：`1_Pooling/config.json`、`modules.json`、`config_sentence_transformers.json`
- **本次实测**：`temp/eg2bench/*.py`，语料来自 `data/notes/*.md` 与项目内英文文档
- 本项目代码：`resources/embedding/default.json`、`app/core/embedder.py`、`app/core/chunker.py`、`app/core/converters.py`
