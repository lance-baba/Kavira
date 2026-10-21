# `eval/embedding_eval/` —— 嵌入模型评估基础设施

> 本目录属于 **评测**，不进发布包（`eval/` 从不被 `build_release.py` 拷贝）。
> 报告一律写 `eval/reports/embedding_eval/`（**新子目录**，绝不覆盖冻结报告
> `eval/reports/paraphrase_probe*.json`、`holdout_b*.json`）。
> 候选字节放 `vendor/cache/embedding_candidates/<id>/`（在 `.gitignore` 的 `vendor/cache/` 内，不进 Git）。

## 顺序铁律（PRD §5.3 / §10，不可跳步）

```
Step A  修 pooling（P0-0）+ 零回归验证      → pooling_regression.py / tests/test_pooling.py
Step B  核实候选 metadata → 门槛0           → inspect_artifact.py
Step C  门槛1 速度（不过关即否决，不测质量） → bench_speed.py
Step D  门槛2 质量 + 门槛3 安全（开/关各一次）→ run_probe.py / holdout_b_run.py
```

**pooling 修复必须先于任何非 CLS 候选评测**；**维度核实必须先于阈值调优**。

## 文件

| 文件 | 作用 |
|---|---|
| `candidates.json` | 候选清单：`id → embedding_dir / 期望维度 / pooling / license / 前缀` |
| `pooling_regression.py` | P0-0 零回归自证：`capture`（改动前拍 golden）/ `verify`（逐位比对）/ `selftest`（mean vs cls） |
| `inspect_artifact.py` | **独立** artifact 体检（不 import app）：size / SHA256 重算 / ORT IO / 真实维度 / pooling 交叉核对 → §12 provenance |
| `bench_speed.py` | 门槛1：2 线程测 单条 / batch=32 / 加载 / 全量重建 |
| `run_matrix.py` | 编排：逐候选 × 逐闸门起**子进程**并聚合 → `reports/embedding_eval/summary.json` |

## 环境（硬要求）

- 随包运行时：`runtime/python-3.11-embed/python.exe`；
- 跑 app 前先设 `KAVIRA_EMBEDDING_DIR=<repo>/vendor/cache/embedding`
  （`app/core/paths.py:125` 模块级求值，**必须 import 前**设）；`bench_speed.py` /
  `inspect_artifact.py` / `run_matrix.py` 会自动按候选设置；
- 全程 TEMP 隔离库（`tests.test_env`），**绝不碰 repo/data**。

## 常用命令

```bash
PY=runtime/python-3.11-embed/python.exe

# P0-0 零回归
$PY eval/embedding_eval/pooling_regression.py capture   # 改动前（默认拒绝覆盖）
$PY eval/embedding_eval/pooling_regression.py verify    # 改动后逐位比对（要求 100%）
$PY eval/embedding_eval/pooling_regression.py selftest  # mean != cls 且 mean 与 numpy 手算 < 1e-6

# 门槛0 + 门槛1（现役基线 / 候选）
$PY eval/embedding_eval/run_matrix.py --id incumbent
$PY eval/embedding_eval/run_matrix.py                   # 全候选
$PY eval/embedding_eval/run_matrix.py --id c1_e5_small --quality   # 过速度门槛后再测质量/安全

# 单项
$PY eval/embedding_eval/inspect_artifact.py --embedding-dir vendor/cache/embedding --id incumbent
$PY eval/embedding_eval/bench_speed.py --embedding-dir vendor/cache/embedding --id incumbent
```

## 门槛判定（PRD §4.3）

- **门槛1**：单条 / 批量 / 全量重建 **每项 ≤ 3× 现役**；session 加载 **≤ 1.0 s**。
  不过关 → **否决候选、不测质量**（F4 铁律）。
- **门槛2**：probe `failure@5 ≤25%`、空结果率 `≤12%`、零字面子集 `≤50%`。
- **门槛3**：Holdout B 开/关各一次 —— `Recall@1 ≥97.5%`、Wrong-doc `0%`、
  No-answer FP `0%`、FA `≤12.5% 且不新增`、citation 结构 `100%`、source-range overlap `≥98.1%`。

## 报告产物（`eval/reports/embedding_eval/`）

- `pooling_golden.cls.json` —— P0-0 golden（改动前基线，逐元素 float32 hex）
- `incumbent.speed.json` / `incumbent.{probe,holdout}.{on,off}.{json,md}` —— 现役基线
- `candidates/<id>.json` —— 门槛0 provenance
- `<id>.speed.json` —— 门槛1 速度
- `<id>.{probe,holdout}.{on,off}.*` —— 门槛2/3
- `summary.json` —— 矩阵聚合
