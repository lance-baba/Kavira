"""本地 GGUF 模型导入（MVP）—— 全部走 Ollama 的 `create`，不自研推理加载器。

产品边界
========
只做「选一个本机 .gguf → 交给 Ollama 建模型 → 试聊验证 → 出现在现有下拉里」。
**不做**模型下载、量化转换、在线拉取、删除模型（删除交给 Ollama 自带，
本模块只在「试聊不合格」时把**自己刚建的**那个模型删掉，免得它冒充可用）。

四条硬护栏
==========
1. **试聊验证**：create 成功后用固定短提示真跑一次 /api/chat。空回复 / 乱码 /
   复述提示词 / 超时 → 一律判失败，删掉该模型并在错误里提示「可能缺少 chat
   template，建议换 instruct 版本」。绝不让一个坏模型留在下拉里。
2. **异步 + 进度**：GB 级拷贝绝不能挡请求。采用与 ``index_bg`` 同一个模式 ——
   单 worker 守护线程 + ``snapshot()`` 观测；请求只做「校验 + 入队」。同一文件
   导入期间重复触发会被明确拒绝。
3. **派生命名**：``kavira-import-<sha8>``（由 **绝对路径 + mtime** 派生）。
   同名已存在视为同源 → 复用（不覆盖、不重复拷一份 4.4GB）；确需新建而名字
   被占则追加 ``-2``…``-5``。绝不覆盖用户自己的模型。
4. **磁盘检查 + 明示位置**：导入前按「文件大小 × 1.2 + 300MB」检查 **Ollama
   模型目录所在磁盘**的剩余空间；UI 上明确写「模型存在 Ollama 全局目录，不在
   U 盘」。

失败必须可见：日志 + ``snapshot()["errors"]`` + 接口消息，三处都要留痕。
"""
from __future__ import annotations

import hashlib
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import config, net_util, paths, proc as proc_mod
from .i18n import DeferredMsg
from .log_util import get_logger
from .ollama_runtime import find_ollama_exe

log = get_logger()

#: 小于这个体积基本不可能是完整模型（量化后的 0.5B 也有几百 MB）
MIN_GGUF_BYTES = 10 * 1024 * 1024
#: 磁盘余量系数：ollama create 是把 gguf 复制进 blobs，等于再存一份
SPACE_HEADROOM = 1.2
#: 额外余量（manifest / 临时文件 / 别让盘刚好写满）
SPACE_EXTRA_BYTES = 300 * 1024 * 1024
#: 派生名前缀 —— 一眼能看出「这是 Kavira 导入的临时模型」
NAME_PREFIX = "kavira-import-"
#: 名字被占时最多加到这个序号
NAME_MAX_SUFFIX = 5
#: 固定试聊提示。故意要求一个**短且可判定**的回答，便于识别「没有 chat template」
VERIFY_PROMPT = "请只回复「可用」两个字，不要解释。"
#: 试聊超时（秒）。7B q4 在 CPU 上首次加载可能很慢，给足但绝不无限等
VERIFY_TIMEOUT_S = 180.0
#: 单次 create 的总超时（秒）。GB 级拷贝 + 慢盘，留够余量
CREATE_TIMEOUT_S = 1800.0
MAX_ERRORS = 20

#: 复述提示词的特征串 —— 出现即说明模型没有按 chat 格式理解指令
_ECHO_MARKERS = ("请只回复", "回复「可用」", "不要解释", "回复两个字")


# --------------------------------------------------------------------------- 状态
_GUARD = threading.Lock()
_QUEUE: "queue.Queue[Path]" = queue.Queue()
_INFLIGHT: set[str] = set()
_BUSY = threading.Event()          # 有任务在跑（无队列语义：同一时刻只允许一个导入）
_WORKER: threading.Thread | None = None
_STOPPING = False

_STATE: dict = {
    "active": False,
    "phase": "idle",          # idle / checking / creating / verifying / done / failed
    "name": "",
    "path": "",
    "detail": "",
    "percent": 0,
    "started_at": 0.0,
    "finished_at": 0.0,
    "errors": [],
    "results": [],
    "last_ok": None,
}


