r"""Kavira 路径解析 —— 全部基于安装根目录的相对解析，杜绝绝对盘符绑定。

U 盘盘符在不同机器上会变化（E:\ F:\ G:\ ...），因此任何路径都不得落盘为绝对路径。
所有路径一律由本模块以 ``__file__`` 为锚点动态推导。
"""
from __future__ import annotations

import sys
import os
from pathlib import Path


def _detect_base_dir() -> Path:
    """定位 Kavira 安装根目录。

    冻结（PyInstaller/Nuitka）场景取可执行文件所在目录；源码场景取 app/core 的上两级。
    """
    if getattr(sys, "frozen", False):  # pragma: no cover - 冻结发行版专用分支
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


BASE_DIR: Path = _detect_base_dir()

#: Library 位置标记文件名 —— 与 ``scripts/install_windows.py`` 的 ``LIBRARY_MARKER``
#: **同名同位置同一约定**（都落在 BASE_DIR 下），安装器写、Core 读、设置页改写。
#: 此前 Core **只认环境变量**，导致「应用自己在设置页改资料目录」无处落盘 ——
#: 入口批处理不在（直接跑 launcher / 托盘拉起）时，Library 就悄悄退回 App 内的 data/。
LIBRARY_MARKER_NAME = "library_path.txt"

APP_DIR: Path = BASE_DIR / "app"
CORE_DIR: Path = APP_DIR / "core"
WEB_DIR: Path = APP_DIR / "web"
VENDOR_DIR: Path = WEB_DIR / "vendor"

def read_library_marker(base: Path | None = None) -> Path | None:
    """读取 BASE_DIR 下的 Library 位置标记。文件名/位置与安装器一致。

    安装态由安装器写入、设置页「更换资料目录」改写；解析不到（文件缺失 / 内容为空 /
    不是绝对路径）一律返回 None 由调用方回退，绝不让一个坏 marker 顶掉默认行为。
    """
    marker = (base or BASE_DIR) / LIBRARY_MARKER_NAME
    if not marker.is_file():
        return None
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        p = Path(text)
    except (ValueError, TypeError):
        return None
    return p if p.is_absolute() else None


