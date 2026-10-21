
"use strict";
/* =========================================================================
 *  Kavira 控制台（零框架 · 零 CDN）
 * ========================================================================= */
/* ---------------------------- i18n ----------------------------
 * 文案 → 翻译层：**中文原文直接作 key**，缺失时自然回退中文（不引入 ID 体系）。
 * 只翻译界面文案；用户数据（笔记标题/正文/片段/输入）与后端返回内容一律原样透传。
 * 语言在首次渲染之前确定：localStorage["kavira.lang"] → navigator.language。
 * 切换语言写入 localStorage 后整页 reload —— 避免重渲染丢掉对话/笔记状态。
 * ------------------------------------------------------------- */
const I18N_EN = {
  /* ---- 顶栏 / 标签页 ---- */
  "Kavira · 随身知识库": "Kavira · Portable Knowledge Base",
  "随身知识库": "Portable Knowledge Base",
  "初始化中…": "Initializing…",
  "本地智能搜索 —": "Local semantic search —",
  "AI 对话 —": "AI Chat —",
  "授权 —": "License —",
  "同步 —": "Sync —",
  "重新拉取状态": "Re-fetch status",
  "刷新": "Refresh",
  "安全退出": "Safe Shutdown",
  "问答": "Q&A",
  "剪藏": "Clip",
  "笔记": "Notes",
  "设置": "Settings",
  "语言": "Language",

  /* ---- 问答 ---- */
  "<b>欢迎使用 Kavira。</b> 我会在你的本地资料里搜索最相关的内容，组织成回答，并标注每一处引用的出处。资料默认保存在本机：使用本地搜索和本地 AI 时无需上传；若你主动配置云端 AI，回答所需的问题和相关资料片段会发送给你选择的服务商。":
    "<b>Welcome to Kavira.</b> I search your local library for the most relevant passages, compose an answer, and cite the source of every claim. Your data stays on this machine by default: local search and local AI need no upload. If you configure a cloud AI, the question and the relevant snippets are sent to the provider you choose.",
  "向你的知识库提问…  (Enter 发送 / Shift+Enter 换行)": "Ask your knowledge base…  (Enter to send / Shift+Enter for a new line)",
  "发送": "Send",
  "问答需激活后使用 —— 到「设置 → 产品授权」激活；笔记浏览与本地搜索不受限制。":
    "Q&A requires activation — activate under Settings → Product License. Browsing notes and local search stay available.",
  "检索知识库…": "Searching the knowledge base…",
  "无法连接本地服务（Kavira 可能已退出）：": "Cannot reach the local service (Kavira may have exited): ",
  "请求失败：{0}": "Request failed: {0}",
  "我": "Me",
  "引用 {0}": "Citation {0}",
  "\n\n⚠ 这条引用来自语义相似匹配，原文未出现你的原话":
    "\n\n⚠ This citation comes from a semantic similarity match; your wording does not appear in the source",
  "点击跳转到该笔记": "Click to open this note",
  "模型服务异常": "Model service error",

  /* ---- 空库引导 ---- */
  "知识库还是空的 —— 先加内容，问答才有东西可查": "Your knowledge base is empty — add content first, then you can ask questions",
  "点顶部 <b>「剪藏」</b> 标签 →  把 <code>.md</code> 文件拖进虚线框，或粘贴一个网址抓取":
    "Click the <b>Clip</b> tab at the top → drag a <code>.md</code> file into the dashed box, or paste a URL to capture",
  "也可以把 .md / .txt 笔记直接放进资料库的 <code>notes</code> 文件夹（安装版默认在 文档\\Kavira-Data\\notes），15 秒内自动入库":
    "You can also drop .md / .txt notes straight into the <code>notes</code> folder of the library (the installer defaults to Documents\\Kavira-Data\\notes); indexed within 15 seconds",
  "入库后回到这里提问，回答会带 <b>[1]</b> 角标指向原文出处":
    "Then come back here and ask; answers carry <b>[1]</b> markers pointing to the original source",
  "去添加第一份内容 →": "Add your first piece of content →",
  "正在后台重建向量索引，完成后自动恢复智能搜索（无需任何操作）。":
    "Rebuilding the vector index in the background. Semantic search resumes automatically — no action needed.",

  /* ---- 剪藏 ---- */
  "往知识库添加内容 —— 三种方式任选": "Add to the knowledge base — pick any of three ways",
  "<b><span class=\"n\">1</span>拖文件进来</b>把 .md / .txt 拖进下面的虚线框（或点它选文件）。最快，支持一次拖多个。":
    "<b><span class=\"n\">1</span>Drag files in</b>Drop .md / .txt files into the dashed box below (or click it to choose). Fastest; multiple files at once.",
  "<b><span class=\"n\">2</span>抓网页</b>粘贴文章网址，自动提取正文入库。":
    "<b><span class=\"n\">2</span>Capture a web page</b>Paste an article URL; the body text is extracted and indexed automatically.",
  "<b><span class=\"n\">3</span>粘贴文字</b>微信公众号、PDF 里复制的文字，贴进最下面文本框保存。":
    "<b><span class=\"n\">3</span>Paste text</b>Text copied from WeChat articles or PDFs: paste it into the box at the bottom and save.",
  "把文件拖到这里": "Drop files here",
  "Word / PPT / Excel / PDF / EPUB / HTML / 邮件 / CSV / 代码 / 字幕 / 纯文本 等 —— 自动转成 Markdown 入库":
    "Word / PPT / Excel / PDF / EPUB / HTML / email / CSV / code / subtitles / plain text and more — converted to Markdown and indexed automatically",
  "或": "or",
  "点击选择文件": "choose files",
  "　·　也可以把 .md / .txt 文件直接放进资料库的 <code>notes</code> 文件夹<span id=\"ddNotesHint\">（位置见「设置 → 资料目录」）</span>，15 秒内自动入库":
    "　·　You can also drop .md / .txt files straight into the <code>notes</code> folder of the library<span id=\"ddNotesHint\"> (see Settings → Data Directory)</span>; indexed within 15 seconds",
  "支持哪些格式？<span class=\"hint\">点开看完整清单</span>": "Which formats are supported?<span class=\"hint\">Expand for the full list</span>",
  "正在读取…": "Loading…",
  "抓网页入库": "Capture a web page",
  "抓取入库": "Fetch & Index",
  "抓取网页需激活后使用 —— 到「设置 → 产品授权」激活；拖入文件与粘贴文字不受限制。":
    "Web capture requires activation — activate under Settings → Product License. Dragging files and pasting text stay available.",
  "动态 SPA / 强反爬页面会自动降级为「保留快照 + 引导粘贴」。":
    "Dynamic SPAs and heavily protected pages automatically fall back to \"keep a snapshot + paste manually\".",
  "粘贴文字入库": "Paste text",
  "标题": "Title",
  "例如：某篇论文的要点摘录": "e.g. Key points from a paper",
  "正文（支持 Markdown 与 [[双向链接]]）": "Body (Markdown and [[wiki links]] supported)",
  "粘贴内容…": "Paste content…",
  "保存并索引": "Save & Index",
  "暂不支持：": "Not supported yet: ",
  "PDF 解析库未安装：执行 {0} 后可用。": "PDF parser not installed: run {0} to enable it.",

  /* ---- 笔记 ---- */
  "已索引文档": "Indexed documents",
  "过滤标题 / 路径…": "Filter by title / path…",
  "按分类筛选（只筛选列表，不影响搜索 / 问答）": "Filter by collection (list only; does not affect search / Q&A)",
  "全部分类": "All collections",
  "正文": "Document",
  "阅读": "Reading",
  "原件": "Original",
  "从左侧选择一篇文档查看。": "Select a document on the left to view it.",
  "(无标题)": "(untitled)",
  "回收站": "Trash",
  "回收站（{0}）": "Trash ({0})",
  "快照": "Snapshot",
  "{0} 切片": "{0} chunks",
  "更多操作": "More actions",
  "回收站是空的。": "Trash is empty.",
  "暂无文档，去「剪藏」页录入一篇吧。": "No documents yet — add one on the Clip page.",
  "恢复": "Restore",
  "永久删除": "Delete permanently",
  "编辑标题": "Edit title",
  "分类": "Collections",
  "移入回收站": "Move to trash",
  "只改显示标题，不动文件名（文件仍是 {0}）。": "Only the display title changes; the file name stays {0}.",
  "保存": "Save",
  "标题已更新": "Title updated",
  "保存失败": "Save failed",
  "重命名类目": "Rename collection",
  "删除类目（不会删除文档）": "Delete collection (documents are kept)",
  "分类（可多选）": "Collections (multi-select)",
  "还没有类目，在下面新建一个。": "No collections yet — create one below.",
  "新建类目，回车添加": "New collection, press Enter",
  "新建": "Create",
  "重命名失败": "Rename failed",
  "类目已重命名": "Collection renamed",
  "删除类目「{0}」？\n\n只删除这个类目，不会删除任何文档。":
    "Delete collection \"{0}\"?\n\nOnly the collection is deleted; no documents are removed.",
  "删除失败": "Delete failed",
  "类目已删除": "Collection deleted",
  "新建失败": "Create failed",
  "分类已更新": "Collections updated",
  "把「{0}」移入回收站？\n\n文件不会被删除，可在「回收站」里恢复。":
    "Move \"{0}\" to trash?\n\nThe file is not deleted; you can restore it from Trash.",
  "已移入回收站": "Moved to trash",
  "操作失败": "Operation failed",
  "已恢复": "Restored",
  "永久删除？": "Delete permanently?",
  "即将<b>永久删除</b>「{0}」": "This will <b>permanently delete</b> \"{0}\"",
  "此操作不可撤销": "This cannot be undone",
  "：笔记文件与其检索索引会被彻底清除，无法再从回收站恢复。":
    ": the note file and its search index are erased for good and cannot be restored from Trash.",
  "同时删除它的<b>原件文件</b>（剪藏网页 / 导入的 Office、PDF 等）":
    "Also delete its <b>original file</b> (captured web page / imported Office, PDF, etc.)",
  "默认不勾选 —— 原件往往无法再生；该笔记若无原件，勾选也无影响。":
    "Unchecked by default — originals often cannot be regenerated; harmless if this note has no original.",
  "该笔记已被永久删除。": "This note has been permanently deleted.",
  "已永久删除": "Permanently deleted",
  "读取失败": "Load failed",
  "请重新启动 Kavira（双击启动脚本）后刷新本页。": "Restart Kavira (double-click the launcher) and reload this page.",
  "读取失败：{0}": "Load failed: {0}",
  "查看{0}：{1}（{2}）": "View {0}: {1} ({2})",
  "{0}：{1}（{2}）": "{0}: {1} ({2})",
  "很快": "moments",
  "不到 1 分钟": "under a minute",
  "约 {0} 分钟": "about {0} min",
  "约 {0} 小时": "about {0} h",
  "该笔记没有留存原件（纯 Markdown / 纯文本导入）": "No original file was kept for this note (plain Markdown / text import)",
  "找不到该笔记（可能已被删除）": "Note not found (it may have been deleted)",
  "该引用缺少定位信息，已打开原文": "This citation has no location data; the document was opened instead",
  "该引用来自旧索引，已打开对应文档": "This citation comes from an old index; the document was opened instead",
  "网页快照": "Web snapshot",
  "新标签打开快照": "Open snapshot in new tab",
  "在新标签打开": "Open in new tab",
  "访问原网页": "Visit original page",
  "预览由服务端转换生成，保留表格与结构，不还原原始排版":
    "Preview generated by the server; tables and structure are kept, exact layout is not",
  "下载原件": "Download original",
  "宽度：": "Width: ",
  "适应宽度": "Fit width",
  "实际大小": "Actual size",
  "剪藏页已禁用脚本，需登录/展开等交互时请用「下载原件」在浏览器打开":
    "Scripts are disabled in captured pages; for login or expand interactions, use \"Download original\" and open it in a browser",
  "⚠️ 该网页由前端脚本动态渲染，安全沙箱内（已禁用脚本）无法显示其内容。请用上方「新标签打开快照」或「下载原件」在浏览器中查看完整快照；正文请回「阅读」视图。":
    "⚠️ This page is rendered by client-side scripts, so its content cannot be shown in the security sandbox (scripts disabled). Use \"Open snapshot in new tab\" or \"Download original\" above to view the full snapshot in a browser; use the Reading view for the text.",
  "原版预览": "Original preview",
  "该格式无法内嵌预览。": "This format cannot be previewed inline.",
  "（空文档）": "(empty document)",

  /* ---- 状态 / 统计 ---- */
  "已就绪": "Ready",
  "本地智能搜索：可用": "Local semantic search: available",
  "本地智能搜索：仅关键词": "Local semantic search: keywords only",
  "本地模型": "Local model",
  "云端": "Cloud",
  "尚未配置": "Not configured",
  "不可用": "Unavailable",
  "AI 对话：{0}": "AI Chat: {0}",
  "AI 对话：{0} —— {1}": "AI Chat: {0} — {1}",
  "同步：{0}": "Sync: {0}",
  "{0} 篇 · {1}s": "{0} docs · {1}s",
  "未运行": "Not running",
  "授权：{0}": "License: {0}",
  "已激活": "Activated",
  "未激活": "Not activated",
  "异常": "Error",
  "需激活后使用": "Requires activation",
  "✅ 就绪": "✅ Ready",
  "（{0}）": " ({0})",
  "未检测到本地 Ollama": "Local Ollama not detected",
  "Ollama 已启动，但本机尚无模型": "Ollama is running, but no model is installed",
  "本机已有模型，请选择用哪个对话": "Models are installed — choose one for chat",
  "原配置的模型在本机已不存在": "The configured model no longer exists on this machine",
  "：{0}": ": {0}",
  "控制台端口": "Console port",
  "运行时长": "Uptime",
  "{0} 秒": "{0} s",
  "文档 / 切片 / 父块": "Documents / chunks / parents",
  "库规模": "Library size",
  "向量召回": "Vector recall",
  "已启用": "Enabled",
  "未启用": "Disabled",
  "嵌入源 / 维度": "Embedding source / dim",
  "嵌入签名": "Embedding signature",
  "AI 模式 / 实际": "AI mode / resolved",
  "对话能力": "Chat capability",
  "本机模型": "Installed models",
  "{0} 个": "{0}",
  "，已选 {0}": " (selected: {0})",
  "，未选择": " (none selected)",
  "Ollama 探测": "Ollama probe",
  "在线": "Online",
  "离线 ({0})": "Offline ({0})",
  "已配置": "Configured",
  "未配置": "Not configured",
  "同步轮次 / 更新": "Sync cycles / updates",
  "冷启动耗时": "Cold start",
  "（无）": "(none)",

  /* ---- 抓取 / 导入 ---- */
  "抓取网页需激活后使用（设置 → 产品授权）": "Web capture requires activation (Settings → Product License)",
  "问答需激活后使用（设置 → 产品授权）": "Q&A requires activation (Settings → Product License)",
  "请输入 URL": "Please enter a URL",
  "正在检查这个网页是否已保存过…": "Checking whether this page was already saved…",
  "⚠ 该网页已经保存过：{0}": "⚠ This page was already saved: {0}",
  "请选择处理方式": "Choose what to do",
  "打开已有": "Open existing",
  "更新已有": "Update existing",
  "另存为新版本": "Save as new version",
  "取消": "Cancel",
  "已取消，未做任何改动。": "Cancelled — nothing was changed.",
  "正在抓取并清洗正文…": "Fetching and cleaning the article body…",
  "已保存：{0} · 快照：{1}": "Saved: {0} · snapshot: {1}",
  "该页面为前端动态渲染，仅保留快照": "This page is rendered dynamically; only a snapshot was kept",
  "抓取成功": "Capture succeeded",
  "标题：{0} · 字数：{1} · 文件：{2} · 抽取器：{3}":
    "Title: {0} · characters: {1} · file: {2} · extractor: {3}",
  "已入库并建立索引": "Indexed",
  "抓取失败": "Capture failed",
  "正文不能为空": "The body cannot be empty",
  "上一批还在导入，请等它完成": "The previous batch is still importing — please wait",
  "{0}（超过 20MB）": "{0} (over 20 MB)",
  "{0}（不支持 {1}）": "{0} (unsupported {1})",
  "已跳过：{0}": "Skipped: {0}",
  "没有可导入的文件": "No importable files",
  "正在导入 {0}/{1}：{2}": "Importing {0}/{1}: {2}",
  "正在导入 {0}/{1}（成功 {2}）：": "Importing {0}/{1} ({2} succeeded):",
  " —— 读取失败：{0}": " — read failed: {0}",
  " —— {0}{1}": " — {0}{1}",
  " —— {0}": " — {0}",
  "已入库": "Indexed",
  "（{0} 字）": " ({0} chars)",
  "导入失败": "Import failed",
  "导入完成：成功 {0} / {1}": "Import finished: {0} / {1} succeeded",
  "，失败 {2}": ", {2} failed",
  "⚠ 全部导入失败，请看下方原因": "⚠ All imports failed — see the reasons below",
  "读取文档列表失败": "Failed to load the document list",

  /* ---- 设置 ---- */
  "配置": "Configuration",
  "默认只显示<b>常用项</b>（一共 7 个），其余全部收在下方「高级设置」里 —— <b>不改它们完全不影响使用</b>。":
    "Only <b>common settings</b> (7 in total) are shown by default; everything else lives under <b>Advanced</b> below — <b>leaving them untouched will not affect normal use</b>.",
  "高级设置 <span class=\"hint\">向量检索 / 网页抓取 / 系统端口 —— 看不懂就别动</span>":
    "Advanced <span class=\"hint\">vector retrieval / web capture / system ports — leave alone if unsure</span>",
  "保存配置": "Save configuration",
  "放弃修改": "Discard changes",
  "把表单填回出厂默认值（不会立即保存）": "Fill the form with factory defaults (does not save immediately)",
  "恢复默认设置": "Restore defaults",
  "保存后重启程序才完全生效": "Restart the app for changes to take full effect",
  "资料目录": "Data Directory",
  "你的资料现在保存在上面这个位置。想换到一个更大 / 更快的盘，或搬到 U 盘随身携带，都可以在这里完成。":
    "Your library currently lives at the location above. Move it to a larger or faster drive, or onto a USB stick, right here.",
  "换到新目录": "Move to a new folder",
  "例如：E:\\Kavira-Data": "e.g. E:\\Kavira-Data",
  "检查一下": "Check",
  "填一个<b>空文件夹</b>的完整路径。已有资料的目录会被拒绝 —— 不会为了腾地方删里面的东西。":
    "Enter the full path of an <b>empty folder</b>. Folders that already contain data are rejected — nothing is deleted to make room.",
  "开始迁移": "Start migration",
  "数据管理": "Data management",
  "导出知识库备份": "Export library backup",
  "打包成 zip 下载保存": "Packaged as a zip download",
  "备份包含<b>笔记正文、导入的原件、图片素材、分类</b>，以及一份恢复说明；<b>不含</b>检索索引与日志（它们随时能自动重建，带上只会让备份大好几倍）。打包时配置里的云端密钥会被清空，不会跟着备份到处跑。":
    "The backup contains <b>note text, imported originals, images, and collections</b>, plus restore instructions. It <b>does not</b> include search indexes or logs (they rebuild automatically; including them would multiply the size). Cloud API keys in the config are cleared while packing, so they never travel with the backup.",
  "产品授权": "Product License",
  "本机设备码（发给授权方）": "Device code (send to the licensor)",
  "读取中…": "Loading…",
  "复制": "Copy",
  "输入激活码": "Enter activation code",
  "粘贴授权方发来的激活码…": "Paste the activation code from the licensor…",
  "激活": "Activate",
  "清除本机激活": "Clear activation",
  "运行状态": "Runtime status",
  "索引维护": "Index maintenance",
  "全量重建索引": "Rebuild full index",
  "重建向量索引": "Rebuild vector index",
  "数据真相源始终是 <code>data/notes/</code> 下的 Markdown；<code>cache.db</code> 只是可随时重建的衍生索引。<b>换过嵌入模型后必须点「重建向量索引」</b>，否则向量检索会被自动禁用（界面会黄条提醒）。":
    "The source of truth is always the Markdown under <code>data/notes/</code>; <code>cache.db</code> is a derived index that can be rebuilt at any time. <b>After changing the embedding model you must click \"Rebuild vector index\"</b>, otherwise vector retrieval is disabled automatically (a warning bar appears).",
  "运行详情": "Runtime details",
  "系统自动降级 / 自动适配的过程记录。<b>功能正常时无需理会</b>。":
    "A log of automatic fallbacks and adaptations. <b>Safe to ignore while everything works.</b>",
  " · 其他": " · Other",
  "默认值尚未加载，请先刷新": "Defaults are not loaded yet — refresh first",
  "把设置填回出厂默认值？\n\n不会立即保存 —— 确认无误后再点「保存配置」才生效。\n（云端 API Key 不会被清空）":
    "Fill the settings back with factory defaults?\n\nNothing is saved immediately — click \"Save configuration\" to apply.\n(Cloud API keys are not cleared.)",
  "（默认）": "(default)",
  "已填回默认值，确认后点「保存配置」生效": "Defaults filled in — click \"Save configuration\" to apply",
  "正在读取本地 Ollama 模型…": "Reading local Ollama models…",
  "嵌入模型": "embedding model",
  "本地对话模型": "local chat model",
  "填写你本机已安装的模型名": "Enter a model name installed on this machine",
  "⚠ {0} —— 已切换为手动填写。装好 Ollama 后点「刷新模型列表」可恢复下拉。":
    "⚠ {0} — switched to manual entry. After installing Ollama, click \"Refresh model list\" to restore the dropdown.",
  "— 未选择（请从下方本机模型里挑一个）—": "— Not selected (pick one of the installed models below) —",
  "（不支持此用途，请另选）": " (not usable for this role — choose another)",
  "（原配置，本机未找到）": " (configured, not found on this machine)",
  "⚠ Ollama 在线，但本机尚未安装任何模型 —— 请先用 Ollama 装好模型，再点「刷新模型列表」。":
    "⚠ Ollama is online, but no models are installed — install one with Ollama first, then click \"Refresh model list\".",
  "⚠ 本机没有可用于「{0}」的模型 —— 请先用 Ollama 安装（对话模型如 qwen2.5，嵌入模型如 bge-m3），再点「刷新模型列表」。":
    "⚠ No model on this machine can be used as {0} — install one with Ollama (e.g. qwen2.5 for chat, bge-m3 for embeddings), then click \"Refresh model list\".",
  "已筛出 {0} 个可用「{1}」的模型，请选一个（程序不会自动替你选）。":
    "Found {0} models usable for {1}; choose one (the app will not choose for you).",
  "　⚠ 当前 Ollama 未提供能力标签，无法自动分辨用途。":
    "　⚠ This Ollama does not report capability tags, so roles cannot be filtered automatically.",
  "⚠ 当前配置的「{0}」{1}，请重新选择。": "⚠ The configured model \"{0}\" {1}; please choose again.",
  "不支持「{0}」（能力标签里没有 {1}）": "does not support {0} (no {1} capability tag)",
  "在本机已不存在": "no longer exists on this machine",
  "✅ 当前模型：{0}　（Ollama：{1}）": "✅ Current model: {0}　(Ollama: {1})",
  "⚠ 模型选择保存失败：{0}": "⚠ Failed to save model selection: {0}",
  "✅ 已选择本地模型：{0}（已保存，可直接提问）": "✅ Local model selected: {0} (saved; ready to ask)",
  "已清空本地模型选择": "Local model selection cleared",
  "已选择并保存本地模型：{0}": "Local model selected and saved: {0}",
  "正在调用本地 Ollama（首次要加载模型，可能等几秒）…":
    "Calling local Ollama (the first call loads the model and may take a few seconds)…",
  "正在调用云端 API…": "Calling the cloud API…",
  "未知结果": "Unknown result",
  "⚠ 嵌入模型相关设置已变更，请点下方「重建向量索引」，否则向量检索会被禁用":
    "⚠ Embedding settings changed. Click \"Rebuild vector index\" below, or vector retrieval will be disabled",
  "✅ 配置已保存（重启程序后完全生效）": "✅ Configuration saved (restart the app for full effect)",
  "已在后台启动…": "Started in the background…",
  "任务已启动": "Task started",
  "任务已提交后台执行，可继续使用其他功能。": "Task submitted to the background; you can keep using other features.",

  /* ---- 授权 ---- */
  "设备不符": "Device mismatch",
  "已过期": "Expired",
  "签名无效": "Invalid signature",
  "产品不符": "Product mismatch",
  "格式错误": "Malformed",
  "无法验证": "Cannot verify",
  "未知": "Unknown",
  "设备码尚未加载": "Device code is not loaded yet",
  "设备码已复制": "Device code copied",
  "复制失败，请手动选择": "Copy failed — select the text manually",
  "请先粘贴激活码": "Please paste an activation code first",
  "清除本机激活？\n\n清除后本机立即回到未激活状态（不影响资料库与笔记）。":
    "Clear the activation on this machine?\n\nIt immediately returns to the unactivated state (your library and notes are unaffected).",
  "已清除": "Cleared",
  "该引用没有对应的笔记路径": "This citation has no note path",

  /* ---- 资料目录迁移 / 导出 ---- */
  "启动参数指定": "set by launch argument",
  "本机配置指定": "set in local config",
  "程序目录下的 data": "data folder next to the app",
  "当前位置": "Current location",
  "怎么定的": "Determined by",
  "已存文档": "Stored documents",
  "{0} 篇": "{0} docs",
  "占用空间": "Space used",
  "（{0} 个文件）": " ({0} files)",
  "该盘剩余": "Free on drive",
  "备份包约": "Backup ≈ ",
  "，导出约需 {0}": ", export takes {0}",
  "（当前在 {0}）": " (currently {0})",
  "请先填写目标目录": "Enter a target folder first",
  "正在检查…": "Checking…",
  "✓ 可以迁到这里": "✓ You can migrate here",
  "　需要约 {0}，目标可用 {1}。": "　About {0} needed; target has {1} free.",
  "迁移预计需要 {0}（视磁盘速度而定）—— 期间请勿关闭程序或拔出磁盘。":
    "Migration is expected to take {0} (depending on disk speed) — do not close the app or unplug the drive.",
  "预检未通过": "Pre-check failed",
  "检查失败：{0}": "Check failed: {0}",
  "将把现有资料完整复制到：\n\n　{0}\n\n· 复制期间请勿关闭电脑或拔出磁盘\n· 完成后会重新打开资料库，页面会短暂无响应\n· 旧目录会原样保留，等你确认没问题后自己删除\n\n确定开始迁移吗？":
    "Your library will be copied in full to:\n\n　{0}\n\n· Do not shut down the computer or unplug the drive during the copy\n· The library reopens when done; the page may be unresponsive briefly\n· The old folder is left untouched — delete it yourself once you have verified everything\n\nStart the migration?",
  "正在启动迁移任务…": "Starting the migration task…",
  "无法开始迁移": "Cannot start migration",
  "无法开始：{0}": "Cannot start: {0}",
  "✓ 迁移完成：共 {0} 个文件 / {1}，用时 {2} 秒": "✓ Migration complete: {0} files / {1}, took {2} s",
  "资料现在保存在：{0}": "The library now lives at: {0}",
  "旧位置（{0}）仍保留着一份完整副本，确认无误后可自行删除。":
    "The old location ({0}) still holds a full copy; delete it once verified.",
  "资料已迁移到新目录": "Library migrated to the new folder",
  "迁移失败": "Migration failed",
  "正在打包…此项在服务端完成，<b>打包结束后浏览器会自动开始下载</b>。资料较多时请耐心等待，期间可以继续使用其它功能。":
    "Packing… this runs on the server; <b>the browser starts downloading when packing finishes</b>. Large libraries take a while — you can keep using other features.",
  "正在打包备份，完成后浏览器会自动下载": "Packing the backup; the browser downloads it automatically when ready",
  "若迟迟没有开始下载，可以再点一次；打包失败的临时文件会在下次导出前自动清理。":
    "If the download does not start, click again; leftover files from failed packs are cleaned up before the next export.",
  "状态已刷新": "Status refreshed",
  "将执行 WAL 检查点并释放数据库锁，确保 U 盘可直接拔出。\n\n确定要安全退出吗？":
    "This runs a WAL checkpoint and releases database locks so the USB drive can be unplugged safely.\n\nShut down safely?",
  "退出请求失败：{0}": "Shutdown request failed: {0}",
  "已完成安全退出": "Safe shutdown complete",
  "WAL 已刷回主库、临时文件已清理，现在可以安全拔出 U 盘。":
    "WAL has been flushed to the main database and temporary files cleaned up. You can safely unplug the USB drive.",

  /* ---- 设置项：分组标题与说明 ---- */
  "AI 对话模型": "AI chat model",
  "决定回答由谁生成。什么都不改也能正常用 —— 会自动降级成本地检索摘要，不会崩。":
    "Decides who generates answers. The defaults work fine — the app degrades to local retrieval summaries instead of failing.",
  "AI 提示注入预算": "AI prompt budget",
  "控制「一次给模型塞多少背景资料」。调大更全但更慢更费 token，调小可能漏信息。":
    "Controls how much context is sent to the model per answer. Larger is more complete but slower and costs more tokens; smaller may miss information.",
  "向量检索（决定「怎么找」）": "Vector retrieval (how matching works)",
  "把问题变成向量做语义匹配。这一组程序会自己适配，基本不用碰。":
    "Turns questions into vectors for semantic matching. The app adapts automatically; rarely needs changes.",
  "网页抓取（剪藏行为）": "Web capture (Clip behavior)",
  "只影响「剪藏」页抓网页的表现。": "Affects web capture on the Clip page only.",
  "入库分析（AI 增强）": "Ingestion analysis (AI-assisted)",
  "入库时是否用本地模型生成一句话摘要。确定性抽取（关键词 / 实体 / 语言）永远执行，不受此影响。":
    "Whether a local model writes a one-line summary at ingestion. Deterministic extraction (keywords / entities / language) always runs regardless.",
  "检索引用策略": "Citation policy",
  "控制「引用来源」的严格程度。": "Controls how strict citation sourcing is.",
  "文件导入边界（安全上限）": "Import limits (safety caps)",
  "防止超大文件 / 压缩炸弹打爆处理流程。默认值保守，正常文档都能打开。":
    "Prevents huge files / zip bombs from overwhelming the pipeline. Conservative defaults; normal documents still open.",
  "系统（端口与后台扫描）": "System (ports and background scanning)",
  "一般完全不用改。": "Normally never needs changes.",

  /* ---- 设置项：字段标签与说明 ---- */
  "AI 模式": "AI mode",
  "「自动」最省心：优先用本地 Ollama（免费、离线），不行再走云端 API，都没有就纯离线检索。":
    "\"Auto\" is the easiest: prefer local Ollama (free, offline), fall back to a cloud API, and otherwise use offline retrieval only.",
  "自动（推荐）": "Auto (recommended)",
  "只用本地 Ollama": "Local Ollama only",
  "只用云端 API": "Cloud API only",
  "纯离线，不调用 AI": "Offline only, no AI",
  "Ollama 服务地址": "Ollama endpoint",
  "Ollama 装在本机就用默认值，别改。": "Keep the default when Ollama runs on this machine.",
  "自动启动 Ollama": "Start Ollama automatically",
  "开启后，程序启动时若发现 Ollama 没在跑，会在**后台静默拉起**（无窗口、不阻塞启动）——你就不必自己去开 Ollama。找不到 Ollama 或启动失败时会自动降级为纯离线检索，不影响使用。介意程序自起后台进程的话可以关掉。":
    "When enabled, if Ollama is not running at startup the app **starts it silently in the background** (no window, non-blocking) — no need to start it yourself. If Ollama is missing or fails to start, the app falls back to offline retrieval. Turn this off if you dislike background processes.",
  "自动启动（推荐）": "Start automatically (recommended)",
  "不自动启动": "Do not start automatically",
  "本地对话模型": "Local chat model",
  "从你本机已安装的 Ollama 模型里挑一个。下拉只会列出**能对话**的模型（嵌入/向量模型不会出现，选了也没用）。程序不会替你预设或自动选择任何模型；本机还没有模型时请先用 Ollama 安装，然后点「刷新模型列表」。":
    "Pick one of the Ollama models installed on this machine. The dropdown lists only **chat-capable** models (embedding models are excluded). The app never preselects a model; if none is installed, install one with Ollama and click \"Refresh model list\".",
  "云端接口地址": "Cloud API base URL",
  "选一家常用服务商，或自己填兼容 OpenAI 协议的地址。": "Pick a provider, or enter any OpenAI-compatible base URL.",
  "通义千问": "Qwen",
  "Kimi 月之暗面": "Kimi (Moonshot)",
  "智谱 GLM": "Zhipu GLM",
  "云端 API Key": "Cloud API key",
  "留空就不用云端。请妥善保管，勿泄露给他人。": "Leave empty to skip the cloud. Keep it private.",
  "云端对话模型": "Cloud chat model",
  "填服务商文档里的模型名，比如 deepseek-chat。": "Use the model name from the provider's docs, e.g. deepseek-chat.",
  "每段最多注入（字）": "Max characters per passage",
  "每一段背景最多截取多少字符。默认 400。": "Characters taken from each context passage. Default 400.",
  "整轮注入上限（字）": "Max characters per turn",
  "一次回答里，所有背景段加起来的字符上限。默认 1800。": "Total characters across all context passages per answer. Default 1800.",
  "向量嵌入来源": "Embedding source",
  "local_onnx 用随包自带的本地模型（bge-small-zh-v1.5，开箱可用、不联网）；ollama 借本机 Ollama 算；api 用云端算。本机没有嵌入能力时会自动降级为纯词法检索，不会崩。":
    "local_onnx uses the bundled model (bge-small-zh-v1.5, works out of the box, no network); ollama uses local Ollama; api uses the cloud. Without embeddings the app falls back to lexical search.",
  "本地 ONNX": "Local ONNX",
  "本地 Ollama": "Local Ollama",
  "云端 API": "Cloud API",
  "嵌入模型名": "Embedding model",
  "用 Ollama 做嵌入时从下拉里选——下拉只列出**能嵌入**的模型（如 bge-m3、nomic-embed-text），对话模型不会出现。用 local_onnx / api 时会自动变回手动填写。":
    "When embedding through Ollama, choose from the dropdown — it lists only **embedding-capable** models (e.g. bge-m3, nomic-embed-text). With local_onnx / api this becomes a manual field.",
  "向量维度": "Vector dimensions",
  "用 ollama / api 时程序会自动探测并覆盖这个值，不用填。只有 local_onnx 才需要手填。改错会让向量检索被自动禁用。":
    "With ollama / api the app detects this automatically. Only local_onnx requires manual entry; a wrong value disables vector retrieval.",
  "送入 AI 的段落数": "Passages sent to the AI",
  "一次给大模型看几段背景。越多信息越全，但更慢、更费 token。默认 5。":
    "How many context passages the model sees per answer. More is more complete but slower and costs more tokens. Default 5.",
  "每路召回候选数": "Candidates per recall channel",
  "词法和向量各捞多少个候选来融合排序。默认 20，不用动。":
    "How many candidates each lexical and vector channel fetches for fusion. Default 20.",
  "正文降级门限（字）": "Body fallback threshold (chars)",
  "抓下来的正文少于这个字数，就判定为动态页面，自动改成「存快照 + 提示手动粘贴」。默认 150。":
    "If the extracted body is shorter than this, the page is treated as dynamic and falls back to \"save a snapshot + prompt manual paste\". Default 150.",
  "动态页渲染抓取": "Render dynamic pages",
  "开启后遇到动态页面会调用本机 Chrome 渲染（更慢更重）。默认关闭 —— 反爬页面不硬刚。":
    "When enabled, dynamic pages are rendered with local Chrome (slower, heavier). Off by default — bot-protected pages are not forced.",
  "关闭（推荐）": "Off (recommended)",
  "开启": "On",
  "请求超时（秒）": "Request timeout (s)",
  "默认 20 秒。": "Default 20 seconds.",
  "降级快照保留字数": "Snapshot length (chars)",
  "默认 1000。": "Default 1000.",
  "抓取网页子资源（离线可看）": "Save page sub-resources (offline viewing)",
  "开启后剪藏网页时把 CSS / 图片 / 字体一起存到本地资源池 —— 离线也能还原版式，且浏览时不向外部发任何请求。默认开启。":
    "When enabled, CSS / images / fonts are saved to the local asset pool during capture — layout works offline and viewing makes no external requests. On by default.",
  "开启（推荐）": "On (recommended)",
  "关闭（只留 HTML）": "Off (HTML only)",
  "单页资源预算（KB）": "Per-page asset budget (KB)",
  "单个网页最多存多少 KB 的资源，超出后剩余资源改用占位符，避免个别页面吃掉整块 U 盘。默认 5120（5 MB）。":
    "Maximum KB of assets per page; beyond this, placeholders are used so one page cannot fill the USB drive. Default 5120 (5 MB).",
  "单个资源上限（KB）": "Per-asset limit (KB)",
  "单个图片 / 字体超过这个大小就跳过（留占位，保留原始尺寸以免撑破布局）。默认 512。":
    "Skip an image / font larger than this (a placeholder keeps its original size so the layout stays intact). Default 512.",
  "允许抓取内网地址": "Allow private network addresses",
  "默认关闭：只允许公网地址（防 SSRF，逐跳校验重定向）。开启表示你明确允许抓局域网 / 本机资源；协议白名单与重定向校验仍不变。":
    "Off by default: public addresses only (SSRF protection, redirects checked hop by hop). Enabling it explicitly allows LAN / localhost resources; the protocol allowlist and redirect checks still apply.",
  "允许内网": "Allow private network",
  "生成一句话摘要": "Generate a one-line summary",
  "模型不在线会自动跳过，不影响入库速度与成功率。默认开启。":
    "Skipped automatically when no model is online; ingestion speed and success are unaffected. On by default.",
  "关闭": "Off",
  "允许「仅语义相关」进入引用": "Allow semantic-only citations",
  "默认开启：允许语义通道召回 —— 当你换一种说法提问、原文没有出现你的原话时，仍能找到相关资料。放行的引用会标注 semantic-only（原文未出现你的原话）。关闭则引用必须有字面依据，宁可回答「没找到」。":
    "On by default: allow semantic-channel hits — when you rephrase a question and the source never uses your words, relevant material is still found. Such citations are labelled semantic-only. When off, citations need literal evidence; the answer may be \"not found\".",
  "显示 semantic-only 徽标": "Show semantic-only badge",
  "默认开启：在来自语义匹配的引用卡片上显示「semantic-only」徽标与一句人话解释。关闭后仅隐藏徽标，不影响检索行为，也不影响后端对引用的来源判定。":
    "On by default: semantic matches show a \"semantic-only\" badge and a plain-language note. Turning it off only hides the badge; retrieval and source attribution are unchanged.",
  "显示（推荐）": "Show (recommended)",
  "隐藏": "Hide",
  "语义旁证门限（条）": "Semantic corroboration threshold",
  "语义-only 放行要求「同一文档内有 ≥ 本值 条候选的语义分 ≥ 语义通道最低相似度」。调高更保守（更难放行）。默认 2。仅影响语义通道，不触碰防编造闸门。":
    "A semantic-only citation requires at least this many candidates in the same document scoring above the minimum similarity. Higher is stricter. Default 2. Affects the semantic channel only, never the anti-fabrication gate.",
  "语义通道最低相似度": "Minimum semantic similarity",
  "语义-only 放行的固定相似度下限（放行阈值 = max(本值, 词法候选池最高分 + 0.05)）。默认 0.84：防止「孤立语义近邻」被误引。仅影响语义通道，不触碰防编造闸门。":
    "Fixed similarity floor for semantic-only citations (threshold = max(this value, best lexical score + 0.05)). Default 0.84, which prevents isolated semantic neighbours from being cited. Affects the semantic channel only, never the anti-fabrication gate.",
  "单文件上限（MB）": "Max file size (MB)",
  "普通文件（PDF / CSV / Markdown 等）单文件大小上限。默认 50。":
    "Size limit for a single ordinary file (PDF / CSV / Markdown, etc.). Default 50.",
  "压缩包内文件数上限": "Max entries per archive",
  "OOXML / EPUB 等压缩容器内的条目数上限。默认 5000。": "Entry limit inside archives such as OOXML / EPUB. Default 5000.",
  "压缩包单条目上限（MB）": "Max archive entry size (MB)",
  "单个解压后条目的大小上限。默认 50。": "Size limit for one extracted entry. Default 50.",
  "压缩包总解压上限（MB）": "Max total extracted size (MB)",
  "整个压缩包解压后的总大小上限。默认 200。": "Total extracted size limit for an archive. Default 200.",
  "最大压缩比": "Max compression ratio",
  "解压膨胀倍数上限（防压缩炸弹）。默认 100。": "Expansion ratio limit (zip-bomb protection). Default 100.",
  "服务起始端口": "Starting service port",
  "被占用时程序会自动 +1 往后找，最多试 10 个，所以这里基本不用改。":
    "If busy, the app tries the next port, up to 10 times; rarely needs changing.",
  "监听地址": "Listen address",
  "保持 127.0.0.1 —— 只有本机能访问。别改成 0.0.0.0，那会把整个知识库暴露给局域网。":
    "Keep 127.0.0.1 — local access only. Do not use 0.0.0.0; that exposes the whole library to the LAN.",
  "外部文件扫描间隔（秒）": "External file scan interval (s)",
  "你用 Obsidian / Typora 改了笔记后，多久被同步进索引。默认 15 秒。":
    "How soon edits made in Obsidian / Typora are synced into the index. Default 15 seconds.",
  "日志级别": "Log level",
  "INFO（默认）": "INFO (default)",
  "DEBUG（排查问题用）": "DEBUG (troubleshooting)",
  "留空则不使用云端 API": "Leave empty to skip the cloud API",
  "加载中…": "Loading…",
  "重新读取本机已安装的 Ollama 模型": "Re-read the Ollama models installed on this machine",
  "刷新模型列表": "Refresh model list",
  "测试本地 Ollama": "Test local Ollama",
  "测试云端 API": "Test cloud API",
  "会先自动保存当前表单，再真实跑一次调用": "Saves the current form first, then makes a real call",
};