def _set(**kw) -> None:
    with _GUARD:
        _STATE.update(kw)


def _record_error(msg: DeferredMsg | str) -> None:
    with _GUARD:
        errs = _STATE["errors"]
        errs.append(msg)
        del errs[:-MAX_ERRORS]
    log.error("GGUF 导入失败：%s", msg)


def snapshot() -> dict:
    """导入进度快照（供 ``/api/ollama/import/status``）。含 DeferredMsg，勿直接 JSON。"""
    with _GUARD:
        out = {k: (list(v) if isinstance(v, list) else v) for k, v in _STATE.items()}
        if out["active"] and out["started_at"]:
            out["elapsed"] = round(time.time() - out["started_at"], 1)
        elif out["started_at"] and out["finished_at"]:
            out["elapsed"] = round(out["finished_at"] - out["started_at"], 1)
        else:
            out["elapsed"] = 0.0
    out["models_dir"] = str(ollama_models_dir())
    out["busy"] = _BUSY.is_set()
    return out


def stop() -> None:
    """安全退出时调用：不再接受新任务（正在跑的 create 交给子进程自己结束）。"""
    global _STOPPING
    with _GUARD:
        _STOPPING = True
        _INFLIGHT.clear()


# --------------------------------------------------------------------- 路径校验
def _fail(zh: str, **fmt) -> dict:
    return {"ok": False, "error": DeferredMsg(zh, **fmt)}


def _mb(n: float) -> str:
    n = float(n or 0)
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.2f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    return f"{n / 1024:.0f} KB"


def inspect_path(raw) -> dict:
    """校验用户填的路径能否作为 GGUF 导入源。

    依次检查：非空 → 绝对路径 → 存在 → 是文件 → ``.gguf``（大小写不敏感）
    → 体积下限 → 能读出 ``GGUF`` 魔数。返回 ``{"ok", "path", "size", "name"}``
    或 ``{"ok": False, "error": DeferredMsg}``。
    """
    s = str(raw or "").strip().strip('"').strip("'").strip()
    if not s:
        return _fail("请填写 .gguf 文件的完整路径")
    p = Path(os.path.expandvars(os.path.expanduser(s)))
    if not p.is_absolute():
        return _fail("请填写完整路径（从盘符开始），不要只填文件名：{path}", path=s)
    try:
        st = p.stat()
    except FileNotFoundError:
        return _fail("文件不存在：{path}", path=str(p))
    except OSError as exc:
        return _fail("无法读取该路径（权限不足或路径过长）：{path}（{exc}）", path=str(p), exc=exc)
    if not p.is_file():
        return _fail("这不是一个文件：{path}", path=str(p))
    if p.suffix.lower() != ".gguf":
        return _fail("只支持 .gguf 文件（当前扩展名：{ext}）",
                     ext=p.suffix or DeferredMsg("（无）"))
    if st.st_size < MIN_GGUF_BYTES:
        return _fail("文件只有 {size}，小到不可能是完整模型（至少 {min_size}）：{path}",
                     size=_mb(st.st_size), min_size=_mb(MIN_GGUF_BYTES), path=str(p))
    try:
        with open(p, "rb") as fh:
            magic = fh.read(4)
    except OSError as exc:
        return _fail("文件不可读（权限不足或被其它程序独占）：{path}（{exc}）", path=str(p), exc=exc)
    if magic != b"GGUF":
        return _fail("文件头不是 GGUF 魔数，可能不是有效的 GGUF 模型：{path}", path=str(p))
    p = p.resolve()
    return {"ok": True, "path": str(p), "size": int(st.st_size), "name": derive_name(p)}


def derive_name(path) -> str:
    """``kavira-import-<sha8>``：由**绝对路径 + mtime** 派生。

    为什么带 mtime：同一个路径换了文件内容（重新下载 / 重新量化）应得到新名字，
    否则会撞上旧模型、误判「已导入过」。
    Windows 路径大小写不敏感，故先 normcase，避免 D:\\x.gguf 与 d:\\x.gguf 派生两个名字。
    """
    p = Path(path)
    try:
        key = str(p.resolve())
    except OSError:                      # 盘符不存在等异常路径：退回原样
        key = str(p)
    try:
        mtime = int(p.stat().st_mtime)
    except OSError:
        mtime = 0
    seed = f"{os.path.normcase(key)}|{mtime}"
    return NAME_PREFIX + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]


