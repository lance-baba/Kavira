"""剪藏 / 导入后的**后台索引队列**（单 worker + 文件级互斥）。

为什么要有这个模块（2026-10-22）：
    剪藏与导入曾在**请求线程**里 inline 调 ``indexer.index_file``。一篇长文
    （~470 块 × 270ms/块）会把 HTTP 响应拖到 **2 分钟**，浏览器只能干等。
    现在请求只做「落盘 + 入队」，嵌入在后台守护线程里跑；调用方拿到
    ``indexed=False / pending=True / chunks=0``，前端轮询 ``/api/index/status``。

设计边界：
    * **单 worker**（不是线程池）：嵌入本身已吃满 CPU，多线程只会互相抢 GIL 与内存；
    * **daemon 线程**：绝不阻止进程退出。退出时没跑完的文件不用急 —— 下次启动由
      ``NoteSyncer`` 扫目录补上（它们已落盘，索引是可重建的衍生物）；
    * **文件级锁**：与 ``NoteSyncer`` 的扫描线程共用同一把 per-path 锁。两个线程
      同时对同一文件 purge + 重写会撕裂 chunks / 向量表，这是必须挡住的；
    * **指纹去重**：worker 先比对 ``documents`` 里的 (size, 前 4KB 哈希)，与 syncer
      的判定同源；已被 syncer 索引过的文件直接跳过，日志写明「跳过（已索引）」；
    * **失败可见**：任何异常都记日志 + 进 ``snapshot()["errors"]``，绝不静默吞掉。
"""
from __future__ import annotations

import contextlib
import queue
import threading
from pathlib import Path

from . import indexer, paths
from .log_util import get_logger

log = get_logger()

MAX_ERRORS = 20

_GUARD = threading.Lock()
_QUEUE: "queue.Queue[tuple]" = queue.Queue()
#: 已入队 / 正在跑的文件（绝对路径），用于 pending 计数与重复入队去重
_INFLIGHT: set[str] = set()
#: 路径 -> [Lock, 引用计数]（无等待者时回收，避免长跑后锁表无限增长）
_LOCKS: dict[str, list] = {}
_WORKER: threading.Thread | None = None
#: 退出中：不再开始新的索引任务（已落盘的文件下次启动由 syncer 补）
_STOPPING = False
_STATE = {"current": "", "done": 0, "skipped": 0, "failed": 0, "errors": []}


# --------------------------------------------------------------------------- 锁
@contextlib.contextmanager
def file_lock(abs_path):
    """同一文件的索引互斥（后台 worker 与 NoteSyncer 共用）。

    引用计数保证「无人持有 / 等待」时从表里移除 —— syncer 每轮都会摸一遍全库，
    若永久保留锁对象，40 万笔记会白吃几十 MB。
    """
    key = str(abs_path)
    with _GUARD:
        entry = _LOCKS.get(key)
        if entry is None:
            entry = [threading.Lock(), 0]
            _LOCKS[key] = entry
        entry[1] += 1
    lock = entry[0]
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _GUARD:
            entry[1] -= 1
            if entry[1] <= 0:
                _LOCKS.pop(key, None)


# ------------------------------------------------------------------ 指纹（去重）
def _prefix_hash(p: Path, size: int = 4096) -> str:
    """前 4KB 快速哈希 —— 直接复用 syncer 的算法（惰性导入避开循环依赖）。"""
    from .sync import prefix_hash  # noqa: PLC0415

    return prefix_hash(Path(p), size)


def fingerprint(db, abs_path) -> dict | None:
    """文件**已按当前内容索引过**时返回基线 ``{mtime,size,prefix}``，否则 ``None``。

    判定与 ``NoteSyncer._decide`` 同源：大小一致 + 前 4KB 哈希一致 → 索引是最新的。
    调用方拿到基线后可直接写回自己的 ``_state``，省掉一次全量重嵌。
    """
    p = Path(abs_path)
    try:
        st = p.stat()
    except OSError:
        return None
    rel = paths.rel_to_data(p)
    try:
        row = db.query_one(
            "SELECT mtime, file_size, sha1 FROM documents WHERE rel_path = ? LIMIT 1",
            (rel,),
        )
    except Exception:  # noqa: BLE001 - 表可能尚未建出（老库 / 首次启动）
        return None
    if not row:
        return None
    if int(row["file_size"] or 0) != int(st.st_size):
        return None
    stored = str(row["sha1"] or "")
    if not stored or stored != _prefix_hash(p):
        return None
    return {
        "mtime": float(row["mtime"] or st.st_mtime),
        "size": int(st.st_size),
        "prefix": stored,
    }


