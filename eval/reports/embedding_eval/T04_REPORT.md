# T04 交付报告 —— 前缀协议 + 英文探针 + 规范 probe 报告重生成

> 作者：寇豆码 | 阶段：e5 前缀机制落地（产品码）。**门槛2/3 本轮不做**。
> 未动 chunker / `_is_grounded()` / Holdout B 冻结 gold / 既有 fixtures。

---

## (a) 前缀协议支持（默认零影响）

| 文件 | 改动（行） |
|---|---|
| `app/core/embedder.py` | • `EmbeddingResource` 新增可选字段 `query_prefix: str = ""` / `document_prefix: str = ""`；<br>• `load_embedding_resource()` 从 artifact.json 解析 `query_prefix`/`document_prefix`（缺省 → ""）；<br>• `signature_extra()`：**非空时**才纳入前缀键（空前缀 ⇒ 现役签名逐字段不变）；<br>• `BaseEmbedder` 加类属性 `query_prefix`/`document_prefix`（默认 ""）与 `embed_query()`/`embed_documents()`（**不改 `embed()` 签名**）；<br>• `OnnxEmbedder.__init__` 从 resource 读入前缀 |
| `app/core/search.py:629` | 查询路径：`qvec = embedder.embed_query(query)`（原 `embedder.embed([query])[0]`） |
| `app/core/indexer.py:139` | 文档路径：`_embed_in_batches` 内 `embedder.embed_documents(chunk)`（原 `embedder.embed(chunk)`） |

**调用点普查**（`grep '\.embed('`）：仅两处**生产**语义路径 —— `search.py:629`（query）与 `indexer.py:160`（document，经 `_embed_in_batches`）。其余 `embedder.py:337/372/635` 是 `probe_dim` / `probe` 的探测调用，**非** query/document 语义路径，保持原样。

**C1 前缀已写入** `vendor/cache/embedding_candidates/c1_e5_small/artifact.json`：`query_prefix="query: "`、`document_prefix="passage: "`；并在 `eval/embedding_eval/candidates/c1_e5_small.json`（provenance）中记录。

### (a) 零回归证据
1. **报告级逐字段不变**（现役空前缀）：
   ```
   probe.on / probe.off / holdout.on / holdout.off  prefix-before==after : True (全部)
   PREFIX ZERO-REGRESSION ALL EQUAL: True
   ```
2. **signature 不变**：现役 `signature_extra()` 键集仍为 `{artifact_sha256, tokenizer_sha256, precision}`（**不含**前缀键）⇒ 不会触发多余重建；非空前缀才出现 `query_prefix/document_prefix`。
3. **单测** `tests/test_prefix_protocol.py`：**10/10 PASS**（空前缀 ≡ embed；非空前缀按用途施加；资源默认空 + 解析；签名含/不含前缀）。已注册进 `tests/test_suite.py`。

---

## (b) 英文探针语料（新建）

- 语料：`eval/fixtures_paraphrase_en/`（**8 篇**英文文档，镜像 holdout_b 形态：bridge / warehouse / flood / clinic / lab / software / substation / subway）。
- 题集：`eval/paraphrase_en/queries_en.json`（**24 条**英文改写题，同构于中文探针：同义/口语/上位说法替换文档原词，`avoid_terms` 记录被替换的原词）。
- **自检：24/24 全部通过**双向断言（`validate_queries`，语言无关）—— 每个 `avoid_term` 逐字在 gold_doc 内、且不在 query 内。

跑通（现役 bge-small-zh 口径）：
```
run_probe.py --queries eval/paraphrase_en/queries_en.json --fixtures eval/fixtures_paraphrase_en
```
| 口径 | failure@5 | Recall@1 | 空结果率 |
|---|---:|---:|---:|
| 开闸门 `incumbent.probe_en.on` | **4.17%** | 75.0% | 0.0% |
| 关闸门 `incumbent.probe_en.off` | **8.33%** | 70.8% | 4.2% |

### ⚠ 重要发现（影响 G2 阈值，请主理人决策）
本英文探针**偏词法**、对「语义改善」区分度不足：

| | cases | avg_lexical_candidates | 零字面重合题数 | failure@5 |
|---|---:|---:|---:|---:|
| **中文探针** | 32 | 1.69 | **10/32 (31%)** | 40.6% |
| **英文探针** | 24 | **5.08** | **1/24 (4%)** | 4.17% |

- 根因：FTS5 对**英文按词切分**（连 `the/a/of` 等虚词都建索引）→ 英文 query 几乎必然与文档有字面重合（`route=fts`），字面路直接命中，语义路无发挥空间；而中文 FTS5 按整段 CJK run 切分 → 大量题零字面重合。
- 后果：现役**开闸门 failure@5 仅 4.17%** ⇒ **「相对现役改善 ≥5pp」的阈值在开闸门口径下不可达**（上限 4.17pp）。
- 建议（三选一，请拍板）：
  1. 英文 G2 改用**语义信号**：探针已内建 `vector_ceiling`（`gold_in_vec_candidates` / `gold_vec_sim_ge_floor`）与「零字面重合子集」—— 用它们对比现役 vs C1；
  2. 调整阈值（如按 `recall@1` 或关闸门口径 8.33% 设阈值）；
  3. 重新授权我按「零虚词重合」重写一版更硬的英文题集（可做，但题面会比较"口语/绕"，且数量受限）。
  当前 24 题**已交付且自检通过**，可直接用于 C1 对比；只提示判定口径需相应调整。

---

## (c) 规范 probe 报告重生成（消除口径漂移）

`eval/reports/paraphrase_probe.json`（原为 N=1 旧值 31.25%）已用**现役默认代码**（含 `semantic_min_corroboration=2`）重跑覆盖：

```
failure@5 = 40.6%   空结果率 = 25.0%   debug.semantic.min_corroboration = 2
```
与 PRD §1.2 现况一致。`holdout_b*` 冻结报告**未动**。

---

## git status 摘要

本次我改动：`app/core/embedder.py`、`app/core/search.py`(+2 行)、`app/core/indexer.py`(+3/-1)、`tests/test_suite.py`(+14)；重新生成 `eval/reports/paraphrase_probe.{json,md}`。
新增：`eval/embedding_eval/`、`eval/fixtures_paraphrase_en/`、`eval/paraphrase_en/`、`eval/reports/embedding_eval/`（含 T04 基线）、`tests/test_prefix_protocol.py`。
（`config.py/llm.py/relation_guard.py/app.js` 等 `M` 为本阶段之前的既有改动，非本次所动。）

## 无阻塞
门槛2/3（C1 质量/安全）等你下一轮指令。C1 前缀已在候选 artifact 中就绪。