def unique_name(base: str, existing) -> str:
    """名字被占时追加 ``-2``…``-5``；全占则返回 ``base-<序号>`` 兜底（仍不覆盖）。"""
    taken = {str(x).lower() for x in (existing or [])}
    if base.lower() not in taken:
        return base
    for i in range(2, NAME_MAX_SUFFIX + 1):
        cand = f"{base}-{i}"
        if cand.lower() not in taken:
            return cand
    return f"{base}-{int(time.time()) % 10000}"


def build_modelfile(path) -> str:
    """生成 Modelfile 内容。

    只写 ``FROM``：Ollama 会从 GGUF 自带的元数据里读 template / 参数，
    不替用户发明 system prompt 或采样参数（那会掩盖「这个 GGUF 本来没有
    chat template」的事实）。路径统一正斜杠 + 引号，避免 Windows 反斜杠
    在 Modelfile 解析里被当转义。
    """
    q = Path(path).resolve().as_posix().replace('"', '\\"')
    return f'FROM "{q}"\n'


# --------------------------------------------------------------------- 磁盘检查
def ollama_models_dir() -> Path:
    """Ollama 的全局模型目录（导入后的 blob 就落在这里）。

    与 Ollama 自己同源：``OLLAMA_MODELS`` 优先，否则 ``~/.ollama/models``。
    """
    env = (os.environ.get("OLLAMA_MODELS") or "").strip()
    return Path(env) if env else (Path.home() / ".ollama" / "models")


def _nearest_existing(p: Path) -> Path | None:
    cur = p
    for _ in range(40):
        try:
            if cur.exists():
                return cur
        except OSError:
            return None
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def check_space(size: int) -> dict:
    """目标盘（Ollama 模型目录所在盘）剩余空间是否够再放一份。

    返回 ``{"ok", "free", "need", "dir"}`` 或 ``{"ok": False, "error": DeferredMsg, ...}``。
    """
    need = int(int(size or 0) * SPACE_HEADROOM) + SPACE_EXTRA_BYTES
    target = ollama_models_dir()
    probe = _nearest_existing(target)
    if probe is None:
        return {"ok": False, "free": 0, "need": need, "dir": str(target),
                "error": DeferredMsg("找不到 Ollama 模型目录（{dir}），无法确认磁盘空间", dir=str(target))}
    try:
        free = shutil.disk_usage(str(probe)).free
    except OSError as exc:
        return {"ok": False, "free": 0, "need": need, "dir": str(probe),
                "error": DeferredMsg("无法检查磁盘剩余空间（{exc}）；为避免写满磁盘，已取消导入", exc=exc)}
    out = {"ok": free >= need, "free": int(free), "need": need, "dir": str(probe)}
    if not out["ok"]:
        out["error"] = DeferredMsg(
            "Ollama 模型目录所在磁盘空间不足：导入约需 {need}，当前可用 {free}（{dir}）。"
            "请清理磁盘或改小模型后重试",
            need=_mb(need), free=_mb(free), dir=str(probe),
        )
    return out


# ------------------------------------------------------------------ Ollama 调用
def _host() -> str:
    return net_util.normalize_base(config.get_str("AI", "ollama_host", "http://127.0.0.1:11434"))


def _installed_models() -> tuple[bool, list[str], DeferredMsg | str]:
    """GET /api/tags → (available, names, detail)"""
    status, body, _h = net_util.http_get(
        net_util.join_url(_host(), "/api/tags"), timeout=6.0, with_proxy=False
    )
    if status != 200:
        return False, [], (f"HTTP {status}" if status else DeferredMsg("连不上 Ollama"))
    try:
        import json  # noqa: PLC0415 - 仅此处需要

        data = json.loads(body.decode("utf-8", "replace"))
        names = [str(m.get("name") or "") for m in (data.get("models") or []) if m.get("name")]
    except Exception as exc:  # noqa: BLE001
        return False, [], DeferredMsg("返回内容无法解析：{exc}", exc=exc)
    return True, names, ""