/* 语言优先级：localStorage → navigator.language（zh* → zh，其它 → en） */
function detectLang() {
  try {
    const saved = localStorage.getItem("kavira.lang");
    if (saved === "zh" || saved === "en") return saved;
  } catch (e) { /* 隐私模式禁用存储时忽略 */ }
  const nav = String(navigator.language || navigator.userLanguage || "").toLowerCase();
  return nav.indexOf("zh") === 0 ? "zh" : "en";
}

// 先定语言，再渲染 —— 后续所有 t() 都依赖 LANG
let LANG = detectLang();

/* t(文案, 参数...)：LANG==="en" 时查表并替换 {0}/{1} 占位符；
   缺翻译（或中文界面）时回退原文，占位符同样替换（中文原文里也带占位符）。 */
function t(s, ...args) {
  let out = s;
  if (LANG === "en" && Object.prototype.hasOwnProperty.call(I18N_EN, s)) out = I18N_EN[s];
  if (args.length) {
    out = String(out).replace(/\{(\d+)\}/g,
      (m, i) => (args[+i] == null ? m : String(args[+i])));
  }
  return out;
}

/* 静态文案：按 data-i18n* 属性里的中文 key 就位；同步 <html lang> 与 <title>。
   必须在任何动态渲染之前调用 —— 否则后续 innerHTML 会把翻译覆盖回中文。 */
