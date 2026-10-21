#!/usr/bin/env python3
r"""扫点内层运行器（**子进程**）：在**内存级覆写**下跑 probe / holdout 之一。

只被 `sweep_channel.py` 调用。**绝不改产品默认值**：所有覆写都在本进程内存里，
进程退出即消失（`config.update(persist=False)` + monkeypatch `search.SEMANTIC_FLOOR`）。

⚠ 只允许覆写**语义通道**参数（`SEMANTIC_FLOOR`）；**不碰** `_is_grounded()` 的
   `SEM_FLOOR`（闸门 rule B/C 的 floor）。

用法（内部）::

    python _sweep_runner.py --mode holdout|probe --embedding-dir <C1 dir> \
        --corrob N --floor F --out <abs base path>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_DIR = HERE.parent
REPO = EVAL_DIR.parent
sys.path.insert(0, str(REPO))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="_sweep_runner.py")
    ap.add_argument("--mode", choices=["holdout", "probe"], required=True)
    ap.add_argument("--embedding-dir", required=True)
    ap.add_argument("--corrob", type=int, default=None)
    ap.add_argument("--floor", type=float, default=None)
    ap.add_argument("--out", required=True, help="报告输出基名（绝对路径，不含扩展名）")
    args = ap.parse_args(argv)

    # ⚠ 必须早于 import 任何 app 模块（paths.py 模块级求值）
    os.environ["KAVIRA_EMBEDDING_DIR"] = str(args.embedding_dir)

    if args.mode == "probe":
        sys.path.insert(0, str(EVAL_DIR / "paraphrase"))
        import run_probe as H  # noqa: E402  —— import 即激活隔离库 + import app.core.paths
    else:
        sys.path.insert(0, str(EVAL_DIR))
        import holdout_b_run as H  # noqa: E402

    # —— 内存级覆写（仅语义通道参数）——
    from app.core import config, search as S  # noqa: E402

    if args.corrob is not None:
        config.update({"SEARCH": {"semantic_min_corroboration": str(args.corrob)}},
                      persist=False)
    if args.floor is not None:
        # 通道 floor 现为配置项（与 semantic_min_corroboration 同模式）；内存级覆写
        config.update({"SEARCH": {"semantic_floor": str(args.floor)}}, persist=False)
    # 保险：确认闸门 floor 未被触碰
    assert S.SEM_FLOOR == 0.6, "SEM_FLOOR（闸门 rule B/C）绝不允许被改动"

    if args.mode == "probe":
        return H.main(["--semantic", "on", "--force", "--no-hash-control", "--out", args.out])
    return H.main(["--semantic", "on", "--no-llm", "--force", "--out", args.out])


if __name__ == "__main__":
    raise SystemExit(main())
