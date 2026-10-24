"""后端文案的轻量双语层（零依赖，按请求语言输出）。

## 为什么用「中文原文作 key」

与前端 ``app/web/app.js`` 的 ``I18N_EN`` 保持同一套约定：中文原文即 key，
缺失翻译自然回退中文。这样：

* 中文输出**逐字节不变**（``t()`` 在 zh 下原样返回，仅按需填充占位符）；
* 新增文案忘了翻译也不会崩，最差是英文界面里出现一句中文（graceful）；
* 不需要 ID 体系，grep 中文原文就能定位所有调用点。

## 为什么用 ContextVar

``ThreadingHTTPServer`` 每个请求一个线程，语言是**请求级**状态。
``app/server.py`` 在请求线程最开头按 ``X-Kavira-Lang`` 头 ``set_lang()``，
之后同线程内所有 ``t()`` 都读得到；线程结束即丢弃，不污染其它请求。

后台工作线程（迁移 / 重建）不会自动继承上下文，调用方需显式把语言传进去
（见 ``api/datadir.py`` 的线程包装），否则按默认 ``zh`` 输出（安全回退）。
"""
from __future__ import annotations

from contextvars import ContextVar

#: 当前请求语言（"zh" / "en"）；默认中文
_LANG: ContextVar[str] = ContextVar("kavira_lang", default="zh")


def set_lang(v: str | None) -> str:
    """设置当前上下文语言：``en*`` → en，其它一律 zh。返回生效值。"""
    lang = "en" if str(v or "").strip().lower().startswith("en") else "zh"
    _LANG.set(lang)
    return lang


def get_lang() -> str:
    """当前上下文语言（"zh" / "en"）。"""
    return _LANG.get()