function applyI18n() {
  document.documentElement.setAttribute("lang", LANG === "en" ? "en" : "zh-CN");
  document.title = t("Kavira · 随身知识库");
  $$("[data-i18n]").forEach(el => { el.textContent = t(el.getAttribute("data-i18n")); });
  $$("[data-i18n-html]").forEach(el => { el.innerHTML = t(el.getAttribute("data-i18n-html")); });
  $$("[data-i18n-placeholder]").forEach(el => {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
  });
  $$("[data-i18n-title]").forEach(el => { el.setAttribute("title", t(el.getAttribute("data-i18n-title"))); });
  $$("[data-i18n-aria]").forEach(el => { el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria"))); });
  $$("[data-lang]").forEach(b => b.classList.toggle("on", b.dataset.lang === LANG));
}

const $  = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

const S = {
  ready: false,
  refs: [],          // 兼容字段：最近一次回答的引用（新代码走 refsByTurn）
  // A：引用身份必须是 turn-scoped —— [N] 只在单条 assistant 回答内唯一，不是全局唯一。
  // 每条 assistant turn 自己保存自己的 refs 快照，点击时按「turn_id + ref_id」取回，
  // 绝不读取最新一轮的 S.refs（否则回答 A 的 [1] 会串到回答 B 的 [1]）。
  refsByTurn: new Map(),   // turn_id -> [ {id,path,parent_id,snippet,source_start_line,source_end_line,...} ]
  turn: 0,                 // 当前正在流式输出的 assistant turn id
  turnSeq: 0,              // turn id 自增计数器
  rendered: "",      // 已渲染的文本（不含滞留缓冲）
  holding: "",       // 未闭合角标滞留缓冲
  full: "",          // 收到的完整文本
  q: "",             // 最近一次提问
  // 本轮「问题实词」（后端 meta 帧下发）：引用跳转后据此在证据区域内高亮关键字。
  // 不用 snippet 文本匹配 —— 那带 Markdown 语法，必然匹配失败。
  terms: [],
  busy: false,
  licenseOK: true,   // 已激活？未激活时禁用受限功能（抓网页 / 问答）；由 applyLicenseGate 维护
};

// B：导航串行化守卫 —— 连续点击不同 citation 时，旧请求不得覆盖较新的点击结果。
let NOTE_NAV_SEQ = 0;

// P0-4：是否在引用上显示 semantic-only 徽标 + 人话解释（来自 [SEARCH] show_semantic_label）。
// 仅控「显隐」—— 关闭后内部 data-match-mode / 后端 match_mode 标记仍在（供调试与归因守卫）。
// 默认 true（安全优先：先让用户知道来源性质）；loadConfig() 拿到配置后按真实值刷新。
let SEM_LABEL_ON = true;

/* ---------------------------- 工具 ---------------------------- */
function toast(msg, ms) {
  const d = document.createElement("div");
  d.textContent = msg;
  $("#toast").appendChild(d);
  setTimeout(() => d.remove(), ms || 2600);
}
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
// 仅用于属性值转义（值为字符串/数字；不破坏 HTML 结构）
function attrEsc(v) {
  return String(v == null ? "" : v).replace(/[&"]/g, c => ({ "&": "&amp;", '"': "&quot;" }[c]));
}
function api(path, opts) {
  return fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}))
    .then(r => r.json())
    // 把「连不上本地服务」翻译成人话 —— 典型场景：用户把启动窗口关掉了，
    // 后端进程随之结束，页面还留在浏览器里。没有这层包装时 fetch 只会静默 reject，
    // 表现为「点笔记标题变、内容不变」，看起来像 bug，其实是服务已经没了。
    .catch(err => {
      throw new Error(t("无法连接本地服务（Kavira 可能已退出）：")
        + ((err && err.message) || err));
    });
}

/* -------------------- 轻量 Markdown 渲染 -------------------- */
function mdToHtml(src, refs) {
  const blocks = [];
  let text = String(src || "");
  // 代码块先摘出来，避免内部被行内规则污染
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, code) => {
    blocks.push('<pre><code>' + esc(code.replace(/\n$/, "")) + "</code></pre>");
    return "\u0000BLK" + (blocks.length - 1) + "\u0000";
  });
  text = esc(text);
  // UX-2：把后端下发的命中哨兵（控制字符 \u0001/\u0002）转成 <mark>。
  // 必须放在 esc() **之后**：关键词本身已随全文一起转义，这里只把哨兵换成标签 ——
  // 既不破坏 HTML 转义，也不会在表格/路径里乱插标签。
  text = text.replace(/\u0001/g, "<mark>").replace(/\u0002/g, "</mark>");
  text = text.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  text = text.replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>");
  text = text.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  text = text.replace(/^#{1,6}\s*(.+)$/gm, "<h4>$1</h4>");
  text = text.replace(/^&gt;\s?(.*)$/gm, "<blockquote>$1</blockquote>");
  text = text.replace(/^\s*[-*]\s+(.+)$/gm, "<p>• $1</p>");
  text = text.replace(/^\s*(\d+)\.\s+(.+)$/gm, "<p>$1. $2</p>");
  // 引用角标 [^1] / [1] —— turn-scoped：直接把该轮 refs 身份写进 span 的 data-*，
  // 点击时不再回查全局 S.refs（A：防止跨轮串号）。
  const refsArr = (refs || []).filter(Boolean);
  const byId = {};
  refsArr.forEach(r => { byId[String(r.id)] = r; });
  text = text.replace(/\[\^?(\d+)\]/g, (m, n) => {
    const ref = byId[String(n)];
    if (!ref) return '<span class="cite" data-ref="' + n + '" data-tip="' + attrEsc(t("引用 {0}", n)) + '">' + n + "</span>";
    // P0-4：语义-only 引用在角标 tooltip 里额外给一句人话解释（原文未出现你的原话）。
    const isSem = (ref.match_mode === "semantic-only");
    let tip = ((ref.display_source || ref.title) + "\n" + ref.path + "\n\n" + (ref.snippet || "")).slice(0, 320);
    if (isSem) tip += t("\n\n⚠ 这条引用来自语义相似匹配，原文未出现你的原话");
    // 引用身份全部内联：点击时由 span 自身数据集驱动，不依赖任何全局状态
    const attr = (k, v) => " data-" + k + '="' + attrEsc(v) + '"';
    return '<span class="cite' + (isSem ? " cite-sem" : "") + '" data-ref="' + n + '"' +
      attr("match-mode", ref.match_mode || "lexical") +
      attr("path", ref.path || "") +
      attr("parent-id", ref.parent_id || "") +
      attr("snippet", ref.snippet || "") +
      attr("src-start", ref.source_start_line || 0) +
      attr("src-end", ref.source_end_line || 0) +
      ' data-tip="' + esc(tip).replace(/\n/g, "&#10;") + '">' + n + "</span>";
  });
  text = text.replace(/\n{2,}/g, "</p><p>");
  text = text.replace(/\n/g, "<br>");
  text = "<p>" + text + "</p>";
  text = text.replace(/<p>\s*<\/p>/g, "");
  text = text.replace(/\u0000BLK(\d+)\u0000/g, (m, i) => blocks[+i]);
  return text;
}

/* -------- 未闭合角标缓冲：滞留在缓冲区，待闭合后再统一绘制 -------- */
function splitHold(s) {
  const i = s.lastIndexOf("[");
  if (i < 0) return [s, ""];
  const tail = s.slice(i);
  // 匹配结尾处「可能是角标但尚未闭合」的片段
  if (/^\[\^?\d{0,3}$/.test(tail)) return [s.slice(0, i), tail];
  return [s, ""];
}

/* ---------------------------- 状态 ---------------------------- */
function applyStatus(st) {
  const d = st && st.data ? st.data : st;
  S.ready = !!(d && d.ready);
  const cR = $("#chipReady"), cE = $("#chipEmbed"), cA = $("#chipAI"), cS = $("#chipSync");

  cR.textContent = S.ready ? t("已就绪") : t("初始化中…");
  cR.className = "chip " + (S.ready ? "on" : "off");

  if (!S.ready) return;

  const emb = d.embedding || {}, ai = d.ai || {}, syn = d.sync || {}, db = d.db || {};
  const vecOK = db.vec_ready && !emb.signature_mismatch;
  cE.textContent = vecOK ? t("本地智能搜索：可用") : t("本地智能搜索：仅关键词");
  cE.className = "chip " + (vecOK ? "on" : "warn");

  const aiLabel = ({ ollama: t("本地模型"), api: t("云端"), offline: t("尚未配置"), error: t("不可用") }[ai.resolved] || ai.provider_mode || "—");
  cA.textContent = t("AI 对话：{0}", aiLabel);
  // 悬停说明「为什么是当前状态」—— offline 时尤其要给 reason（如「该模型不支持对话」），
  // 否则用户只看到「尚未配置」，根本不知道卡在哪一步。
  cA.title = ai.reason ? t("AI 对话：{0} —— {1}", aiLabel, ai.reason) : "";
  cA.className = "chip " + (ai.resolved === "ollama" || ai.resolved === "api" ? "on" : (ai.resolved === "error" ? "warn" : "off"));

  cS.textContent = t("同步：{0}", syn.running ? t("{0} 篇 · {1}s", syn.tracked, syn.interval) : t("未运行"));
  cS.className = "chip " + (syn.running ? "on" : "off");

  // 离线授权芯片（状态由后端在 boot 时重算设备指纹并验签得到）
  const cL = $("#chipLicense");
  if (cL) {
    const lic = d.license || {};
    const licOK = lic.status === "OK";
    cL.textContent = t("授权：{0}", licOK ? t("已激活") : (lic.status === "NO_LICENSE" ? t("未激活") : t("异常")));
    cL.className = "chip " + (licOK ? "on" : (lic.status === "NO_LICENSE" ? "off" : "warn"));
    cL.title = lic.message || "";
  }

  renderAlerts(d);
  renderStats(d);
  renderEmptyGuide(d);
  applyLicenseGate(d);
}

/* 未激活时的功能门禁：只拦「抓网页入库 / AI 问答」，
   笔记浏览、本地搜索、拖入文件与粘贴文字入库**始终可用**（绝不锁用户自己的数据）。 */
function applyLicenseGate(d) {
  const lic = (d && d.license) || {};
  if (typeof lic.activated === "boolean") S.licenseOK = lic.activated;
  const show = (sel, on) => { const el = $(sel); if (el) el.hidden = !on; };
  const dis = (sel, off) => {
    const el = $(sel); if (!el) return;
    el.disabled = off; el.title = off ? t("需激活后使用") : "";
  };
  if (!S.licenseOK) {
    dis("#btnCapture", true); dis("#capUrl", true); dis("#btnSend", true);
  } else {
    dis("#btnCapture", false); dis("#capUrl", false);
    // btnSend 交回 send() 自己管理（避免问答流式期间被抢管）
  }
  show("#capGate", !S.licenseOK);
  show("#chatGate", !S.licenseOK);
}

/* 知识库为空时，在问答页顶部直接给出「下一步该点哪里」 */
function renderEmptyGuide(d) {
  const box = $("#emptyGuide");
  if (!box || !d || !d.ready) return;
  if ((d.db && d.db.docs) > 0) { box.innerHTML = ""; return; }
  if (box.dataset.shown === "1") return;   // 只渲染一次，避免输入框被打断
  box.dataset.shown = "1";
  box.innerHTML =
    '<div class="empty-guide"><h5>' + t("知识库还是空的 —— 先加内容，问答才有东西可查") + '</h5><ol>' +
    '<li>' + t("点顶部 <b>「剪藏」</b> 标签 →  把 <code>.md</code> 文件拖进虚线框，或粘贴一个网址抓取") + '</li>' +
    '<li>' + t("也可以把 .md / .txt 笔记直接放进资料库的 <code>notes</code> 文件夹（安装版默认在 文档\\Kavira-Data\\notes），15 秒内自动入库") + '</li>' +
    '<li>' + t("入库后回到这里提问，回答会带 <b>[1]</b> 角标指向原文出处") + '</li></ol>' +
    '<div style="margin-top:11px"><button class="btn primary" onclick="switchTab(\'capture\')">' + t("去添加第一份内容 →") + '</button></div>' +
    "</div>";
}

function renderAlerts(d) {
  const box = $("#alerts");
  const items = [];
  if (d && d.vec_healing) {
    // 自愈中：只给中性提示，不吓人 —— 换过嵌入模型后首次启动会短暂出现，完成后自动消失
    items.push({ cls: "", text: t("正在后台重建向量索引，完成后自动恢复智能搜索（无需任何操作）。") });
  } else if (d && d.db && d.db.signature_mismatch) {
    // 文案由后端生成：真配置变更会给「需重建」指引，临时降级会说明「索引已保留」
    items.push({ cls: "err", text: d.db.signature_mismatch });
  }
  (d && d.warnings ? d.warnings : []).forEach(w => items.push({ cls: "", text: w }));
  box.innerHTML = items.map((it, i) =>
    '<div class="alert ' + it.cls + '">' + esc(it.text) + '<button data-al="' + i + '">×</button></div>'
  ).join("");
  $$("#alerts .alert button").forEach(b => b.onclick = e => e.target.parentElement.remove());
}

/* 对话能力状态文案（后端 ai.state 是稳定枚举，前端只做展示映射）
   ⚠ 不在这里推荐任何具体模型 —— 产品尚未拍板推荐型号。 */
function chatStateText(ai) {
  if (!ai) return "—";
  if (ai.chat_ready) return t("✅ 就绪") + (ai.selected_model ? t("（{0}）", ai.selected_model) : "");
  const map = {
    no_runtime: t("未检测到本地 Ollama"),
    no_model: t("Ollama 已启动，但本机尚无模型"),
    selection_required: t("本机已有模型，请选择用哪个对话"),
    model_missing: t("原配置的模型在本机已不存在"),
  };
  return (map[ai.state] || t("尚未配置")) + (ai.reason ? t("：{0}", ai.reason) : "");
}

function renderStats(d) {
  if (!d || !d.ready) return;
  const emb = d.embedding || {}, ai = d.ai || {}, db = d.db || {}, syn = d.sync || {};
  const rows = [
    [t("控制台端口"), d.port || "—"],
    [t("运行时长"), t("{0} 秒", d.uptime || 0)],
    [t("文档 / 切片 / 父块"), (db.docs || 0) + " / " + (db.chunks || 0) + " / " + (db.parents || 0)],
    // 库规模档位：让用户有个参照系，而不是只看到一个孤零零的切片数
    [t("库规模"), (d.capacity && d.capacity.message) || "—"],
    [t("向量召回"), db.vec_ready && !emb.signature_mismatch ? t("已启用") : t("未启用")],
    [t("嵌入源 / 维度"), (emb.source || "—") + " / " + (emb.dim || "—")],
    [t("嵌入签名"), emb.signature ? (emb.signature.model + "@" + emb.signature.dim) : "—"],
    [t("AI 模式 / 实际"), (ai.provider_mode || "—") + " / " + (ai.resolved || "—")],
    [t("对话能力"), chatStateText(ai)],
    [t("本机模型"), t("{0} 个", ai.installed_model_count || 0) +
      (ai.selected_model ? t("，已选 {0}", ai.selected_model) : t("，未选择"))],
    [t("Ollama 探测"), ai.ollama_healthy ? t("在线") : t("离线 ({0})", ai.ollama_detail || "—")],
    ["API Key", ai.api_key_configured ? t("已配置") : t("未配置")],
    [t("同步轮次 / 更新"), (syn.cycles || 0) + " / " + ((syn.indexed || 0) + (syn.updated || 0))],
    [t("冷启动耗时"), (d.boot && d.boot.boot_ms ? d.boot.boot_ms : "—") + " ms"],
  ];
  $("#statKV").innerHTML = rows.map(r => "<b>" + esc(r[0]) + "</b><span>" + esc(r[1]) + "</span>").join("");
  renderNotes(d);
}

/* 系统自愈/自动适配的过程信息 —— 不是告警，放在设置页供排查时查证 */
function renderNotes(d) {
  const box = $("#runNotes");
  if (!box) return;
  const notes = (d && d.notes) || [];
  if (!notes.length) { box.innerHTML = '<div class="hint">' + esc(t("（无）")) + '</div>'; return; }
  box.innerHTML = notes.map(n =>
    '<div class="note-line">· ' + esc(n) + "</div>").join("");
}

async function pollStatus(loop, probe) {
  try {
    // probe=true：让后端绕过 60s 健康缓存现场重探（顶部「刷新」按钮用）。
    // 常规轮询不带 probe —— 后端会在缓存过期后自动重探（最多 60s 一次）。
    const st = await api("/api/status" + (probe ? "?probe=1" : ""));
    applyStatus(st);
    if (loop) setTimeout(() => pollStatus(S.ready), S.ready ? 15000 : 900);
  } catch (e) {
    setTimeout(() => pollStatus(loop), 1500);
  }
}

/* ---------------------------- 问答 ---------------------------- */
function pushMsg(role, html) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.innerHTML = '<div class="who">' + (role === "user" ? t("我") : "W") + '</div><div class="bubble"></div>';
  const bub = wrap.querySelector(".bubble");
  if (html != null) bub.innerHTML = html;
  $("#chatScroll").appendChild(wrap);
  $("#chatScroll").scrollTop = $("#chatScroll").scrollHeight;
  return bub;
}

function renderStream(bub) {
  const [safe] = splitHold(S.full);
  if (safe === S.rendered) return;
  S.rendered = safe;
  S.holding = S.full.slice(safe.length);
  bub.innerHTML = mdToHtml(safe, bub._refs) + '<span class="pending-dot"></span>';
  $("#chatScroll").scrollTop = $("#chatScroll").scrollHeight;
}

async function send() {
  if (!S.licenseOK) { toast(t("问答需激活后使用（设置 → 产品授权）"), 3600); return; }
  const input = $("#chatInput");
  const q = input.value.trim();
  if (!q || S.busy) return;
  S.busy = true;
  $("#btnSend").disabled = true;

  pushMsg("user", mdToHtml(q));
  input.value = "";

  S.full = ""; S.rendered = ""; S.holding = ""; S.refs = []; S.terms = [];
  S.turn = ++S.turnSeq;                // A：新的一轮，分配独立 turn id
  S.q = q;
  const bub = pushMsg("assistant", '<span class="hint">' + esc(t("检索知识库…")) + '</span>');
  bub._refs = [];                      // 本轮的 refs 快照（随 references 帧到达而填充）
  bub._terms = [];                     // 本轮的「问题实词」（随 meta 帧到达而填充）

  try {
    const resp = await fetch("/api/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q, history: [] }),
    });
    if (!resp.ok || !resp.body) throw new Error("HTTP " + resp.status);

    const reader = resp.body.getReader();
    const dec = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx); buf = buf.slice(idx + 2);
        const line = raw.split("\n").find(l => l.startsWith("data:"));
        if (!line) continue;
        handleFrame(JSON.parse(line.slice(5).trim()), bub);
      }
    }
    // 收尾：强制绘制滞留缓冲
    const [safe] = splitHold(S.full);
    const refs = bub._refs || [];
    bub.innerHTML = mdToHtml(S.full, refs) + (refs.length ? refsHtml(refs) : "");
  } catch (e) {
    bub.innerHTML = '<div class="alert err" style="margin:0">' + esc(t("请求失败：{0}", e.message)) + "</div>";
  } finally {
    S.busy = false;
    $("#btnSend").disabled = false;
    $("#chatScroll").scrollTop = $("#chatScroll").scrollHeight;
  }
}

function refsHtml(refs) {
  // 底部「来源」是**文档级**列表：同一篇文档只出现一次。
  // 旧实现按父块逐条渲染 → 一次覆盖型回答会把同一份报告列 5~14 遍（用户看到
  // 一排一模一样的标签）。正文里的 [N] 角标才是逐条证据，来源列表只回答
  // 「答案来自哪几篇资料」。同一文档被引用多处时用 ×N 标注。
  const seen = new Map();
  refs.forEach(r => {
    const key = r.path || (r.display_source || r.title);
    if (!seen.has(key)) seen.set(key, { r, n: 0, allSem: true });
    const g = seen.get(key);
    g.n += 1;
    // P0-4：只有该文档的引用**全部**来自语义通道，才把它标为 semantic-only；
    // 只要有一条字面命中，就按字面命中处理（绝不误标 P0-4「字面命中引用零误标」）。
    if (r.match_mode !== "semantic-only") g.allSem = false;
  });
  const uniq = [...seen.values()];
  const attr = (k, v) => " data-" + k + '="' + attrEsc(v) + '"';
  return '<div class="refs">' + uniq.map(({ r, n, allSem }) => {
    // 来源 chip：文档级跳转（只打开整篇，不强制跳某 Parent），身份内联 data-path。
    const cnt = n > 1 ? ' <span class="ref-n">×' + n + "</span>" : "";
    // semantic-only 徽标：仅当该文档全为语义-only 引用、且用户未关闭标注时显示。
    const badge = (allSem && SEM_LABEL_ON)
      ? '<span class="ref-tag semantic">semantic-only</span>' : "";
    const semNote = allSem ? t("\n\n⚠ 这条引用来自语义相似匹配，原文未出现你的原话") : "";
    return '<span class="ref"' + attr("path", r.path || "") +
      attr("match-mode", allSem ? "semantic-only" : "lexical") +
      ' title="' + esc((r.path || "") + "\n" + (r.snippet || t("点击跳转到该笔记")) + semNote) + '">' +
      // UX-1：来源显示名优先（导入文件→源文件名；剪藏/笔记→标题）
      esc(r.display_source || r.title) + badge + cnt + "</span>";
  }).join("") + "</div>";
}