def _delete_model(name: str) -> bool:
    """删掉**自己刚建**的模型（试聊不合格时）。失败只记日志，不掩盖原始错误。

    方法要兼容两个时代：Ollama 0.4+ 只认 ``DELETE /api/delete``（POST 会 405），
    更早的版本只认 POST。先 DELETE，405 再退回 POST。
    """
    url = net_util.join_url(_host(), "/api/delete")
    status, data = net_util.http_delete_json(url, {"name": name}, timeout=20.0)
    if status == 405:
        status, data = net_util.http_post_json(url, {"name": name}, timeout=20.0, with_proxy=False)
    if status == 200:
        log.warning("试聊未通过的模型已从 Ollama 删除：%s", name)
        return True
    log.error("删除试聊未通过的模型失败（%s）：HTTP %s %s", name, status, str(data)[:200])
    return False


def _chat_probe(name: str) -> dict:
    """固定短提示跑一次真实对话。返回 ``{"ok", "reply", "detail"}``。"""
    status, data = net_util.http_post_json(
        net_util.join_url(_host(), "/api/chat"),
        {
            "model": name,
            "messages": [{"role": "user", "content": VERIFY_PROMPT}],
            "stream": False,
            "options": {"num_predict": 24, "temperature": 0},
        },
        timeout=VERIFY_TIMEOUT_S, with_proxy=False,
    )
    if status == 0:
        return {"ok": False, "reply": "", "detail": DeferredMsg(
            "试聊超时或连不上 Ollama（等了 {s} 秒）：{err}", s=int(VERIFY_TIMEOUT_S), err=str(data)[:160])}
    if status != 200:
        msg = data.get("error") if isinstance(data, dict) else str(data)
        return {"ok": False, "reply": "", "detail": DeferredMsg(
            "试聊调用失败（HTTP {code}）：{msg}", code=status, msg=str(msg)[:160])}
    reply = ""
    if isinstance(data, dict):
        reply = str(((data.get("message") or {}).get("content"))
                    or data.get("response") or "").strip()
    return {"ok": True, "reply": reply, "detail": ""}


def judge_reply(reply: str) -> dict:
    """判断试聊回复是否「真的像正常对话」。返回 ``{"ok", "reason"}``。

    reason 取值：``""`` / ``empty`` / ``mojibake`` / ``echo`` / ``rambling`` / ``off_target``。
    """
    text = (reply or "").strip()
    if not text:
        return {"ok": False, "reason": "empty"}
    bad = sum(1 for ch in text if ch == "\ufffd" or (ord(ch) < 32 and ch not in "\n\r\t"))
    if bad / max(1, len(text)) > 0.05:
        return {"ok": False, "reason": "mojibake"}
    # 典型「UTF-8 被当 Latin-1 解码」的乱码：西欧重音字母 + 中文标点残片占比过高
    latin = sum(1 for ch in text if 0x80 <= ord(ch) <= 0xFF or 0x2018 <= ord(ch) <= 0x201E)
    if len(text) >= 6 and latin / len(text) > 0.3:
        return {"ok": False, "reason": "mojibake"}
    if any(m in text for m in _ECHO_MARKERS):
        return {"ok": False, "reason": "echo"}
    if len(text) > 200:
        return {"ok": False, "reason": "rambling"}
    if "可用" in text or re.match(r"^(ok|okay|available|yes|yes,? available)\W*$", text, re.I):
        return {"ok": True, "reason": ""}
    # 干净但答非所问的短句：放过，但留一条警告（绝不静默）
    return {"ok": True, "reason": "off_target"}


_HINT = "该 GGUF 可能缺少 chat template，建议换 instruct / chat 版本再试"

#: 试聊不合格的原因 → 可翻译文案（占位符 reply 为回复片段）
_REASON_MSG = {
    "empty": "试聊返回空内容",
    "mojibake": "试聊返回乱码（{reply}）",
    "echo": "模型在复述提示词、不像正常对话（{reply}）",
    "rambling": "回复异常冗长、不像正常对话（前 60 字：{reply}）",
}


