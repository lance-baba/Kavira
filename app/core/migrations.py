"""索引结构版本检查与升级 —— 刻意**不做**通用 migration framework。

## 为什么可以这么简单

本项目有一个很强的架构前提：**Markdown 是真相源，``cache.db`` 是纯派生索引**，
任何时候都能从 ``data/notes/*.md`` 全量重建。既然如此，维护
``ALTER TABLE`` / ``1.1→1.2→1.3`` 的增量迁移链**只会增加错误面**，换不来任何东西。

所以升级策略就一句话：

    DB 版本旧于程序  →  备份旧库 → 建新库 → 从 Markdown 全量重建

等将来数据库里真的存了「不存在于 Markdown 的人工数据」（手写标签、收藏、
编辑状态）时，再引入真正的增量迁移。**现在不要过度设计。**

## 关键约束：检查必须在建表之前

旧代码的顺序是「先跑完所有 ``CREATE TABLE IF NOT EXISTS``，再写版本号」。
那意味着**程序已经部分修改了旧库**，之后才发现它版本不对 —— 而且版本号还会被
``INSERT OR REPLACE`` 静默改写成当前版本，从此再也查不出它原本是哪一版。

正确顺序是：

    库是否存在 → 只读探测最小元数据 → 判定版本 → 决定动作 → 才初始化完整 Schema

本模块的 :func:`probe` 用 **read-only URI 连接**，只读 ``sys_meta`` 一行，
绝不创建任何表、绝不写任何东西。

## 比程序更新的库必须拒绝

DB=1.5 / APP=1.3 时**不允许**自动重建、覆盖或降级 —— 用户可能只是误开了旧程序，
而旧程序不该擅自破坏新程序产生的数据状态。此时直接拒绝启动并给出明确提示。
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .log_util import get_logger

log = get_logger()

# 索引结构版本。唯一来源 —— db.py 从这里取，不再各写一份。
CURRENT_SCHEMA_VERSION = "1.7"   # 1.7: parent_blocks 增加 source_start_line/end（引用 stable anchor）   # 1.6: chunks 增加 section_path / retrieval_text（P0-4 标题感知检索）

META_SCHEMA_VERSION = "schema_version"

# 判定结果
FRESH = "fresh"            # 库不存在 → 按当前结构新建
OK = "ok"                  # 版本一致 → 正常启动，不得改写版本号
UPGRADE = "upgrade"        # 库旧于程序 → 备份 + 重建
DOWNGRADE = "downgrade"    # 库新于程序 → **拒绝启动**
UNKNOWN = "unknown"        # 有库但读不出/读不懂版本 → 保守按重建处理


class SchemaTooNewError(RuntimeError):
    """索引由更新版本的 Kavira 创建，拒绝以旧程序打开。
    这是**保护性失败**：宁可让用户升级程序，也不能让旧程序按旧结构去写
    新结构的数据（可能丢字段、破坏派生状态、甚至损坏 Markdown 之外的资产）。
    """

    def __init__(self, db_version: str, app_version: str) -> None:
        self.db_version = db_version
        self.app_version = app_version
        super().__init__(
            f"该知识库索引由更新版本的 Kavira 创建（索引结构 {db_version}，"
            f"当前程序仅支持 {app_version}）。请升级 Kavira 后再打开。"
        )


class BackupAborted(RuntimeError):
    """备份在**动手之前**就被否决（空间不足 / 读不到源库）。

    与「拷贝中途失败」区分开，是为了给用户一句能照着做的提示
    （"清理空间后重试"），而不是干巴巴一句"备份失败"。
    """


@dataclass
class Probe:
    """只读探测结果。"""

    exists: bool = False
    version: str = ""
    has_meta_table: bool = False
    error: str = ""


def get_schema_version(db_path: str | Path) -> str:
    """只读读出库内记录的结构版本；读不到返回空串。**绝不建表、绝不写入。**"""
    return probe(db_path).version


def probe(db_path: str | Path) -> Probe:
    """只读探测：库是否存在、``sys_meta`` 有无、版本号是多少。

    用 ``mode=ro`` URI 打开，因此**不会因为「打开动作本身」而创建空库**——
    这点很关键：若在这里意外建出空库，就会被误判成「已存在但无版本」。
    """
    path = Path(db_path)
    if not path.exists():
        return Probe(exists=False)

    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5.0)
    except sqlite3.Error as exc:
        return Probe(exists=True, error=str(exc))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sys_meta'"
        ).fetchone()
        if not row:
            return Probe(exists=True, has_meta_table=False)
        vrow = conn.execute(
            "SELECT value FROM sys_meta WHERE key = ?", (META_SCHEMA_VERSION,)
        ).fetchone()
        version = str(vrow[0]) if vrow and vrow[0] is not None else ""
        return Probe(exists=True, version=version, has_meta_table=True)
    except sqlite3.Error as exc:
        return Probe(exists=True, error=str(exc))
    finally:
        conn.close()


def _parse(v: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(x) for x in (v or "").split("."))
    except (TypeError, ValueError):
        return None


def needs_migration(db_path: str | Path) -> str:
    """判定需要做什么，返回 FRESH / OK / UPGRADE / DOWNGRADE / UNKNOWN 之一。"""
    p = probe(db_path)
    if not p.exists:
        return FRESH
    if p.error:
        return UNKNOWN
    if not p.has_meta_table or not p.version:
        # 有库但读不到版本：可能是极早期版本，也可能被外部工具动过 ——
        # 保守按 UNKNOWN 处理（走重建），因为索引本来就是可再生的。
        return UNKNOWN
    cur = _parse(p.version)
    want = _parse(CURRENT_SCHEMA_VERSION)
    if cur is None or want is None:
        return UNKNOWN
    if cur == want:
        return OK
    if cur < want:
        return UPGRADE
    return DOWNGRADE


#: **自动备份的保留上限**（2026-10-02 引入，便携形态的空间护栏）
#:
#: 每次索引结构升级都会留一份**完整的** cache.db 快照（连 -wal/-shm 一起），
#: 而旧实现**只增不减**。实测本仓库 dev 库堆积了 4 份 bak 合计 13.7MB，
#: 已经是 cache.db 本体（4.9MB）的近 3 倍。
#:
#: ⚠ **份数必须再叠一个字节预算**（2026-10-02 补）：本产品面向的是"资料长到
#: 几十上百 GB"的场景，那时的索引本身就会到 GB 级 —— 届时"保留 3 份"
#: 等于吃掉 20~30GB，U 盘直接爆掉。**备份是为了省下重建向量的几小时，
#: 而不是为了让用户丢资料**（索引随时能从 Markdown 重建），
#: 因此一旦超预算必须牺牲备份数量，**绝不能让备份把用户的盘吃满**。
MAX_AUTO_BACKUPS = 2
MAX_AUTO_BACKUP_BYTES = 3 * 1024 ** 3     # 自动备份总预算 3 GB

#: 只匹配本模块**自动生成**的备份名后缀，即 ``.v<版本数字>r<YYYYMMDD-HHMMSS>.bak``。
#: 手工留下的备份（如 ``cache.db.pre-docx-fix.bak``）不匹配 → **永不清理**，避免误删退路。
_AUTO_BK_RE = re.compile(r"^\.v\d+r\d{8}-\d{6}\.bak$")


def backup_cache(db_path: str | Path, when: str | None = None) -> Path | None:
    """给旧 ``cache.db`` 打时间戳备份，连同 ``-wal`` / ``-shm`` 边车一起。

    返回备份路径；库不存在时返回 ``None``。备份失败**必须中止升级**——
    宁可下次再升，也不能在没有退路的情况下删用户数据。

    备份成功后会顺带清理超额的旧自动备份（见 :func:`prune_cache_backups`）——
    顺序刻意是**先建新的、再删旧的**，绝不会出现「旧的已删、新的还没成」的空窗。
    """
    import shutil
    from datetime import datetime as _dt

    path = Path(db_path)
    if not path.exists():
        return None

    # ---- 动手之前先算空间：GB 级索引拷到一半失败会留下一个半截的大文件 ----
    try:
        need = path.stat().st_size
        free = shutil.disk_usage(str(path.parent)).free
    except OSError as exc:
        raise BackupAborted(f"无法读取索引所在磁盘的空间信息：{exc}") from exc
    if need > 0 and free >= 0 and free < need * 1.15:
        raise BackupAborted(
            f"索引备份需要约 {_gb(need)} 的可用空间（另留 15% 余量），"
            f"但索引所在磁盘只剩 {_gb(free)}。请先清理空间再启动程序 —— "
            f"未清理前不会升级，也不会删除任何数据。"
        )

    stamp = when or _dt.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.v{_safe_ver()}r{stamp}.bak")
    shutil.copy2(path, target)
    for suffix in ("-wal", "-shm"):
        side = Path(str(path) + suffix)
        if side.exists():
            try:
                shutil.copy2(side, Path(str(target) + suffix))
            except OSError:
                pass
    # 新的退路已经落盘，这时清理旧的才是安全的。
    removed = prune_cache_backups(path)
    if removed:
        log.info("已清理 %d 个超额的索引自动备份（份数上限 %d / 总量上限 %s）",
                 len(removed), MAX_AUTO_BACKUPS, _gb(MAX_AUTO_BACKUP_BYTES))
    return target


def _gb(n) -> str:
    try:
        return f"{float(n) / 1024 ** 3:.1f} GB"
    except (TypeError, ValueError):
        return "-"


def prune_cache_backups(db_path: str | Path,
                        keep: int = MAX_AUTO_BACKUPS,
                        max_bytes: int = MAX_AUTO_BACKUP_BYTES) -> list[str]:
    """清理超额的**自动生成**索引备份，返回被清理的文件名列表。

    **双约束**（缺一不可）：

    1. **份数** ≤ ``keep``；
    2. **总量** ≤ ``max_bytes`` —— 这条才是应对大资料库的那道闸：索引到了 GB 级，
       光按份数裁剪会留下几十 GB 备份，把用户的 U 盘吃满。两条都超了就从**最老的**开始删。

    另外三重的安全约束：

    4. **只认自动化命名**：严格按 ``_AUTO_BK_RE`` 匹配，手建/改名的备份一概不动；
    5. **只动索引备份**：绝不触碰 ``notes/``、``originals/``、``assets/`` —— 那是真相源；
    6. **按 mtime 判先后**，统计失败即跳过该文件（保守优先）。

    ⚠ 至少保留 1 份最新的（``keep <= 0`` 归一为 1）：完全没有退路比多占空间更危险。
    """
    path = Path(db_path)
    if keep <= 0:
        keep = 1
    if max_bytes <= 0:
        max_bytes = MAX_AUTO_BACKUP_BYTES

    stem = path.name
    cands: list[tuple[float, int, Path]] = []
    try:
        entries = list(path.parent.iterdir())
    except OSError:
        return []
    for p in entries:
        if not p.is_file() or not p.name.startswith(stem + "."):
            continue
        if not _AUTO_BK_RE.match(p.name[len(stem):]):
            continue
        try:
            st = p.stat()
            cands.append((st.st_mtime, st.st_size, p))
        except OSError:
            continue

    if not cands:
        return []
    cands.sort(key=lambda x: x[0])            # 老的在前

    # 先按份数裁剪。
    # ⚠ 必须 **复制一份**：下面要往 survivors 里 pop，而 cands 与它若是同一对象，
    #   pop 会连带把 cands 改掉，后面的 doomed 就再也算不出「谁该删」——
    #   结果是字节预算完全失效（静默地）。
    survivors = list(cands[-keep:]) if len(cands) > keep else list(cands)
    # 再按总量裁剪（从最老的开始删，直到落回预算内）
    total = sum(sz for _mt, sz, _p in survivors)
    while len(survivors) > 1 and total > max_bytes:
        _mt, sz, oldest = survivors.pop(0)
        total -= sz

    keep_set = {q for _m, _s, q in survivors}
    doomed = {p for _mt, _sz, p in cands if p not in keep_set}
    removed: list[str] = []
    for p in sorted(doomed, key=lambda x: x.name):
        try:
            p.unlink()
            removed.append(p.name)
        except OSError:
            continue
        # 备份当时连带的 -wal/-shm 边车，也一并收走
        for suffix in ("-wal", "-shm"):
            side = Path(str(p) + suffix)
            if side.exists():
                try:
                    side.unlink()
                    removed.append(side.name)
                except OSError:
                    pass
    return removed


def _safe_ver() -> str:
    return CURRENT_SCHEMA_VERSION.replace(".", "")


def remove_cache(db_path: str | Path) -> list[str]:
    """删除旧 ``cache.db`` 及其边车；返回被删的文件名列表。

    ⚠ **只删缓存**。任何时候都不得以任何方式改动 ``data/notes/*.md`` ——
    那是用户真相源，删了无法恢复。
    """
    removed: list[str] = []
    path = Path(db_path)
    for p in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if p.exists():
            try:
                p.unlink()
                removed.append(p.name)
            except OSError as exc:
                log.warning("删除旧缓存失败 %s: %s", p.name, exc)
    return removed


def migrate(db_path: str | Path) -> dict:
    """执行结构升级（实际就是「备份 + 清缓存」，重建由调用方在全量索引阶段完成）。

    返回 ``{action, db_version, app_version, backup, removed, message}``。

    * ``action == "reject"`` 时抛 :class:`SchemaTooNewError`（比程序新，拒绝）。
    * ``action == "rebuild"`` 时旧库已被备份并移除，调用方建好新 Schema 后
      **必须**执行一次全量重建。
    """
    action = needs_migration(db_path)
    probe_res = probe(db_path)
    info: dict = {
        "action": action,
        "db_version": probe_res.version,
        "app_version": CURRENT_SCHEMA_VERSION,
        "backup": None,
        "removed": [],
        "message": "",
    }

    if action == OK:
        info["message"] = f"索引结构一致（{CURRENT_SCHEMA_VERSION}）"
        return info

    if action == DOWNGRADE:
        raise SchemaTooNewError(probe_res.version, CURRENT_SCHEMA_VERSION)

    if action == FRESH:
        info["action"] = "create"
        info["message"] = f"无索引，将按当前结构新建（{CURRENT_SCHEMA_VERSION}）"
        return info

    # UPGRADE / UNKNOWN → 备份 + 清缓存，随后由调用方全量重建
    try:
        backup = backup_cache(db_path)
    except BackupAborted as exc:
        # 空间不足等「动手前就被否决」的情形：把可照做的提示原样带给用户，
        # 并且**绝不继续升级**（宁死不做，绝不留下没有退路的半截状态）。
        raise RuntimeError(f"旧索引备份未执行，已中止结构升级（未删除任何数据）：{exc}") from exc
    info["backup"] = str(backup) if backup else None
    if backup is None and Path(db_path).exists():
        # 有库却备份失败：中止升级，绝不冒删数据的风险
        raise RuntimeError("旧索引备份失败，已中止结构升级（未删除任何数据）")
    info["removed"] = remove_cache(db_path)
    reason = "索引结构已更新" if action == UPGRADE else "索引结构无法识别"
    info["action"] = "rebuild"
    info["message"] = (
        f"{reason}（{probe_res.version or '未知'} → {CURRENT_SCHEMA_VERSION}），"
        f"已备份旧索引并清空，将从 data/notes 全量重建"
    )
    return info


def rebuild_cache_if_incompatible(db_path: str | Path) -> dict:
    """对外统一入口：不兼容就升级，兼容则什么都不做。"""
    return migrate(db_path)