function handleFrame(f, bub) {
  if (f.type === "references") {
    const refs = f.refs || [];
    S.refs = refs;                              // 兼容旧引用
    S.refsByTurn.set(S.turn, refs);            // A：按 turn 保存快照
    if (bub) bub._refs = refs;                 // 本轮 bubble 自身携带
  } else if (f.type === "meta") {
    (f.warnings || []).forEach(w => toast("⚠ " + w, 3600));
    // 关键词高亮词：随本轮 bubble 保存（turn-scoped，旧轮点击不会串用新轮关键词）
    S.terms = f.terms || [];
    if (bub) bub._terms = S.terms;
    const [safe] = splitHold(S.full);
    // 注意：必须带 bub._refs，否则 meta 帧重绘会丢掉角标的 data-* 身份（点不动）
    // 「提供方 / 检索路由」这类内部术语不再展示 —— 用户只在意"是不是智能回答"，
    // 专业字段留给设置页「运行状态」自己去查。
    bub.innerHTML = mdToHtml(safe, bub._refs) + '<span class="pending-dot"></span>';
  } else if (f.type === "notice") {
    toast("⚠ " + f.message, 3600);
  } else if (f.type === "delta") {
    S.full += f.content || "";
    renderStream(bub);   // 未闭合角标滞留，不提前绘制半截标记
  } else if (f.type === "error") {
    S.full += "\n\n> ⚠ " + (f.message || t("模型服务异常"));
    bub.innerHTML = mdToHtml(S.full);
  }
}

  /* ---------------------------- 剪藏 ---------------------------- */
  /* 抓取前先问后端「这个网页是不是已经保存过」。
     注意后端在真正抓取时**自己也会再查一次** —— 这里的预检只是为了让界面
     能在重复时给出选择，不是安全/正确性的依据。 */
  async function doCapture() {
  if (!S.licenseOK) { toast(t("抓取网页需激活后使用（设置 → 产品授权）"), 3600); return; }
    const url = $("#capUrl").value.trim();
    if (!url) return toast(t("请输入 URL"));
    const box = $("#capResult");
    box.innerHTML = '<span class="hint"><span class="spin"></span> ' + esc(t("正在检查这个网页是否已保存过…")) + '</span>';
    $("#btnCapture").disabled = true;
    let dup = null;
    try {
      const chk = await api("/api/capture/duplicate?url=" + encodeURIComponent(url));
      dup = (chk.data || {}).existing || null;
    } catch (e) {
      // 预检失败不阻断抓取：后端自己会判重，真重复时会返回 409
    }
    $("#btnCapture").disabled = false;
    if (dup) return renderDuplicateChoice(url, dup);
    return doCaptureWith(url, "abort");
  }

  /* 重复来源 URL 的四个选项。刻意不做「一律禁止重复」—— 网页会更新，
     用户有时确实要保存同一页面的不同版本，所以把决定权交回用户。 */
  function renderDuplicateChoice(url, dup) {
    const box = $("#capResult");
    box.innerHTML =
      '<div class="alert">' + esc(t("⚠ 该网页已经保存过：{0}", dup.title || dup.rel_path)) + "</div>" +
      '<div class="hint" style="margin:6px 0">' + esc(t("请选择处理方式")) + "</div>" +
      '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
      '<button class="btn" data-dup="open">' + esc(t("打开已有")) + "</button>" +
      '<button class="btn primary" data-dup="update">' + esc(t("更新已有")) + "</button>" +
      '<button class="btn" data-dup="new">' + esc(t("另存为新版本")) + "</button>" +
      '<button class="btn ghost" data-dup="cancel">' + esc(t("取消")) + "</button>" +
      "</div>";
    $$("#capResult [data-dup]").forEach(function (b) {
      b.onclick = function () {
        const act = b.dataset.dup;
        if (act === "cancel") {
          box.innerHTML = '<span class="hint">' + esc(t("已取消，未做任何改动。")) + '</span>';
          return;
        }
        if (act === "open") return openNoteByPath(dup.rel_path);
        return doCaptureWith(url, act);
      };
    });
  }

  async function doCaptureWith(url, onDup) {
    const box = $("#capResult");
    box.innerHTML = '<span class="hint"><span class="spin"></span> ' + esc(t("正在抓取并清洗正文…")) + '</span>';
    $("#btnCapture").disabled = true;
    try {
      const r = await api("/api/capture/url", {
        method: "POST",
        body: JSON.stringify({ url: url, on_duplicate: onDup }),
      });
    const d = r.data || {};
    // 系统自愈 / 自动降级的过程信息：按项目约定不打扰用户，只在结果区作说明
    const notesHtml = (d.notes && d.notes.length)
      ? '<div class="hint" style="margin-top:6px">' + d.notes.map(function (n) { return "· " + esc(n); }).join("<br>") + "</div>"
      : "";
    if (r.status === "partial_fallback") {
      box.innerHTML = '<div class="alert">⚠ ' + esc(r.message) + "</div>" +
        '<div class="hint">' + esc(t("已保存：{0} · 快照：{1}", d.file_path, d.snapshot_path || "—")) + "</div>" + notesHtml;
      toast(t("该页面为前端动态渲染，仅保留快照"), 4200);
    } else if (r.code === 200) {
      box.innerHTML = '<div class="alert info">✅ ' + esc(r.message || t("抓取成功")) + "</div>" +
        '<div class="hint">' + esc(t("标题：{0} · 字数：{1} · 文件：{2} · 抽取器：{3}",
          d.title, d.char_count, d.file_path, d.extractor || "—")) + "</div>" + notesHtml;
      toast(t("已入库并建立索引"));
    } else {
      box.innerHTML = '<div class="alert err">' + esc(r.message || t("抓取失败")) + "</div>";
    }
  } catch (e) {
    box.innerHTML = '<div class="alert err">' + esc(e.message) + "</div>";
  } finally {
    $("#btnCapture").disabled = false;
    loadNotes();
  }
}

async function doSaveNote() {
  const title = $("#noteTitle").value.trim(), content = $("#noteBody").value.trim();
  if (!content) return toast(t("正文不能为空"));
  $("#btnSaveNote").disabled = true;
  try {
    const r = await api("/api/notes/save", { method: "POST", body: JSON.stringify({ title, content }) });
    $("#saveHint").textContent = r.code === 200 ? "✅ " + r.message + " · " + (r.data.file_path || "") : "⚠ " + r.message;
    if (r.code === 200) { $("#noteTitle").value = ""; $("#noteBody").value = ""; loadNotes(); }
  } finally { $("#btnSaveNote").disabled = false; }
}

/* ------------------- 拖拽 / 选择文件导入知识库 ------------------- */
/* 由后端 /api/import/formats 提供能力清单，前端不硬编码，避免两边漂移 */
const IMPORT = { exts: [], loaded: false };

async function loadImportFormats() {
  try {
    const r = await api("/api/import/formats");
    const d = r.data || {};
    IMPORT.exts = d.exts || [];
    IMPORT.loaded = true;
    const picker = $("#fileInput");
    if (picker && IMPORT.exts.length) picker.setAttribute("accept", IMPORT.exts.join(","));
    const hint = $("#formatHint");
    if (hint) {
      const cats = (d.categories || []).filter(c => (c.exts || []).length);
      hint.innerHTML = cats.map(c =>
        "<b>" + esc(c.name) + "</b>　" + c.exts.map(e => "<code>" + esc(e) + "</code>").join(" ")
      ).join("<br>") +
        "<br><span style='color:var(--warn)'>" + esc(t("暂不支持：")) +
        esc((d.unsupported.legacy_office || []).join(" ")) + " " +
        esc((d.unsupported.image || []).join(" ")) + " " +
        esc((d.unsupported.av || []).slice(0, 4).join(" ")) +
        " —— " + esc(d.unsupported.note) + "</span>" +
        (d.pdf_backend ? "" : "<br><span style='color:var(--warn)'>" +
          t("PDF 解析库未安装：执行 {0} 后可用。", "<code>python setup_runtime_windows.py --with-pdf</code>") +
          "</span>");
    }
  } catch (e) { /* 拿不到就退化为「不限制 accept」，由后端给出明确错误 */ }
}

function isBinaryExt(name) {
  const ext = ("." + (name.split(".").pop() || "")).toLowerCase();
  // 文本族前端直读（可顺带处理 GBK）；其余一律走 base64，避免二进制被 UTF-8 破坏
  const TEXTY = [".md", ".markdown", ".mdown", ".txt", ".log", ".ini", ".cfg", ".conf",
    ".env", ".properties", ".rst", ".org", ".csv", ".tsv", ".json", ".jsonl", ".ndjson",
    ".yaml", ".yml", ".toml", ".xml", ".srt", ".vtt", ".ass", ".ssa", ".lrc",
    ".html", ".htm", ".xhtml", ".rtf"];
  if (TEXTY.includes(ext)) return false;
  return true;
}

async function readTextSmart(file) {
  const buf = await file.arrayBuffer();
  let text = new TextDecoder("utf-8").decode(buf);
  // 中文环境常见 GBK 编码：UTF-8 解出替换符就换 GB18030 再试
  if (text.includes("\ufffd")) {
    try {
      const alt = new TextDecoder("gb18030").decode(buf);
      if (!alt.includes("\ufffd")) return alt;
    } catch (e) { /* 浏览器不支持则保持 UTF-8 结果 */ }
  }
  return text;
}

function bufToBase64(buf) {
  const bytes = new Uint8Array(buf);
  let bin = "";
  const CHUNK = 0x8000;                 // 分块拼接，避免超长字符串导致栈溢出
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

async function importFiles(files) {
  const zone = $("#dropZone"), out = $("#dzResult");
  if (!zone || !out) return;
  // 防重入：导入期间用户完全可以再拖一批/再选一次。没有这道闸，两个循环会并发跑，
  // 进度文本互相覆盖，同一个文件还可能被入库两次（拖拽 + 选择器同时触发）。
  if (zone.classList.contains("busy")) {
    toast(t("上一批还在导入，请等它完成"), 3000);
    return;
  }
  const mainLabel = zone.querySelector(".dz-main");

  // ---- 1) 先只按元信息过滤，**不读内容** ----
  const accepted = [], skipped = [];
  for (const f of files) {
    if (f.size > 20 * 1024 * 1024) { skipped.push(t("{0}（超过 20MB）", f.name)); continue; }
    const ext = ("." + (f.name.split(".").pop() || "")).toLowerCase();
    if (IMPORT.loaded && IMPORT.exts.length && !IMPORT.exts.includes(ext)) {
      skipped.push(t("{0}（不支持 {1}）", f.name, ext));
      continue;
    }
    accepted.push(f);
  }
  const skipHtml = skipped.length
    ? '<span class="bad">' + esc(t("已跳过：{0}", skipped.join(LANG === "en" ? ", " : "、"))) + "</span><br>" : "";
  if (!accepted.length) {
    out.innerHTML = '<span class="bad">' + esc(t("没有可导入的文件")) + '</span><br>' + skipHtml;
    return;
  }

  zone.classList.add("busy");
  const rows = [];
  let okN = 0, failN = 0;

  const render = (headline) => {
    out.innerHTML = (headline ? "<b>" + esc(headline) + "</b><br>" : "")
      + skipHtml + rows.join("<br>");
  };

  /* ---- 2) 逐个提交：每完成一个就刷新一次进度 ----
   *
   * 为什么不用「一次性 POST 全部」：
   *   · **没有进度**：几十个文件要几十秒到几分钟，界面只显示一句「正在转换并索引…」，
   *     用户会以为卡死而刷新页面 —— 刷新会中断剩余文件（已完成的会保住）；
   *   · **内存峰值高**：原实现先把每个文件都读成 base64 再攒成一个大 payload，
   *     50 个几 MB 的文件能吃掉上百 MB 内存（浏览器标签页会明显变卡）。
   *     逐文件提交后，任一时刻内存里只有一个文件；
   *   · **单点失败会连坐**：整批一个请求，任一文件抛错都会让整批的结果变得可疑。
   *     现在每个文件独立成败，最后一个失败不影响其余的落库。
   * 本地回环请求开销可忽略（每次几毫秒）。
   */
  try {
    for (let i = 0; i < accepted.length; i++) {
      const f = accepted[i];
      const short = f.name.length > 30 ? f.name.slice(0, 28) + "…" : f.name;
      mainLabel.textContent = t("正在导入 {0}/{1}：{2}", i + 1, accepted.length, short);
      render(t("正在导入 {0}/{1}（成功 {2}）：", i + 1, accepted.length, okN));

      let item;
      try {
        item = isBinaryExt(f.name)
          ? { filename: f.name, content_base64: bufToBase64(await f.arrayBuffer()) }
          : { filename: f.name, content: await readTextSmart(f) };
      } catch (e) {
        failN++;
        rows.push('<span class="bad">❌ ' + esc(f.name) + "</span>" + esc(t(" —— 读取失败：{0}", (e.message || e))));
        continue;
      }

      try {
        const r = await api("/api/notes/import", {
          method: "POST", body: JSON.stringify({ files: [item] }),
        });
        const x = (((r.data || {}).results) || [])[0] || {};
        if (x.ok) {
          okN++;
          rows.push('<span class="ok">✅ ' + esc(f.name) + "</span>" + esc(t(" —— {0}{1}",
            x.message || t("已入库"), t("（{0} 字）", x.char_count || 0))));
        } else {
          failN++;
          rows.push('<span class="bad">❌ ' + esc(f.name) + "</span>" + esc(t(" —— {0}",
            x.message || t("导入失败"))));
        }
      } catch (e) {
        failN++;
        rows.push('<span class="bad">❌ ' + esc(f.name) + "</span> —— " + esc(e.message));
      }
    }
  } finally {
    // ⚠ 必须放 finally：中途任何异常都不能让拖拽区卡在 busy 状态（那样用户再也拖不进文件）
    zone.classList.remove("busy");
    mainLabel.textContent = t("把文件拖到这里");
  }

  const summary = t("导入完成：成功 {0} / {1}", okN, accepted.length)
    + (failN ? t("，失败 {2}", failN) : "");
  render(summary);
  if (okN) toast("✅ " + summary);
  else toast(t("⚠ 全部导入失败，请看下方原因"), 4000);
  await loadNotes();
}

function initDropZone() {
  const zone = $("#dropZone"), picker = $("#fileInput");
  if (!zone || !picker) return;
  ["dragenter", "dragover"].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); zone.classList.add("over"); }));
  ["dragleave", "dragend", "drop"].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); zone.classList.remove("over"); }));
  zone.addEventListener("drop", e => {
    const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []);
    if (files.length) importFiles(files);
  });
  picker.addEventListener("change", e => {
    const files = Array.from(e.target.files || []);
    if (files.length) importFiles(files);
    e.target.value = "";
  });
  // 阻止把文件拖到页面其他位置时浏览器直接打开它
  ["dragover", "drop"].forEach(ev =>
    window.addEventListener(ev, e => { if (e.target.closest("#dropZone") === null) e.preventDefault(); }));
}

/* ---------------------------- 笔记 ---------------------------- */
let noteCache = [];
async function loadNotes() {
  let r;
  try {
    r = await api("/api/notes?limit=500");
  } catch (e) {
    // 服务已停（如启动窗口被关）时给出明确提示，而不是静默保持旧列表
    toast(e.message || t("读取文档列表失败"), 5200);
    return;
  }
  noteCache = r.data || [];
  $("#docCount").textContent = noteCache.length;
  await loadCollections();   // 分类是管理视图数据；拉不到也不能阻断笔记列表
  renderNoteList();
}
/* -------------------- Collections（资料集）：用户组织层 --------------------
 * 只做「组织 / 浏览 / 筛选」：类目、一篇多分类、显示标题、回收站。
 * **完全不参与**搜索与问答 —— 默认检索仍全局（见 docs/COLLECTIONS_ARCHITECTURE.md）。
 * 分类数据是 durable 用户状态，存 <Library>/metadata/collections.json（后端）。
 * ------------------------------------------------------------------------- */
let collCache = { collections: [], membership: {}, display_titles: {}, trash: [] };

async function loadCollections() {
  try {
    const r = await api("/api/collections");
    if (r && r.code === 200 && r.data) collCache = r.data;
  } catch (e) { /* 分类用不了时保持旧缓存，绝不阻断笔记列表与正文 */ }
  renderCollectionFilter();
}

function collById(id) { return (collCache.collections || []).find(c => c.id === id); }
function docCollections(docId) {
  return (collCache.membership[docId] || []).map(collById).filter(Boolean);
}
function docDisplayTitle(n) {
  return collCache.display_titles[n.doc_id] || n.display_source || n.title || t("(无标题)");
}
function isTrashed(n) { return (collCache.trash || []).indexOf(n.doc_id) >= 0; }

function renderCollectionFilter() {
  const sel = $("#noteCollectionFilter");
  if (!sel) return;
  const cur = sel.value;
  const opts = ['<option value="">' + esc(t("全部分类")) + "</option>"];
  (collCache.collections || []).slice()
    .sort((a, b) => a.name.localeCompare(b.name, "zh"))
    .forEach(c => opts.push('<option value="' + esc(c.id) + '">' + esc(c.name) + "</option>"));
  const nTrash = (collCache.trash || []).length;
  opts.push('<option value="__trash__">' + esc(nTrash ? t("回收站（{0}）", nTrash) : t("回收站")) + "</option>");
  sel.innerHTML = opts.join("");
  if (Array.from(sel.options).some(o => o.value === cur)) sel.value = cur;
}

function renderNoteList() {
  const kw = $("#noteFilter").value.trim().toLowerCase();
  const cf = $("#noteCollectionFilter") ? $("#noteCollectionFilter").value : "";
  const inTrash = cf === "__trash__";
  // 回收站视图 vs 正常视图：正常视图永远不含已软删的笔记
  let list = noteCache.filter(n => isTrashed(n) === inTrash);
  if (!inTrash) {
    if (cf) list = list.filter(n => (collCache.membership[n.doc_id] || []).indexOf(cf) >= 0);
    if (kw) list = list.filter(n =>
      (docDisplayTitle(n) || "").toLowerCase().includes(kw)
      || (n.title || "").toLowerCase().includes(kw) || (n.rel_path || "").toLowerCase().includes(kw));
  }
  $("#noteList").innerHTML = list.map(n => {
    const tags = docCollections(n.doc_id)
      .map(c => '<span class="tag">' + esc(c.name) + "</span>").join("");
    return '<div class="list-item" data-path="' + esc(n.rel_path) + '">' +
      '<div class="t">' + esc(docDisplayTitle(n)) + "</div>" +
      '<div class="m"><span>' + esc(n.rel_path) + "</span>" +
      (n.status === "partial_fallback" ? '<span class="pill warn">' + esc(t("快照")) + "</span>" : "") +
      "<span>" + esc(t("{0} 切片", n.chunks || 0)) + "</span></div>" +
      (tags ? '<div class="tags">' + tags + "</div>" : "") +
      '<button class="more" title="' + attrEsc(t("更多操作")) + '">⋯</button>' +
    "</div>";
  }).join("") || '<div class="hint">'
    + esc(inTrash ? t("回收站是空的。") : t("暂无文档，去「剪藏」页录入一篇吧。")) + "</div>";

  $$("#noteList .list-item").forEach(el => {
    el.onclick = () => openNoteItem(el);
    const btn = el.querySelector(".more");
    if (btn) btn.onclick = (e) => {
      e.stopPropagation();
      const n = noteCache.find(x => x.rel_path === el.dataset.path);
      if (n) openNoteMenu(btn, n, inTrash);
    };
  });
}

/* ---- 自绘弹层（零框架，零依赖）---- */
function _closePop() { $$(".pop-layer").forEach(x => x.remove()); }

function _popup(anchor, html) {
  _closePop();
  const wrap = document.createElement("div");
  wrap.className = "pop-layer";
  wrap.innerHTML = html;
  document.body.appendChild(wrap);
  const r = anchor.getBoundingClientRect();
  wrap.style.left = Math.max(8, Math.min(r.right - wrap.offsetWidth, window.innerWidth - wrap.offsetWidth - 10)) + "px";
  wrap.style.top = (r.bottom + 4) + "px";
  setTimeout(() => document.addEventListener("click", _closePop, { once: true }), 0);
  return wrap;
}

function openNoteMenu(anchor, n, inTrash) {
  const items = inTrash
    ? [[t("恢复"), "restore", ""], [t("永久删除"), "purge", "danger"]]
    : [[t("编辑标题"), "title", ""], [t("分类"), "collections", ""], [t("移入回收站"), "trash", "danger"]];
  const wrap = _popup(anchor, '<div class="menu">' + items.map(([label, act, cls]) =>
    '<button data-act="' + act + '"' + (cls ? ' class="' + cls + '"' : "") + ">" + esc(label) + "</button>")
    .join("") + "</div>");
  wrap.querySelectorAll("button").forEach(b => b.onclick = (e) => {
    e.stopPropagation();
    _closePop();
    const act = b.dataset.act;
    if (act === "title") editNoteTitle(n);
    else if (act === "collections") editNoteCollections(n);
    else if (act === "trash") trashNote(n);
    else if (act === "restore") restoreNote(n);
    else if (act === "purge") purgeNote(n);
  });
}

function _modal(title, bodyHtml, onReady) {
  _closePop();
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  mask.innerHTML = '<div class="modal"><h4>' + esc(title) + "</h4>" + bodyHtml + "</div>";
  document.body.appendChild(mask);
  mask.onclick = (e) => { if (e.target === mask) mask.remove(); };
  const close = () => mask.remove();
  if (onReady) onReady(mask.querySelector(".modal"), close);
  return mask;
}

function editNoteTitle(n) {
  _modal(t("编辑标题"),
    '<input type="text" id="_titleIn" value="' + attrEsc(docDisplayTitle(n)) + '">' +
    '<div class="hint" style="margin-top:8px">' + esc(t("只改显示标题，不动文件名（文件仍是 {0}）。", n.rel_path)) + "</div>" +
    '<div class="row" style="margin-top:12px;justify-content:flex-end">' +
    '<button class="btn" data-cancel>' + esc(t("取消")) + '</button><button class="btn primary" data-ok>' + esc(t("保存")) + '</button></div>',
    (root, close) => {
      const inp = root.querySelector("#_titleIn");
      inp.focus(); inp.select();
      root.querySelector("[data-cancel]").onclick = close;
      root.querySelector("[data-ok]").onclick = async () => {
        const r = await api("/api/notes/display_title", {
          method: "POST", body: JSON.stringify({ doc_id: n.doc_id, title: inp.value })
        });
        if (r.code === 200) {
          const title = inp.value.trim();
          if (title) collCache.display_titles[n.doc_id] = title; else delete collCache.display_titles[n.doc_id];
          close(); renderNoteList(); toast(t("标题已更新"));
        } else { toast(r.message || t("保存失败"), 3200); }
      };
    });
}

