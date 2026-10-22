"""外部 Markdown 增量同步（PRD 4.5 + 编码阶段提示 #1 加固）。

exFAT 时间戳精度只有 2 秒，且等长编辑（把"买"改成"卖"）字节数完全相同 ——
单靠「大小变化」会漏更新。因此判定升级为三分支：

  1. ``current_mtime > last_mtime + 2.0s``                → 时间明显后移，必须更新
  2. ``|Δt| <= 2.0s 且 file_size != last_size``           → 容差期内大小变化，必须更新
  3. ``|Δt| <= 2.0s 且 file_size == last_size``           → 比对前 4KB 快速哈希(XXH64/blake2b)
                                                            哈希不同则更新，否则视作未变

分支 1 与分支 3 共同封堵了「等长编辑 + 2 秒窗口边缘」的漏扫盲区。
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from pathlib import Path

from . import chunker, config, index_bg, indexer, paths
from .db import Database
from .log_util import get_logger

log = get_logger()

MTIME_TOLERANCE = 2.0
PREFIX_BYTES = 4096
#: 连续多少轮「毫无变化」之后才拉长轮询间隔。前几轮保持快节奏，
#: 是为了兑现「把 .md 丢进文件夹 15 秒内自动入库」这个对用户的承诺。
IDLE_ROUNDS_BEFORE_BACKOFF = 3


# --------------------------------------------------------------------------
def prefix_hash(p: Path, size: int = PREFIX_BYTES) -> str:
    """前 4KB 快速哈希；优先 xxhash（可选依赖），缺失时回退 blake2b。"""
    try:
        data = p.open("rb").read(size)
    except OSError:
        return ""
    try:
        import xxhash  # type: ignore

        return xxhash.xxh64(data).hexdigest()
    except ImportError:
        return hashlib.blake2b(data, digest_size=8).hexdigest()


class NoteSyncer:
    """后台轮询扫描 data/notes 的轻量增量同步器。"""

    def __init__(self, db: Database, embedder=None) -> None:
        self.db = db
        self.embedder = embedder
        self.interval = max(3, config.get_int("SYSTEM", "sync_interval", 15))
        #: 连续多少轮「什么都没变」之后才开始拉长间隔（见 :meth:`_next_interval`）
        self._idle_rounds = 0
        #: 首轮标志：用来决定要不要做那次「全表兜底校准」（见 :meth:`scan_once`）
        self._first_scan_done = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # rel_path -> {"mtime","size","prefix"}
        self._state: dict[str, dict] = {}
        #: 进度快照（/api/index/status 用）：只记录「本轮扫描」的推进情况。
        #   Done/Total 以**文件数**计，pending 由「本轮剩余 + 后台队列」算出。
        self._prog_lock = threading.Lock()
        self._scanning = False
        self._cycle_total = 0
        self._cycle_done = 0
        self._current = ""
        self._errors: list[str] = []
        self.stats = {
            "cycles": 0,
            "indexed": 0,
            "updated": 0,
            "removed": 0,
            "last_run": 0.0,
            "last_report": {},
        }

    # ------------------------------------------------------------------
    def seed_from_db(self) -> None:
        """从 documents 表回灌基线，避免重启后把全库误判为“新增”。"""
        try:
            rows = self.db.query(
                "SELECT rel_path, mtime, file_size, sha1 FROM documents"
            )
        except sqlite3.Error:
            return
        for r in rows:
            self._state[r["rel_path"]] = {
                "mtime": float(r["mtime"] or 0.0),
                "size": int(r["file_size"] or 0),
                "prefix": r["sha1"] or "",
            }
        log.info("同步基线已载入 %d 个文档", len(self._state))

    # ------------------------------------------------------------------
    @staticmethod
    def _decide(p: Path, st, base: dict | None) -> tuple[bool, str, str]:
        """三分支判定：返回 (是否需要重建索引, 判定依据, 当前前缀哈希)。

        分支 1「时间明显后移」与分支 3「等长编辑哈希比对」共同封堵 exFAT
        2 秒时间窗 + 等长编辑造成的漏扫盲区。
        """
        if not base:
            return True, "new", ""

        last_mtime = float(base.get("mtime") or 0.0)
        last_size = int(base.get("size") or 0)
        last_prefix = base.get("prefix") or ""
        delta = st.st_mtime - last_mtime

        # 1) 时间明显后移：即便字节数完全相同也必须更新
        if delta > MTIME_TOLERANCE:
            return True, "mtime-advanced", ""

        # 2) 2 秒容差期内，文件大小发生变化
        if abs(delta) <= MTIME_TOLERANCE and st.st_size != last_size:
            return True, "size-changed", ""

        # 3) 容差期且大小相同 —— 必须比对前 4KB 快速哈希
        if abs(delta) <= MTIME_TOLERANCE:
            cur_prefix = prefix_hash(p)
            if not last_prefix:
                # 基线缺失（首次升级/旧库）：保守重建一次以建立哈希基线
                return True, "baseline-missing", cur_prefix
            if cur_prefix != last_prefix:
                return True, "same-length-edit", cur_prefix
            return False, "unchanged", cur_prefix

        # 时间倒流（外部工具回写 / 时钟漂移）：保守重建
        return True, "mtime-rewound", ""

    # ------------------------------------------------------------------
    def scan_once(self) -> dict:
        """执行一轮扫描，返回本轮报告（外层只负责进度标记，见 :meth:`_scan_body`）。"""
        with self._prog_lock:
            self._scanning = True
            self._cycle_total = 0
            self._cycle_done = 0
            self._current = ""
            self._errors = []
        try:
            return self._scan_body()
        finally:
            # 无论扫描怎么结束（含异常），都必须收起「扫描中」，
            # 否则 progress().pending 会永远挂着一个不存在的剩余量。
            with self._prog_lock:
                self._scanning = False
                self._current = ""

    def _scan_body(self) -> dict:
        """一轮扫描的实际工作。"""
        if not paths.NOTES_DIR.exists():
            paths.NOTES_DIR.mkdir(parents=True, exist_ok=True)

        disk: dict[str, Path] = {}
        for p in paths.NOTES_DIR.rglob("*.md"):
            try:
                if p.is_file():
                    disk[paths.rel_to_data(p)] = p
            except OSError:
                continue

        with self._prog_lock:
            self._cycle_total = len(disk)

        report = {"indexed": 0, "updated": 0, "unchanged": 0, "removed": [],
                  "errors": [], "notes": [], "disk": len(disk),
                  "deferred": 0, "already": 0}

        for rel, p in sorted(disk.items()):
            try:
                st = p.stat()
            except OSError as exc:
                report["errors"].append(f"{rel}: {exc}")
                self._note_error(f"{rel}: {exc}")
                self._tick()
                continue

            base = self._state.get(rel)
            need, reason, cur_prefix = self._decide(p, st, base)
            if not need:
                report["unchanged"] += 1
                self._tick()
                continue

            # 与后台索引队列（剪藏 / 导入的落点）互斥：两个线程同时对同一文件
            # purge + 重写会撕裂 chunks / 向量表。锁内先看「已索引」再决定要不要嵌。
            with index_bg.file_lock(p):
                if index_bg.is_queued(p):
                    # 后台正要索引它 —— 让后台干，本轮不要重复嵌入（长文要几分钟）
                    report["deferred"] += 1
                    log.info("增量同步跳过（后台索引中）: %s", rel)
                    self._tick()
                    continue

                already = index_bg.fingerprint(self.db, p)
                if already is not None:
                    # DB 里的 (size, 前 4KB 哈希) 与磁盘一致 → 内容没变，只是内存基线
                    # 落后（典型：刚剪藏/导入完，后台已经索引过）。补基线即可，不重嵌。
                    self._state[rel] = already
                    report["already"] += 1
                    log.info("增量同步跳过（已索引）: %s", rel)
                    self._tick()
                    continue

                self._set_current(rel)
                result = indexer.index_file(self.db, p, self.embedder)
                if result.get("ok"):
                    if not cur_prefix:
                        cur_prefix = prefix_hash(p)
                    self._state[rel] = {
                        "mtime": float(st.st_mtime),
                        "size": int(st.st_size),
                        "prefix": cur_prefix,
                    }
                    if reason == "new":
                        report["indexed"] += 1
                    else:
                        report["updated"] += 1
                    log.info("增量同步 [%s] %s (%d 切片)", reason, rel, result.get("chunks", 0))
                else:
                    report["errors"].append(f"{rel}: {result.get('error')}")
                    self._note_error(f"{rel}: {result.get('error')}")
            self._tick()

        # ---- 重命名 / 删除 -> 孤儿切片回收 ----
        known = set(self._state.keys())
        vanished = known - set(disk.keys())
        for rel in vanished:
            n = indexer.purge_by_rel_path(self.db, rel)
            self._state.pop(rel, None)
            report["removed"].append({"path": rel, "chunks": n})
            log.info("孤儿切片回收: %s (%d 切片)", rel, n)

        # ---- 兜底全表扫描：只在「首轮」或「本轮出过异常」时才做 ----
        # 为什么不每轮都做（2026-10-02 修）：它是 `SELECT * FROM documents` + 逐行
        # Python 比对，实测 40 万文档时**每轮白花 293ms**，而 99.9% 的轮次一个孤儿
        # 都扫不出来 —— 纯浪费，还会在 U 盘上多一轮全盘读。
        #
        # 降频是安全的：启动时 `seed_from_db()` 已把基线灌成**DB 全量**，
        # 所以「DB 有、磁盘已无」的文件在**首轮的 vanished 分支**就已被全部回收；
        # 这个全表兜底只覆盖「运行中途 DB 与基线不一致」这种罕见情况
        # （例如入库成功但基线更新前就崩了），而那些场景必然伴随本轮异常。
        sweep_reason = ""
        if not self._first_scan_done:
            sweep_reason = "首轮校准"
        elif report["removed"] or report["errors"]:
            sweep_reason = "本轮检测到变更或异常"
        if sweep_reason:
            try:
                stale = indexer.purge_orphans(self.db, set(disk.keys()))
                if stale:
                    log.info("兜底回收（%s）: %d 个文档", sweep_reason, len(stale))
                for s in stale:
                    report["removed"].append({"path": s, "chunks": -1})
            except Exception as exc:  # noqa: BLE001
                report["errors"].append(f"orphan-sweep: {exc}")
                self._note_error(f"orphan-sweep: {exc}")
        self._first_scan_done = True

        # 原件安全（Pilot D1）：**永不自动删除** originals/ —— 它们是用户原始资料。
        # 后台只能报告「暂未关联」，绝不 unlink/移入回收站。
        try:
            from . import crawler as crawler_mod  # noqa: PLC0415

            kept = crawler_mod.find_orphan_originals(set(disk.keys()))
            if kept:
                report["notes"].append(
                    f"发现 {len(kept)} 份暂未关联原件，已保留（不自动删除用户原件）")
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(f"original-sweep: {exc}")
            self._note_error(f"original-sweep: {exc}")

        self.stats["cycles"] += 1
        self.stats["indexed"] += report["indexed"]
        self.stats["updated"] += report["updated"]
        self.stats["removed"] += len(report["removed"])
        self.stats["last_run"] = time.time()
        self.stats["last_report"] = report
        return report

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        """本轮扫描每处理完一个文件就前进一格（/api/index/status 的 done）。"""
        with self._prog_lock:
            self._cycle_done += 1

    def _set_current(self, rel: str) -> None:
        with self._prog_lock:
            self._current = rel

    def _note_error(self, message: str) -> None:
        with self._prog_lock:
            self._errors.append(str(message))
            del self._errors[:-20]

    def progress(self) -> dict:
        """索引进度快照（供 ``GET /api/index/status``）。

        ``pending`` = 后台队列里还没跑完的文件 + 本轮扫描尚未处理的文件。
        界面只要看到 ``pending == 0`` 就可以刷新列表并收掉「后台索引中…」。
        """
        bg = index_bg.snapshot()
        with self._prog_lock:
            scan_pending = max(0, self._cycle_total - self._cycle_done) if self._scanning else 0
            current = self._current
            done = self._cycle_done
            total = self._cycle_total
            errors = list(self._errors)
        errors.extend(bg["errors"])
        return {
            "pending": int(bg["pending"]) + scan_pending,
            "current": current or bg["current"],
            "done": done,
            "total": total,
            # indexed = 本轮同步器入库 + 后台队列入库（两者互斥，不会重复计数）
            "indexed": int(self.stats.get("indexed", 0)) + int(bg["done"]),
            "updated": int(self.stats.get("updated", 0)),
            "cycles": int(self.stats.get("cycles", 0)),
            "errors": errors[-20:],
        }

    # ------------------------------------------------------------------
    def _next_interval(self, report: dict) -> int:
        """按**文档规模**与**空闲程度**决定下一轮间隔（秒）。

        为什么必须自适应（2026-10-02 修）：一轮 ``scan_once`` 是对 notes/ 的
        **全量递归遍历 + 逐篇 stat**，成本随文档数**线性增长**。固定 15 秒时：

        * 4 万篇 → 每轮几万次 stat，15 秒一轮 = 磁盘常年被摸；
        * 40 万篇 → 每轮本身就要几十秒到几分钟，**扫描线程会一直占着 I/O**。

        而产品跑在 U 盘上 —— 持续无谓的读写既拖慢整机，也在损耗闪存寿命。
        所以两条规则：**规模越大间隔越长**（扫描成本本来就随规模涨），
        **连续空闲则退避**（没人动资料时不必反复摸盘），一有变化立刻回到基准。
        """
        n = max(int(report.get("disk") or 0), len(self._state), 0)
        base = self.interval
        if n > 50_000:
            base *= 4
        elif n > 10_000:
            base *= 2

        changed = (report.get("indexed", 0) + report.get("updated", 0)
                   + len(report.get("removed", ())))
        if changed:
            self._idle_rounds = 0
            return max(1, int(base))

        self._idle_rounds += 1
        if self._idle_rounds < IDLE_ROUNDS_BEFORE_BACKOFF:
            return max(1, int(base))
        # 退避最多到 4 倍基准：再长就损害「把 .md 丢进文件夹 15 秒内入库」的承诺
        factor = min(4.0, 1.5 ** min(self._idle_rounds - IDLE_ROUNDS_BEFORE_BACKOFF + 1, 4))
        return max(1, int(base * factor))

    def _loop(self) -> None:
        log.info("外部文件增量同步已启动（基准间隔 %ds，扫描成本随资料量自适应）",
                 self.interval)
        while not self._stop.is_set():
            report: dict = {}
            try:
                report = self.scan_once()
            except Exception as exc:  # noqa: BLE001 - 同步线程绝不因单轮异常而退出
                log.error("同步轮次异常: %s", exc)
            try:
                wait_s = self._next_interval(report)
            except Exception:  # noqa: BLE001 - 间隔计算失败就退回基准，绝不退出循环
                wait_s = self.interval
            self._stop.wait(wait_s)
        log.info("外部文件增量同步已停止")

    def start(self, run_now: bool = True) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self.seed_from_db()
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="note-syncer", daemon=True)
            self._thread.start()
        if run_now:
            threading.Thread(target=self._safe_initial_scan, daemon=True).start()

    def _safe_initial_scan(self) -> None:
        try:
            self.scan_once()
        except Exception as exc:  # noqa: BLE001
            log.error("首次全量扫描异常: %s", exc)

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)

    def status(self) -> dict:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "interval": self.interval,
            "tracked": len(self._state),
            **{k: v for k, v in self.stats.items() if k != "last_report"},
        }