#: 中文原文 → 英文（键里可带 ``{占位符}``，英文值必须使用同名占位符）
EN: dict[str, str] = {
    # ---- 通用 ----
    "缺少 path 参数": "Missing path parameter",
    "非法路径": "Invalid path",
    "越权访问被拒绝": "Access denied",
    "文件不存在": "File not found",
    "资源不存在": "Resource not found",
    "接口不存在": "Endpoint not found",
    "读取失败：{exc}": "Read failed: {exc}",
    "写入失败：{exc}": "Write failed: {exc}",
    "无法生成预览：{exc}": "Cannot generate preview: {exc}",

    # ---- 笔记 / 原件 / 证据 ----
    "该笔记没有留存原件": "No original file is kept for this note",
    "缺少 path 或 parent_id 参数": "Missing path or parent_id parameter",
    "证据块不存在（索引可能已重建）": "Evidence block not found (the index may have been rebuilt)",
    "证据块与该笔记不匹配": "Evidence block does not match this note",
    "单次最多导入 200 个文件": "At most 200 files per import",
    "base64 解码失败：{exc}": "base64 decoding failed: {exc}",
    "导入完成：成功 {ok} / {total}": "Import complete: {ok} of {total} succeeded",

    # ---- Collections ----
    "类目数据损坏，未做任何修改（{exc}）":
        "Collection data is corrupted; nothing was changed ({exc})",
    "类目不存在": "Collection not found",
    "已创建类目": "Collection created",
    "已重命名": "Renamed",
    "已删除类目（文档不受影响）": "Collection deleted (documents are unaffected)",
    "已更新分类": "Collections updated",
    "已更新标题": "Title updated",
    "已移入回收站": "Moved to trash",
    "已永久删除": "Permanently deleted",
    "已恢复": "Restored",
    "缺少 doc_id 或 path": "Missing doc_id or path",
    "缺少 doc_id": "Missing doc_id",
    "类目名不能为空": "The collection name cannot be empty",
    "找不到该文档的笔记路径（可能已被清理）":
        "Note path not found for this document (it may already have been cleaned up)",
    "原件路径越权访问被拒绝": "Access to the original file path denied",

    # ---- 功能门禁 ----
    "此功能需激活后使用。请到「设置 → 产品授权」完成激活。":
        "This feature requires activation. Activate it under Settings → Product License.",

    # ---- 问答 / AI ----
    "服务尚未初始化完成": "The service is not ready yet",
    "target 仅支持 ollama / api": "target supports only ollama / api",

    # ---- 资料目录 ----
    "打包失败": "Packaging failed",
    "打包失败：{exc}": "Packaging failed: {exc}",
    "预检通过": "Precheck passed",
    "请填写目标目录": "Please enter a target directory",
    "已有迁移任务在进行中": "A migration is already in progress",
    "资料迁移任务已启动，请留意进度提示":
        "Data migration started; watch the progress indicator",
    "当前没有可用的资料目录": "No data directory is available",
    "无法创建临时目录（可能只读）：{exc}":
        "Cannot create a temporary directory (possibly read-only): {exc}",

    # ---- 诊断 ----
    "向量嵌入源不可用，已退化为纯 FTS5 词法检索":
        "Vector embedding source unavailable; degraded to pure FTS5 lexical retrieval",

    # ---- 配置 / 系统 ----
    "配置已保存": "Configuration saved",
    "索引全量重建任务已在后台启动": "Full index rebuild started in the background",
    "向量索引重建任务已在后台启动": "Vector index rebuild started in the background",
    "正在安全退出，请稍候…": "Shutting down safely, please wait…",
    "服务内部错误：{exc}": "Internal server error: {exc}",
    "请求体过大": "Request body too large",
    "已拒绝": "Rejected",
    "请求失败：{exc}": "Request failed: {exc}",
    "（{detail}）": " ({detail})",

    # ---- 传输层安全闸门 ----
    "请求的 Host 不被允许：本服务只接受本机回环地址访问":
        "Host not allowed: this service only accepts loopback access",
    "已拒绝来自其它网站的跨站请求": "Cross-site request from another website rejected",
    "已拒绝跨源请求：本服务不对外开放跨域访问":
        "Cross-origin request rejected: this service does not expose cross-origin access",
    "变更类接口只接受 application/json": "Mutating endpoints accept only application/json",

    # ---- 网页抓取的安全拒绝原因（net_guard.REASON_TEXT）----
    "只支持 http / https 协议": "Only http / https URLs are supported",
    "URL 格式不合法": "The URL format is invalid",
    "URL 不允许携带用户名或密码": "URLs must not contain a username or password",
    "端口不合法": "Invalid port",
    "URL 缺少主机名": "The URL is missing a host name",
    "域名无法解析": "The domain name could not be resolved",
    "请求失败": "Request failed",
    "该地址不是公网地址，已拒绝访问（如需抓取内网请显式开启 allow_private_network）":
        "This address is not public, so access was denied (enable allow_private_network "
        "explicitly to capture intranet hosts)",
    "该域名同时解析出公网与内网地址，出于安全考虑已拒绝":
        "This domain resolves to both public and private addresses and was rejected for "
        "security reasons",
    "重定向次数超过 {max} 次": "More than {max} redirects",
    "检测到重定向环路": "Redirect loop detected",
    "重定向响应缺少 Location": "The redirect response is missing Location",

    # ---- 导入文件的安全拒绝原因（file_guard.REASON_TEXT）----
    "文件名或压缩包内路径试图跳出允许的目录":
        "The file name or archive entry path tries to escape the allowed directory",
    "文件名不合法": "Invalid file name",
    "文件超过大小上限": "The file exceeds the size limit",
    "压缩包内文件数量过多": "Too many files in the archive",
    "压缩包内单个文件过大": "An entry in the archive is too large",
    "压缩包解压后总量过大": "The archive expands to an excessive total size",
    "压缩包压缩比异常（疑似压缩炸弹）":
        "Abnormal archive compression ratio (possible zip bomb)",
    "压缩包含有符号链接等特殊文件，已拒绝":
        "The archive contains special entries such as symbolic links; rejected",
    "压缩包内存在重复的同名条目，已拒绝":
        "The archive contains duplicate entries with the same name; rejected",
    "压缩包内条目名不合法": "An entry name in the archive is invalid",
    "文件不合法": "Invalid file",

    # ---- 诊断（issues / chat.reason）----
    "资料库目录不存在": "The library directory does not exist",
    "顶层不是 JSON 对象": "the top level is not a JSON object",
    "library.json 损坏：{exc}；可用修复功能显式重建该文件":
        "library.json is corrupted: {exc}; the repair action can rebuild it explicitly",
    "检测到旧版资料库（无 manifest），程序已按 Data Format 0 识别，打开时会自动接管为 V1":
        "Legacy library detected (no manifest); it is treated as Data Format 0 and taken "
        "over as V1 when opened",
    "该目录不是 Kavira 资料库，程序不会改动它":
        "This directory is not a Kavira library; the program will not modify it",
    "资料格式版本 {dv} 高于当前程序支持的 1，请升级程序":
        "Data format version {dv} is newer than the supported version 1; please upgrade "
        "the program",
    "索引数据库不存在，可从资料库重新建立索引":
        "The index database is missing; it can be rebuilt from the library",
    "索引数据库无法打开（可整库重建）：{exc}":
        "The index database cannot be opened (the database can be rebuilt): {exc}",
    "索引表 {table} 缺失，可从资料库重建":
        "Index table {table} is missing; it can be rebuilt from the library",
    "全文索引缺失，可从资料库重建":
        "The full-text index is missing; it can be rebuilt from the library",
    "向量索引缺失，可从资料库重建":
        "The vector index is missing; it can be rebuilt from the library",
    "索引完整性检查未通过：{qc}": "Index integrity check failed: {qc}",
    "无结果": "no result",
    "索引完整性检查失败：{exc}": "Index integrity check error: {exc}",
    "索引数据库无法读取（可整库重建）：{exc}":
        "The index database cannot be read (the database can be rebuilt): {exc}",
    "运行时 AI 状态读取失败（不影响诊断）：{exc}":
        "Failed to read runtime AI status (diagnostics are unaffected): {exc}",
    "Ollama 探测失败（不影响诊断）：{exc}":
        "Ollama probe failed (diagnostics are unaffected): {exc}",
    "未探测到可用的本地对话模型": "No usable local chat model was detected",
    "未提供运行时状态（静态诊断）": "No runtime state was provided (static diagnostics)",
    "版本信息读取失败：{exc}": "Failed to read version info: {exc}",
    "资料库诊断失败：{exc}": "Library diagnostics failed: {exc}",
    "数据库诊断失败：{exc}": "Database diagnostics failed: {exc}",
    "AI 配置读取失败：{exc}": "Failed to read AI configuration: {exc}",

    "索引结构已升级，但全量重建失败，请到「设置」页手动点一次「全量重建索引」":
        "The index structure was upgraded but the full rebuild failed. Open Settings and "
        "run Full index rebuild once.",
    "向量索引自愈未生效，请到「设置」点一次「全量重建索引」":
        "Vector index self-healing did not take effect. Open Settings and run "
        "Full index rebuild once.",
    "向量索引自动重建失败，请到「设置」手动点一次「全量重建索引」":
        "Automatic vector index rebuild failed. Open Settings and run Full index rebuild once.",
    "索引已按新结构重建：{indexed} 篇 / {chunks} 切片":
        "Index rebuilt for the new structure: {indexed} documents / {chunks} chunks",
    "索引已自动重建：{indexed} 篇 / {chunks} 切片":
        "Index rebuilt automatically: {indexed} documents / {chunks} chunks",
    "已自动启动本地 Ollama（等待 {s}s 后就绪）":
        "Started local Ollama automatically (ready after {s}s)",
    "未能自动启动本地 Ollama：{reason}":
        "Could not start local Ollama automatically: {reason}",

    # ---- 本地 Ollama 自启动原因（ollama_runtime.reason）----
    "已在运行": "already running",
    "未启用自动启动": "automatic start is disabled",
    "非 Windows 平台，仅探测不自动拉起": "not Windows: probe only, no auto-start",
    "未找到 ollama 可执行文件（PATH 与官方安装目录均无）":
        "ollama executable not found (neither PATH nor the official install directory)",
    "拉起 ollama serve 失败：{exc}": "failed to launch ollama serve: {exc}",
    "已自动启动（等待 {s}s）": "started automatically (waited {s}s)",
    "拉起后等待 {s}s 仍不可达": "still unreachable after waiting {s}s",

    # ---- 本地 Ollama 就绪状态（llm._STATE_REASON / ollama_detail）----
    "未检测到本地 Ollama 运行时": "No local Ollama runtime detected",
    "Ollama 已启动，但本机尚未安装任何模型":
        "Ollama is running, but no model is installed on this machine",
    "本机已有模型，但尚未选择用哪个模型对话":
        "Models are available, but no chat model has been selected yet",
    "原来选择的模型在本机已不存在":
        "The previously selected model no longer exists on this machine",
    "该模型不支持对话（通常是嵌入/向量模型）":
        "This model does not support chat (it is usually an embedding/vector model)",
    "已选择模型且本机可用": "Model selected and available on this machine",
    "{reason}：{model}": "{reason}: {model}",
    "{reason}（本机发现 {n} 个）": "{reason} ({n} found on this machine)",
    "尚未探测到本地 Ollama（后台探测中）":
        "Local Ollama not detected yet (probing in the background)",
    "连接失败（HTTP {code}）": "Connection failed (HTTP {code})",
    "连不上 Ollama，请确认它已启动（命令行执行 ollama serve）":
        "Cannot reach Ollama; make sure it is running (run ollama serve in a terminal)",
    "在线，发现 {n} 个模型": "Online, models found: {n}",
    "返回内容无法解析": "The response could not be parsed",

    # ---- 索引结构迁移（migrations.message）----
    "索引结构一致（{v}）": "Index structure is up to date ({v})",
    "无索引，将按当前结构新建（{v}）":
        "No index yet; it will be created with the current structure ({v})",
    "索引结构已更新": "Index structure updated",
    "索引结构无法识别": "Index structure not recognized",
    "未知": "unknown",
    "{reason}（{old} → {new}），已备份旧索引并清空，将从 data/notes 全量重建":
        "{reason} ({old} → {new}); the old index was backed up and cleared, and will be "
        "rebuilt from data/notes",

    # ---- 抓取时的资源本地化说明（archiver notes）----
    "未启用资源本地化 → 该页离线时样式与图片不可用（可在 config.ini 打开 save_assets）":
        "Resource localization is disabled → styles and images are unavailable offline "
        "(enable save_assets in config.ini)",
    "已把 {n} 个资源存档到本地（{kb} KB{reuse}，用时 {s}s），原版预览可离线还原":
        "Archived {n} resources locally ({kb} KB{reuse}, took {s}s); the original view "
        "works offline",
    "，{n} 个复用已有": ", {n} reused",
    "{n} 个资源未能存档（超限 {large}、预算用尽 {budget}、类型不适 {kind}、抓取失败 {failed}），已用占位代替以保证离线时不发起任何外部请求":
        "{n} resources could not be archived (too large {large}, budget exhausted {budget}, "
        "unsupported type {kind}, fetch failed {failed}); placeholders are used so nothing "
        "is requested from the network when offline",
    "{n} 个样式表未能存档，该页版式可能不完整":
        "{n} stylesheets could not be archived; the page layout may be incomplete",
    "{n} 个图标（favicon 等）未能存档，已删除以避免浏览时外发请求":
        "{n} icons (favicons and the like) could not be archived and were removed to avoid "
        "outgoing requests while browsing",
    "已省略 {n} 个外部脚本（预览沙箱禁用脚本，存档中不再保留）":
        "Omitted {n} external scripts (the preview sandbox disables scripts; they are not "
        "kept in the archive)",
    "{n} 个资源被安全策略拦下（非公网地址或非法协议），已用占位符替代{sample}":
        "{n} resources were blocked by the security policy (non-public address or invalid "
        "protocol); placeholders were used instead{sample}",
    "：{list}": ": {list}",

    # ---- 抓取时的资源本地化说明结束 ----

    # ---- 授权（离线激活）----
    "尚未激活。": "Not activated yet.",
    "已激活。": "Activated.",
    "激活码格式无法识别，请核对后重新输入。":
        "Unrecognized activation code format. Check it and try again.",
    "激活码无效或已被篡改。": "The activation code is invalid or has been tampered with.",
    "该激活码不属于本产品。": "This activation code does not belong to this product.",
    "此激活码不属于当前设备。": "This activation code does not belong to this device.",
    "此激活码已过期。": "This activation code has expired.",
    "本机缺少签名校验组件，暂时无法验证授权。":
        "The signature verification component is missing on this machine; "
        "the license cannot be verified right now.",
    "激活信息保存失败：{exc}": "Failed to save activation data: {exc}",
    "已清除本机激活。": "Activation cleared on this machine.",
    "本机原本未激活。": "This machine was not activated.",

    # ---- 抓取 / 导入结果 ----
    "仅支持 http/https 开头的标准 URL":
        "Only standard URLs starting with http/https are supported",
    "该网页已经保存过：{title}（可在弹窗里选择打开已有 / 更新已有 / 另存为新版本）":
        "This page has already been saved: {title} "
        "(choose open existing / update existing / save as a new version in the dialog)",
    "安全策略已拒绝该地址：{exc}": "The address was rejected by the security policy: {exc}",
    "页面抓取失败：{err}": "Failed to fetch the page: {err}",
    "空响应": "empty response",
    "抓取失败": "Fetch failed",
    "网络出口未就绪": "Network egress is not ready",
    "未找到本机 Chrome/Edge 可执行文件": "No local Chrome/Edge executable found",
    "抓取成功": "Capture succeeded",
    "该页面为前端动态渲染，仅保留快照，建议通过复制粘贴方式记录重要内容":
        "This page renders on the client side, so only a snapshot was kept. "
        "Consider copying and pasting the key content.",
    "资源本地化失败，该页离线时样式与图片可能不完整":
        "Resource localization failed; styles and images may be incomplete offline",
    "（索引写入失败：{exc}）": " (index write failed: {exc})",
    "（索引异常：{exc}）": " (index error: {exc})",
    "（后台索引任务提交失败：{exc}）":
        " (failed to queue the background index job: {exc})",

    # ---- 后台索引进度（/api/index/status）----
    "索引已完成": "Indexing complete",
    "正在索引：{current}（剩余 {n} 个文件）":
        "Indexing {current} ({n} files left)",
    "等待索引：剩余 {n} 个文件": "Waiting to index: {n} files left",
    "内容为空，未保存": "Content is empty; nothing was saved",
    "笔记已保存": "Note saved",
    "缺少文件名": "Missing file name",
    "{name}：不支持隐藏文件": "{name}: hidden files are not supported",
    "已导入 {name}{note}": "Imported {name}{note}",
    "（{kind} → Markdown）": " ({kind} → Markdown)",

    # ---- 资料迁移预检 / 进度 ----
    "目标目录就是当前资料目录，无需迁移。":
        "The target is already the current data directory; no migration is needed.",
    "资料目录不能放在程序安装目录里（程序重装/回滚会连带影响资料）。":
        "The data directory cannot live inside the program installation directory "
        "(reinstall/rollback would affect your data).",
    "目标目录是当前资料目录的上级 —— 会把整个资料目录套进更深的层级。":
        "The target is a parent of the current data directory, "
        "which would nest the data one level deeper.",
    "目标目录在当前资料目录内部，形成嵌套。":
        "The target is inside the current data directory, which would create nesting.",
    "目标路径已存在且不是目录。": "The target path exists but is not a directory.",
    "目标目录里已经有一份资料库，为避免混淆已中止。请换一个空目录，或先手动整理再迁移。":
        "The target directory already holds a library, so the migration was aborted to "
        "avoid confusion. Choose an empty directory, or tidy it up first.",
    "目标目录已存在且不为空 —— 不会为了腾地方删除里面的文件。请选择一个空目录。":
        "The target directory exists and is not empty — files are never deleted to make "
        "room. Choose an empty directory.",
    "目标位置没有写入权限（可能是写保护的 U 盘或只读介质）：{path}":
        "The target is not writable (write-protected USB drive or read-only media?): {path}",
    "目标位置不可达：找不到驱动器 {anchor}（请确认磁盘/U 盘已接好）":
        "Target unreachable: drive {anchor} not found "
        "(make sure the disk/USB drive is connected)",
    "目标位置剩余空间不足：需要约 {need}，可用 {free}（额外预留了 5% 余量）。":
        "Not enough free space at the target: about {need} needed, {free} available "
        "(an extra 5% is reserved).",
    "无法读取目标位置的剩余空间，请自行确认磁盘够用。":
        "Cannot read the free space at the target; please confirm the disk has room.",
    "目标在 {dst} 盘、程序在 {app} 盘 —— 程序与资料分离。拔掉该盘后程序仍能启动，但看不到资料。":
        "The target is on drive {dst} and the program on drive {app} — program and data "
        "are separated. Unplugging that drive still lets the program start, but your data "
        "will not be visible.",
    "正在校验目标目录…": "Validating the target directory…",
    "正在停止写入（做检查点、关闭索引）…": "Stopping writes (checkpoint, closing the index)…",
    "正在复制资料…": "Copying data…",
    "正在复制资料… {done}/{total} 个文件": "Copying data… {done}/{total} files",
    "临时目录已存在，请稍后重试": "The temporary directory already exists; try again later",
    "正在逐文件校验副本…": "Verifying the copy file by file…",
    "副本校验未通过，已保留原位置": "Copy verification failed; the original location was kept",
    "正在切换到新目录…": "Switching to the new directory…",
    "正在按新目录重新打开资料库…": "Reopening the library at the new directory…",
    "重新打开后文档数不一致，已回退": "Document count mismatch after reopening; rolled back",
    "迁移完成": "Migration complete",
    "资料已迁移到新目录，旧目录已原样保留。":
        "Data migrated to the new directory; the old directory is kept as is.",
    "迁移失败：{exc}": "Migration failed: {exc}",
    "迁移无法开始：{exc}": "Migration could not start: {exc}",
    "已中止，资料保持原样（仍在 {src}）。原因：{reason}":
        "Aborted; data is unchanged (still at {src}). Reason: {reason}",
    "副本校验未通过：{detail}": "Copy verification failed: {detail}",
    "临时目录已存在：{path}": "The temporary directory already exists: {path}",
    "新目录打开异常：原 {old} 篇 / 新 {new} 篇":
        "Reopening at the new directory failed: {old} documents before / {new} after",
    "确认新目录资料无误后，可自行删除旧目录释放空间。":
        "Once you have verified the new directory, you can delete the old one to free space.",
    "文件数量不一致（源 {s} / 副本 {d}）": "File count mismatch (source {s} / copy {d})",
    "总字节不一致（源 {s} / 副本 {d}）": "Total size mismatch (source {s} / copy {d})",
    "抽样读取失败：{name}（{exc}）": "Sampled read failed: {name} ({exc})",
    "内容不一致：{name}": "Content mismatch: {name}",

    # ---- 库规模档位 ----
    "暂无索引内容": "No indexed content yet",
    "余量充足（{n} 切片，检索通常快于 0.3 秒）":
        "Plenty of headroom ({n} chunks; retrieval usually takes under 0.3s)",
    "规模较大（{n} 切片，问答检索约 0.3~1.5 秒）":
        "Large library ({n} chunks; Q&A retrieval takes about 0.3–1.5s)",
    "接近上限（{n} 切片，检索可能要数秒）。建议按主题拆分多个资料库，或优先使用关键词搜索":
        "Near the limit ({n} chunks; retrieval may take several seconds). Consider "
        "splitting into topic libraries, or preferring keyword search",

    # ---- 检索告警 ----
    "查询词均为虚词或语气词，请补充实词（人名 / 术语 / 关键词）后再试":
        "The query consists only of function words; add content words "
        "(names / terms / keywords) and try again",
    "未找到字面匹配：知识库中没有出现查询实词的内容（已避免用语义相近但无关的文档冒充引用来源）":
        "No literal match: no content in the library contains the query's content words "
        "(semantically similar but unrelated documents are not passed off as sources)",
    "向量召回路未启用，本次为纯 FTS5 词法检索":
        "The vector retrieval path is disabled; this run is pure FTS5 lexical retrieval",

    # ---- 格式转换（导入失败原因 / 告警）----
    "内容超过 {n} 万字，已截断": "Content exceeds {n} × 10,000 characters and was truncated",
    "按 {enc} 解码": "Decoded as {enc}",
    "JSON 解析失败，按原文保存（{exc}）": "JSON parsing failed; saved as plain text ({exc})",
    "XML 结构异常，按原文保存（{exc}）": "XML structure is invalid; saved as plain text ({exc})",
    "{name} 内容为空": "{name} is empty",
    "表格超过 3000 行，仅保留前 3000 行": "The table exceeds 3000 rows; only the first 3000 are kept",
    "RTF 为有损转换（仅提取可见文字，不保留样式）":
        "RTF conversion is lossy (visible text only, no styling)",
    "{name} 中未抽取到正文": "No body text could be extracted from {name}",
    "正文抽取降级为 {extractor}": "Body extraction fell back to {extractor}",
    "{name} 中未找到可读正文": "No readable body text found in {name}",
    "{name} 邮件正文为空": "The email body in {name} is empty",
    "{name} 不是有效的 .docx（可能后缀被改过）":
        "{name} is not a valid .docx (the extension may have been changed)",
    "{name} 中找不到 word/document.xml": "word/document.xml not found in {name}",
    "document.xml 解析失败：{exc}": "Failed to parse document.xml: {exc}",
    "文档结构异常（缺少 body）": "Unexpected document structure (missing body)",
    "{name} 未提取到文字（可能是纯图片文档，需 OCR）":
        "{name} contains no extractable text (it may be an image-only document needing OCR)",
    "{name} 中没有幻灯片": "No slides found in {name}",
    "演示稿含 {n} 页备注，已一并提取": "The deck has {n} note pages, which were extracted too",
    "{name} 不是有效的 .pptx（可能后缀被改过）":
        "{name} is not a valid .pptx (the extension may have been changed)",
    "{name} 未提取到文字（可能是纯图片幻灯片，需 OCR）":
        "{name} contains no extractable text (it may be image-only slides needing OCR)",
    "{name} 中没有工作表": "No worksheets found in {name}",
    "「{display}」超过 {limit} 行，仅保留前 {limit} 行":
        "\"{display}\" exceeds {limit} rows; only the first {limit} are kept",
    "{name} 未提取到数据（可能全是空表）":
        "{name} contains no extractable data (the sheets may all be empty)",
    "{name} 不是有效的 .xlsx（可能后缀被改过）":
        "{name} is not a valid .xlsx (the extension may have been changed)",
    "{name} 中找不到 OPF 清单": "No OPF manifest found in {name}",
    "{name} 不是有效的 .epub": "{name} is not a valid .epub",
    "EPUB 清单解析失败：{exc}": "Failed to parse the EPUB manifest: {exc}",
    "{name} 未提取到章节正文": "No chapter text could be extracted from {name}",
    "未安装 PDF 解析库，无法读取 {name}。请在 U 盘根目录执行：{cmd}（或重新执行 python setup_runtime_windows.py）":
        "The PDF parsing library is not installed, so {name} cannot be read. Run this in "
        "the USB drive root: {cmd} (or re-run python setup_runtime_windows.py)",
    "{name} 是加密 PDF，无法解析": "{name} is an encrypted PDF and cannot be parsed",
    "第 {i} 页解析失败（{exc}）": "Failed to parse page {i} ({exc})",
    "PDF 解析失败：{exc}": "PDF parsing failed: {exc}",
    "{name} 未提取到文字 —— 大概率是扫描件/图片型 PDF，需要 OCR（本项目不含该能力）":
        "{name} contains no extractable text — most likely a scanned/image PDF needing OCR "
        "(not included in this product)",
    "使用 {backend} 提取（段落结构会丢失；装 pdfminer.six 可保留段落空行）":
        "Extracted with {backend} (paragraph structure is lost; installing pdfminer.six "
        "preserves paragraph breaks)",
    "{name} 是空文件": "{name} is an empty file",
    "{name}：旧版二进制 Office 格式无法解析，请用 Office/WPS 另存为 {ext} 后再导入":
        "{name}: legacy binary Office formats cannot be parsed; save it as {ext} in "
        "Office/WPS and import again",
    "{name}：图片需要 OCR，本项目不含该能力":
        "{name}: images require OCR, which this product does not include",
    "{name}：音视频需要语音转写，本项目不含该能力":
        "{name}: audio/video requires speech transcription, which this product does not include",
    "{name}：暂不支持 {ext} 格式": "{name}: {ext} format is not supported yet",
    "无扩展名": "no extension",
    "{name} 转换异常：{exc}": "Failed to convert {name}: {exc}",

    # ---- 本地 GGUF 导入（model_import.py）----
    "请填写 .gguf 文件的完整路径": "Enter the full path of the .gguf file",
    "请填写完整路径（从盘符开始），不要只填文件名：{path}":
        "Enter the full path (starting with the drive letter), not just a file name: {path}",
    "文件不存在：{path}": "File not found: {path}",
    "无法读取该路径（权限不足或路径过长）：{path}（{exc}）":
        "Cannot read this path (insufficient permissions or path too long): {path} ({exc})",
    "这不是一个文件：{path}": "This is not a file: {path}",
    "只支持 .gguf 文件（当前扩展名：{ext}）": "Only .gguf files are supported (current extension: {ext})",
    "文件只有 {size}，小到不可能是完整模型（至少 {min_size}）：{path}":
        "The file is only {size}, too small to be a complete model (at least {min_size}): {path}",
    "文件不可读（权限不足或被其它程序独占）：{path}（{exc}）":
        "The file is not readable (permission denied or held open by another program): {path} ({exc})",
    "文件头不是 GGUF 魔数，可能不是有效的 GGUF 模型：{path}":
        "The file header is not a GGUF magic number; it may not be a valid GGUF model: {path}",
    "找不到 Ollama 模型目录（{dir}），无法确认磁盘空间":
        "Cannot locate the Ollama model directory ({dir}) to check free disk space",
    "无法检查磁盘剩余空间（{exc}）；为避免写满磁盘，已取消导入":
        "Cannot check free disk space ({exc}); the import was cancelled to avoid filling the disk",
    "Ollama 模型目录所在磁盘空间不足：导入约需 {need}，当前可用 {free}（{dir}）。请清理磁盘或改小模型后重试":
        "Not enough space on the disk holding the Ollama model directory: about {need} is "
        "needed, {free} available ({dir}). Free some space or use a smaller model and retry",
    "该文件正在导入中，请等待它完成（重复触发不会加速）":
        "This file is already being imported; wait for it to finish (retrying does not speed it up)",
    "已有导入任务正在进行，请等它结束后再试":
        "Another import is already running; wait for it to finish and try again",
    "程序正在退出，未开始导入": "The app is shutting down, so the import was not started",
    "已开始导入：{name}": "Import started: {name}",
    "连不上 Ollama（{why}）—— 请先启动 Ollama 再导入":
        "Cannot reach Ollama ({why}) — start Ollama first, then import",
    "ollama create 失败：{detail}": "ollama create failed: {detail}",
    "导入过程异常：{exc}": "Unexpected error during import: {exc}",
    "试聊超时或连不上 Ollama（等了 {s} 秒）：{err}":
        "The trial chat timed out or Ollama was unreachable (waited {s}s): {err}",
    "试聊调用失败（HTTP {code}）：{msg}": "The trial chat call failed (HTTP {code}): {msg}",
    "试聊返回空内容": "the trial chat returned nothing",
    "试聊返回乱码（{reply}）": "the trial chat returned garbled text ({reply})",
    "模型在复述提示词、不像正常对话（{reply}）":
        "the model echoed the prompt instead of answering ({reply})",
    "回复异常冗长、不像正常对话（前 60 字：{reply}）":
        "the reply was abnormally long and did not look like a normal answer (first 60 chars: {reply})",
    "该 GGUF 可能缺少 chat template，建议换 instruct / chat 版本再试":
        "this GGUF may lack a chat template; try an instruct/chat build instead",
    "导入的模型未通过验证：{detail} —— {hint}（已从 Ollama 删除，避免它在模型列表里冒充可用）":
        "The imported model failed verification: {detail} — {hint} (it has been removed from "
        "Ollama so it does not masquerade as usable in the model list)",
    "导入的模型未通过验证：{why} —— {hint}（已从 Ollama 删除，避免它在模型列表里冒充可用）":
        "The imported model failed verification: {why} — {hint} (it has been removed from "
        "Ollama so it does not masquerade as usable in the model list)",
    "检查文件与磁盘空间…": "Checking the file and free disk space…",
    "试聊验证中…": "Running the trial chat…",
    "正在导入（拷贝模型文件）…": "Importing (copying the model file)…",
    "同名模型已存在，跳过拷贝，直接试聊验证…":
        "A model with the same name already exists; skipping the copy and running the trial chat…",
    "导入完成：{name}": "Import complete: {name}",
    "文件校验失败": "File validation failed",
    "磁盘空间不足": "Not enough disk space",
    "Ollama 不可达": "Ollama is unreachable",
    "create 失败": "create failed",
    "（无）": "(none)",
    "（空）": "(empty)",
    "连不上 Ollama": "Cannot reach Ollama",
    "返回内容无法解析：{exc}": "The response could not be parsed: {exc}",
    "ollama create 失败（HTTP {code}）：{msg}": "ollama create failed (HTTP {code}): {msg}",
    "ollama create 超时（>{s} 秒）被终止":
        "ollama create timed out (> {s}s) and was terminated",
    "ollama create 异常退出（退出码 {rc}）":
        "ollama create exited abnormally (exit code {rc})",
    "试聊未通过：{why}": "Trial chat failed: {why}",
}