async function editNoteCollections(n) {
  await loadCollections();
  const cur = new Set(collCache.membership[n.doc_id] || []);
  const rows = (collCache.collections || []).slice()
    .sort((a, b) => a.name.localeCompare(b.name, "zh"))
    .map(c => '<div class="ck-row">'
      + '<label class="ck"><input type="checkbox" value="' + attrEsc(c.id) + '"'
      + (cur.has(c.id) ? " checked" : "") + '> <span class="ck-name">' + esc(c.name) + "</span></label>"
      + '<button class="ck-op" data-ren="' + attrEsc(c.id) + '" title="' + attrEsc(t("重命名类目")) + '">✎</button>'
      + '<button class="ck-del" data-del="' + attrEsc(c.id) + '" title="' + attrEsc(t("删除类目（不会删除文档）")) + '">✕</button>'
      + "</div>").join("");
  _modal(t("分类（可多选）"),
    '<div class="ck-list">' + (rows || '<div class="hint">' + esc(t("还没有类目，在下面新建一个。")) + "</div>") + "</div>" +
    '<div class="row" style="margin-top:10px;gap:8px">' +
    '<input type="text" id="_newColl" class="grow" placeholder="' + attrEsc(t("新建类目，回车添加")) + '">' +
    '<button class="btn" id="_addColl">' + esc(t("新建")) + '</button></div>' +
    '<div class="row" style="margin-top:12px;justify-content:flex-end">' +
    '<button class="btn" data-cancel>' + esc(t("取消")) + '</button><button class="btn primary" data-ok>' + esc(t("保存")) + '</button></div>',
    (root, close) => {
      // 重命名类目：点 ✎ → 就地变成输入框（Enter 提交 / Esc 取消 / 失焦提交）
      const bindRen = (btn) => {
        if (!btn) return;
        btn.onclick = (e) => {
          e.preventDefault(); e.stopPropagation();
          const row = btn.closest(".ck-row");
          const c = collCache.collections.find(x => x.id === btn.dataset.ren);
          const nameEl = row && row.querySelector(".ck-name");
          if (!c || !nameEl) return;
          const input = document.createElement("input");
          input.type = "text"; input.className = "ck-rename"; input.value = c.name;
          nameEl.replaceWith(input); input.focus(); input.select();
          let done = false;
          const finish = async () => {
            if (done) return; done = true;
            const nm = input.value.trim();
            if (!nm || nm === c.name) { if (input.parentNode) input.replaceWith(nameEl); return; }
            const rr = await api("/api/collections/rename",
              { method: "POST", body: JSON.stringify({ id: c.id, name: nm }) });
            if (rr.code !== 200) { toast(rr.message || t("重命名失败"), 3200); if (input.parentNode) input.replaceWith(nameEl); return; }
            c.name = nm;
            close();
            await loadCollections();
            toast(t("类目已重命名"));
            editNoteCollections(n);
          };
          input.onkeydown = (ev) => {
            if (ev.key === "Enter") { ev.preventDefault(); finish(); }
            else if (ev.key === "Escape") { done = true; if (input.parentNode) input.replaceWith(nameEl); }
          };
          input.onblur = () => finish();
        };
      };
      // 删除类目：只删类目，**绝不删除文档**（后端已保证；关系从所有成员移除）
      const bindDel = (btn) => {
        if (!btn) return;
        btn.onclick = async (e) => {
          e.preventDefault(); e.stopPropagation();
          const c = collCache.collections.find(x => x.id === btn.dataset.del);
          if (!confirm(t("删除类目「{0}」？\n\n只删除这个类目，不会删除任何文档。", c ? c.name : ""))) return;
          const r = await api("/api/collections/delete",
            { method: "POST", body: JSON.stringify({ id: btn.dataset.del }) });
          if (r.code !== 200) { toast(r.message || t("删除失败"), 3200); return; }
          close();
          await loadCollections();
          toast(t("类目已删除"));
          editNoteCollections(n);   // 重开，反映最新类目与勾选状态
        };
      };
      const addNew = async () => {
        const inp = root.querySelector("#_newColl");
        const name = inp.value.trim();
        if (!name) return;
        const r = await api("/api/collections/create", { method: "POST", body: JSON.stringify({ name }) });
        if (r.code !== 200) { toast(r.message || t("新建失败"), 3200); return; }
        inp.value = "";
        collCache.collections.push(r.data);
        const listEl = root.querySelector(".ck-list");
        const hint = listEl.querySelector(".hint"); if (hint) hint.remove();
        const row = document.createElement("div");
        row.className = "ck-row";
        row.innerHTML = '<label class="ck"><input type="checkbox" value="' + attrEsc(r.data.id)
          + '" checked> <span class="ck-name">' + esc(r.data.name) + "</span></label>"
          + '<button class="ck-op" data-ren="' + attrEsc(r.data.id) + '" title="' + attrEsc(t("重命名类目")) + '">✎</button>'
          + '<button class="ck-del" data-del="' + attrEsc(r.data.id)
          + '" title="' + attrEsc(t("删除类目（不会删除文档）")) + '">✕</button>';
        listEl.appendChild(row);
        bindRen(row.querySelector("[data-ren]"));
        bindDel(row.querySelector("[data-del]"));
      };
      root.querySelectorAll("[data-ren]").forEach(bindRen);
      root.querySelectorAll("[data-del]").forEach(bindDel);
      root.querySelector("#_addColl").onclick = addNew;
      root.querySelector("#_newColl").onkeydown = (e) => {
        if (e.key === "Enter") { e.preventDefault(); addNew(); }
      };
      root.querySelector("[data-cancel]").onclick = close;
      root.querySelector("[data-ok]").onclick = async () => {
        const ids = $$('input[type=checkbox]', root).filter(x => x.checked).map(x => x.value);
        const r = await api("/api/collections/assign", {
          method: "POST", body: JSON.stringify({ doc_id: n.doc_id, collection_ids: ids })
        });
        if (r.code === 200) {
          if (ids.length) collCache.membership[n.doc_id] = ids;
          else delete collCache.membership[n.doc_id];
          close(); renderNoteList(); toast(t("分类已更新"));
        } else { toast(r.message || t("保存失败"), 3200); }
      };
    });
}

async function trashNote(n) {
  if (!confirm(t("把「{0}」移入回收站？\n\n文件不会被删除，可在「回收站」里恢复。", docDisplayTitle(n)))) return;
  const r = await api("/api/notes/trash", { method: "POST", body: JSON.stringify({ doc_id: n.doc_id }) });
  if (r.code === 200) {
    if ((collCache.trash || []).indexOf(n.doc_id) < 0) collCache.trash.push(n.doc_id);
    renderCollectionFilter(); renderNoteList(); toast(t("已移入回收站"));
  } else { toast(r.message || t("操作失败"), 3200); }
}

async function restoreNote(n) {
  const r = await api("/api/notes/restore", { method: "POST", body: JSON.stringify({ doc_id: n.doc_id }) });
  if (r.code === 200) {
    collCache.trash = (collCache.trash || []).filter(x => x !== n.doc_id);
    renderCollectionFilter(); renderNoteList(); toast(t("已恢复"));
  } else { toast(r.message || t("操作失败"), 3200); }
}

/* 永久删除 —— 回收站的最后一站，**不可逆**。
 * 交互强度：明确警告的确认弹层（红字「此操作不可撤销」+ 取消/永久删除）。
 * 删除范围：默认只删 Markdown 真相源与派生索引（索引可全量重建）；
 *   「原件」（剪藏网页 / 导入的 Office / PDF）往往**无法再生**，
 *   所以做成勾选框由用户当场决定 —— 不替用户销毁不可替代的数据。 */
function purgeNote(n) {
  const name = docDisplayTitle(n);
  _modal(t("永久删除？"),
    '<div style="line-height:1.75">' + t("即将<b>永久删除</b>「{0}」", esc(name)) + '<br>' +
      '<span class="hint">' + esc(n.rel_path) + '</span><br><br>' +
      '<span style="color:var(--danger);font-weight:600">' + esc(t("此操作不可撤销")) + '</span>' +
      esc(t("：笔记文件与其检索索引会被彻底清除，无法再从回收站恢复。")) + '</div>' +
    '<label class="row" style="margin-top:12px;gap:7px;align-items:flex-start;' +
      'font-size:12.5px;line-height:1.55;cursor:pointer">' +
      '<input type="checkbox" id="_purgeOrig" style="margin-top:3px">' +
      '<span>' + t("同时删除它的<b>原件文件</b>（剪藏网页 / 导入的 Office、PDF 等）") + '<br>' +
      '<span class="hint">' + esc(t("默认不勾选 —— 原件往往无法再生；该笔记若无原件，勾选也无影响。")) + '</span>' +
      '</span></label>' +
    '<div class="row" style="margin-top:14px;justify-content:flex-end">' +
      '<button class="btn" data-cancel>' + esc(t("取消")) + '</button>' +
      '<button class="btn danger" data-ok>' + esc(t("永久删除")) + '</button></div>',
    (root, close) => {
      root.querySelector("[data-cancel]").onclick = close;
      root.querySelector("[data-ok]").onclick = async () => {
        const also = !!root.querySelector("#_purgeOrig").checked;
        const r = await api("/api/notes/purge", {
          method: "POST",
          body: JSON.stringify({ doc_id: n.doc_id, delete_originals: also })
        });
        if (r.code !== 200) { toast(r.message || t("删除失败"), 3200); return; }
        collCache.trash = (collCache.trash || []).filter(x => x !== n.doc_id);
        delete collCache.membership[n.doc_id];
        delete collCache.display_titles[n.doc_id];
        noteCache = noteCache.filter(x => x.doc_id !== n.doc_id);
        close();
        renderCollectionFilter(); renderNoteList();
        // 删掉的正好是当前打开的那篇 → 清掉面板，避免留下「已删除内容」的残影
        if (NOTE && NOTE.path === n.rel_path) {
          NOTE.payload = null;
          $("#noteTitleBar").textContent = "";
          $("#noteView").innerHTML = '<span class="empty">' + esc(t("该笔记已被永久删除。")) + '</span>';
        }
        toast(t("已永久删除"));
      };
    });
}

/* 打开一条笔记（列表项已渲染时使用）。抽成具名函数，供问答引用跳转复用。
 * jump 非空时（B）：证据跳转 —— 打开后按 parent_id 定位证据块并高亮。 */
async function openNoteItem(el, jump, nav, terms) {
    $$("#noteList .list-item").forEach(x => x.classList.remove("active"));
    el.classList.add("active");
    $("#noteTitleBar").textContent = el.querySelector(".t").textContent;
    let r;
    try {
      r = await api("/api/notes/content?path=" + encodeURIComponent(el.dataset.path));
    } catch (e) {
      // 关键：失败必须**显式**呈现。旧实现没有 try/catch，连接失败时
      // 「标题变了、内容不动」，用户会误以为程序坏了（真机反馈过）。
      NOTE.payload = null;
      $("#noteSeg").hidden = true;
      $("#noteView").innerHTML = '<div class="alert err" style="margin:8px 0">'
        + esc(e.message || t("读取失败")) + "<br>" + esc(t("请重新启动 Kavira（双击启动脚本）后刷新本页。")) + "</div>";
      return;
    }
    if (nav != null && nav !== NOTE_NAV_SEQ) return;                 // B：有更新的导航已发生 → 放弃
    if (r.code !== 200) {
      NOTE.payload = null;
      $("#noteSeg").hidden = true;
      $("#noteView").innerHTML = '<span class="empty">' + esc(t("读取失败：{0}", r.message || "")) + "</span>";
      return;
    }
    NOTE.payload = r.data;
    const orig = r.data.original;
    $("#noteSeg").hidden = false;
    const btn = $("#segOriginal");
    btn.disabled = !orig;
    btn.title = orig
      ? t("查看{0}：{1}（{2}）", noteLabels(orig).original, orig.name, fmtSize(orig.size))
      : t("该笔记没有留存原件（纯 Markdown / 纯文本导入）");
    if (jump) {
      // 证据跳转只在「渲染」视图里定位（B4：不做 PDF/DOCX 页面坐标）。
      // 若该笔记默认开「原版」，先切回渲染视图再定位。
      NOTE.view = "rendered";
      setNoteView(NOTE.view);
      await jumpToEvidence(el.dataset.path, jump, nav, terms);
      return;
    }
    // C：打开一篇笔记即清掉上一次引用的持久高亮（用户主动切换了上下文）
    _clearEvidenceHighlight();
    // 动态页降级（partial_fallback）的快照在沙箱里只会白屏（正文全靠脚本渲染），
    // 默认进「阅读」视图才有内容；用户仍可手动点「网页快照」（有明确提示条）。
    const isFallback = frontmatterValue(r.data.content, "status") === "partial_fallback";
    NOTE.view = (orig && !isFallback) ? "original" : "rendered";
    setNoteView(NOTE.view);
}

/* 按路径打开笔记：供问答内文角标 / 底部来源 chips 跳转使用 */
async function openNoteByPath(path, jump, nav, terms) {
  if (!path) return;
  if (nav != null && nav !== NOTE_NAV_SEQ) return;                 // B：守卫
  switchTab("notes");
  await loadNotes();                                // 列表异步渲染，必须等它出来
  if (nav != null && nav !== NOTE_NAV_SEQ) return;                 // B：等待期间可能被新点击覆盖
  const find = () => $$("#noteList .list-item").find(x => x.dataset.path === path);
  let el = find();
  if (!el && $("#noteFilter") && $("#noteFilter").value) {
    $("#noteFilter").value = "";        // 可能被过滤词挡住 → 清空后重试
    await loadNotes();
    if (nav != null && nav !== NOTE_NAV_SEQ) return;
    el = find();
  }
  if (!el) { toast(t("找不到该笔记（可能已被删除）"), 3200); return; }
  el.scrollIntoView({ block: "center" });
  await openNoteItem(el, jump, nav, terms);
}

/* -------- B/A：证据精确定位（**源行锚点为主**，snippet 文本仅作旧索索引兜底） --------
   A1/A4：parent_id → source_start_line/source_end_line → 与 DOM 块的
   data-src-start/data-src-end 求交集 → 定位。同一文字在目录与正文各出现一次时，
   两者源行号不同 → 必然落在正文（旧实现在全文搜第一处相同文字，会跳到目录）。 */
/* 清掉 noteView 里残留的引用高亮（C：切换笔记/重新点击时调用） */
function _clearEvidenceHighlight() {
  const box = $("#noteView");
  if (!box) return;
  box.querySelectorAll("mark").forEach(m => {
    const p = m.parentNode;
    while (m.firstChild) p.insertBefore(m.firstChild, m);
    m.remove();
    if (p.normalize) p.normalize();
  });
  box.querySelectorAll(".ev-hl,.ev-hl-persist,.ev-region-soft").forEach(el =>
    el.classList.remove("ev-hl", "ev-hl-persist", "ev-region-soft"));
}

async function jumpToEvidence(path, jump, nav, terms) {
  const box = $("#noteView");
  if (!box || !jump) return;
  if (nav != null && nav !== NOTE_NAV_SEQ) return;                 // B：有更新的导航已覆盖

  // 1) 证据块元数据：parent_id → /api/notes/evidence（section_path + content + 源行范围）
  let ev = null;
  if (jump.parent_id) {
    try {
      const r = await api("/api/notes/evidence?path=" + encodeURIComponent(path) +
        "&parent_id=" + encodeURIComponent(jump.parent_id));
      if (nav != null && nav !== NOTE_NAV_SEQ) return;             // B：证据请求返回前已被新点击覆盖
      if (r.code === 200) ev = r.data;
    } catch (e) { /* 走兜底 */ }
  }
  const src = (ev && ev.content) || jump.snippet || "";
  if (!src) { toast(t("该引用缺少定位信息，已打开原文"), 3000); return; }

  // 源行范围：SSE 引用帧优先，其次 evidence 接口（两者同源，都为 0 表示老索引）
  const rStart = Number(jump.source_start_line || 0) || Number((ev && ev.source_start_line) || 0);
  const rEnd = Number(jump.source_end_line || 0) || Number((ev && ev.source_end_line) || 0);

  // 2) 清掉上一次的高亮（noteView 里的 <mark> 全部是本功能写入的）
  box.querySelectorAll("mark").forEach(m => {
    const p = m.parentNode;
    while (m.firstChild) p.insertBefore(m.firstChild, m);
    m.remove();
    if (p.normalize) p.normalize();
  });
  box.querySelectorAll(".ev-hl,.ev-hl-fade,.ev-hl-persist,.ev-region-soft").forEach(el =>
    el.classList.remove("ev-hl", "ev-hl-fade", "ev-hl-persist", "ev-region-soft"));

  const blocks = _evBlocks(box);
  const texts = blocks.map(b => _normTxt(b.textContent));
  let region = [];

  // 3) 主路径（stable anchor）：源行范围 ∩ 块的 data-src-* 范围
  if (rStart > 0 && rEnd >= rStart) {
    region = blocks.filter(b => {
      const a = Number(b.dataset.srcStart || 0), z = Number(b.dataset.srcEnd || 0);
      return a && z && a <= rEnd && z >= rStart;
    });
  }

  // 4) 兜底（A5：老索引/陈旧引用没有源行范围）：才退回文本匹配
  if (!region.length) {
    const lines = src.split("\n").map(s => _normTxt(s)).filter(s => s.length >= 6);
    let start = -1;
    if (lines.length) {
      for (let i = 0; i < blocks.length && start < 0; i++) {
        for (const ln of lines) {
          if (texts[i].indexOf(ln) >= 0) { start = i; break; }
          if (texts[i].length >= 8 && ln.indexOf(texts[i]) === 0) { start = i; break; }
        }
      }
      if (start < 0) {
        const head = lines[0].slice(0, 12);
        for (let i = 0; i < blocks.length; i++)
          if (head.length >= 6 && texts[i].indexOf(head) >= 0) { start = i; break; }
      }
    }
    if (start < 0) {
      toast(t("该引用来自旧索引，已打开对应文档"), 3400);
      return;
    }
    const targetLen = _normTxt(src).length;
    let end = start, acc = 0;
    for (let j = start; j < blocks.length && j <= start + 15; j++) {
      end = j; acc += texts[j].length;
      if (acc >= targetLen) break;
    }
    region = blocks.slice(start, end + 1);
  }

  // 5) 高亮（语义分离）：
  //    ① claim 证据句 = 整句强黄 mark + 居中滚动     ← 主高亮（「[N] 支持哪一句」）
  //    ② parent region = 极浅上下文（左 accent）      ← 不再整块明显铺蓝（否则全是重点=没重点）
  //    降级链：claim 句 → ref.snippet 句 → query terms（弱）→ parent-range context。
  //    任何失败都不得破坏已完成的定位；最差不劣于旧版（terms + 整块高亮）。
  const blockTexts = region.map(b => b.textContent || "");
  let hit = _matchEvidenceSentence(blockTexts, (jump && jump.claim) || "");
  if (!hit) {
    const phrases = _evidencePhrases(jump.snippet);
    if (phrases.length) hit = _matchEvidenceSentence(blockTexts, phrases[0]);
  }

  if (hit) {
    region.forEach(b => b.classList.add("ev-region-soft"));
    const mk = _wrapRange(region[hit.index], hit.start, hit.end, "ev-claim");
    const target = mk || region[hit.index];
    if (target.scrollIntoView) target.scrollIntoView({ block: "center", behavior: "smooth" });
    return;                                   // 成功：不再叠加 terms，避免「全是重点」
  }

  // 降级：query terms（弱）+ 整块可见高亮 == 旧版行为，保证不退步
  region.forEach(b => { b.classList.remove("ev-hl-fade"); b.classList.add("ev-hl"); });
  let kws = (terms || []).map(t => String(t || "").trim()).filter(t => t.length >= 2);
  if (!kws.length) kws = _evidencePhrases(jump.snippet);
  // 长词优先：避免「监测频率」先被短词「频率」切碎成两段 mark
  kws.sort((a, b) => String(b).length - String(a).length);
  if (kws.length) {
    region.forEach(b => {
      const walker = document.createTreeWalker(b, NodeFilter.SHOW_TEXT, null);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(n => _markNode(n, kws, "mark", "ev-ev"));
    });
  }
  region[0].scrollIntoView({ block: "center", behavior: "smooth" });
  // 1s 后从 pulse 转 persistent（仅调淡背景，保留左色边线 + 黄色关键字）
  setTimeout(() => region.forEach(b => {
    if (b.classList.contains("ev-hl")) b.classList.replace("ev-hl", "ev-hl-persist");
  }), 1000);
}

