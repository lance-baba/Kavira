"""资料目录（Library）类 API —— 查询位置 / 预检目标 / 执行迁移 / 轮询进度。

为什么单独成模块：资料目录是**程序（App）与用户数据（Library）的边界**，操作涉及
整棵 ``data/`` 的复制与重新挂载；它和「笔记内容」完全不是一回事（``library.py`` 管的是
后者），混在一起会让两边的失败语义互相污染。

四个接口刻意**不受激活门禁限制** —— 换一个地方放资料是用户对自己数据的基本处置权，
和 AI 问答 / 网页抓取这类「付费权益」无关。
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from ..core import datadir as dd_mod
from ..core.log_util import get_logger

if TYPE_CHECKING:
    from ..server import Handler

log = get_logger()


def handle_get(h: "Handler", path: str) -> bool:
    if path == "/api/datadir":
        info = dd_mod.library_info()
        info["busy"] = dd_mod.is_busy()
        h._send_json({"code": 200, "data": info})
        return True

    if path == "/api/datadir/progress":
        h._send_json({"code": 200, "data": dd_mod.progress_snapshot()})
        return True

    if path == "/api/datadir/export":
        # 「U 盘会坏」的兜底：把用户资料打包成 zip 交给浏览器下载。
        res = dd_mod.export_package()
        if not res.get("ok"):
            h._send_json({"code": 500, "message": res.get("message", "打包失败")}, 500)
            return True
        try:
            h._send_file_stream(res["path"], "application/zip", res["name"])
        finally:
            # 临时包用完即删 —— 它落在系统临时目录，不留垃圾、更不会混进资料目录。
            try:
                Path(res["path"]).unlink(missing_ok=True)
            except OSError:
                pass
        return True
    return False


def handle_post(h: "Handler", path: str) -> bool:
    if path == "/api/datadir/precheck":
        body = h._read_json() or {}
        ck = dd_mod.precheck(str(body.get("target") or ""))
        if ck["ok"]:
            h._send_json({"code": 200, "message": "预检通过", "data": ck})
        else:
            # 400 而非 500：这是**用户的输入不合规**，不是服务故障。
            h._send_json({"code": 400, "message": "；".join(ck["errors"]),
                          "data": ck}, 400)
        return True

    if path == "/api/datadir/migrate":
        body = h._read_json() or {}
        target = str(body.get("target") or "").strip()
        if not target:
            h._send_json({"code": 400, "message": "请填写目标目录"}, 400)
            return True
        if dd_mod.is_busy():
            h._send_json({"code": 409, "message": "已有迁移任务在进行中"}, 409)
            return True
        # 迁移可能持续几分钟到几十分钟（几十 GB + 机械/U 盘），**必须异步**；
        # 期间服务会短暂不可用（context 关闭再重开），前端靠 progress 轮询跟进度。
        threading.Thread(target=dd_mod.migrate, args=(target,),
                         name="datadir-migrate", daemon=True).start()
        h._send_json({"code": 202, "message": "资料迁移任务已启动，请留意进度提示"})
        return True
    return False