def _verify_and_settle(name: str) -> tuple[bool, DeferredMsg | str]:
    """试聊 + 结算。返回 (ok, 失败原因)。

    失败时**先把模型从 Ollama 删掉**再报错 —— 否则它会以「已安装」的身份留在
    前端下拉里冒充可用，这正是本护栏要杜绝的。
    """
    _set(phase="verifying", percent=92, detail="试聊验证中…")
    probe = _chat_probe(name)
    if not probe["ok"]:
        detail_msg = probe["detail"]
        _delete_model(name)
        _record_error(DeferredMsg(
            "导入的模型未通过验证：{detail} —— {hint}（已从 Ollama 删除，避免它在模型列表里冒充可用）",
            detail=detail_msg, hint=DeferredMsg(_HINT)))
        return False, detail_msg
    verdict = judge_reply(probe["reply"])
    if not verdict["ok"]:
        snippet = (probe["reply"] or "")[:60].replace("\n", " ") or DeferredMsg("（空）")
        _delete_model(name)
        why = DeferredMsg(_REASON_MSG.get(verdict["reason"], verdict["reason"]), reply=snippet)
        _record_error(DeferredMsg(
            "导入的模型未通过验证：{why} —— {hint}（已从 Ollama 删除，避免它在模型列表里冒充可用）",
            why=why, hint=DeferredMsg(_HINT)))
        return False, why
    if verdict["reason"] == "off_target":
        log.warning("试聊回复与预期不同（模型 %s）：%s", name, (probe["reply"] or "")[:80])
    return True, ""


# ---------------------------------------------------------------- create（CLI）
def _iter_pipe_lines(stream):
    """把子进程输出切成「行」—— ``\\r`` 与 ``\\n`` 都当分隔符。

    ollama 的进度条在非 TTY 下仍可能用 ``\\r`` 刷新；只按 ``\\n`` 读会卡住，
    前端就会看到「一直 0%」。
    """
    buf = b""
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        buf += chunk
        while True:
            idxs = [i for i in (buf.find(b"\r"), buf.find(b"\n")) if i >= 0]
            if not idxs:
                break
            i = min(idxs)
            line, buf = buf[:i], buf[i + 1:]
            yield line.decode("utf-8", "replace")
    if buf:
        yield buf.decode("utf-8", "replace")


_PCT = re.compile(r"(\d{1,3})\s*%")
#: ANSI 控制序列（ollama 的进度条会发 ``\x1b[K`` 之类的清行码）—— 必须剥掉，
#: 否则会原样出现在前端进度文字里，显示成「parsing GGUF \u001b[K」
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)")


def _progress_from_line(line: str) -> tuple[int, str] | None:
    """把一行 ollama 输出映射成 (percent, detail)。无法识别返回 None。

    区间按 **create 的真实阶段顺序**分配：copying（10→60）→ parsing GGUF（65）
    → using existing layer（80）→ writing manifest（95）。调用方还会做一次「只
    增不减」的兜底 —— ollama 各版本输出顺序并不完全一致，进度条倒退比没有
    进度条更像 bug。
    """
    s = line.strip()
    if not s:
        return None
    low = s.lower()
    if "gathering model components" in low:
        return 5, s
    m = _PCT.search(s)
    if m:
        p = max(0, min(100, int(m.group(1))))
        return 10 + int(p * 0.5), s
    if "parsing gguf" in low:
        return 65, s
    if "using existing layer" in low:
        return 80, s
    if "writing manifest" in low:
        return 95, s
    if "success" in low:
        return 99, s
    if "copying file" in low or "transferring" in low:
        return 15, s
    return None