def is_queued(abs_path) -> bool:
    """该文件是否已在本后台队列里（排队中或正在索引）。"""
    with _GUARD:
        return str(abs_path) in _INFLIGHT


# ---------------------------------------------------------------------- 提交
def submit(db, abs_path, embedder=None) -> bool:
    """把文件交给后台索引。返回 ``False`` 表示入队失败（调用方必须让失败可见）。

    重复提交同一文件是幂等的（已在队列里就不再排一次），返回 ``True`` ——
    对调用方语义仍是「它会被索引」。
    """
    p = Path(abs_path)
    key = str(p)
    with _GUARD:
        if _STOPPING:
            log.warning("正在退出，后台索引未入队: %s", key)
            return False
        if key in _INFLIGHT:
            log.debug("后台索引已在队列中，忽略重复提交: %s", key)
            return True
        _INFLIGHT.add(key)
        _QUEUE.put((db, p, embedder))
        _ensure_worker_locked()
    return True


def stop() -> None:
    """请求 worker 停止（安全退出时调用）。

    只置位、不 join：daemon 线程不能拖住进程退出。**尚未开始**的任务会被丢弃 ——
    文件已经在磁盘上，下次启动 ``NoteSyncer`` 扫目录会补上（索引是可重建的衍生物）。
    """
    global _STOPPING
    with _GUARD:
        _STOPPING = True
        _INFLIGHT.clear()


def _ensure_worker_locked() -> None:
    """懒启动 worker（调用方必须持 ``_GUARD``）。"""
    global _WORKER
    if _WORKER is not None and _WORKER.is_alive():
        return
    _WORKER = threading.Thread(target=_loop, name="index-bg", daemon=True)
    _WORKER.start()


def _loop() -> None:
    log.info("后台索引队列已启动（单 worker，daemon）")
    while True:
        db, p, embedder = _QUEUE.get()
        key = str(p)
        if _STOPPING:
            # 退出中：不再对磁盘/DB 做新的写入（用户马上要拔 U 盘）
            with _GUARD:
                _INFLIGHT.discard(key)
            _QUEUE.task_done()
            continue
        try:
            _run_one(db, p, embedder)
        except Exception as exc:  # noqa: BLE001 - 单文件异常绝不能让 worker 退出
            _record_error(key, f"{key}: {exc}")
            log.exception("后台索引异常（已记录，worker 继续）: %s", key)
        finally:
            with _GUARD:
                _INFLIGHT.discard(key)
                _STATE["current"] = ""
            _QUEUE.task_done()


def _run_one(db, p: Path, embedder) -> None:
    rel = paths.rel_to_data(p)
    with file_lock(p):
        with _GUARD:
            _STATE["current"] = rel
        try:
            p.stat()
        except OSError as exc:
            _record_error(rel, f"{rel}: {exc}")
            log.error("后台索引失败（文件不可读）%s: %s", rel, exc)
            return

        if fingerprint(db, p) is not None:
            with _GUARD:
                _STATE["skipped"] += 1
            # 与 syncer 撞车的正常路径：它先跑完了，这里不必再嵌一遍
            log.info("后台索引跳过（已索引）: %s", rel)
            return

        r = indexer.index_file(db, p, embedder)
        if r.get("ok"):
            with _GUARD:
                _STATE["done"] += 1
            if r.get("warning"):
                # 向量化失败等「降级成功」不算硬失败，但必须留痕（status.errors 只收硬失败）
                log.warning("后台索引降级 [%s]: %s", rel, r["warning"])
            log.info("后台索引完成 [%s] %d 切片", rel, r.get("chunks", 0))
        else:
            _record_error(rel, f"{rel}: {r.get('error')}")
            log.error("后台索引失败 %s: %s", rel, r.get("error"))


def _record_error(rel: str, message: str) -> None:
    with _GUARD:
        _STATE["failed"] += 1
        errs = _STATE["errors"]
        errs.append(message)
        del errs[:-MAX_ERRORS]


# ---------------------------------------------------------------------- 观测
def snapshot() -> dict:
    """队列进度快照（供 ``NoteSyncer.progress()`` / ``/api/index/status``）。"""
    with _GUARD:
        return {
            "pending": len(_INFLIGHT),
            "current": _STATE["current"],
            "done": _STATE["done"],
            "skipped": _STATE["skipped"],
            "failed": _STATE["failed"],
            "errors": list(_STATE["errors"]),
        }