/* -------- 证据定位辅助（B/A 引用稳定锚点用） -------- */
function _normTxt(s) {
  return String(s == null ? "" : s).replace(/\s+/g, " ").trim().toLowerCase();
}
function _evBlocks(box) {
  // 阅读视图的顶层渲染块（带 data-src-* 源行身份），用于与引用源行范围求交集
  return Array.prototype.filter.call(box.children, b => b.dataset && b.dataset.srcStart);
}
function _evidencePhrases(snippet) {
  // 从 ref.snippet 提炼**能真正匹配正文**的证据句片段（仅作老帧/离线帧兜底；
  // 主路径是后端 meta 帧下发的 terms）。两个必踩的坑：
  //   ① snippet 带 Markdown 语法（### / | / --- / ` ）→ 必须先剥掉，否则永远匹配不上；
  //   ② 长句会跨越多个文本节点（标题/列表各自成节点）→ 必须按句读切成**短片段**。
  return String(snippet || "")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "")
    .replace(/[#>*`|]/g, " ")
    .replace(/[-=]{3,}/g, " ")
    .split(/[…\n]|\.\.\.|[。！？；;]/)
    .map(t => t.replace(/\s+/g, " ").trim())
    .filter(t => t.length >= 4)
    .slice(0, 6);
}

/* -------- Citation Precision Highlight（纯 Citation UX patch） --------
   语义分离：
     · query terms    = 「为什么检索到这里」（弱信号，仅在降级时使用）
     · claim sentence = 「正文 [N] 到底支持哪一句」（强信号，主高亮）
   claim 来自**被点击角标所在段落、角标之前的正文**（turn-scoped），绝不用整轮 query 代替。
   匹配只在**已按 source-range 定位好的 region 内**做，绝不跨出 region 全文 fuzzy。
   不改检索 / prompt / DB / source anchor / citation identity。 */

// 角标所在块（bullet/paragraph）中、角标之前的正文 → claim 原文
function _claimTextOf(chip) {
  if (!chip || !chip.parentNode) return "";
  const block = (chip.closest && chip.closest("p,li,blockquote,h1,h2,h3,h4,h5,h6,div"))
    || chip.parentNode;
  let out = "";
  const w = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, null);
  while (w.nextNode()) {
    const n = w.currentNode;
    if (n === chip || (chip.contains && chip.contains(n))) break;   // 到角标自身即停
    out += n.nodeValue || "";
  }
  return out;
}

// 归一化：去行首项目符号/序号 → 折叠空白（DOM 可能把一句拆成多节点）→ 小写 → 去首尾标点。
// 注意：**不能**无条件去行首数字（「9月19日…」的 9 是正文，不是序号）；序号须带终止符。
function _claimNorm(s) {
  let t = String(s == null ? "" : s)
    .replace(/^\s*(?:[•·▪◦‣]|[-*–—]|\d{1,3}\s*[.)、．]|[（(]\s*\d{1,3}\s*[）)])\s*/, "")
    .replace(/[\s\u3000]+/g, "")
    .toLowerCase();
  return t
    .replace(/^[，。！？；：、,.!?;:…"'“”‘’]+/, "")
    .replace(/[，。！？；：、,.!?;:…"'“”‘’]+$/, "");
}

// 按 。！？；换行 切句，返回**块内字符区间** [{start,end}]（供高亮映射回 DOM）
function _sentSpans(text) {
  const out = [];
  const re = /[^。！？；\n\r]+/g;
  let m;
  while ((m = re.exec(text))) {
    const raw = m[0];
    const s = m.index + (raw.length - raw.replace(/^\s+/, "").length);
    const e = m.index + raw.replace(/\s+$/, "").length;
    if (e > s) out.push({ start: s, end: e });
  }
  return out;
}

// claim 的轻量 token：数字 + 英文词 + 中文双字片段（滑窗 bigram）
function _claimTokens(norm) {
  const s = String(norm || "");
  const toks = [];
  (s.match(/\d+/g) || []).forEach(x => toks.push(x));
  (s.match(/[a-z]+/g) || []).forEach(x => toks.push(x));
  const runs = s.match(/[\u3400-\u9fff]+/g) || [];
  for (const run of runs)
    for (let k = 0; k + 2 <= run.length; k++) toks.push(run.slice(k, k + 2));
  return toks.length ? Array.from(new Set(toks)) : [];
}

// 在 region（各块纯文本）内为 claim 选最贴合的候选句。
// 返回 { index, start, end, mode:"exact"|"overlap", score } 或 null。
// blockTexts[i] 必须与 region 第 i 块的 textContent 一致（高亮区间据此映射回 DOM）。
function _matchEvidenceSentence(blockTexts, claimText) {
  const claim = _claimNorm(claimText);
  if (claim.length < 4) return null;                 // 太短不作为证据句（避免误标）
  const toks = _claimTokens(claim);
  let best = null;
  for (let i = 0; i < blockTexts.length; i++) {
    const text = String(blockTexts[i] || "");
    for (const sp of _sentSpans(text)) {
      const norm = _claimNorm(text.slice(sp.start, sp.end));
      if (!norm) continue;
      // A. 归一化精确子串（双向包含；更紧的句子得分更高）
      if (norm.indexOf(claim) >= 0 || claim.indexOf(norm) >= 0) {
        const score = 1 + Math.min(norm.length, claim.length) / Math.max(norm.length, claim.length);
        if (!best || score > best.score)
          best = { index: i, start: sp.start, end: sp.end, mode: "exact", score };
        continue;
      }
      // B. 轻量重叠分（中文双字 / 数字 / 英文 token 命中比例）
      if (!toks.length) continue;
      let hit = 0;
      for (const t of toks) if (norm.indexOf(t) >= 0) hit++;
      const score = hit / toks.length;
      if (score > 0 && (!best || score > best.score))
        best = { index: i, start: sp.start, end: sp.end, mode: "overlap", score };
    }
  }
  if (!best) return null;
  if (best.mode === "exact") return best;
  return best.score >= 0.34 ? best : null;           // 共同 token 太少 → 视为没找到（降级）
}

// 在 block 内把文本区间 [start,end) 包成 <mark class=cls>（可跨 <b>/<mark>/多个文本节点）
function _wrapRange(block, start, end, cls) {
  if (!block) return null;
  const w = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, null);
  const jobs = [];
  let acc = 0;
  while (w.nextNode()) {
    const n = w.currentNode;
    const val = n.nodeValue || "";
    const s = Math.max(start, acc) - acc;
    const e = Math.min(end, acc + val.length) - acc;
    if (e > s) jobs.push({ n, s, e, len: val.length });
    acc += val.length;
  }
  let first = null;
  for (const { n, s, e, len } of jobs) {
    let target = n;
    if (e < len) target.splitText(e);
    if (s > 0) target = target.splitText(s);
    const m = document.createElement("mark");
    m.className = cls;
    m.textContent = target.nodeValue;
    target.parentNode.replaceChild(m, target);
    if (!first) first = m;
  }
  return first;
}


function _markNode(node, terms, tag, cls) {
  // 在文本节点上包 <tag class=cls>，命中最长最靠前的一组 terms；不碰任何标签/属性。
  const text = node.nodeValue;
  if (!text || !text.trim()) return;
  let best = null;
  for (const t of terms) {
    if (!t) continue;
    const i = text.toLowerCase().indexOf(String(t).toLowerCase());
    if (i >= 0 && (!best || i < best.i)) best = { i, t: String(t) };
  }
  if (!best) return;
  const frag = document.createDocumentFragment();
  if (best.i > 0) frag.appendChild(document.createTextNode(text.slice(0, best.i)));
  const mk = document.createElement(tag);
  mk.className = cls || "";
  mk.textContent = text.slice(best.i, best.i + best.t.length);
  frag.appendChild(mk);
  const tail = document.createTextNode(text.slice(best.i + best.t.length));
  frag.appendChild(tail);
  node.parentNode.replaceChild(frag, node);
  _markNode(tail, terms, tag, cls);          // tail 严格更短 → 必然终止
}

/* -------- 笔记视图：渲染 / 原版 / 源码 -------- */
const NOTE = { payload: null, view: "rendered" };
/* View 产品语义（本轮修正）：三个视图 = 阅读 / 原件（或网页快照）/ Markdown。
   「源码」是误称 —— 它其实是转换后的 Markdown，不是 PDF/DOCX/HTML 的真源码。 */
function noteLabels(orig) {
  const isWeb = !!(orig && (orig.ext === ".html" || orig.ext === ".htm"));
  return {
    rendered: t("阅读"),
    original: isWeb ? t("网页快照") : t("原件"),
    raw: "Markdown",
  };
}
/* 阅读视图不显示内部 metadata：剥掉开头的 YAML frontmatter 块（磁盘上的真相源不动） */
function stripFrontmatter(src) {
  const m = String(src || "").match(/^\uFEFF?---\r?\n[\s\S]*?\r?\n---\r?\n?/);
  return m ? String(src).slice(m[0].length) : String(src || "");
}
/* frontmatter 占用的行数（阅读视图渲染正文时作为源行号偏移量，A3） */
function frontmatterLineCount(src) {
  const m = String(src || "").match(/^﻿?---\r?\n[\s\S]*?\r?\n---\r?\n?/);
  return m ? (m[0].match(/\n/g) || []).length : 0;
}
/* 从 Markdown 头部读一个 frontmatter 字段（只读展示用） */
function frontmatterValue(src, key) {
  const m = String(src || "").match(/^\uFEFF?---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return "";
  const hit = m[1].match(new RegExp("^" + key + ":\\s*\"?([^\"\\n]+?)\"?\\s*$", "m"));
  return hit ? hit[1].trim() : "";
}

function fmtSize(n) {
  n = Number(n) || 0;
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
  return (n / 1073741824).toFixed(2) + " GB";
}

/* 把秒数说成人话。用于导出/迁移的耗时预告 —— 不预告的话，用户在大库上会
   以为程序卡死，进而强杀进程（那反而会留下半截文件）。估算刻意保守。 */
function fmtDuration(sec) {
  sec = Math.max(0, Math.round(Number(sec) || 0));
  if (!sec) return t("很快");
  if (sec < 45) return t("不到 1 分钟");
  const min = Math.round(sec / 60);
  if (min < 60) return t("约 {0} 分钟", min);
  const hr = min / 60;
  return t("约 {0} 小时", hr < 10 ? hr.toFixed(1) : Math.round(hr));
}

function setNoteView(view) {
  const d = NOTE.payload;
  if (!d) return;
  const orig = d.original;
  if (view === "original" && !orig) view = "rendered";
  NOTE.view = view;
  const labels = noteLabels(orig);
  $$("#noteSeg button").forEach(b => {
    b.textContent = labels[b.dataset.view] || b.textContent;
    b.classList.toggle("on", b.dataset.view === view);
  });
  const box = $("#noteView");
  box.className = "doc-md";

  if (view === "raw") {
    // Markdown 视图：完整显示转换后的 Markdown（含 frontmatter，便于核对）
    box.innerHTML = '<pre class="doc" style="white-space:pre-wrap;margin:0">' + esc(d.content) + "</pre>";
    return;
  }

  if (view === "original") {
    const isWeb = orig.ext === ".html" || orig.ext === ".htm";
    const url = "/api/notes/original?path=" + encodeURIComponent(d.path);
    // 「在新标签打开」实际打开的是本地离线快照 → 文案必须说清楚（网页剪藏）；
    // PDF/Office 的它就是原件本身，保留「在新标签打开」。
    const openLabel = isWeb ? t("新标签打开快照") : t("在新标签打开");
    const srcUrl = frontmatterValue(d.content, "source_url");
    const visit = (isWeb && /^https?:\/\//i.test(srcUrl))
      ? '　<a href="' + esc(srcUrl) + '" target="_blank" rel="noopener noreferrer">' + esc(t("访问原网页")) + '</a>'
      : "";
    const isPdf = orig.ext === ".pdf";
    // Office 原件（docx/xlsx）：浏览器不认这类格式，必须由服务端转成 HTML 再预览
    const isOffice = /^\.(docx|docm|dotx|dotm|xlsx|xlsm|xltx)$/.test(orig.ext);
    const meta = '<div class="doc-meta">' + esc(t("{0}：{1}（{2}）", labels.original, orig.name, fmtSize(orig.size))) + visit +
      (isOffice
        ? '<span class="hint">　' + esc(t("预览由服务端转换生成，保留表格与结构，不还原原始排版")) + '</span>'
        : "") +
      '　<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + esc(openLabel) + "</a>" +
      '　<a href="' + url + '?download=1" download>' + esc(t("下载原件")) + "</a></div>";

    // 剪藏页加宽度切换；PDF 用浏览器自带查看器（自带缩放），无需切换
    const tools = isWeb
      ? '<div class="frame-tools">' + esc(t("宽度："))
        + '<button type="button" data-m="fit" class="on">' + esc(t("适应宽度")) + '</button>'
        + '<button type="button" data-m="raw">' + esc(t("实际大小")) + '</button>'
        + '<span>' + esc(t("剪藏页已禁用脚本，需登录/展开等交互时请用「下载原件」在浏览器打开")) + '</span></div>'
      : "";

    // 动态页降级快照（partial_fallback）：正文完全靠前端脚本渲染，
    // 沙箱（禁脚本——安全底线）里只会是一片空白。与其让用户对着白屏
    // 以为「快照打不开」，不如把原因和出路一次说清楚。
    const snapWarn = (isWeb && frontmatterValue(d.content, "status") === "partial_fallback")
      ? '<div class="snap-warn">' + esc(t("⚠️ 该网页由前端脚本动态渲染，安全沙箱内（已禁用脚本）无法显示其内容。请用上方「新标签打开快照」或「下载原件」在浏览器中查看完整快照；正文请回「阅读」视图。")) + '</div>'
      : "";

    box.className = "doc-md doc-original";   // 让 #noteView 成为填满面板的 flex 列
    box.innerHTML = snapWarn + meta + tools +
      '<div class="frame-wrap fit"><iframe class="doc-frame" title="' + attrEsc(t("原版预览")) + '"></iframe></div>';
    const wrap = box.querySelector(".frame-wrap");
    const frame = wrap.querySelector("iframe");

    if (isPdf) {
      // 浏览器内置 PDF 查看器 —— 与直接打开 PDF 完全一致的观感。
      // 不参与下面的 1280px 虚拟宽度缩放：查看器自带缩放/适配，transform-scale
      // 只会把工具栏和页面一起压小（窄面板下小到不可用）。
      frame.style.width = "100%";
      frame.style.height = "100%";
      frame.src = url + "#toolbar=1&view=FitH";
      // 某些环境（浏览器关闭了内置 PDF 查看器 / 旧内核）iframe 里看不到 PDF ——
      // 「在新标签打开」就是兜底（C2），同一 URL 浏览器会用自带查看器整页打开。
      return;
    } else if (isWeb) {
      // 剪藏的原网页：沙箱 iframe 还原版式。sandbox="" 屏蔽脚本/表单/弹窗，
      // 因为抓来的第三方 HTML 属于不可信内容 —— 这条安全底线不能放宽
      frame.setAttribute("sandbox", "");
      frame.setAttribute("referrerpolicy", "no-referrer");
      frame.src = url;
    } else if (/^\.(png|jpe?g|gif|webp|bmp|svg)$/.test(orig.ext)) {
      wrap.outerHTML = '<img src="' + url + '" alt="' + esc(orig.name) + '" style="max-width:100%;border-radius:9px">';
      return;
    } else if (isOffice) {
      // Office 原件预览：服务端转 HTML（?as=html），沿用与剪藏快照同一条安全底线
      // —— sandbox="" 禁脚本 + 禁 referrer。产物本身也不含任何 script。
      frame.setAttribute("sandbox", "");
      frame.setAttribute("referrerpolicy", "no-referrer");
      frame.style.width = "100%";
      frame.style.height = "100%";
      frame.src = url + "&as=html";
      return;
    } else {
      wrap.outerHTML = '<div class="doc-dl">' + esc(t("该格式无法内嵌预览。")) + '<br><br>' +
        '<a class="btn" href="' + url + '?download=1" download>' + esc(t("下载原件")) + '</a></div>';
      return;
    }

    // 剪藏页适配：X / 微博这类站点是桌面固定宽度布局，塞进窄面板必被横向裁半。
    // 方案：按 1280px 的桌面宽度渲染，再等比缩放到面板宽 —— 整页横向永远完整可见。
    // 沙箱（无 allow-same-origin）拿不到内容高度，因此高度按「缩放后恰好填满」反推，
    // 页面更长时由 iframe 自己出滚动条，全程只有一根滚动条。
    const VIRTUAL_W = 1280;
    let mode = "fit";
    const layout = () => {
      const w = wrap.clientWidth, h = wrap.clientHeight;
      if (!w || !h) return;
      if (mode === "fit") {
        // 原则：窄面板可以缩小，宽面板**绝不放大超过原尺寸**（>1280px 时保持 1:1）
        const k = Math.min(1, w / VIRTUAL_W);
        frame.style.width = VIRTUAL_W + "px";
        frame.style.height = Math.max(400, Math.floor(h / k)) + "px";
        frame.style.transformOrigin = "0 0";
        frame.style.transform = "scale(" + k + ")";
      } else {
        frame.style.width = "100%";
        frame.style.height = "100%";
        frame.style.transform = "none";
      }
    };
    layout();
    if (window.__frameRO) window.__frameRO.disconnect();
    window.__frameRO = new ResizeObserver(layout);
    window.__frameRO.observe(wrap);
    box.querySelectorAll(".frame-tools button").forEach(b =>
      b.addEventListener("click", () => {
        mode = b.dataset.m;
        box.querySelectorAll(".frame-tools button").forEach(x => x.classList.toggle("on", x === b));
        wrap.classList.toggle("fit", mode === "fit");
        wrap.classList.toggle("raw", mode !== "fit");
        layout();
      }));
    return;
  }

  // 阅读视图：剥掉内部 metadata（frontmatter），只渲染 Markdown 正文。
  // baseLine = 被剥掉的行数 —— 保证块上的 data-src-* 仍是**真相源行号**（引用锚点用）。
  box.innerHTML = docToHtml(stripFrontmatter(d.content), frontmatterLineCount(d.content));
}

/* -------- 文档级 Markdown 渲染（比聊天气泡版更完整：表格/多级标题/列表） --------
   A3：每个顶层块携带 **源行锚点** data-src-start / data-src-end（真相源行号，1-based）。
   引用跳转据此做「源位置 → DOM 位置」定位，不再靠搜相似文字（目录与正文同文必跳错）。 */
function docToHtml(src, baseLine) {
  const off = baseLine || 0;                 // 前面被剥掉的行数（如 frontmatter）
  const fences = [];
  let text = String(src || "").replace(/\r\n/g, "\n");
  // 围栏换成占位符时**必须保留原换行数**，否则之后所有行号会整体偏移
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, code) => {
    fences.push("<pre><code>" + esc(code.replace(/\n$/, "")) + "</code></pre>");
    return "\u0000F" + (fences.length - 1) + "\u0000" + "\n".repeat((m.match(/\n/g) || []).length);
  });

  const lines = esc(text).split("\n");
  const out = [];
  let list = null, para = [], quote = [];
  let paraStart = 0, listStart = 0, quoteStart = 0;
  const attr = (a, b) => ' data-src-start="' + (off + a + 1) + '" data-src-end="' + (off + b + 1) + '"';

  const flushPara = () => {
    if (para.length) { out.push("<p" + attr(paraStart, paraStart + para.length - 1) + ">" + para.join("<br>") + "</p>"); para = []; }
  };
  const flushList = () => {
    if (list) {
      out.push("<" + list.tag + attr(listStart, listStart + list.count - 1) + ">" + list.items.join("") + "</" + list.tag + ">");
      list = null;
    }
  };
  const flushQuote = () => {
    if (quote.length) { out.push("<blockquote" + attr(quoteStart, quoteStart + quote.length - 1) + ">" + quote.join("<br>") + "</blockquote>"); quote = []; }
  };
  const flushAll = () => { flushPara(); flushList(); flushQuote(); };

  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    const t = ln.trim();

    if (!t) { flushAll(); continue; }
    if (/^\u0000F\d+\u0000$/.test(t)) { flushAll(); out.push(t); continue; }

    // 表格：表头 + 分隔行 + 数据行
    if (t.startsWith("|") && i + 1 < lines.length &&
        /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      flushAll();
      const cells = r => r.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const head = cells(t);
      let j = i + 2, rows = [];
      while (j < lines.length && lines[j].trim().startsWith("|")) { rows.push(cells(lines[j].trim())); j++; }
      out.push("<table" + attr(i, j - 1) + "><thead><tr>" + head.map(c => "<th>" + c + "</th>").join("") +
        "</tr></thead><tbody>" +
        rows.map(r => "<tr>" + r.map(c => "<td>" + c + "</td>").join("") + "</tr>").join("") +
        "</tbody></table>");
      i = j - 1;
      continue;
    }

    const h = t.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushAll();
      const lv = h[1].length;
      out.push("<h" + lv + attr(i, i) + ">" + inline(h[2]) + "</h" + lv + ">");
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(t)) { flushAll(); out.push("<hr" + attr(i, i) + ">"); continue; }

    const q = t.match(/^&gt;\s?(.*)$/);
    if (q) { flushPara(); flushList(); if (!quote.length) quoteStart = i; quote.push(inline(q[1])); continue; }

    const ul = t.match(/^[-*+]\s+(.*)$/);
    const ol = t.match(/^(\d+)[.)]\s+(.*)$/);
    if (ul || ol) {
      flushPara(); flushQuote();
      const tag = ul ? "ul" : "ol";
      if (!list || list.tag !== tag) { flushList(); list = { tag, items: [], count: 0 }; listStart = i; }
      list.items.push("<li" + attr(i, i) + ">" + inline(ul ? ul[1] : ol[2]) + "</li>");
      list.count += 1;
      continue;
    }

    flushList(); flushQuote();
    if (!para.length) paraStart = i;
    para.push(inline(t));
  }
  flushAll();
  return out.join("").replace(/\u0000F(\d+)\u0000/g, (m, i) => fences[+i]) ||
    '<span class="empty">' + esc(t("（空文档）")) + '</span>';
}

function inline(s) {
  return s
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, '<img src="$2" alt="$1">')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>")
    .replace(/~~([^~\n]+)~~/g, "<s>$1</s>");
}

/* ---------------------------- 设置 ---------------------------- */
/* schema 驱动渲染：common=true 的组默认展开，其余折叠进「高级设置」。
   config.ini 保持完整不删项 —— 只是把「看不懂的」收起来，并给每一项配人话说明。 */