def _create_via_cli(name: str, modelfile_text: str, exe: Path) -> tuple[bool, str]:
    """调 ``ollama create <name> -f Modelfile`` 并流式更新进度。返回 (ok, detail)。"""
    # Modelfile 写进数据目录而不是系统临时目录：本项目「拔盘即走、不在宿主机
    # 留东西」的便携红线（data/ 本来就在盘上），而且不会被系统清理任务半路删掉。
    tmpdir = paths.DATA_DIR / "temp_gguf_import"
    try:
        tmpdir.mkdir(parents=True, exist_ok=True)
        mf = tmpdir / f"Modelfile-{name}"
        mf.write_text(modelfile_text, encoding="utf-8")
        env = dict(os.environ)
        # CLI 默认连 127.0.0.1:11434；用户改了 ollama_host 时必须让它跟着走，
        # 否则「建在了另一个 Ollama 上」—— 列表里当然看不到。
        env["OLLAMA_HOST"] = re.sub(r"^https?://", "", _host())
        cmd = [str(exe), "create", name, "-f", str(mf)]
        log.info("开始 ollama create：%s（源 Modelfile=%s）", name, mf)
        proc = subprocess.Popen(  # noqa: S603 - 可执行文件来自 find_ollama_exe，参数固定
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0, env=env,
            **proc_mod.silent_kwargs(),   # 无控制台运行时不闪黑框（见 proc.py 的取舍说明）
        )
        killed = {"v": False}

        def _kill():
            killed["v"] = True
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass

        timer = threading.Timer(CREATE_TIMEOUT_S, _kill)
        timer.daemon = True
        timer.start()
        tail: list[str] = []
        try:
            for raw_line in _iter_pipe_lines(proc.stdout):
                line = _ANSI.sub("", raw_line).strip()
                if not line:
                    continue
                tail.append(line)
                del tail[:-8]
                mapped = _progress_from_line(line)
                if mapped:
                    # 只增不减：不同 Ollama 版本的输出顺序不一致，倒退的进度条
                    # 会被用户当成「又从头开始了」
                    with _GUARD:
                        pct = max(int(_STATE["percent"]), mapped[0])
                    _set(percent=pct, detail=mapped[1].strip()[:200])
            rc = proc.wait()
        finally:
            timer.cancel()
        if killed["v"]:
            return False, DeferredMsg("ollama create 超时（>{s} 秒）被终止", s=int(CREATE_TIMEOUT_S))
        if rc != 0:
            last = (tail[-1].strip() if tail else "")[:400]
            return False, (last or DeferredMsg("ollama create 异常退出（退出码 {rc}）", rc=rc))
        return True, ""
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _create_via_http(name: str, modelfile_text: str) -> tuple[bool, str]:
    """没有 ollama 可执行文件时的兜底（远程 / 精简安装）：走 /api/create。

    一次性请求、无逐段进度（前端只能看到「正在导入」+ 已用秒数）。
    """
    log.info("使用 HTTP /api/create 导入（未找到 ollama 可执行文件）")
    status, data = net_util.http_post_json(
        net_util.join_url(_host(), "/api/create"),
        {"name": name, "modelfile": modelfile_text, "stream": False},
        timeout=CREATE_TIMEOUT_S, with_proxy=False,
    )
    if status == 200:
        return True, ""
    msg = data.get("error") if isinstance(data, dict) else str(data)
    return False, DeferredMsg("ollama create 失败（HTTP {code}）：{msg}",
                              code=status, msg=str(msg)[:300])


# --------------------------------------------------------------------- 任务编排
def submit(raw_path) -> dict:
    """校验并入队。返回 ``{"ok", "code", "message"}``；``code`` 便于测试与前端区分。

    * ``invalid``   —— 路径校验没过（消息已可读，含具体原因）
    * ``duplicate`` —— 同一文件正在导入
    * ``busy``      —— 已有另一个导入在跑（单 worker，避免两条 4.4GB 拷贝互相抢盘）
    * ``stopping``  —— 正在安全退出
    * ``queued``    —— 成功入队
    """
    info = inspect_path(raw_path)
    if not info.get("ok"):
        return {"ok": False, "code": "invalid", "message": info["error"]}

    path = Path(info["path"])
    key = os.path.normcase(str(path))
    with _GUARD:
        if _STOPPING:
            return {"ok": False, "code": "stopping",
                    "message": DeferredMsg("程序正在退出，未开始导入")}
        if key in _INFLIGHT:
            return {"ok": False, "code": "duplicate",
                    "message": DeferredMsg("该文件正在导入中，请等待它完成（重复触发不会加速）")}
        if _BUSY.is_set():
            return {"ok": False, "code": "busy",
                    "message": DeferredMsg("已有导入任务正在进行，请等它结束后再试")}
        _INFLIGHT.add(key)
        _BUSY.set()
        _STATE.update({"active": True, "phase": "checking", "name": info["name"],
                       "path": str(path), "percent": 2, "detail": "检查文件与磁盘空间…",
                       "started_at": time.time(), "finished_at": 0.0, "last_ok": None})
        _QUEUE.put(path)
        _ensure_worker_locked()
    log.info("GGUF 导入已入队：%s → %s", path, info["name"])
    return {"ok": True, "code": "queued", "message": DeferredMsg("已开始导入：{name}", name=info["name"]),
            "name": info["name"]}


