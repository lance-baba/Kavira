"""资料目录（Library）迁移 —— 正确性测试（standalone，不接入 test_suite）。

为什么单独跑（与 ``test_license_offline.py`` 同策略）：迁移涉及整棵目录的复制、
marker 改写与 ``paths`` 热重绑，跑完之后**进程级状态变了**，混进全量套件容易
污染后续用例自己对 DATA_DIR 的假设。这里自带完整前置/后置清理，单独执行即可：

    runtime\\python-3.11-embed\\python.exe tests\\test_datadir_migrate.py

覆盖（每条断言都对应一次真实事故形态）：
  T1 预检红线   —— 同目录 / 嵌套 / App 内 / 非空目标 / 已有资料 一律拒
  T2 复制保真   —— 逐文件数量 + 字节一致，跳过项不进副本
  T3 校验有效性 —— 故意漏拷 / 截断 must 被查出（防止「校验形同虚设」）
  T4 成功迁移   —— 新目录完整、marker 正确、**旧目录一个字节都没少**
  T5 失败回滚   —— 复制中途抛错 → marker 复原、paths 拨回旧位置、源仍完好
  T6 解析优先级 —— 环境变量 > App 内 marker > 程序目录下 data
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tests.test_env as test_env  # noqa: E402  —— 必须在 import paths 之前激活

test_env.activate_test_library(prefix="usb-wiki-datadir-")
test_env.print_banner()

import app.core.context as ctx_mod  # noqa: E402
from app.core import datadir as dd, paths  # noqa: E402

PASS = FAIL = 0
TMP_ROOT = Path(tempfile.mkdtemp(prefix="datadir-case-"))


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}{(' —— ' + detail) if detail else ''}")


# ---------------------------------------------------------------------------
# 替身 AppContext：迁移会在搬运前后调用 shutdown()/boot()。
# 真实 ctx.boot() 要加载嵌入模型（数十秒），那是 context/embedder 自己的测试职责；
# 这里只关心「暂停写入 → 搬运 → 重新打开」的**编排是否正确**。
# ---------------------------------------------------------------------------
class FakeCtx:
    def __init__(self) -> None:
        self.shutdown_calls = 0
        self.boot_calls = 0

    def shutdown(self) -> dict:
        self.shutdown_calls += 1
        return {"syncer": True, "db": {}}

    def boot(self, *a, **kw) -> dict:
        self.boot_calls += 1
        return {}


def make_library(name: str, with_content: bool = True) -> Path:
    """造一个看起来像真的资料库：notes / originals / assets / cache.db。"""
    p = TMP_ROOT / name
    (p / "notes").mkdir(parents=True, exist_ok=True)
    (p / "originals").mkdir(parents=True, exist_ok=True)
    (p / "assets").mkdir(parents=True, exist_ok=True)
    (p / "metadata").mkdir(parents=True, exist_ok=True)
    (p / "snapshots").mkdir(parents=True, exist_ok=True)
    if with_content:
        (p / "notes" / "a.md").write_text("# 甲\n正文甲" * 40, encoding="utf-8")
        (p / "notes" / "b.md").write_text("# 乙\n正文乙" * 60, encoding="utf-8")
        (p / "notes" / "sub").mkdir(exist_ok=True)
        (p / "notes" / "sub" / "c.md").write_text("# 丙\n正文丙", encoding="utf-8")
        (p / "originals" / "doc.html").write_bytes(b"<html>" * 100)
        (p / "assets" / "logo.png").write_bytes(bytes(range(256)) * 4)
        (p / "cache.db").write_bytes(b"SQLITE-FAKE" * 50)
        # zip 只归档文件、不归档空目录 —— 分类数据要有内容才验证得到「被打包进去了」
        (p / "metadata" / "collections.json").write_text(
            '{"collections": [], "membership": []}', encoding="utf-8")
        (p / "library.json").write_text(
            '{"format": "usb-wiki-library", "data_version": 1}', encoding="utf-8")
        (p / "wiki-usb.log").write_text("旧日志，不该被搬走\n", encoding="utf-8")
        (p / "temp_chrome_profile").mkdir(exist_ok=True)
        (p / "temp_chrome_profile" / "junk").write_text("临时\n", encoding="utf-8")
    return p


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """给一棵目录按相对路径做 (size, mtime_ns) 快照 —— 判断「动没动过」。"""
    out: dict[str, tuple[int, int]] = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            full = Path(dirpath) / f
            rel = full.relative_to(root).as_posix()
            try:
                st = full.stat()
                out[rel] = (st.st_size, st.st_mtime_ns)
            except OSError:
                out[rel] = (-1, -1)
    return out


def set_current(lib: Path) -> None:
    os.environ["WIKIUSB_LIBRARY"] = str(lib)
    paths.rebind(lib)


def clear_marker() -> None:
    m = paths.BASE_DIR / paths.LIBRARY_MARKER_NAME
    if m.exists():
        m.unlink()


# ---------------------------------------------------------------------------
def t1_precheck() -> None:
    print("\nT1 预检红线")
    cur = make_library("cur")
    set_current(cur)

    r = dd.precheck(str(cur))
    check("拒绝：目标=当前资料目录", not r["ok"], str(r["errors"]))

    r = dd.precheck(str(cur / "notes"))
    check("拒绝：目标嵌在当前资料目录内", not r["ok"], str(r["errors"]))

    r = dd.precheck(str(paths.BASE_DIR / "somewhere"))
    check("拒绝：目标落在程序安装目录里", not r["ok"], str(r["errors"]))

    occupied = make_library("occupied-nonlibrary")
    (occupied / "random.txt").write_text("别的文件\n", encoding="utf-8")
    r = dd.precheck(str(occupied))
    check("拒绝：目标非空且不是资料库", not r["ok"], str(r["errors"]))

    another_lib = make_library("another-lib")
    r = dd.precheck(str(another_lib))
    check("拒绝：目标里已经有一份资料库", not r["ok"], str(r["errors"]))

    # 不存在的盘符：放过去会让用户看到「预检通过 → 迁移失败」这种自相矛盾
    r = dd.precheck("K:/definitely-not-a-drive/USB-WIKI-Data")
    check("拒绝：目标盘符不存在", not r["ok"], str(r["errors"]))

    empty_target = TMP_ROOT / "empty-ok"
    r = dd.precheck(str(empty_target))
    check("放行：不存在的空路径", r["ok"], str(r["errors"]))
    check("放行时回报源与目标", r.get("current") == str(cur)
          and r.get("path") == str(empty_target))

    r = dd.precheck("")
    check("拒绝：空输入", not r["ok"])


def t2_copy_fidelity() -> None:
    print("\nT2 复制保真")
    src = make_library("src")
    dst = TMP_ROOT / "dst"

    files, size = dd._copy_tree(src, dst)
    check("副本存在", dst.is_dir())
    check("跳过日志不入副本", not (dst / "wiki-usb.log").exists())
    check("跳过临时 Chrome profile 不入副本",
          not (dst / "temp_chrome_profile").exists())
    check("保留深层子目录", (dst / "notes" / "sub" / "c.md").is_file())
    check("保留 binary 原件/资产",
          (dst / "originals" / "doc.html").is_file()
          and (dst / "assets" / "logo.png").is_file())
    check("报告文件数 > 0 且字节数 > 0", files > 0 and size > 0, f"{files}/{size}")

    problems = dd._verify(src, dst)
    check("校验通过（数量+逐文件大小+抽样内容）", not problems, str(problems))


def t3_verify_catches() -> None:
    print("\nT3 校验能不能真的查出问题")
    src = make_library("vs")
    dst = TMP_ROOT / "vd"
    dd._copy_tree(src, dst)

    # 3a 漏拷
    (dst / "notes" / "b.md").unlink()
    problems = dd._verify(src, dst)
    check("查出漏拷文件", any("文件数量不一致" in p for p in problems), str(problems))

    # 3b 截断（同样大小必须不可能这里只验证 size 路径）
    dst2 = TMP_ROOT / "vd2"
    dd._copy_tree(src, dst2)
    (dst2 / "cache.db").write_bytes(b"SQLITE-FAKE")     # 明显变小
    problems = dd._verify(src, dst2)
    check("查出字节数不一致", any("总字节不一致" in p for p in problems), str(problems))

    # 3c 等长但内容被改 → 抽样比对兜住。
    #    必须按**字节**改：read_text/write_text 会把 \r\n 与 \n 互相归一，
    #    Windows 上一来一回字节数就变了，那测到的是「大小不一致」而不是内容比对。
    dst3 = TMP_ROOT / "vd3"
    dd._copy_tree(src, dst3)
    raw = (src / "notes" / "a.md").read_bytes()
    bad = raw[:100] + b"X" + raw[101:]          # 等长，只动前 256 字节内的一个字节
    assert len(bad) == len(raw)
    (dst3 / "notes" / "a.md").write_bytes(bad)
    problems = dd._verify(src, dst3)
    check("查出等长但内容被改", any("内容不一致" in p for p in problems), str(problems))


def t4_success() -> None:
    print("\nT4 完整迁移（最关键的断言：旧目录一个字节都不能少）")
    src = make_library("m-src")
    dst = TMP_ROOT / "m-dst"
    set_current(src)
    clear_marker()

    before = snapshot(src)
    notes_n = len(list((src / "notes").rglob("*.md")))

    fake = FakeCtx()
    old_ctx = ctx_mod._ctx
    ctx_mod._ctx = fake
    try:
        res = dd.migrate(str(dst))
    finally:
        ctx_mod._ctx = old_ctx

    check("迁移返回成功", bool(res.get("ok")), str(res))
    check("先停写、后重开", fake.shutdown_calls == 1 and fake.boot_calls >= 1,
          f"shutdown={fake.shutdown_calls} boot={fake.boot_calls}")
    check("新目录有全部 notes", len(list((dst / "notes").rglob("*.md"))) == notes_n,
          f"{len(list((dst / 'notes').rglob('*.md')))} vs {notes_n}")
    check("新目录有索引库", (dst / "cache.db").is_file())

    after = snapshot(src)
    check("**旧目录完好无损**（文件数一致）", len(after) == len(before),
          f"{len(after)} vs {len(before)}")
    check("**旧目录内容未被改动**（逐文件 size+mtime 一致）", after == before)
    check("旧目录未被删除", src.is_dir())

    marker = paths.BASE_DIR / paths.LIBRARY_MARKER_NAME
    check("marker 已写入并指向新目录",
          marker.is_file() and Path(marker.read_text(encoding="utf-8").strip()) == dst,
          marker.read_text(encoding="utf-8") if marker.exists() else "(无 marker)")
    check("paths 已热重绑到新目录", paths.DATA_DIR == dst.resolve(),
          f"{paths.DATA_DIR} vs {dst}")
    check("派生路径一并跟随", paths.NOTES_DIR == (dst / "notes")
          and paths.CACHE_DB == (dst / "cache.db"))
    check("结果里报告了 kept_source", res.get("kept_source") is True)


def t5_rollback() -> None:
    print("\nT5 复制中途失败 → 回滚且源完好")
    src = make_library("rb-src")
    dst = TMP_ROOT / "rb-dst"
    set_current(src)
    clear_marker()

    before = snapshot(src)
    fake = FakeCtx()
    old_ctx = ctx_mod._ctx
    ctx_mod._ctx = fake
    real_copy = dd._copy_tree
    try:
        dd._copy_tree = lambda s, d: (_ for _ in ()).throw(
            RuntimeError("模拟磁盘错误：复制中断"))          # type: ignore[assignment]
        res = dd.migrate(str(dst))
    finally:
        dd._copy_tree = real_copy                            # type: ignore[assignment]
        ctx_mod._ctx = old_ctx

    check("迁移返回失败", not res.get("ok"), str(res))
    check("显式声明已回滚", res.get("rolled_back") is True)
    check("paths 仍指回旧目录", paths.DATA_DIR == src.resolve(), str(paths.DATA_DIR))
    after = snapshot(src)
    check("源目录完好（size+mtime 一致）", after == before)
    check("半成品未变成正式目录", not dst.exists())


def t6_priority() -> None:
    print("\nT6 Library 位置解析优先级")
    src = make_library("pr-src")
    set_current(src)
    clear_marker()

    check("环境变量优先时 source=env", paths.library_source() == "env")

    marker_target = TMP_ROOT / "marker-lib"
    os.environ.pop("WIKIUSB_LIBRARY", None)
    paths.write_library_marker(marker_target)
    # write_library_marker 会顺手把值塞回环境变量（供同进程重启后读取），
    # 这里模拟「下次冷启动」的环境，重新推导一次。
    env_backup = os.environ.pop("WIKIUSB_LIBRARY", None)
    check("无环境变量、有 marker → source=marker", paths.library_source() == "marker",
          paths.library_source())

    os.environ.pop("WIKIUSB_LIBRARY", None)
    (paths.BASE_DIR / paths.LIBRARY_MARKER_NAME).unlink(missing_ok=True)
    check("都没有 → source=default", paths.library_source() == "default")

    if env_backup:
        os.environ["WIKIUSB_LIBRARY"] = env_backup
    paths.rebind(src)


def t7_export() -> None:
    print("\nT7 导出备份（U 盘坏了怎么办）")
    src = make_library("exp-src")
    # 塞进"不该进备份"的东西：索引、自动备份、日志
    (src / "cache.db.v17r20260101-010101.bak").write_bytes(b"BAK" * 50)
    (src / "wiki-usb.log").write_text("日志不该进备份\n", encoding="utf-8")
    set_current(src)

    # 一份带密钥的假配置（真实 config.ini 明文存 api_key，绝对不能跟着备份到处跑）
    fake_cfg = TMP_ROOT / "config.ini"
    fake_cfg.write_text(
        "[AI]\napi_key = sk-LIVE-SECRET-1234567890\napi_chat_model = deepseek-chat\n"
        "[SYSTEM]\nport = 28765\n", encoding="utf-8")
    old_cfg = paths.CONFIG_FILE
    paths.CONFIG_FILE = fake_cfg
    try:
        res = dd.export_package(dest_dir=TMP_ROOT / "out")
    finally:
        paths.CONFIG_FILE = old_cfg

    check("导出成功", bool(res.get("ok")), str(res))
    if not res.get("ok"):
        return
    zp = Path(res["path"])
    check("备份包不在资料目录内（否则下次会把自己也打包进去）",
          not str(zp).startswith(str(src)) and zp.parent != src, str(zp))

    import zipfile
    with zipfile.ZipFile(zp) as zf:
        names = zf.namelist()
        check("含笔记真相源", any(n.startswith("notes/") for n in names), str(names[:8]))
        check("含原始文件", any(n.startswith("originals/") for n in names))
        check("含图片素材", any(n.startswith("assets/") for n in names))
        check("含分类数据", any(n.startswith("metadata/") for n in names))
        check("**不含**检索索引 cache.db", "cache.db" not in names)
        check("**不含**索引备份 .bak", not any(n.endswith(".bak") for n in names),
              str([n for n in names if n.endswith(".bak")]))
        check("**不含**日志", not any(n.endswith(".log") for n in names))
        check("含恢复说明", dd.EXPORT_README_NAME in names)
        check("含配置", dd.EXPORT_CONFIG_NAME in names)
        check("**含格式清单 library.json**（少了它，恢复时会被当成旧格式资料库）",
              dd.EXPORT_MANIFEST_NAME in names, str(names[:10]))

        cfg_text = zf.read(dd.EXPORT_CONFIG_NAME).decode("utf-8", "replace")
        check("**配置里的密钥已被清空**", "sk-LIVE-SECRET" not in cfg_text, cfg_text[:80])
        check("非密钥配置保留", "deepseek-chat" in cfg_text and "28765" in cfg_text)

        readme = zf.read(dd.EXPORT_README_NAME).decode("utf-8", "replace")
        check("恢复说明讲了怎么恢复", "怎么恢复" in readme and "notes" in readme)

    zp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
def main() -> int:
    print("资料目录迁移 —— 正确性测试")
    print(f"用例根目录：{TMP_ROOT}")
    print(f"BASE_DIR   ：{paths.BASE_DIR}")
    try:
        t1_precheck()
        t2_copy_fidelity()
        t3_verify_catches()
        t4_success()
        t5_rollback()
        t6_priority()
        t7_export()
    finally:
        clear_marker()          # ⚠ 必须清掉：残留会让整个工作区改读别处的资料
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    print("\n" + "─" * 60)
    print(f"  PASS={PASS}  FAIL={FAIL}")
    print("─" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
