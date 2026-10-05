"""便携形态护栏测试（standalone）—— U 盘不用的时候：路径不写死、空间不失控。

    runtime\\python-3.11-embed\\python.exe tests\\test_portable_guard.py

三件事，每件都对应「用户把 U 盘拔走换台电脑」的真实场景：

  T1 路径解析只有**一个**答案 —— paths / library / diagnostics 三处必须**始终一致**，
     否则「同一份资料」在同一次运行里会算出两个目录（曾真实存在：library.py 自己实现了
     一份只认环境变量、不认 marker 的解析）。
  T2 不依赖启动方式 —— cwd 换到任何地方，关键路径都不能跟着变。
  T3 空间护栏 —— 日志有轮转上限；索引自动备份有保留上限，且**永远不碰手建备份**。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp(prefix="portable-guard-"))
PASS = FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}{(' —— ' + detail) if detail else ''}")


from app.core import library as lib_mod, paths  # noqa: E402
from app.core.migrations import (MAX_AUTO_BACKUPS, _AUTO_BK_RE,  # noqa: E402
                                 prune_cache_backups)


# ---------------------------------------------------------------------------
def t1_single_source() -> None:
    print("\nT1 资料目录解析必须只有一个答案")
    base = TMP / "AppBase"
    (base / "app" / "core").mkdir(parents=True, exist_ok=True)

    # 场景：装进 U 盘后，marker 是唯一落盘的线索（没有环境变量也能认）
    marked = TMP / "UdiskData"
    marked.mkdir(parents=True, exist_ok=True)

    saved_env = os.environ.pop("KAVIRA_LIBRARY", None)
    try:
        # 让 BASE_DIR 临时指向我们的假 App（markker 就写在它里面）
        real_base = paths.BASE_DIR
        paths.BASE_DIR = base
        try:
            paths.write_library_marker(marked, base=base)

            # ① paths 权威路径
            expect = marked.resolve()
            check("① paths 认得 marker", paths._detect_data_dir(base) == expect,
                  str(paths._detect_data_dir(base)))

            # ② library.detect_library_root 必须算出**同一个**答案
            got = lib_mod.detect_library_root(base)
            check("② library.detect_library_root 与 paths 一致", got == expect,
                  f"{got} vs {expect}")

            # ③ 环境变量仍在时，两者还是要一致（环境变量优先级更高）
            os.environ["KAVIRA_LIBRARY"] = str(marked)
            got_env = lib_mod.detect_library_root(base)
            check("③ 有环境变量时两处仍一致",
                  got_env == paths._detect_data_dir(base) == expect,
                  str(got_env))
        finally:
            paths.BASE_DIR = real_base
    finally:
        os.environ.pop("KAVIRA_LIBRARY", None)
        if saved_env:
            os.environ["KAVIRA_LIBRARY"] = saved_env


def t2_no_cwd_dependency() -> None:
    print("\nT2 关键路径不得依赖启动时的 cwd")
    from app.core import diagnostics

    here = Path(__file__).resolve()
    app_root = (here.parents[1] / "data").resolve()

    original = os.getcwd()
    try:
        os.chdir(tempfile.gettempdir())       # 换到一个完全无关的工作目录
        from_cfg = diagnostics._default_library_root()
    finally:
        os.chdir(original)

    check("diagnostics 的资料根不受 cwd 影响", from_cfg == app_root,
          f"{from_cfg} vs {app_root}")
    check("diagnostics 的资料根不在临时目录里",
          "Temp" not in str(from_cfg) and str(tempfile.gettempdir()) not in str(from_cfg),
          str(from_cfg))


def t3_space_guard() -> None:
    print("\nT3 空间护栏")

    # ---- 3a 日志：必须有轮转上限，且上限够小 ----
    from app.core.log_util import MAX_LOG_BYTES, MAX_LOG_BACKUPS
    budget = MAX_LOG_BYTES * (MAX_LOG_BACKUPS + 1)
    check("日志总占用有上限且 ≤ 2MB", budget <= 2 * 1024 * 1024,
          f"{MAX_LOG_BYTES} × {MAX_LOG_BACKUPS + 1} = {budget}")
    check("日志会轮转（backupCount ≥ 1）", MAX_LOG_BACKUPS >= 1)

    # ---- 3b 备份清理：手建备份绝不能被删 ----
    lib = TMP / "g3"
    (lib / "notes").mkdir(parents=True, exist_ok=True)
    db = lib / "cache.db"
    db.write_bytes(b"current" * 100)

    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(time.time() - 86400 * 30))
    auto_old = [
        lib / f"cache.db.v14r{stamp}.bak",
        lib / f"cache.db.v15r{stamp}.bak",
        lib / f"cache.db.v16r{stamp}.bak",
        lib / f"cache.db.v17r{stamp}.bak",
        lib / f"cache.db.v18r{stamp}.bak",
    ]
    for i, p in enumerate(auto_old):
        p.write_bytes(b"auto" * 100)
        os.utime(p, (time.time() - 86400 * (30 - i),) * 2)   # 越靠后越新

    # 这些是"用户的退路"，哪怕再旧也不许动
    manual = lib / "cache.db.pre-docx-fix.bak"
    manual.write_bytes(b"manual" * 100)
    renamed = lib / "cache.db.manual-safety.bak"
    renamed.write_bytes(b"manual2" * 100)
    customers = lib / "notes" / "keep.md"
    customers.write_text("真相源\n", encoding="utf-8")
    os.utime(manual, (time.time() - 86400 * 900,) * 2)        # 比所有自动备份都旧
    os.utime(renamed, (time.time() - 86400 * 900,) * 2)

    removed = prune_cache_backups(db)
    check(f"超额的自动备份被清理（保留最近 {MAX_AUTO_BACKUPS} 份）",
          len(removed) == len(auto_old) - MAX_AUTO_BACKUPS,
          f"清理 {len(removed)} / 共 {len(auto_old)}")
    check("手建备份（pre-docx-fix）**没被删**", manual.exists())
    check("手工改名备份**没被删**", renamed.exists())
    check("notes 真相源**没被删**", customers.exists())
    check("当前 cache.db **没被删**", db.exists())
    left = sorted(p.name for p in lib.glob("cache.db.v*.bak"))
    newest = sorted(p.name for p in auto_old[-MAX_AUTO_BACKUPS:])
    check(f"剩余正好 {MAX_AUTO_BACKUPS} 份，且是**最新**那几份",
          left == newest, f"{left} vs {newest}")

    # ---- 3c 数量没超就不许删 ----
    removed2 = prune_cache_backups(db)
    check("未超额时不删任何东西", removed2 == [], str(removed2))

    # ---- 3d 字节预算：份数够但**总量超预算**时也要删（GB 级索引的真护栏）----
    lib2 = TMP / "g3d"
    lib2.mkdir(parents=True, exist_ok=True)
    db2 = lib2 / "cache.db"
    db2.write_bytes(b"x" * 10)
    big = []
    for i in range(6):
        p = lib2 / f"cache.db.v20r2026010{i}-000000.bak"
        p.write_bytes(b"B" * 1024)                       # 每份 1KB
        os.utime(p, (time.time() - 86400 * (10 - i),) * 2)
        big.append(p)
    # keep 给足 10（份数不是约束），只靠 2.5KB 的字节预算裁剪
    prune_cache_backups(db2, keep=10, max_bytes=2500)
    left2 = sorted(p.name for p in lib2.glob("cache.db.v*.bak"))
    check("字节预算生效：总量被裁到预算内（≤2 份 × 1KB）", len(left2) <= 2, str(left2))
    check("字节裁剪同样保留最新的那几份",
          left2 == sorted(p.name for p in big[-2:]) or left2 == sorted(p.name for p in big[-1:]),
          str(left2))
    check("字节裁剪**至少留一份**退路（没有退路比多占空间更危险）", len(left2) >= 1)

    # ---- 3d 命名patterns边界：必须严格，避免误吃别人的文件 ----
    check("不匹配：手工命名", not _AUTO_BK_RE.match(".pre-docx-fix.bak"))
    check("不匹配：带中文后缀", not _AUTO_BK_RE.match(".张三备份.bak"))
    check("匹配：标准自动命名", bool(_AUTO_BK_RE.match(".v17r20260920-185807.bak")))


# ---------------------------------------------------------------------------
def main() -> int:
    print("便携形态护栏测试")
    print(f"临时目录：{TMP}")
    try:
        t1_single_source()
        t2_no_cwd_dependency()
        t3_space_guard()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print("\n" + "─" * 60)
    print(f"  PASS={PASS}  FAIL={FAIL}")
    print("─" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