def _ensure_worker_locked() -> None:
    global _WORKER
    if _WORKER is not None and _WORKER.is_alive():
        return
    _WORKER = threading.Thread(target=_loop, name="gguf-import", daemon=True)
    _WORKER.start()


def _loop() -> None:
    log.info("GGUF 导入 worker 已启动（单 worker，daemon）")
    while True:
        path = _QUEUE.get()
        try:
            _run_one(path)
        except Exception as exc:  # noqa: BLE001 - worker 绝不能被单次失败打死
            _record_error(DeferredMsg("导入过程异常：{exc}", exc=exc))
            log.exception("GGUF 导入异常")
            _set(phase="failed", percent=0, detail=str(exc)[:200])
        finally:
            with _GUARD:
                _INFLIGHT.clear()
                _STATE["active"] = False
                _STATE["finished_at"] = time.time()
            _BUSY.clear()
            _QUEUE.task_done()


def _run_one(path: Path) -> None:
    size = path.stat().st_size
    info = inspect_path(str(path))
    if not info.get("ok"):
        _record_error(info["error"])
        _set(phase="failed", percent=0, detail="文件校验失败")
        return

    space = check_space(size)
    if not space["ok"]:
        _record_error(space["error"])
        _set(phase="failed", percent=0, detail="磁盘空间不足")
        return

    available, names, why = _installed_models()
    if not available:
        _record_error(DeferredMsg("连不上 Ollama（{why}）—— 请先启动 Ollama 再导入", why=why))
        _set(phase="failed", percent=0, detail="Ollama 不可达")
        return

    base = info["name"]
    reuse = base.lower() in {n.lower() for n in names}
    name = base
    if reuse:
        # 名字由「路径 + mtime」派生 → 同名即同源：直接复用，不覆盖、不重复拷一份
        log.info("同名模型已存在，复用而不重建：%s", base)
        _set(name=base, phase="verifying", percent=90,
             detail="同名模型已存在，跳过拷贝，直接试聊验证…")
    else:
        name = unique_name(base, names)
        _set(name=name, phase="creating", percent=8, detail="正在导入（拷贝模型文件）…")
        modelfile = build_modelfile(path)
        log.info("Modelfile:\n%s", modelfile)
        exe = find_ollama_exe()
        if exe is not None:
            ok, detail = _create_via_cli(name, modelfile, exe)
        else:
            ok, detail = _create_via_http(name, modelfile)
        if not ok:
            _record_error(DeferredMsg("ollama create 失败：{detail}", detail=detail))
            _set(phase="failed", percent=0, detail=detail)
            return

    ok, why_fail = _verify_and_settle(name)
    if not ok:
        _set(phase="failed", percent=0, detail=DeferredMsg("试聊未通过：{why}", why=why_fail))
        return

    with _GUARD:
        _STATE["results"].insert(0, {"name": name, "path": str(path), "size": int(size),
                                     "at": time.time()})
        del _STATE["results"][5:]
        _STATE["last_ok"] = name
    _set(phase="done", percent=100, detail=DeferredMsg("导入完成：{name}", name=name))
    log.info("GGUF 导入成功：%s（%s，%s）", name, path, _mb(size))