const CFG_SCHEMA = [
  {
    sec: "AI", title: "AI 对话模型", common: true, test: "ai",
    desc: "决定回答由谁生成。什么都不改也能正常用 —— 会自动降级成本地检索摘要，不会崩。",
    fields: [
      { key: "provider", label: "AI 模式", type: "select",
        tip: "「自动」最省心：优先用本地 Ollama（免费、离线），不行再走云端 API，都没有就纯离线检索。",
        options: [["auto", "自动（推荐）"], ["ollama", "只用本地 Ollama"], ["api", "只用云端 API"], ["offline", "纯离线，不调用 AI"]] },
      { key: "ollama_host", label: "Ollama 服务地址", type: "text", placeholder: "http://127.0.0.1:11434",
        tip: "Ollama 装在本机就用默认值，别改。" },
      { key: "ollama_autostart", label: "自动启动 Ollama", type: "select",
        tip: "开启后，程序启动时若发现 Ollama 没在跑，会在**后台静默拉起**（无窗口、不阻塞启动）——" +
             "你就不必自己去开 Ollama。找不到 Ollama 或启动失败时会自动降级为纯离线检索，不影响使用。" +
             "介意程序自起后台进程的话可以关掉。",
        options: [["1", "自动启动（推荐）"], ["0", "不自动启动"]] },
      { key: "ollama_chat_model", label: "本地对话模型", type: "ollama-model",
        tip: "从你本机已安装的 Ollama 模型里挑一个。下拉只会列出**能对话**的模型" +
             "（嵌入/向量模型不会出现，选了也没用）。程序不会替你预设或自动选择任何模型；" +
             "本机还没有模型时请先用 Ollama 安装，然后点「刷新模型列表」。" },
      { key: "api_base_url", label: "云端接口地址", type: "preset-text", placeholder: "https://api.deepseek.com/v1",
        tip: "选一家常用服务商，或自己填兼容 OpenAI 协议的地址。",
        options: [["https://api.deepseek.com/v1", "DeepSeek"], ["https://dashscope.aliyuncs.com/compatible-mode/v1", "通义千问"], ["https://api.moonshot.cn/v1", "Kimi 月之暗面"], ["https://open.bigmodel.cn/api/paas/v4", "智谱 GLM"], ["https://api.openai.com/v1", "OpenAI"]] },
      { key: "api_key", label: "云端 API Key", type: "password",
        tip: "留空就不用云端。请妥善保管，勿泄露给他人。" },
      { key: "api_chat_model", label: "云端对话模型", type: "datalist", placeholder: "deepseek-chat",
        tip: "填服务商文档里的模型名，比如 deepseek-chat。",
        options: ["deepseek-chat", "deepseek-reasoner", "qwen-plus", "qwen-turbo", "moonshot-v1-8k", "glm-4-flash", "gpt-4o-mini"] },
    ],
  },
  {
    sec: "AI", title: "AI 提示注入预算", common: false,
    desc: "控制「一次给模型塞多少背景资料」。调大更全但更慢更费 token，调小可能漏信息。",
    fields: [
      { key: "inject_per_parent_chars", label: "每段最多注入（字）", type: "number", min: 100,
        tip: "每一段背景最多截取多少字符。默认 400。" },
      { key: "inject_total_chars", label: "整轮注入上限（字）", type: "number", min: 200,
        tip: "一次回答里，所有背景段加起来的字符上限。默认 1800。" },
    ],
  },
  {
    sec: "AI", title: "向量检索（决定「怎么找」）", common: false,
    desc: "把问题变成向量做语义匹配。这一组程序会自己适配，基本不用碰。",
    fields: [
      { key: "embedding_source", label: "向量嵌入来源", type: "select",
        tip: "local_onnx 用随包自带的本地模型（bge-small-zh-v1.5，开箱可用、不联网）；"
             + "ollama 借本机 Ollama 算；api 用云端算。本机没有嵌入能力时会自动降级为纯词法检索，不会崩。",
        options: [["local_onnx", "本地 ONNX"], ["ollama", "本地 Ollama"], ["api", "云端 API"]] },
      { key: "embedding_model_name", label: "嵌入模型名", type: "ollama-model",
        tip: "用 Ollama 做嵌入时从下拉里选——下拉只列出**能嵌入**的模型（如 bge-m3、nomic-embed-text），" +
             "对话模型不会出现。用 local_onnx / api 时会自动变回手动填写。" },
      { key: "embedding_dim", label: "向量维度", type: "number", min: 64, max: 4096,
        tip: "用 ollama / api 时程序会自动探测并覆盖这个值，不用填。只有 local_onnx 才需要手填。改错会让向量检索被自动禁用。" },
      { key: "top_k_parents", label: "送入 AI 的段落数", type: "number", min: 1, max: 20,
        tip: "一次给大模型看几段背景。越多信息越全，但更慢、更费 token。默认 5。" },
      { key: "recall_candidates", label: "每路召回候选数", type: "number", min: 5, max: 100,
        tip: "词法和向量各捞多少个候选来融合排序。默认 20，不用动。" },
    ],
  },
  {
    sec: "CRAWLER", title: "网页抓取（剪藏行为）", common: false,
    desc: "只影响「剪藏」页抓网页的表现。",
    fields: [
      { key: "min_body_chars", label: "正文降级门限（字）", type: "number", min: 0,
        tip: "抓下来的正文少于这个字数，就判定为动态页面，自动改成「存快照 + 提示手动粘贴」。默认 150。" },
      { key: "enable_headless_chrome", label: "动态页渲染抓取", type: "select",
        tip: "开启后遇到动态页面会调用本机 Chrome 渲染（更慢更重）。默认关闭 —— 反爬页面不硬刚。",
        options: [["0", "关闭（推荐）"], ["1", "开启"]] },
      { key: "request_timeout", label: "请求超时（秒）", type: "number", min: 5, max: 120,
        tip: "默认 20 秒。" },
      { key: "snapshot_chars", label: "降级快照保留字数", type: "number", min: 100,
        tip: "默认 1000。" },
      { key: "save_assets", label: "抓取网页子资源（离线可看）", type: "select",
        tip: "开启后剪藏网页时把 CSS / 图片 / 字体一起存到本地资源池 —— 离线也能还原版式，且浏览时不向外部发任何请求。默认开启。",
        options: [["1", "开启（推荐）"], ["0", "关闭（只留 HTML）"]] },
      { key: "assets_budget_kb", label: "单页资源预算（KB）", type: "number", min: 256,
        tip: "单个网页最多存多少 KB 的资源，超出后剩余资源改用占位符，避免个别页面吃掉整块 U 盘。默认 5120（5 MB）。" },
      { key: "asset_max_kb", label: "单个资源上限（KB）", type: "number", min: 32,
        tip: "单个图片 / 字体超过这个大小就跳过（留占位，保留原始尺寸以免撑破布局）。默认 512。" },
      { key: "allow_private_network", label: "允许抓取内网地址", type: "select",
        tip: "默认关闭：只允许公网地址（防 SSRF，逐跳校验重定向）。开启表示你明确允许抓局域网 / 本机资源；协议白名单与重定向校验仍不变。",
        options: [["0", "关闭（推荐）"], ["1", "允许内网"]] },
    ],
  },
  {
    sec: "ANALYZE", title: "入库分析（AI 增强）", common: false,
    desc: "入库时是否用本地模型生成一句话摘要。确定性抽取（关键词 / 实体 / 语言）永远执行，不受此影响。",
    fields: [
      { key: "ai_summary", label: "生成一句话摘要", type: "select",
        tip: "模型不在线会自动跳过，不影响入库速度与成功率。默认开启。",
        options: [["1", "开启（推荐）"], ["0", "关闭"]] },
    ],
  },
  {
    sec: "SEARCH", title: "检索引用策略", common: false,
    desc: "控制「引用来源」的严格程度。",
    fields: [
      { key: "allow_semantic_only", label: "允许「仅语义相关」进入引用", type: "select",
        tip: "默认开启：允许语义通道召回 —— 当你换一种说法提问、原文没有出现你的原话时，" +
          "仍能找到相关资料。放行的引用会标注 semantic-only（原文未出现你的原话）。" +
          "关闭则引用必须有字面依据，宁可回答「没找到」。",
        options: [["1", "开启（推荐）"], ["0", "关闭"]] },
      { key: "show_semantic_label", label: "显示 semantic-only 徽标", type: "select",
        tip: "默认开启：在来自语义匹配的引用卡片上显示「semantic-only」徽标与一句人话解释。" +
          "关闭后仅隐藏徽标，不影响检索行为，也不影响后端对引用的来源判定。",
        options: [["1", "显示（推荐）"], ["0", "隐藏"]] },
      { key: "semantic_min_corroboration", label: "语义旁证门限（条）", type: "number",
        min: 1, max: 10,
        tip: "语义-only 放行要求「同一文档内有 ≥ 本值 条候选的语义分 ≥ 语义通道最低相似度」。" +
          "调高更保守（更难放行）。默认 2。仅影响语义通道，不触碰防编造闸门。" },
      { key: "semantic_floor", label: "语义通道最低相似度", type: "number",
        min: 0, max: 1, step: 0.01,
        tip: "语义-only 放行的固定相似度下限（放行阈值 = max(本值, 词法候选池最高分 + 0.05)）。" +
          "默认 0.84：防止「孤立语义近邻」被误引。仅影响语义通道，不触碰防编造闸门。" },
    ],
  },
  {
    sec: "IMPORT", title: "文件导入边界（安全上限）", common: false,
    desc: "防止超大文件 / 压缩炸弹打爆处理流程。默认值保守，正常文档都能打开。",
    fields: [
      { key: "max_file_mb", label: "单文件上限（MB）", type: "number", min: 1,
        tip: "普通文件（PDF / CSV / Markdown 等）单文件大小上限。默认 50。" },
      { key: "max_archive_entries", label: "压缩包内文件数上限", type: "number", min: 1,
        tip: "OOXML / EPUB 等压缩容器内的条目数上限。默认 5000。" },
      { key: "max_archive_entry_mb", label: "压缩包单条目上限（MB）", type: "number", min: 1,
        tip: "单个解压后条目的大小上限。默认 50。" },
      { key: "max_archive_total_mb", label: "压缩包总解压上限（MB）", type: "number", min: 1,
        tip: "整个压缩包解压后的总大小上限。默认 200。" },
      { key: "max_compression_ratio", label: "最大压缩比", type: "number", min: 1,
        tip: "解压膨胀倍数上限（防压缩炸弹）。默认 100。" },
    ],
  },
  {
    sec: "SYSTEM", title: "系统（端口与后台扫描）", common: false,
    desc: "一般完全不用改。",
    fields: [
      { key: "port", label: "服务起始端口", type: "number", min: 1024, max: 65535,
        tip: "被占用时程序会自动 +1 往后找，最多试 10 个，所以这里基本不用改。" },
      { key: "host", label: "监听地址", type: "text",
        tip: "保持 127.0.0.1 —— 只有本机能访问。别改成 0.0.0.0，那会把整个知识库暴露给局域网。" },
      { key: "sync_interval", label: "外部文件扫描间隔（秒）", type: "number", min: 3,
        tip: "你用 Obsidian / Typora 改了笔记后，多久被同步进索引。默认 15 秒。" },
      { key: "log_level", label: "日志级别", type: "select",
        options: [["INFO", "INFO（默认）"], ["DEBUG", "DEBUG（排查问题用）"], ["WARNING", "WARNING"], ["ERROR", "ERROR"]] },
    ],
  },
];
const SENSITIVE = new Set(["AI.api_key"]);
let CFG_ORIGINAL = {};   // 记住加载时的值，用于检测「嵌入模型变了要重建索引」
let CFG_DEFAULTS = {};   // 内置默认值（由 /api/config 附带），供「恢复默认设置」

function cfgVal(cfg, sec, key) {
  const v = cfg && cfg[sec] ? cfg[sec][key] : undefined;
  return (v === undefined || v === null) ? "" : v;
}

function cfgControl(sec, f, val) {
  const a = 'data-sec="' + esc(sec) + '" data-key="' + esc(f.key) + '"';
  switch (f.type) {
    case "select":
      return "<select " + a + ">" + f.options.map(o =>
        '<option value="' + esc(o[0]) + '"' + (String(val) === String(o[0]) ? " selected" : "") + ">" +
        esc(t(o[1])) + "</option>").join("") + "</select>";
    case "preset-text":
    case "datalist":
      return '<div class="ctl-inline"><input type="text" ' + a + ' list="dl_' + sec + "_" + f.key +
        '" value="' + esc(val) + '" placeholder="' + esc(t(f.placeholder || "")) + '"><datalist id="dl_' +
        sec + "_" + f.key + '">' + (f.options || []).map(o =>
          Array.isArray(o) ? '<option value="' + esc(o[0]) + '">' + esc(t(o[1])) + "</option>"
                           : '<option value="' + esc(o) + '"></option>').join("") + "</datalist></div>";
    case "password":
      return '<input type="password" ' + a + ' value="' + esc(val) +
        '" placeholder="' + attrEsc(t("留空则不使用云端 API")) + '" autocomplete="off">';
    case "number":
      return '<input type="number" ' + a + ' value="' + esc(val) + '" style="max-width:140px"' +
        (f.min != null ? ' min="' + f.min + '"' : "") + (f.max != null ? ' max="' + f.max + '"' : "") +
        (f.step != null ? ' step="' + f.step + '"' : "") + ">";
    case "range":
      return '<div class="ctl-inline"><input type="range" ' + a + ' min="' + f.min + '" max="' + f.max +
        '" step="' + f.step + '" value="' + esc(val) +
        '" oninput="this.closest(\'.field\').querySelector(\'.rangeval\').textContent=(+this.value).toFixed(2)">' +
        '<span class="rangeval">' + (+val).toFixed(2) + "</span></div>";
    case "ollama-model":
      // 对话模型：选中即持久化（P0-A），不要求再点「测试」/重启/刷新浏览器。
      // 嵌入模型复用同一控件，但不需要即时落盘，故只对 ollama_chat_model 挂 onchange。
      const selOnChange = f.key === "ollama_chat_model" ? ' onchange="onSelectChatModel(this)"' : "";
      return '<div class="ctl-inline ollama-ctl"><select ' + a + ' class="ollama-sel"' + selOnChange + '>' +
        '<option value="' + esc(val) + '">' + esc(val || t("加载中…")) + "</option></select>" +
        '<button class="btn" type="button" title="' + attrEsc(t("重新读取本机已安装的 Ollama 模型")) + '" onclick="refreshOllamaModels()">' + esc(t("刷新模型列表")) + '</button></div>' +
        '<div class="tip ollama-hint">' + esc(t("正在读取本地 Ollama 模型…")) + '</div>';
    default:
      return '<input type="text" ' + a + ' value="' + esc(val) + '" placeholder="' + esc(t(f.placeholder || "")) + '">';
  }
}

function cfgGroup(g, cfg) {
  const body = g.fields.map(f => '<div class="field">' +
    '<div class="frow"><label>' + esc(t(f.label)) + "</label></div>" +
    cfgControl(g.sec, f, cfgVal(cfg, g.sec, f.key)) +
    (f.tip ? '<div class="tip">' + esc(t(f.tip)) + "</div>" : "") + "</div>").join("");
  const testbar = g.test === "ai"
    ? '<div class="testbar">' +
      '<button class="btn" type="button" title="' + attrEsc(t("会先自动保存当前表单，再真实跑一次调用")) + '" onclick="testAI(\'ollama\')">' + esc(t("测试本地 Ollama")) + '</button>' +
      '<button class="btn" type="button" title="' + attrEsc(t("会先自动保存当前表单，再真实跑一次调用")) + '" onclick="testAI(\'api\')">' + esc(t("测试云端 API")) + '</button>' +
      '<div class="test-out" id="testOut"></div></div>'
    : "";
  return '<div class="cfg-group"><h4>' + esc(t(g.title)) + "</h4>" +
    (g.desc ? '<div class="gdesc">' + esc(t(g.desc)) + "</div>" : "") + body + testbar + "</div>";
}

async function loadConfig() {
  const r = await api("/api/config");
  const cfg = r.data || {};
  CFG_DEFAULTS = r.defaults || {};
  CFG_ORIGINAL = JSON.parse(JSON.stringify(cfg));
  // P0-4：语义-only 徽标显隐（[SEARCH] show_semantic_label，默认开）。
  // 只影响徽标是否绘制；引用上的 data-match-mode / 后端 match_mode 标记始终保留。
  SEM_LABEL_ON = String(cfgVal(cfg, "SEARCH", "show_semantic_label")) !== "0";

  const seen = new Set();
  const common = [], advanced = [];
  CFG_SCHEMA.forEach(g => {
    g.fields.forEach(f => seen.add(g.sec + "." + f.key));
    (g.common ? common : advanced).push(cfgGroup(g, cfg));
  });
  // config.ini 里存在但 schema 未覆盖的键 —— 兜底渲染，保证保存时不丢。
  // 排除合成的 *_set 字段（GET /api/config 为「是否已配置密钥」附加，不是真实配置项）。
  const extra = [];
  Object.keys(cfg).forEach(sec => {
    const hidden = Object.keys(cfg[sec]).filter(k => !seen.has(sec + "." + k) && !/_set$/.test(k));
    if (!hidden.length) return;
    extra.push('<div class="cfg-group"><h4>' + esc(sec + t(" · 其他")) + "</h4>" + hidden.map(k =>
      '<div class="field"><div class="frow"><label>' + esc(k) + "</label></div>" +
      '<input type="text" data-sec="' + esc(sec) + '" data-key="' + esc(k) +
      '" value="' + esc(cfg[sec][k]) + '"></div>').join("") + "</div>");
  });

  $("#cfgForm").innerHTML = common.join("");
  $("#cfgAdvanced").innerHTML = advanced.join("") + extra.join("");
  refreshOllamaModels();
}

/* 「恢复默认设置」：把表单填回出厂默认值（**不落盘**，用户再点「保存配置」才生效）。
   密钥字段刻意跳过 —— 默认值为空，重置会把真 Key 覆盖掉。 */
function applyConfigDefaults() {
  if (!Object.keys(CFG_DEFAULTS).length) { toast(t("默认值尚未加载，请先刷新")); return; }
  if (!confirm(t("把设置填回出厂默认值？\n\n不会立即保存 —— 确认无误后再点「保存配置」才生效。\n（云端 API Key 不会被清空）"))) return;
  $$("#cfgForm [data-sec], #cfgAdvanced [data-sec]").forEach(el => {
    const sec = el.dataset.sec, key = el.dataset.key;
    if (SENSITIVE.has(sec + "." + key)) return;            // 不重置密钥
    const d = CFG_DEFAULTS[sec] ? CFG_DEFAULTS[sec][key] : undefined;
    if (d === undefined) return;
    if (el.tagName === "SELECT" && !Array.from(el.options).some(o => o.value === String(d))) {
      const o = document.createElement("option");
      o.value = String(d); o.textContent = String(d) || t("（默认）");
      el.appendChild(o);
    }
    el.value = d;
    if (el.type === "range") {
      const rv = el.closest(".field") && el.closest(".field").querySelector(".rangeval");
      if (rv) rv.textContent = (+d).toFixed(2);
    }
  });
  toast(t("已填回默认值，确认后点「保存配置」生效"));
}

/* Ollama 模型下拉（对话模型 + 嵌入模型通用）：在线就列出本机已装模型，
   **并按用途做能力过滤**（对话只列 completion、嵌入只列 embedding）；
   不在线退化成手填，绝不丢用户已填的值。 */
async function refreshOllamaModels() {
  const sels = $$(".ollama-sel");
  if (!sels.length) return;
  sels.forEach(s => { const h = s.closest(".ollama-ctl").parentElement.querySelector(".ollama-hint");
                      if (h) h.textContent = t("正在读取本地 Ollama 模型…"); });
  let d = null;
  try {
    const r = await api("/api/ollama/models");
    d = r.data || {};
  } catch (e) {
    sels.forEach(sel => {
      const h = sel.closest(".ollama-ctl").parentElement.querySelector(".ollama-hint");
      if (h) h.textContent = t("读取失败：{0}", e.message);
    });
    return;
  }

  sels.forEach(sel => {
    const current = String(sel.value || "").trim();
    const field = sel.closest(".ollama-ctl").parentElement;
    const hint = field.querySelector(".ollama-hint");
    // 每个下拉只列**真正胜任该用途**的模型（以 Ollama 的 capabilities 为准）：
    // 对话只认 completion，嵌入只认 embedding。否则用户会把 bge-m3 这类嵌入模型
    // 选成对话模型 —— 保存成功、状态还显示"就绪"，一提问才撞 HTTP 400
    // "does not support chat"。能力过滤把这类错误挡在**选择之前**。
    const role = sel.dataset.key === "embedding_model_name" ? "embed" : "chat";
    const needCap = role === "embed" ? "embedding" : "completion";
    const roleName = role === "embed" ? t("嵌入模型") : t("本地对话模型");

    if (!d.available) {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.dataset.sec = sel.dataset.sec;
      inp.dataset.key = sel.dataset.key;
      inp.value = current;
      inp.placeholder = t("填写你本机已安装的模型名");
      sel.replaceWith(inp);
      if (hint) hint.innerHTML = esc(t("⚠ {0} —— 已切换为手动填写。装好 Ollama 后点「刷新模型列表」可恢复下拉。",
        d.detail || t("未检测到本地 Ollama")));
      return;
    }
    const all = d.models || [];
    const capsOf = m => (m.capabilities || []);
    // 旧版 Ollama 不返回 capabilities → 按能力过滤会把模型全藏掉。宁可全列 + 说明，
    // 也不能让用户以为「本机一个模型都没有」。后端状态判定同样对此保持向后兼容。
    const hasCaps = all.some(m => capsOf(m).length);
    const models = hasCaps ? all.filter(m => capsOf(m).indexOf(needCap) >= 0) : all;
    const bits = m => [m.params, m.size_text].filter(Boolean).join(" · ");
    const installed = all.some(m => m.name === current);
    const usableNow = models.some(m => m.name === current);
    sel.innerHTML = '<option value="">' + esc(t("— 未选择（请从下方本机模型里挑一个）—")) + '</option>' +
      (current && !usableNow
        ? '<option value="' + esc(current) + '">' + esc(current) +
          esc(installed ? t("（不支持此用途，请另选）") : t("（原配置，本机未找到）")) + "</option>"
        : "") +
      models.map(m =>
        '<option value="' + esc(m.name) + '">' + esc(m.name) +
        (bits(m) ? "　" + esc(bits(m)) : "") + "</option>").join("");
    // ⚠ **绝不自动选中 models[0]**：用户没选就保持「未选择」——
    //   替用户挑一个模型等于偷偷替他拍板。选了就在保存时显式持久化。
    sel.value = current;
    if (hint) {
      if (!all.length) {
        hint.innerHTML = esc(t("⚠ Ollama 在线，但本机尚未安装任何模型 —— 请先用 Ollama 装好模型，再点「刷新模型列表」。"));
      } else if (hasCaps && !models.length) {
        hint.innerHTML = esc(t("⚠ 本机没有可用于「{0}」的模型 —— 请先用 Ollama 安装（对话模型如 qwen2.5，嵌入模型如 bge-m3），再点「刷新模型列表」。", roleName));
      } else if (!current) {
        hint.innerHTML = esc(t("已筛出 {0} 个可用「{1}」的模型，请选一个（程序不会自动替你选）。", models.length, roleName)) +
          (hasCaps ? "" : esc(t("　⚠ 当前 Ollama 未提供能力标签，无法自动分辨用途。")));
      } else if (!usableNow) {
        hint.innerHTML = esc(t("⚠ 当前配置的「{0}」{1}，请重新选择。", current,
          installed ? t("不支持「{0}」（能力标签里没有 {1}）", roleName, needCap)
                    : t("在本机已不存在")));
      } else {
        hint.innerHTML = esc(t("✅ 当前模型：{0}　（Ollama：{1}）", current, d.host));
      }
    }
  });
}