def _detect_data_dir(base: Path) -> Path:
    """资料库根的解析：环境变量 → **App 内 marker** → 程序目录下 data/。

    ⚠ 这是 **App 与 Library 的边界**：环境变量 ``KAVIRA_LIBRARY`` 可把资料库
    指到任意位置（另一块盘 / 另一台电脑），程序目录即使整个删除，
    资料库仍可被新程序接管。默认值保持向后兼容（不强行搬目录）。

    为什么要在环境变量之后补一层 marker（2026-10-02）：
      入口批处理会把自己注入的环境变量传给子进程，所以「从 .bat 启动」一路没问题；
      但直接跑 ``launcher.py`` / 被其它进程拉起时环境变量不在，Library 会**静默退回
      App 内的 data/** —— 用户在设置页指定的目录形同失效（表现为资料「消失」）。
      marker 是**落盘的**真实约定，能让任何入口都找到同一个 Library。
    """
    env = (os.environ.get("KAVIRA_LIBRARY") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    marked = read_library_marker(base)
    if marked is not None:
        return marked.resolve()
    return (base / "data").resolve()


DATA_DIR: Path = _detect_data_dir(BASE_DIR)
NOTES_DIR: Path = DATA_DIR / "notes"
SNAPSHOT_DIR: Path = DATA_DIR / "snapshots"
# 原文件留存：导入的 PDF/Office 原件、剪藏的原始 HTML。
# 让笔记界面能用浏览器原生查看器还原「原版」观感，而 Markdown 只承担可检索的职责。
ORIGINALS_DIR: Path = DATA_DIR / "originals"
# 网页存档的**共享资源池**：剪藏时把 CSS/图片/字体等子资源抓下来存这里，
# 按 URL 哈希命名 → 同一站点的样式与 logo 被多篇文章共用时只存一份。
# 这样「原版预览」才能在不联网的前提下还原版式（Local-First / 零外发）。
ASSETS_DIR: Path = DATA_DIR / "assets"
# 用户组织层（Collections / 类目 / 成员关系 / 显示标题 / 回收站）——
# 属 **durable 用户状态**，绝不可只存于可重建的 cache.db。
# 见 docs/COLLECTIONS_ARCHITECTURE.md（§8 durable metadata / §9 方案 A sidecar）。
METADATA_DIR: Path = DATA_DIR / "metadata"
CACHE_DB: Path = DATA_DIR / "cache.db"
WAL_FILE: Path = DATA_DIR / "cache.db-wal"
SHM_FILE: Path = DATA_DIR / "cache.db-shm"
CHROME_PROFILE_DIR: Path = DATA_DIR / "temp_chrome_profile"

RUNTIME_DIR: Path = BASE_DIR / "runtime"

# --- 随包本地嵌入资源（属于 App，**不属于 Library**）---
# 可随程序重装 / 覆盖 / rollback / 从 U 盘恢复；Library 不受影响。
#
# ⚠ **不写死任何模型文件名**。资源由 `resources/embedding/artifact.json` 描述，
#   Core 只认识「id / artifact 路径 / tokenizer 路径 / 维度 / 精度 / hash」——
#   换 artifact 只需换资源目录里的字节与清单，不需要改代码
#   （此前 `ONNX_MODEL_FILE = .../bge-small-zh-q4.onnx` 把发布文件名焊死在 Core 里）。
EMBEDDING_ARTIFACT_NAME = "artifact.json"


def _detect_embedding_dir(base: Path) -> Path:
    """嵌入资源目录的解析。

    默认 ``<App>/resources/embedding``（安装态由安装器铺好）。
    ``KAVIRA_EMBEDDING_DIR`` 可覆盖：开发机指向 ``vendor/cache/embedding``，
    测试指向临时资源目录。**该目录缺失是正常状态**（未随包 / 未取件），
    由 embedder 报告 `local_onnx unavailable` 并按契约降级，不在这里偷偷创建。
    """
    env = (os.environ.get("KAVIRA_EMBEDDING_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (base / "resources" / "embedding").resolve()


EMBEDDING_DIR: Path = _detect_embedding_dir(BASE_DIR)
EMBEDDING_ARTIFACT_JSON: Path = EMBEDDING_DIR / EMBEDDING_ARTIFACT_NAME

def _detect_config_file(base: Path) -> Path:
    """配置文件路径；``KAVIRA_CONFIG`` 可覆盖（测试必须指向临时文件）。

    此前写死 ``BASE_DIR / "config.ini"`` 且**无任何覆盖手段**，导致
    ``tests/test_suite.py::test_no_absolute_paths``（注释声称"路径已隔离到临时目录"）
    实际 ``unlink`` 并重新生成的是**用户真实配置**（2026-10-24 踩到：974 字节的
    精简配置被 7KB 完整模板顶掉）。测试隔离必须能覆盖到这个路径。
    """
    env = (os.environ.get("KAVIRA_CONFIG") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return base / "config.ini"


CONFIG_FILE: Path = _detect_config_file(BASE_DIR)
LOG_FILE: Path = DATA_DIR / "kavira.log"

# 相对 data/ 的展示前缀（写入 Markdown frontmatter / API 返回值时统一使用）
NOTES_REL_PREFIX = "notes"


def ensure_dirs() -> None:
    """确保运行期必需的目录存在（含曾被清理过的 data 树）。

    刻意**不**创建 ``EMBEDDING_DIR``：嵌入资源是否存在是事实信息，
    空目录会让「未随包」与「随包但文件缺失」看起来一样。
    """
    for d in (DATA_DIR, NOTES_DIR, SNAPSHOT_DIR, ORIGINALS_DIR, ASSETS_DIR, METADATA_DIR, RUNTIME_DIR):
        d.mkdir(parents=True, exist_ok=True)


def rel_to_data(p: Path) -> str:
    """把绝对路径转换成相对 ``data/`` 的 POSIX 风格路径，用于跨机器持久化。

    ⚠ **绝不返回绝对路径** —— 那会让资料库无法整盘搬移（Data Contract 第 6 条）。
    Library 根被重定向时（如恢复测试 / KAVIRA_LIBRARY），文件不在 DATA_DIR 下，
    此前 ``except ValueError`` 直接返回 ``p.as_posix()``（绝对路径），
    导致 CI 的换目录测试失败。现按优先级退回相对形式：
    data/ 相对 → notes/ 相对 → 仅文件名。
    """
    p = p.resolve()
    try:
        return p.relative_to(DATA_DIR.resolve()).as_posix()
    except ValueError:
        pass
    try:
        return "notes/" + p.relative_to(NOTES_DIR.resolve()).as_posix()
    except ValueError:
        pass
    return "notes/" + p.name


def write_library_marker(target: Path, base: Path | None = None) -> Path:
    """把 Library 新位置写进 BASE_DIR 的 marker（原子写，供下次任意入口读取）。

    返回 marker 路径。失败不吞 —— 迁移流程里「marker 没写成」必须让上层知道，
    否则会出现「数据搬走了、下次启动还读旧目录」的错位。
    """
    marker = (base or BASE_DIR) / LIBRARY_MARKER_NAME
    text = str(Path(target).resolve())
    try:
        from .atomic_io import atomic_write_text  # noqa: PLC0415 - 避免循环导入

        atomic_write_text(marker, text + "\n")
    except Exception:  # noqa: BLE001 - atomic_io 不可用时退回普通写
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(text + "\n", encoding="utf-8")
    os.environ["KAVIRA_LIBRARY"] = text   # 同进程内的重启动作也要读到新位置
    return marker


def library_source() -> str:
    """当前 Library 位置由哪种方式决定（诊断 / 设置页展示用，不带盘符信息）。"""
    if (os.environ.get("KAVIRA_LIBRARY") or "").strip():
        return "env"
    if read_library_marker() is not None:
        return "marker"
    return "default"


def rebind(new_library: Path) -> Path:
    """把 Library 根整组重绑到 *new_library* —— **迁移切换后免重启**的关键。

    为什么可以这样做（前提已核实）：全仓除 ``diagnostics.py`` 一处**函数内**
    ``from .paths import DATA_DIR``（每次调用都重新取值）外，其余一律以
    ``paths.X`` 属性方式访问，因此改模块属性即可全局生效；
    若将来有人图省事写成**模块级** ``from .paths import DATA_DIR``，
    那份快照会停止跟随 —— 新增导入时请沿用 ``from ..core import paths`` 写法。

    ⚠ 只负责路径常量，**不做任何 IO、不建目录、不动数据库**；
      调用顺序必须是：搬数据 → 写 marker → rebind → ensure_dirs → 重开上下文。
    """
    global DATA_DIR, NOTES_DIR, SNAPSHOT_DIR, ORIGINALS_DIR, ASSETS_DIR
    global METADATA_DIR, CACHE_DB, WAL_FILE, SHM_FILE, CHROME_PROFILE_DIR, LOG_FILE
    DATA_DIR = Path(new_library).resolve()
    NOTES_DIR = DATA_DIR / "notes"
    SNAPSHOT_DIR = DATA_DIR / "snapshots"
    ORIGINALS_DIR = DATA_DIR / "originals"
    ASSETS_DIR = DATA_DIR / "assets"
    METADATA_DIR = DATA_DIR / "metadata"
    CACHE_DB = DATA_DIR / "cache.db"
    WAL_FILE = DATA_DIR / "cache.db-wal"
    SHM_FILE = DATA_DIR / "cache.db-shm"
    CHROME_PROFILE_DIR = DATA_DIR / "temp_chrome_profile"
    LOG_FILE = DATA_DIR / "kavira.log"
    return DATA_DIR


def abs_from_data(rel: str) -> Path:
    """把 ``notes/xxx.md`` 之类的相对路径还原成本机绝对路径。"""
    rel = rel.replace("\\", "/").lstrip("/")
    if rel.startswith("data/"):
        rel = rel[5:]
    return (DATA_DIR / rel).resolve()