def t(zh: str, **fmt) -> str:
    """把中文原文按当前语言输出。

    * zh：原样返回（``fmt`` 非空时按占位符填充，保证中文输出与 f-string 逐字节一致）；
    * en：查 ``EN`` 命中即用英文模板，未命中回退中文；
    * 占位符缺失 / 格式非法时不抛异常（绝不因为一句提示让接口 500）。
    """
    out = EN.get(zh, zh) if _LANG.get() == "en" else zh
    if fmt:
        try:
            out = out.format(**fmt)
        except (KeyError, IndexError, ValueError):
            pass
    return out


class DeferredMsg:
    """**延后格式化**的一条文案。

    为什么需要：有些提示在**请求线程之外**产生（启动期装配、后台自愈、迁移线程），
    那时根本不知道这次请求是中文还是英文。若当场 format 成定稿，
    响应边界再拿到「索引已按新结构重建：12 篇 / 480 切片」这种成品，
    就再也匹配不上词条了。

    这类文案只记模板与参数，等真正要下发给前端时（响应边界）再按当前语言渲染：

        self.notes.append(DeferredMsg("索引已按新结构重建：{indexed} 篇 / {chunks} 切片",
                                      indexed=12, chunks=480))

    ``__str__`` 走 ``t()``，因此 zh 下与原来的 f-string 逐字节一致；
    未收录词条时自然回退中文。
    """

    __slots__ = ("zh", "fmt")

    def __init__(self, zh: str, **fmt) -> None:
        self.zh = zh
        self.fmt = fmt

    def __str__(self) -> str:
        if not isinstance(self.zh, str):
            return str(self.zh)
        return t(self.zh, **self.fmt)

    def __repr__(self) -> str:  # 便于日志/调试，不参与文案渲染
        return f"DeferredMsg({self.zh!r}, {self.fmt!r})"


def render(v) -> str:
    """把一条提示渲染成字符串（响应边界用）。

    * ``DeferredMsg`` → 按当前语言格式化；
    * 普通字符串 → 过一遍 ``t()``（启动期写死的中文固定串靠它翻译，未收录则回退）；
    * 其它类型 → ``str()``。
    """
    if isinstance(v, DeferredMsg):
        return str(v)
    if isinstance(v, str):
        return t(v)
    return str(v)