// P0-A：从「本地对话模型」下拉框选择模型 → 立即持久化 AI.ollama_chat_model，
// 刷新 AI readiness，状态立即变 ready，下一次问答直接用 —— 无需点「测试」/重启/刷新页面。
// 「测试本地 Ollama」仅保留为诊断按钮，不再承担「保存选择」的职责。
async function onSelectChatModel(sel) {
  const val = sel ? sel.value : "";
  try {
    const r = await api("/api/config", {
      method: "POST",
      body: JSON.stringify({ data: { AI: { ollama_chat_model: val } } }),
    });
    if (r.code !== 200) { toast(t("⚠ 模型选择保存失败：{0}", r.message || "")); return; }
    // 同步 CFG_ORIGINAL，避免后续「保存配置」把它覆盖回旧值
    if (!CFG_ORIGINAL.AI) CFG_ORIGINAL.AI = {};
    CFG_ORIGINAL.AI.ollama_chat_model = val;
    // 立即刷新后端就绪状态（只读缓存、不发网络请求），UI 状态马上更新
    await pollStatus(false);
    const hint = sel && sel.closest(".ollama-ctl") && sel.closest(".ollama-ctl").parentElement
      ? sel.closest(".ollama-ctl").parentElement.querySelector(".ollama-hint") : null;
    if (hint) {
      hint.innerHTML = val
        ? esc(t("✅ 已选择本地模型：{0}（已保存，可直接提问）", val))
        : esc(t("已清空本地模型选择"));
    }
    toast(val ? t("已选择并保存本地模型：{0}", val) : t("已清空本地模型选择"));
  } catch (e) {
    toast(t("⚠ 模型选择保存失败：{0}", e.message));
  }
}

async function testAI(target) {
  const out = $("#testOut");
  out.className = "test-out loading";
  out.textContent = target === "ollama"
    ? t("正在调用本地 Ollama（首次要加载模型，可能等几秒）…")
    : t("正在调用云端 API…");
  await saveConfig(true);   // 测的是你刚改的值，先落盘
  const r = await api("/api/ai/test", { method: "POST", body: JSON.stringify({ target }) });
  const d = r.data || {};
  out.className = "test-out " + (d.ok ? "ok" : "bad");
  out.textContent = (d.ok ? "✅ " : "❌ ") + (d.detail || r.message || t("未知结果"));
}

async function saveConfig(silent) {
  const data = {};
  $$("#cfgForm [data-sec], #cfgAdvanced [data-sec]").forEach(i => {
    const sec = i.dataset.sec;
    data[sec] = data[sec] || {};
    data[sec][i.dataset.key] = i.value;
  });
  const r = await api("/api/config", { method: "POST", body: JSON.stringify({ data }) });
  if (r.code !== 200) { if (!silent) toast("⚠ " + r.message); return false; }

  // ⚠ 必须在覆盖 CFG_ORIGINAL 之前比对，否则永远检测不到变化
  const embKeys = ["embedding_source", "embedding_model_name", "embedding_dim"];
  const prev = CFG_ORIGINAL.AI || {};
  const changed = embKeys.some(k => String((data.AI || {})[k]) !== String(prev[k]));
  CFG_ORIGINAL = JSON.parse(JSON.stringify(data));

  if (changed) {
    toast(t("⚠ 嵌入模型相关设置已变更，请点下方「重建向量索引」，否则向量检索会被禁用"), 6000);
  }
  if (!silent) toast(t("✅ 配置已保存（重启程序后完全生效）"));
  return true;
}

async function rebuild(vec) {
  const log = $("#rebuildLog");
  log.innerHTML = '<span class="spin"></span> ' + esc(t("已在后台启动…"));
  const r = await api(vec ? "/api/system/rebuild-vectors" : "/api/system/rebuild-index", {
    method: "POST", body: "{}",
  });
  toast(r.message || t("任务已启动"));
  setTimeout(async () => {
    await loadNotes(); await pollStatus(false);
    log.textContent = t("任务已提交后台执行，可继续使用其他功能。");
  }, 2500);
}

/* ---------------------------- 产品授权 ---------------------------- */
function licStatusLabel(st) {
  const m = { OK: t("已激活"), NO_LICENSE: t("未激活"), DEVICE_MISMATCH: t("设备不符"),
              EXPIRED: t("已过期"), BAD_SIGNATURE: t("签名无效"),
              PRODUCT_MISMATCH: t("产品不符"), MALFORMED: t("格式错误"),
              CRYPTO_UNAVAILABLE: t("无法验证") };
  return m[(st && st.status) || ""] || t("未知");
}

function renderLicense(st) {
  st = st || {};
  const box = $("#licState");
  if (box) {
    const cls = st.status === "OK" ? "on" : (st.status === "NO_LICENSE" ? "off" : "warn");
    let html = '<span class="lic-badge ' + cls + '">' + esc(licStatusLabel(st)) + "</span> " +
               esc(st.message || "");
    // 客户界面**只**呈现「是否已激活」—— 客户编号 / 功能位 / 有效期等内部字段一律不显示
    box.innerHTML = html;
  }
  const dc = $("#licDeviceCode");
  if (dc && st.device_code) dc.value = st.device_code;
}

async function loadLicense() {
  try {
    const r = await api("/api/license/status");
    renderLicense(r.data || {});
  } catch (e) {
    const box = $("#licState");
    if (box) box.innerHTML = '<span class="lic-badge warn">' + esc(t("读取失败")) + '</span> ' + esc(e.message);
  }
}

function copyDeviceCode() {
  const v = $("#licDeviceCode") ? $("#licDeviceCode").value : "";
  if (!v) { toast(t("设备码尚未加载")); return; }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(v).then(() => toast(t("设备码已复制")), () => fallbackCopy());
  } else { fallbackCopy(); }
  function fallbackCopy() {
    const el = $("#licDeviceCode"); el.removeAttribute("readonly"); el.select();
    try { document.execCommand("copy"); toast(t("设备码已复制")); } catch (e) { toast(t("复制失败，请手动选择")); }
    el.setAttribute("readonly", "readonly");
  }
}

async function doActivate() {
  const code = ($("#licCode") ? $("#licCode").value : "").trim();
  if (!code) { toast(t("请先粘贴激活码")); return; }
  const r = await api("/api/license/activate", {
    method: "POST", body: JSON.stringify({ code }),
  });
  const d = r.data || {};
  toast((d.ok ? "✅ " : "⚠ ") + (r.message || ""));
  if (d.ok) { $("#licCode").value = ""; renderLicense(d.state || {}); pollStatus(false); }
}

async function doClearLicense() {
  if (!confirm(t("清除本机激活？\n\n清除后本机立即回到未激活状态（不影响资料库与笔记）。"))) return;
  const r = await api("/api/license/clear", { method: "POST", body: "{}" });
  const d = r.data || {};
  toast(r.message || t("已清除"));
  renderLicense(d.state || {}); pollStatus(false);
}

/* ---------------------------- 标签页 ---------------------------- */
function switchTab(name) {
  $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === "panel-" + name));
  if (name === "notes") loadNotes();
  if (name === "settings") { loadConfig(); loadLicense(); loadDataDir(); pollStatus(false); }
}

/* 问答引用跳转（A/B）：
 * 正文角标 [N]（.cite）= **证据**：打开笔记 → 按 parent_id 定位证据块 → 滚动 + 高亮；
 * 底部来源 chips（.ref）= **文档**：只打开整篇资料，不强制跳某个 Parent。
 * 语义区分：数字 = 证据，来源名 = 文档。
 * A：引用身份全部内联在 span 的 data-* 上（turn-scoped，绝不回查全局 S.refs）。
 * B：整条链 await 串行化 + NOTE_NAV_SEQ 守卫，连续点击时旧请求不得覆盖较新结果。 */
document.addEventListener("click", async function (ev) {
  const chip = ev.target && ev.target.closest ? ev.target.closest(".cite,.ref") : null;
  if (!chip) return;
  const path = chip.dataset.path;
  if (!path) { toast(t("该引用没有对应的笔记路径"), 2600); return; }
  const isCite = chip.classList.contains("cite");
  const jump = isCite ? {
    parent_id: chip.dataset.parentId || "",
    snippet: chip.dataset.snippet || "",
    source_start_line: Number(chip.dataset.srcStart) || 0,
    source_end_line: Number(chip.dataset.srcEnd) || 0,
    // claim：角标所在段落、角标**之前**的正文（turn-scoped）—— 用于在 region 内
    // 精确定位「这个角标支持的原文句」。绝不回查全局 refs / 不用整轮 query 代替。
    claim: _claimTextOf(chip),
  } : null;
  // 高亮词取**本 bubble 自己那一轮**（turn-scoped），不用全局最新一轮
  const bubble = chip.closest ? chip.closest(".bubble") : null;
  const terms = (bubble && bubble._terms) || S.terms || [];
  const nav = ++NOTE_NAV_SEQ;             // B：本次导航序号
  await openNoteByPath(path, jump, nav, terms);
});

/* --------------------- 资料目录（Library）迁移 --------------------- */
/* 后端做法：整棵 data/ **复制**到新位置 → 逐文件校验 → 切换指向 → 重开上下文，
   旧位置始终保留完整副本。因为 context 会关掉再打开，期间 /api/status 会短暂
   说「未就绪」—— 所以这里用**独立的进度轮询**，不跟 pollStatus 抢，避免把
   「正在迁移」误显示成「服务断了」。 */
let DD_BUSY = false, DD_TIMER = null, DD_TARGET = "";

function ddSourceText(s) {
  const map = { env: t("启动参数指定"), marker: t("本机配置指定"), default: t("程序目录下的 data") };
  return map[s] || s || "—";
}

async function loadDataDir() {
  const kv = $("#datadirKV");
  if (!kv) return null;
  try {
    const r = await api("/api/datadir");
    const d = r.data || {};
    kv.innerHTML = [
      [t("当前位置"), d.path || "—"],
      [t("怎么定的"), ddSourceText(d.source)],
      [t("已存文档"), t("{0} 篇", d.notes || 0)],
      [t("占用空间"), fmtSize(d.bytes || 0) + t("（{0} 个文件）", d.files || 0)],
      [t("该盘剩余"), d.free_bytes > 0 ? fmtSize(d.free_bytes) : "—"],
      // 预告导出规模与耗时：备份只打包用户资料，比"占用空间"小（不含索引/备份/日志）
      [t("备份包约"), fmtSize(d.export_bytes || 0) + t("，导出约需 {0}", fmtDuration(d.est_export_seconds))],
    ].map(x => "<b>" + esc(x[0]) + "</b><span>" + esc(x[1]) + "</span>").join("");
    // 剪藏页那句提示原本写死「文档\Kavira-Data\notes」——自定义/U盘安装时是错的，
    // 这里按本次读到的真实资料目录回填。
    const nh = $("#ddNotesHint");
    if (nh && d.path) nh.innerHTML = esc(t("（当前在 {0}）", d.path + "/notes"));
    return d;
  } catch (e) {
    kv.innerHTML = '<span class="hint">' + esc(t("读取失败：{0}", e.message)) + "</span>";
    return null;
  }
}

async function ddCheck() {
  const target = ($("#ddTarget").value || "").trim();
  const box = $("#ddResult"), btn = $("#btnDdMigrate");
  if (!target) { box.innerHTML = '<span style="color:var(--warn)">' + esc(t("请先填写目标目录")) + '</span>'; btn.disabled = true; return; }
  box.innerHTML = '<span class="hint">' + esc(t("正在检查…")) + '</span>';
  btn.disabled = true;
  try {
    const r = await api("/api/datadir/precheck", { method: "POST", body: JSON.stringify({ target }) });
    const d = r.data || {};
    // ⚠ 后端统一用 code 字段表示成败（不是 ok）——判断错会让「预检通过」永远显示成失败。
    if (r.code === 200) {
      DD_TARGET = d.path || target;
      let html = '<span style="color:var(--ok)">' + esc(t("✓ 可以迁到这里")) + '</span>' +
        esc(t("　需要约 {0}，目标可用 {1}。", fmtSize(d.bytes || 0), fmtSize(d.free_bytes > 0 ? d.free_bytes : 0))) +
        "<br>" + esc(t("迁移预计需要 {0}（视磁盘速度而定）—— 期间请勿关闭程序或拔出磁盘。", fmtDuration(d.est_migrate_seconds)));
      (d.warnings || []).forEach(w => { html += "<br>· " + esc(w); });
      box.innerHTML = html;
      btn.disabled = false;
    } else {
      DD_TARGET = "";
      box.innerHTML = '<span style="color:var(--danger)">' + esc(r.message || t("预检未通过")) + "</span>";
    }
  } catch (e) {
    DD_TARGET = "";
    box.innerHTML = '<span style="color:var(--danger)">' + esc(t("检查失败：{0}", e.message)) + "</span>";
  }
}

async function ddMigrate() {
  if (!DD_TARGET) return;
  if (!confirm(t("将把现有资料完整复制到：\n\n　{0}\n\n· 复制期间请勿关闭电脑或拔出磁盘\n· 完成后会重新打开资料库，页面会短暂无响应\n· 旧目录会原样保留，等你确认没问题后自己删除\n\n确定开始迁移吗？", DD_TARGET))) return;
  const btn = $("#btnDdMigrate"), chk = $("#btnDdCheck"), inp = $("#ddTarget");
  DD_BUSY = true;
  btn.disabled = true; chk.disabled = true; inp.disabled = true;
  $("#ddProgress").hidden = false;
  $("#ddBar").style.width = "0%";
  $("#ddStage").textContent = t("正在启动迁移任务…");
  try {
    const r = await api("/api/datadir/migrate", { method: "POST", body: JSON.stringify({ target: DD_TARGET }) });
    if (r.code !== 202) {       // 409 已在迁移 / 400 目标不合规 —— 都别开始轮询
      $("#ddStage").innerHTML = '<span style="color:var(--danger)">' +
        esc(r.message || t("无法开始迁移")) + "</span>";
      ddFinish();
      return;
    }
    DD_TIMER = setInterval(ddPoll, 800);
  } catch (e) {
    $("#ddStage").innerHTML = '<span style="color:var(--danger)">' + esc(t("无法开始：{0}", e.message)) + "</span>";
    ddFinish();
  }
}

function ddPoll() {
  api("/api/datadir/progress").then(r => {
    const p = r.data || {};
    $("#ddBar").style.width = (p.percent || 0) + "%";
    $("#ddStage").textContent = (p.message || "") +
      (p.percent ? "　" + p.percent + "%" : "");
    if (p.busy) return;                      // 还在跑 → 继续轮询
    clearInterval(DD_TIMER); DD_TIMER = null;
    const res = p.result || {};
    if (res.ok) {
      $("#ddStage").innerHTML =
        '<span style="color:var(--ok)">' + esc(t("✓ 迁移完成：共 {0} 个文件 / {1}，用时 {2} 秒",
          res.files || 0, fmtSize(res.bytes || 0), res.seconds || 0)) + "</span><br>" +
        esc(t("资料现在保存在：{0}", res.to || "")) + "<br>" +
        '<span class="hint">' + esc(t("旧位置（{0}）仍保留着一份完整副本，确认无误后可自行删除。", res.from || "")) + "</span>";
      DD_TARGET = ""; $("#ddTarget").value = "";
      loadDataDir(); pollStatus(false); loadNotes();
      toast(t("资料已迁移到新目录"));
    } else {
      $("#ddStage").innerHTML =
        '<span style="color:var(--danger)">' + esc(res.message || p.message || t("迁移失败")) +
        "</span>";
      loadDataDir();
    }
    ddFinish();
  }).catch(() => { /* 迁移中服务会短暂重启，单次失败不必惊慌 */ });
}

/* 导出：把资料打包成 zip 交给浏览器下载。
   走 location.href 而不是 fetch+blob —— 备份包可能有几百 MB，
   blob 方案会把整个包读进内存再落地；让浏览器自己流式落盘既省内存又能续传。

   ⚠ 打包在**服务端**完成之后浏览器才开始下载，所以「点完按钮」到「下载出现」
   之间有一段静默期（大库上是分钟到小时级）。这里必须如实预告，
   而不是像早先那样 12 秒就报「已下载」—— 那会让人以为没反应、去点第二次甚至强杀进程。 */
function ddExport() {
  const btn = $("#btnDdExport"), hint = $("#ddExportHint");
  if (btn.disabled) return;
  btn.disabled = true;
  hint.innerHTML = t("正在打包…此项在服务端完成，<b>打包结束后浏览器会自动开始下载</b>。资料较多时请耐心等待，期间可以继续使用其它功能。");
  toast(t("正在打包备份，完成后浏览器会自动下载"));
  window.location.href = "/api/datadir/export";
  // 只是把按钮解禁（不宣称完成）：下载是否真的出现由用户自己看浏览器。
  setTimeout(() => {
    btn.disabled = false;
    hint.innerHTML = '<span class="hint">' + esc(t("若迟迟没有开始下载，可以再点一次；打包失败的临时文件会在下次导出前自动清理。")) + "</span>";
  }, 60000);
}

function ddFinish() {
  DD_BUSY = false;
  if (DD_TIMER) { clearInterval(DD_TIMER); DD_TIMER = null; }
  $("#btnDdCheck").disabled = false;
  $("#ddTarget").disabled = false;
}

/* ---------------------------- 绑定 ---------------------------- */
$$(".tab").forEach(t => t.onclick = () => switchTab(t.dataset.tab));
$("#btnSend").onclick = send;
$("#chatInput").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
$("#btnCapture").onclick = doCapture;
$("#capUrl").addEventListener("keydown", e => { if (e.key === "Enter") doCapture(); });
$("#btnSaveNote").onclick = doSaveNote;
$("#noteFilter").oninput = renderNoteList;
$("#noteCollectionFilter").onchange = renderNoteList;
$("#btnCfgSave").onclick = () => saveConfig(false);
$("#btnCfgReload").onclick = loadConfig;
$("#btnCfgDefaults").onclick = applyConfigDefaults;
$("#btnRebuild").onclick = () => rebuild(false);
$("#btnRebuildVec").onclick = () => rebuild(true);
$("#btnRefresh").onclick = async () => { await pollStatus(false, true); await loadNotes(); toast(t("状态已刷新")); };
if ($("#btnLicCopy")) $("#btnLicCopy").onclick = copyDeviceCode;
if ($("#btnLicActivate")) $("#btnLicActivate").onclick = doActivate;
if ($("#btnLicClear")) $("#btnLicClear").onclick = doClearLicense;
if ($("#btnDdCheck")) $("#btnDdCheck").onclick = ddCheck;
if ($("#btnDdMigrate")) $("#btnDdMigrate").onclick = ddMigrate;
if ($("#btnDdExport")) $("#btnDdExport").onclick = ddExport;

$("#btnShutdown").onclick = async () => {
  if (!confirm(t("将执行 WAL 检查点并释放数据库锁，确保 U 盘可直接拔出。\n\n确定要安全退出吗？"))) return;
  try {
    await api("/api/system/shutdown", { method: "POST", body: "{}" });
    document.body.innerHTML =
      '<div style="display:grid;place-items:center;height:100vh;font:15px/1.8 sans-serif;color:#0f172a;text-align:center">' +
      "<div><h2 style='margin:0 0 8px'>" + esc(t("已完成安全退出")) + "</h2>" +
      "<p style='color:#64748b'>" + esc(t("WAL 已刷回主库、临时文件已清理，现在可以安全拔出 U 盘。")) + "</p></div></div>";
    setTimeout(() => window.close(), 1200);
  } catch (e) { toast(t("退出请求失败：{0}", e.message)); }
};

/* 语言切换：写入 localStorage 后整页 reload —— 不重渲染，避免丢掉对话/笔记状态 */
$$("[data-lang]").forEach(b => b.onclick = () => {
  const next = b.dataset.lang;
  if (next === LANG) return;
  try { localStorage.setItem("kavira.lang", next); } catch (e) { /* 存储不可用时仅本次生效 */ }
  location.reload();
});

/* ---------------------------- 启动 ---------------------------- */
applyI18n();          // 静态文案先就位：语言已在文件顶部确定，之后才是动态渲染
initDropZone();
loadImportFormats();
loadConfig();
loadNotes();
loadLicense();
loadDataDir();
pollStatus(true);

$$("#noteSeg button").forEach(b => {
  b.onclick = () => { if (!b.disabled) setNoteView(b.dataset.view); };
});
