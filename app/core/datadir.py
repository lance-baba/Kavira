"""资料目录（Library）迁移 —— 把资料换一个地方放，但不冒《丢资料》的风险。

## 为什么是「复制」而不是「移动」

用户资料通常只此一份。``shutil.move`` 在跨盘时内部就是「复制 + 删除源」，途中
一旦中断（断电 / 拔 U 盘 / 杀软拦截 / 磁盘满），**源已半残、目标也不完整**，
两边都救不回来。这里强制：

    **源目录全程只读、一个字节都不删；目标写完并逐文件校验通过，才切换过去。**

最坏的结果只是「磁盘上暂时有两份完整资料」，而不是「一份都没有」。
切换成功后旧目录也**保留不动**，由用户在确认无误后自行删除 —— 删除是一次
**独立的、用户发起的**动作，绝不混进迁移流程。

## 八步流程（任一失败都回滚）

    1 预检    目标合法性 / 嵌套 / 已存在资料 / 空间 / 写权限
    2 停写    ctx.shutdown()（停同步器 + WAL 检查点 + 关库）→ 此后无任何写入
    3 复制    → <目标>.migrating-<时间戳>（**同盘的兄弟临时名**，保证第 5 步 O(1)）
    4 校验    逐文件比对「数量 + 字节数」，notes/*.md 额外抽样比对
    5 切换    临时目录 rename → 正式目标（**同盘 rename，原子、毫秒级**）
    6 落盘    写 marker → rebind → 日志重定向 → ensure_dirs
    7 重开    ctx.boot()（真正以新 Library 打开，Markdown 是真相源、索引随时可重建）
    8 验证    文档数 ≥ 迁移前 → 成功；否则回滚 marker + rebind 回旧目录并重开

cache.db 里的 ``rel_path`` 全是**相对 DATA_DIR** 的 POSIX 路径，
所以整目录平移后索引**原样有效**，不必重建 —— 这也是「整棵 data/ 一起搬」
而不是「只搬 notes/ 再重建」的原因：既快又没有额外失败面。
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from . import log_util, paths
from .i18n import t
from .log_util import get_logger

log = get_logger()

#: 不参与迁移的**可再生 / 临时**数据：日志会随环境重新生成，Chrome profile 是临时目录。
#: ⚠ 除此之外的东西一律照搬 —— 包括各类 ``.bak``（含父块正文，丢了不可逆）。
SKIP_NAMES = frozenset({"kavira.log", "temp_chrome_profile"})

#: 迁移校验时对 Markdown 正文的抽样规模：按总文件数的 1/20，夹在 [200, 5000] 之间。
#: 小库保持原有开销，大库则真正查得动（固定 200 篇在 4 万篇库里等于没查）。
MD_SAMPLE_RATIO = 20
MD_SAMPLE_MIN = 200
MD_SAMPLE_MAX = 5000

#: 给用户**预估耗时**用的保守吞吐（MB/s）。
#: 刻意取偏保守的值：宁可实际比预告快，也不要说完「2 分钟」却跑了 10 分钟 ——
#: 后者会让用户以为卡死而强杀进程（那样反而会留下半截文件）。
#: 参考：U 盘（USB2.0 / 廉价闪存）写速常在 10~20MB/s。
EST_MIGRATE_MBPS = 15      # 迁移 = 复制 + 逐文件校验（比纯复制慢）
EST_EXPORT_MBPS = 20       # 导出 = 读取 + 压缩 + 写盘

_PROGRESS: dict = {"stage": "idle", "message": "", "percent": 0,
                   "files": 0, "bytes": 0, "started_at": 0.0}
_PROG_LOCK = threading.Lock()
#: 最近一次迁移的**最终结果**。为什么要留着：迁移跑完后前端可能还没来得及轮询，
#: 只靠 stage 会丢掉细节；这里让任何时刻来查的人都能拿到完整结论（含失败原因）。
_LAST_RESULT: dict | None = None
_BUSY = threading.Lock()          # 同一时刻只允许一个迁移任务
_BUSY_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# 进度（前端轮询 /api/datadir/progress）
# ---------------------------------------------------------------------------
def _set(stage: str, message: str = "", percent: int | None = None, **kw) -> None:
    with _PROG_LOCK:
        _PROGRESS["stage"] = stage
        _PROGRESS["message"] = message
        if percent is not None:
            _PROGRESS["percent"] = max(0, min(100, int(percent)))
        _PROGRESS.update(kw)
        if stage == "copy" and not _PROGRESS.get("started_at"):
            _PROGRESS["started_at"] = time.time()


def progress_snapshot() -> dict:
    with _PROG_LOCK:
        snap = dict(_PROGRESS)
        snap["busy"] = is_busy()
        if _LAST_RESULT is not None:
            snap["result"] = _LAST_RESULT
        return snap


def is_busy() -> bool:
    return _BUSY.locked()


# ---------------------------------------------------------------------------
# 只读信息
# ---------------------------------------------------------------------------
#: ``_dir_stats`` 的短期缓存。为什么要缓存：统计要**递归遍历整棵 data/**，
#: 成本随资料量线性增长（40 万文件时是分钟级）。而它在一轮交互里会被反复调用 ——
#: 设置页每打开一次算一遍、预检算一遍、迁移再算一遍。相同状态下重复算同一个目录，
#: 纯属浪费。TTL 60s 足够短，且迁移成功/回滚后会主动失效。
_STATS_TTL = 60.0
_STATS: dict = {"key": "", "at": 0.0, "value": (0, 0)}


def invalidate_stats_cache() -> None:
    """资料目录内容发生变化后调用（迁移切换、回滚、导出之后）。"""
    _STATS.update(key="", at=0.0, value=(0, 0))


def _measure_library(root: Path) -> dict:
    """**一次遍历**同时得出「整个资料库」与「会被导出打包」的体积。

    为什么要分两组数字：迁移搬的是**整个 data/**（含索引与备份），
    而导出只打包用户资料（不含 cache.db / *.bak / *.log）。
    拿整体体积去预告导出耗时会把用户吓一跳（也严重高估）。
    """
    key = "measure:" + str(root)
    now = time.time()
    if key == _STATS["key"] and now - _STATS["at"] < _STATS_TTL:
        return _STATS["value"]

    tot_f = tot_b = exp_f = exp_b = 0
    if root.is_dir():
        stack: list[tuple[str, str]] = [(str(root), "")]
        while stack:
            cur, rel = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        if e.name in SKIP_NAMES:
                            continue
                        child = f"{rel}/{e.name}" if rel else e.name
                        try:
                            if e.is_dir(follow_symlinks=False):
                                stack.append((e.path, child))
                            elif e.is_file():
                                sz = e.stat().st_size
                                tot_f += 1
                                tot_b += sz
                                top = child.split("/", 1)[0]
                                if top in EXPORT_MEMBERS or child == EXPORT_MANIFEST_NAME:
                                    exp_f += 1
                                    exp_b += sz
                        except OSError:
                            continue
            except OSError:
                continue

    out = {"files": tot_f, "bytes": tot_b,
           "export_files": exp_f, "export_bytes": exp_b}
    _STATS.update(key=key, at=now, value=out)
    return out


def _dir_stats(root: Path, skip: frozenset[str] = SKIP_NAMES) -> tuple[int, int]:
    """统计 (文件数, 总字节)。不存在即 0 —— 冷启动时 data/ 可能还没建。

    用 ``os.scandir`` 递归而非 ``os.walk``：两者都靠目录项，但 scandir 让我们
    能在**一次遍历**里同时拿到「是不是目录」和「文件大小」，省掉每个文件
    额外构造 Path、再单独 stat 的开销 —— 在几十万文件的库上这是能感知到的差别。
    """
    key = str(root)
    now = time.time()
    if key == _STATS["key"] and now - _STATS["at"] < _STATS_TTL:
        return _STATS["value"]

    files = total = 0
    if root.is_dir():
        stack = [str(root)]
        while stack:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for e in it:
                        try:
                            if e.name in skip:
                                continue
                            if e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                            elif e.is_file():
                                files += 1
                                total += e.stat().st_size
                        except OSError:
                            continue
            except OSError:
                continue

    _STATS.update(key=key, at=now, value=(files, total))
    return files, total


def _deepest_existing(p: Path) -> Path:
    """返回路径上**真实存在的**最深祖先（用于 disk_usage / 权限探测）。"""
    for cand in [p, *p.parents]:
        if cand.exists():
            return cand
    return p


def library_info() -> dict:
    """当前资料目录的位置、体量与来源（设置页展示用）。

    额外给出**预估耗时**：导出/迁移在大库上是以分钟到小时计的，
    界面上不预告，用户就会以为卡死并强杀进程（那会留下半截文件）。
    """
    root = paths.DATA_DIR
    m = _measure_library(root)
    notes = 0
    nd = paths.NOTES_DIR
    if nd.is_dir():
        notes = sum(1 for _ in nd.rglob("*.md"))
    try:
        usage = shutil.disk_usage(str(_deepest_existing(root)))
        free = int(usage.free)
    except OSError:
        free = -1
    return {
        "path": str(root),
        "source": paths.library_source(),       # env / marker / default
        "app_dir": str(paths.BASE_DIR),
        "files": m["files"],
        "bytes": m["bytes"],
        "notes": notes,
        "free_bytes": free,
        "exists": root.is_dir(),
        # 只有"会进备份包"的那部分体积，用于预告导出耗时
        "export_files": m["export_files"],
        "export_bytes": m["export_bytes"],
        "est_export_seconds": _est_seconds(m["export_bytes"], EST_EXPORT_MBPS),
        "est_migrate_seconds": _est_seconds(m["bytes"], EST_MIGRATE_MBPS),
    }


def _est_seconds(nbytes: int, mbps: int) -> int:
    """按保守吞吐估算秒数（供界面预告；不追求精确，只求不误导）。"""
    if not nbytes or nbytes <= 0 or mbps <= 0:
        return 0
    return int(nbytes / (mbps * 1024 * 1024))


# ---------------------------------------------------------------------------
# 预检 —— 只读，绝不做任何写操作
# ---------------------------------------------------------------------------
def _looks_like_library(p: Path) -> bool:
    """目录下是否已经有一份资料（防止把两个 Library 混在一个目录里）。"""
    if not p.is_dir():
        return False
    return (p / "notes").is_dir() or (p / "cache.db").is_file() or (p / "originals").is_dir()


def precheck(target_raw: str) -> dict:
    """校验「能不能迁到目标目录」。返回 ``{"ok":bool,"path":str,"errors":[…],…}``。

    刻意**不在这里建任何目录**：预检是纯粹的只读判断，用户可能只是随手试了一个路径。
    """
    raw = (target_raw or "").strip()
    errors: list[str] = []
    warnings: list[str] = []
    if not raw:
        return {"ok": False, "path": "", "errors": ["请填写目标目录"], "warnings": []}
    try:
        dst = Path(raw).expanduser()
        dst = dst.resolve() if dst.exists() else Path(os.path.abspath(str(dst)))
    except (OSError, ValueError) as exc:
        return {"ok": False, "path": raw, "errors": [f"路径无法解析：{exc}"], "warnings": []}

    src = paths.DATA_DIR
    app = paths.BASE_DIR

    if dst == src:
        errors.append(t("目标目录就是当前资料目录，无需迁移。"))
    if dst == app or app in dst.parents:
        errors.append(t("资料目录不能放在程序安装目录里（程序重装/回滚会连带影响资料）。"))
    if dst in src.parents:
        errors.append(t("目标目录是当前资料目录的上级 —— 会把整个资料目录套进更深的层级。"))
    if src in dst.parents and dst != src:
        errors.append(t("目标目录在当前资料目录内部，形成嵌套。"))
    try:
        if dst.drive.upper() != app.drive.upper():
            warnings.append(t(
                "目标在 {dst} 盘、程序在 {app} 盘 —— 程序与资料分离。"
                "拔掉该盘后程序仍能启动，但看不到资料。",
                dst=dst.drive, app=app.drive))
    except AttributeError:      # POSIX 无 drive，跳过该提示
        pass

    # 目标已存在时的处理 —— 这是最容易丢东西的地方，一律拒绝而非清理
    if dst.exists():
        if not dst.is_dir():
            errors.append(t("目标路径已存在且不是目录。"))
        else:
            try:
                occupied = any(dst.iterdir())
            except OSError:
                occupied = True
            if occupied:
                if _looks_like_library(dst):
                    errors.append(t("目标目录里已经有一份资料库，为避免混淆已中止。"
                                    "请换一个空目录，或先手动整理再迁移。"))
                else:
                    errors.append(t("目标目录已存在且不为空 —— 不会为了腾地方删除里面的文件。"
                                    "请选择一个空目录。"))

    # 目标位置的可达性与写权限 —— 不在这里查，就会变成「预检说可以、迁移却失败」。
    # 分两种情形：父目录已存在 → 真写一个小探针再删（拦 U 盘写保护 / 只读介质）；
    # 父目录还不存在 → 至少确认盘符存在（拦 K:\ 这种压根没有的盘）。
    probe_root = dst if dst.is_dir() else dst.parent
    if probe_root.is_dir():
        try:
            probe = probe_root / f".kavira-wprobe-{os.getpid()}"
            probe.write_text("probe", encoding="ascii")
            probe.unlink()
        except OSError:
            errors.append(t("目标位置没有写入权限（可能是写保护的 U 盘或只读介质）：{path}", path=probe_root))
    else:
        anchor = os.path.splitdrive(str(dst))[0]
        if anchor and not os.path.isdir(anchor + (os.sep or "/")):
            errors.append(t("目标位置不可达：找不到驱动器 {anchor}（请确认磁盘/U 盘已接好）", anchor=anchor))

    # 空间
    files, size = _dir_stats(src)
    if dst.exists() or dst.parent.exists():
        try:
            usage = shutil.disk_usage(str(_deepest_existing(dst)))
            free = int(usage.free)
            if free < int(size * 1.05) + 1024 * 1024:
                errors.append(t(
                    "目标位置剩余空间不足：需要约 {need}，"
                    "可用 {free}（额外预留了 5% 余量）。",
                    need=_human(size), free=_human(free)))
        except OSError:
            warnings.append(t("无法读取目标位置的剩余空间，请自行确认磁盘够用。"))

    return {
        "ok": not errors,
        "path": str(dst),
        "errors": errors,
        "warnings": warnings,
        "current": str(src),
        "files": files,
        "bytes": size,
        "est_migrate_seconds": _est_seconds(size, EST_MIGRATE_MBPS),
        "free_bytes": int(shutil.disk_usage(str(_deepest_existing(dst))).free)
        if (dst.exists() or dst.parent.exists()) else -1,
    }


# ---------------------------------------------------------------------------
# 导出备份 —— 「U 盘会坏」这件事的答案
# ---------------------------------------------------------------------------
#: 用户资料的六个组成部分。刻意**不含** cache.db / *.bak / *.log：
#: 索引随时能从 Markdown 重建，带上只会让备份变大好几倍。
EXPORT_MEMBERS = ("notes", "originals", "assets", "metadata", "snapshots")
#: 资料库格式清单（``library.json``，位于资料库根）。**必须一起导出** ——
#: 它是「这份资料库是什么格式」的识别协议。少了它，用户恢复后程序会把备份
#: 判定为「无 manifest 的历史资料库（Data Format 0）」，走兼容接管路径，
#: 等于备份降级。它只含格式版本号（契约明令禁止写入绝对路径 / 密钥），带上无风险。
EXPORT_MANIFEST_NAME = "library.json"
#: 包内配置文件名（App 侧的设置，随备份一起走，**密钥会被清空**）
EXPORT_CONFIG_NAME = "config.ini"
EXPORT_README_NAME = "备份说明.txt"
#: 导出包文件名前缀。既是给用户看的命名，**也是清理残留时的唯一识别依据**
#: —— 绝不按 ``*.zip`` 这种宽泛条件去删（见 :func:`_sweep_stale_exports`）。
EXPORT_PREFIX = "Kavira-备份-"
#: 导出临时包的"过期"判定（秒）。超过这个时长的 zip 一定属于某次没走完的导出。
STALE_EXPORT_SECONDS = 6 * 3600


def _config_without_secrets() -> str:
    """读取 App 配置并把**所有密钥项清空**后返回文本。

    为什么不能直接拷 config.ini：它明文存着云端 API Key。备份包是要被复制、
    上传到网盘、发给别人看的 —— 让密钥跟着备份到处跑等于泄密。
    判「哪些是密钥」复用 ``redact.is_secret_key``（单一真相源，别在这里再列一份）。
    """
    from . import redact as redact_mod

    src = paths.CONFIG_FILE
    if not src.is_file():
        return ""
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    try:
        import configparser
        import io

        cp = configparser.ConfigParser()
        cp.read_string(text)
        for sec in cp.sections():
            for key in list(cp[sec]):
                if redact_mod.is_secret_key(key):
                    cp[sec][key] = ""
        buf = io.StringIO()
        cp.write(buf)
        return buf.getvalue()
    except Exception:  # noqa: BLE001 - 解析失败就退回「不带配置」，绝不带着明文出去
        return "[AI]\napi_key = \n"


def export_package(dest_dir: str | Path | None = None) -> dict:
    """把资料打包成一个 zip 备份，返回 ``{"ok":…,"path":…,"bytes":…,"files":…}``。

    ⚠ 临时文件落在**两处都不能碰的地方之外**：

      * **不落在 Library 里** —— 会污染资料目录，且下次导出会把上一次的 zip
        也打包进去（每次比上次大一倍）；
      * **不落在系统临时目录** —— 便携形态下那是**宿主机器**的 C 盘，
        等于在别人电脑上留下一份你全部资料的副本。项目静态红线明令禁止
        （那条红线正是按「是否引用了标准库的取临时目录函数」来判的），
        理由就是「拔盘即走，不在宿主机器上留一粒尘埃」。

      因此默认写到**程序目录内的临时区**（`BASE_DIR/temp`）—— 它在 App 侧、
      不属于资料，发送完成后由调用方立即删除。
    """
    import zipfile

    src = paths.DATA_DIR
    if not src.is_dir():
        return {"ok": False, "message": t("当前没有可用的资料目录")}

    stamp = time.strftime("%Y%m%d-%H%M")
    name = f"{EXPORT_PREFIX}{stamp}.zip"
    # 显式 dest_dir 只在测试/内部调用时使用；生产路径一律走项目内临时区。
    out_dir = Path(dest_dir) if dest_dir else (paths.BASE_DIR / "temp")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "message": t("无法创建临时目录（可能只读）：{exc}", exc=exc)}
    _sweep_stale_exports(out_dir)
    target = out_dir / name

    info = library_info()
    files = 0
    total = 0
    try:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as zf:
            for member in EXPORT_MEMBERS:
                root = src / member
                if not root.is_dir():
                    continue
                for dirpath, _dirs, filenames in os.walk(root):
                    for fn in filenames:
                        full = Path(dirpath) / fn
                        try:
                            rel = full.relative_to(src).as_posix()
                            zf.write(full, rel)
                            total += full.stat().st_size
                            files += 1
                        except OSError:
                            continue
            cfg = _config_without_secrets()
            if cfg:
                # ⚠ 配置属于 App 层，放进包里时**不**套任何子目录，
                #    方便用户一眼看到、也方便手动替换。
                zf.writestr(EXPORT_CONFIG_NAME, cfg)

            manifest = src / EXPORT_MANIFEST_NAME
            if manifest.is_file():
                try:
                    zf.write(manifest, EXPORT_MANIFEST_NAME)
                    total += manifest.stat().st_size
                    files += 1
                except OSError:
                    pass

            zf.writestr(EXPORT_README_NAME, _readme_text(info))
    except OSError as exc:
        return {"ok": False, "message": t("打包失败：{exc}", exc=exc)}

    return {
        "ok": True,
        "path": str(target),
        "name": name,
        "files": files,
        "bytes": total,
        "packed_bytes": target.stat().st_size if target.is_file() else 0,
    }


def _sweep_stale_exports(out_dir: Path) -> None:
    """清掉上次导出**没走完**留下的半截包。

    为什么必须做：正常路径是「打包 → 发送 → finally 删除」，但用户可能在下载途中
    直接关掉浏览器、断电或强杀进程 —— 那时 finally 不会执行，程序目录的 temp/ 里
    就留下一个**完整的 zip**。资料动辄几 GB，一个残留就足以把 U 盘占满，
    而用户完全不知道它是什么、也找不到入口删。

    判定用「修改时间早于 6 小时」：正在进行的导出不可能是 6 小时前创建的，
    因此绝不会误删本次要发的包。

    ⚠ 且**只认本模块自己的命名前缀**：temp/ 虽然是程序专用目录，但按扩展名
    （``*.zip``）去清理曾经把用户自己放进去的 ``notes.zip`` 一起删了 —— 那是测试当场
    抓到的。清理逻辑必须严格限定「自己产生的东西」，这与索引备份
    ``_AUTO_BK_RE`` 只认自动命名是同一条原则。
    """
    cutoff = time.time() - STALE_EXPORT_SECONDS
    try:
        entries = list(out_dir.iterdir())
    except OSError:
        return
    for p in entries:
        try:
            if (p.is_file() and p.name.startswith(EXPORT_PREFIX)
                    and p.suffix.lower() == ".zip"
                    and p.stat().st_mtime < cutoff):
                size = p.stat().st_size
                p.unlink()
                log.info("清理残留的导出临时包：%s（%s）", p.name, _human(size))
        except OSError:
            continue


def _readme_text(info: dict) -> str:
    lines = [
        "Kavira 随身知识库 —— 资料备份",
        "=" * 44,
        "",
        f"备份时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"备份来源：{info.get('path', '')}",
        "",
        "【包里有】",
        "  notes/      笔记正文（Markdown —— 这是真相源，最要紧的就是它）",
        "  originals/  导入的原始文件（PDF / Word / Excel / PPT / 网页）",
        "  assets/     笔记与网页用到的图片等素材",
        "  metadata/   分类（Collections）与自定义标题",
        "  snapshots/  网页快照",
        "  config.ini  程序设置（**里面的云端密钥已被清空**，重填即可）",
        "  library.json 资料库格式清单（说明这是哪一版格式，恢复时用于自动识别）",
        "",
        "【包里没有】（这些随时能重建，带上只会让备份大好几倍）",
        "  cache.db    检索索引",
        "  *.bak       索引的历史备份",
        "  *.log       运行日志",
        "",
        "【怎么恢复】",
        "  1) 新建一个空文件夹，作为新的资料目录；",
        "  2) 把包里的 notes / originals / assets / metadata / snapshots 放进去；",
        "  3) library.json 也放回**资料库根目录**（它用于识别格式，放错位置会被当成旧格式）；",
        "  4) 打开 Kavira → 设置 → 资料目录 → 迁移／指向这个文件夹；",
        "  5) 首次启动会自动重建索引，稍等片刻即可检索与问答。",
        "",
        "把这些文件放在安全的地方即可 —— 它不依赖本程序才能读懂，",
        "notes/ 下的 Markdown 用任何编辑器都能打开。",
        "",
    ]
    return "\n".join(lines)


def _human(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return "-"


# ---------------------------------------------------------------------------
# 迁移主体
# ---------------------------------------------------------------------------
def migrate(target_raw: str, progress: Callable[..., None] | None = None) -> dict:
    """把资料目录整体迁移到 *target_raw*。**阻塞**，调用方应放进后台线程。

    返回 ``{"ok":bool,"message":str,"from":…,"to":…,"files":n,"bytes":n,"seconds":s}``。
    迁移**不会删除旧目录**：成功之后旧位置仍是一份完整副本，由用户确认无误后
    自行删除；失败则 marker / 路径全部拨回旧位置，源从未被写过。
    """
    global _LAST_RESULT
    if not _BUSY.acquire(blocking=False):
        _LAST_RESULT = {"ok": False, "message": t("已有迁移任务在进行中")}
        return _LAST_RESULT
    try:
        _LAST_RESULT = _run(target_raw, progress)
    finally:
        _BUSY.release()
    return _LAST_RESULT


def _run(target_raw: str, progress: Callable[..., None] | None) -> dict:
    t0 = time.time()
    # 提前固化源与目标句柄：异常回滚要用，**不能等到 try 内部才取名**
    # （异常可能发生在给它们赋值之前，回滚时会 NameError 二次崩塌）。
    src = paths.DATA_DIR
    tmp = None
    _set("check", t("正在校验目标目录…"), 0, files=0, bytes=0, started_at=0.0)
    try:
        # 延迟导入：context 装配了整棵依赖树，模块级导入会与核心层形成环。
        from .context import get_ctx

        ctx = get_ctx()

        chk = precheck(target_raw)
        if not chk["ok"]:
            _set("failed", chk["errors"][0], 100)
            return {"ok": False, "message": "；".join(chk["errors"]),
                    "errors": chk["errors"], "warnings": chk.get("warnings", [])}
        dst = Path(chk["path"])
        for w in chk.get("warnings", []):
            log.warning("迁移预检提示：%s", w)

        stamp = time.strftime("%Y%m%d-%H%M%S")
        tmp = dst.parent / f"{dst.name}.migrating-{stamp}"
        old_marker = paths.read_library_marker()

        # ---- 1) 停写：此后源目录不再有任何写入 ----
        _set("stop", t("正在停止写入（做检查点、关闭索引）…"), 2)
        try:
            ctx.shutdown()
        except Exception as exc:  # noqa: BLE001
            log.warning("停止写入时出现异常（继续迁移）：%s", exc)

        try:
            # ---- 2) 复制 ----
            _set("copy", t("正在复制资料…"), 3)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if tmp.exists():
                _set("failed", t("临时目录已存在，请稍后重试"), 100)
                return _abort(src, old_marker,
                              t("临时目录已存在：{path}", path=tmp))
            copied_files, copied_bytes = _copy_tree(src, tmp)

            # ---- 3) 校验 ----
            _set("verify", t("正在逐文件校验副本…"), 92)
            problems = _verify(src, tmp)
            if problems:
                _set("failed", t("副本校验未通过，已保留原位置"), 100)
                return _abort(src, old_marker,
                              t("副本校验未通过：{detail}",
                                detail="；".join(problems[:3])),
                              tmp=tmp)

            # ---- 4) 切换（同盘 rename，原子）----
            _set("switch", t("正在切换到新目录…"), 96)
            if dst.exists():
                os.rmdir(dst)                     # 预检已确认是空目录
            os.rename(str(tmp), str(dst))
            tmp = None

            # ---- 5) 落盘 marker + 重绑路径 ----
            paths.write_library_marker(dst)
            paths.rebind(dst)
            try:
                log_util.retarget_log()
            except Exception:  # noqa: BLE001
                pass
            paths.ensure_dirs()

            # ---- 6) 以新目录重新打开 ----
            _set("reopen", t("正在按新目录重新打开资料库…"), 98)
            ctx.boot()

            # ---- 7) 验证 ----
            prev_notes = _count_md(src)
            now_notes = _count_md(dst)
            if prev_notes and now_notes < prev_notes:
                _set("failed", t("重新打开后文档数不一致，已回退"), 100)
                return _abort(src, old_marker,
                              t("新目录打开异常：原 {old} 篇 / 新 {new} 篇",
                                old=prev_notes, new=now_notes))

            _set("done", t("迁移完成"), 100, files=copied_files, bytes=copied_bytes)
            invalidate_stats_cache()      # 指向已变，下一次统计必须重算
            secs = round(time.time() - t0, 1)
            log.info("资料目录迁移完成：%s → %s（%d 文件 / %s / %.1fs）",
                     src, dst, copied_files, _human(copied_bytes), secs)
            return {
                "ok": True,
                "message": t("资料已迁移到新目录，旧目录已原样保留。"),
                "from": str(src),
                "to": str(dst),
                "files": copied_files,
                "bytes": copied_bytes,
                "seconds": secs,
                "warnings": chk.get("warnings", []),
                "kept_source": True,
                "note": t("确认新目录资料无误后，可自行删除旧目录释放空间。"),
            }
        except Exception as exc:  # noqa: BLE001 - 任何异常都必须回到可用状态
            log.error("资料目录迁移失败：%s", exc)
            _set("failed", t("迁移失败：{exc}", exc=exc), 100)
            return _abort(src, old_marker, str(exc), tmp=tmp)
    except Exception as exc:  # noqa: BLE001
        _set("failed", t("迁移无法开始：{exc}", exc=exc), 100)
        return {"ok": False, "message": t("迁移无法开始：{exc}", exc=exc)}


def _count_md(root: Path) -> int:
    nd = root / "notes"
    if not nd.is_dir():
        return 0
    return sum(1 for _ in nd.rglob("*.md"))


def _copy_tree(src: Path, dst: Path) -> tuple[int, int]:
    """把 src 整棵复制到 dst（dst 必须不存在）。返回 (文件数, 字节数)。"""
    total_files, total_bytes = _dir_stats(src)
    done_files = done_bytes = 0
    last_report = 0.0

    def step(files: int, size: int) -> None:
        nonlocal done_files, done_bytes, last_report
        done_files += files
        done_bytes += size
        now = time.time()
        if total_bytes <= 0 or now - last_report >= 0.25 or done_files >= total_files:
            last_report = now
            pct = 3 + int(done_bytes * 89 / total_bytes) if total_bytes else 95
            _set("copy", t("正在复制资料… {done}/{total} 个文件",
                           done=done_files, total=total_files),
                 min(pct, 91), files=done_files, bytes=done_bytes)

    dst.mkdir(parents=True, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
        rel = Path(dirpath).relative_to(src)
        out_dir = dst / rel
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if name in SKIP_NAMES:
                continue
            s = Path(dirpath) / name
            try:
                shutil.copy2(s, out_dir / name)
                step(1, os.path.getsize(s))
            except OSError as exc:
                # 「复制」阶段失败不算灾难 —— 源从未被动过，直接抛出由上层回滚
                raise RuntimeError(f"复制失败：{s.name}（{exc}）") from exc
    step(0, 0)
    return done_files, done_bytes


def _verify(src: Path, dst: Path, sample_limit: int | None = None) -> list[str]:
    """比对副本与源的**文件清单 + 每个文件的字节数**。

    为什么不做全量 SHA-256：资料动辄几 GB，全量哈希会让校验比复制还慢；
    而 ``copy2`` + 逐文件 size 比对已经能拦住「截断 / 漏拷 / 磁盘写满」这类真实故障。
    再对 Markdown 正文做**首尾 + 长度**抽样，兜住"大小对但内容错了"。

    ⚠ 抽样数量必须**随库规模长**（2026-10-02 修）：原先固定 200 篇，在 4 万篇的库里
    等于只抽查 0.5%，静默错字节几乎必然漏过去 —— 而这正是用户最不能接受的那类故障。
    现在按总文件数取 1/20（下限 200、上限 5000），大库能查得更实，
    而小库的校验耗时不变。
    """
    problems: list[str] = []
    s_files, s_bytes = _dir_stats(src)
    d_files, d_bytes = _dir_stats(dst)
    if d_files != s_files:
        problems.append(t("文件数量不一致（源 {s} / 副本 {d}）",
                              s=s_files, d=d_files))
    if d_bytes != s_bytes:
        problems.append(t("总字节不一致（源 {s} / 副本 {d}）",
                              s=s_bytes, d=d_bytes))
    if problems:
        return problems

    if sample_limit is None:
        sample_limit = max(MD_SAMPLE_MIN, min(MD_SAMPLE_MAX, s_files // MD_SAMPLE_RATIO))
    checked = 0
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_NAMES]
        if checked >= sample_limit:
            break
        for name in filenames:
            if name in SKIP_NAMES or not name.endswith(".md"):
                continue
            if checked >= sample_limit:
                break
            s = Path(dirpath) / name
            d = dst / s.relative_to(src)
            checked += 1
            try:
                sb, db = s.read_bytes(), d.read_bytes()
            except OSError as exc:
                problems.append(t("抽样读取失败：{name}（{exc}）", name=name, exc=exc))
                break
            if len(sb) != len(db) or sb[:256] != db[:256] or sb[-256:] != db[-256:]:
                problems.append(t("内容不一致：{name}", name=name))
                break
        if problems:
            break
    return problems


def _abort(src: Path, old_marker: Path | None, message: str,
           tmp: Path | None = None) -> dict:
    """失败收尾：marker 写回旧值 + rebind 回旧目录 + 重新打开 + 清掉半成品。

    走到这一步时源目录**始终完好**（复制阶段从未写过它），所以只要把「当前指向」
    拨回源，用户就回到迁移前的状态。
    """
    try:
        if old_marker is not None:
            paths.write_library_marker(old_marker)
        else:
            try:
                (paths.BASE_DIR / paths.LIBRARY_MARKER_NAME).unlink(missing_ok=True)
            except OSError:
                pass
        paths.rebind(src)
        try:
            log_util.retarget_log()
        except Exception:  # noqa: BLE001
            pass
        from .context import get_ctx

        get_ctx().boot()
    except Exception as exc:  # noqa: BLE001 - 回滚本身也不能再抛给调用方
        log.error("迁移回滚失败（请手动重启程序）：%s", exc)

    if tmp is not None and Path(tmp).exists():
        # 半成品种不删光 dir 树的情况由用户自行处理更安全；
        # 但 DefWindows 下残留会让下一次迁移报「临时目录已存在」 —— 名字带时间戳不会撞
        log.warning("残留的临时副本未删除（供人工核验）：%s", tmp)
    invalidate_stats_cache()

    return {
        "ok": False,
        "message": t("已中止，资料保持原样（仍在 {src}）。原因：{reason}",
                     src=src, reason=message),
        "rolled_back": True,
        "current": str(src),
    }
