# 贡献指南

[English](CONTRIBUTING_EN.md) | 中文

感谢你有兴趣改进 Kavira。这个项目的核心约束是**便携与零安装**——
所有改动都要经得起这一条的检验。

---

## 先跑起来

```bash
python -m pip install -r requirements.txt
python tests/test_suite.py          # 应输出「通过 N 项  失败 0 项」
python app/launcher.py --no-browser --port 28765
```

然后打开 <http://127.0.0.1:28765>。

Windows 用户如果想构建带嵌入式运行时的可分发版本：

```bash
python setup_runtime_windows.py            # 标准版（含 onnxruntime / tokenizers）
python scripts/fetch_embedding_resource.py # **另一步**：按契约取回模型字节（大文件不进 Git）
```

> 取件与构建是两个动作：`fetch` 可联网，`build_release.py --strict` **绝不联网**（缺件即失败）。
> 客户安装阶段 0 联网，运行时只 `Tokenizer.from_file(本地 tokenizer.json)`。

---

## 提交前必须通过

```bash
python tests/test_suite.py
```

CI 在 **5 路**上跑同一套测试，两条链路缺一不可：

- **4 路矩阵（开发环境兼容性）**：`Linux + Windows × Python 3.11 + 3.13`，用 runner 的系统 Python，
  依赖从 `requirements-release.lock` 安装（**含 `onnxruntime` / `tokenizers`**）。
- **1 路 Windows Portable（产品真实形态）**：`setup_runtime_windows.py` 构建自包含嵌入式运行时
  （**默认不加 `--with-onnx`，即发布形态不含 `onnxruntime`**），随后依次执行
  运行时体检 → **取件**（`scripts/fetch_embedding_resource.py`）→ 用嵌入式运行时跑同一套测试 →
  `scripts/build_release.py --strict` Stage Gate（`RUNTIME_LOCK_MISMATCH=0` / `LOCK_ENTRY_MISSING=0`）→
  启动冒烟。任一门禁不达即非零退出。

**任何平台的失败都必须让 workflow 真正失败** —— 不得为了「让徽章变绿」把某个 lane 改成非阻塞。

**触发策略**：完整 5 路只在**手动 `workflow_dispatch`** 与 **`v*` tag** 时触发；
普通 push 到 `main` **不触发**（GitHub 在本项目里是代码备份 + 版本回退，不是每次提交的发布验收）。
不要为了「让徽章动起来」把 `push.branches` 加回来。

embedding 相关用例需要模型字节（大文件不进 Git）：4 路矩阵 job **不取件**，相关用例记为 **SKIP**
（不把「本机没取件」伪装成产品缺陷）；Portable job **会先取件**，取件失败即该 job 失败。
「嵌入源不可用时的降级链」另由 `tests/test_embedding_a42b.py` 的 D / E 用例直接模拟验证，
不依赖真的缺依赖。

新增功能请一并补测试。测试素材尽量**由代码现场合成**（参见 `tests/test_converters.py`
里手写 xref 的 PDF、以及用 `zipfile` 现造的 OOXML），不要提交二进制样本文件。

---

## 硬性约束（改代码前请先读）

这些是踩过坑之后定下来的，回退它们会引入真实故障：

1. **零框架** —— 服务层是标准库 `http.server`。引入 Web 框架会直接把运行时体积打爆。
2. **前端零 CDN** —— `app/web/index.html` 是单文件原生 JS，唯一外部资源是
   `vendor/d3.v7.min.js`。它必须能在完全离线的 U 盘上工作。
3. **零盘符绑定** —— 所有路径由 `core/paths.py` 以 `__file__` 为锚点推导。
   U 盘在不同机器上的盘符会变，**绝对路径不得落盘**。
4. **真相源与索引分离** —— `data/notes/*.md` 是唯一资产；`data/cache.db` 必须能
   随时全量重建。任何设计都不得让 `cache.db` 变成必需品。
5. **降级优先于崩溃** —— 任何外部能力（嵌入源 / LLM / 抽取器 / 矢量扩展）都要有降级链，
   且控制台要能说明当前实际走了哪条路径。
6. **告警按「是否需要用户行动」分级** —— 系统自愈的过程信息进 `notes`（设置页运行详情），
   只有需要用户动手的才进 `warnings`（顶部告警条）。
7. **HTTP 响应头只能 latin-1** —— 中文文件名绝不可直接塞进 header，必须按 RFC 6266
   用 `filename*=UTF-8''…` 编码。
8. **依赖清单只有一处** —— 所有安装入口都读 `requirements.txt`，不要新增硬编码列表。

更完整的技术约束与踩坑记录见 [`docs/design-and-implementation.md`](docs/design-and-implementation.md)。

---

## 关于依赖

- 新增依赖前请先问：**它能不能用标准库替代？** 运行时体积是这个项目的核心指标之一。
- `docs/design-and-implementation.md` 记录了各项依赖的体积代价。
- `onnxruntime` / `tokenizers` 现已转为**标准运行依赖**（本地语义检索是 V1 标准能力），
  写在 `requirements.txt` 里并由 lock 精确锁定；新增依赖前仍请先算体积代价。
- **模型字节不进 Git**：只在 `resources/embedding/default.json` 里 pin
  `revision / sha256 / size`，由 `scripts/fetch_embedding_resource.py` 取回并逐文件校验。
- 注意判据是「**要不要模型**」而不是「支持格式多不多」：`.docx` / `.pptx` / `.xlsx` / `.epub`
  都能用标准库 `zipfile` + `xml.etree` 解析，零依赖。

---

## PR 要求

- 一个 PR 只做一件事；避免「顺手重构 + 新功能」混在一起。
- 提交信息请描述**为什么**这么改，而不只是改了哪里。
- 若改动了行为，请同步更新 `README.md` / `README_EN.md` 或 `docs/`。
- 新增文件请确认没有把 `data/`、`config.ini`、`runtime/` 加进版本控制。

## 报告问题

请附上：

- 操作系统与 Python 版本
- 复现步骤
- 控制台「设置 → 运行详情」里的实际降级路径（这通常直接指向根因）
- 相关日志片段

安全相关问题请勿开公开 issue，见 [`SECURITY.md`](SECURITY.md)。
