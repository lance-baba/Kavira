# 多语言（i18n）切换规划

> 状态：**规划中，尚未实施**。本文用于把「界面中英切换」拆成可执行的阶段，
> 供后续独立工程按本文推进。
>
> 用户文档的多语言**已完成**（`START_HERE.txt` / `START_HERE_EN.txt`，
> `User-Manual-ZH.txt` / `User-Manual.txt`）；本文只针对**程序界面与运行时输出**。

---

## 1. 现状盘点（2026-10-05 实测）

### 1.1 前端（用户直接看到的界面）

| 文件 | 中文字符 | 分布行数 | 文件总行数 |
| --- | ---: | ---: | ---: |
| `app/web/index.html` | 956 | 89 | 241 |
| `app/web/app.js` | 9,143 | 635 | 2,392 |
| **合计** | **10,099** | **724** | 2,633 |

可翻译单元粗估：HTML 文本节点 **96** 个 + JS 字符串字面量 **414** 个 ≈ **510 个 key**。

### 1.2 后端（API 返回给界面的提示语）

`app/` 下以 `"message": "…"` 形式返回的中文串约 **115 处**（825 字）。
例如「配置已保存」「已导入 xxx.md」「资料目录不能是当前目录」。

**这类文案和前端一样会被用户看到** —— 只做前端语言包，英文界面里会弹出中文提示，
必须一并处理。

### 1.3 其它中文落点

| 落点 | 位置 | 处理建议 |
| --- | --- | --- |
| 导出包内的恢复说明 | `app/core/datadir.py` 运行时生成 `备份说明.txt` | 应随界面语言输出 |
| 安装器控制台输出 | `scripts/install_windows.py` 的 `[install] …` | 安装时还没有语言设置，建议**中英并列**输出 |
| 文件名（`start-windows.bat` 等） | 发布包 | **保持中文**：改名会破坏用户既有习惯与文档引用，收益低 |
| 用户文档 | 根目录 4 份 | 已完成双语 |

**总量：约 510（前端）+ 115（后端）≈ 625 个可翻译单元。**

---

## 2. 目标与原则

1. **可运行时切换**：用户在「设置」页选择语言，立即生效，无需重启。
2. **选择可持久化**：重启程序后保持上次选择（存 `config.ini`）。
3. **新增文案不漏翻译**：缺 key 时**显式暴露**，而不是静默显示空白或 key 名。
4. **零构建步骤**：语言包是普通 JSON，浏览器直接加载 —— 与项目「前端零 CDN、零构建」的
   现有约束一致。
5. **可扩展**：加一门新语言 = 加一个 JSON 文件，不改代码。

---

## 3. 架构设计

### 3.1 语言包文件

```
app/web/i18n/
├── zh-CN.json      # 简体中文（源语言，key 的语义以此为准）
└── en.json         # English
```

格式（扁平 key，便于 diff 与机械校验）：

```json
{
  "tab.ask": "问答",
  "tab.capture": "剪藏",
  "btn.save": "保存配置",
  "msg.import.ok": "已导入 {name}（{chars} 字）",
  "msg.import.fail": "导入失败：{reason}"
}
```

* **扁平 key 而非嵌套**：`tab.ask` 比 `{"tab": {"ask": …}}` 更容易用脚本比对
  两份语言的 key 集合是否一致（见 5.3 的校验脚本）。
* **占位符用 `{name}`**：不用字符串拼接，避免语序差异导致译文别扭。

### 3.2 前端接入

**HTML** —— 用属性标记，不把文案写死在标签里：

```html
<!-- 之前 -->
<button id="btnSave">保存配置</button>

<!-- 之后 -->
<button id="btnSave" data-i18n="btn.save"></button>
```

**JS** —— 通过 `t()` 取词：

```js
// 之前
toast("配置已保存");

// 之后
toast(t("msg.config.saved"));
```

**加载与切换**（`app/web/i18n.js`，新增）：

```js
const SUPPORTED = ["zh-CN", "en"];
let CATALOG = {}, LANG = "zh-CN";

async function loadLang(lang) {
  const r = await fetch(`/i18n/${lang}.json`);      // 后端静态托管，不经 CDN
  CATALOG = await r.json();
  LANG = lang;
  document.documentElement.lang = lang;
  applyI18n();                                       // 扫 data-i18n 填充
}

function t(key, params) {
  let s = CATALOG[key];
  if (s === undefined) {
    // 原则 3：缺 key 必须显式暴露，不静默吞掉
    console.warn("[i18n] missing key:", key);
    return "⟦" + key + "⟧";
  }
  return params ? s.replace(/\{(\w+)\}/g,
    (_, k) => (params[k] ?? "")) : s;
}
```

`applyI18n()` 遍历 `[data-i18n]`，同时支持 `data-i18n-title` / `data-i18n-placeholder`
覆盖属性类型的文案。

### 3.3 后端消息

**不推荐**在前端做「中文 → 英文」映射表：后端每加一句提示，前端就得跟着改，长期必然漂移。

**推荐**：后端也走语言包，按当前语言返回。

```python
# app/core/i18n.py（新增）
MSG = {
    "zh-CN": {"msg.config.saved": "配置已保存", ...},
    "en":    {"msg.config.saved": "Settings saved", ...},
}

def T(key: str, lang: str | None = None, **params) -> str:
    lang = lang or current_lang()          # 取 config.ini 里的设置
    s = MSG.get(lang, {}).get(key) or MSG["zh-CN"].get(key) or f"⟦{key}⟧"
    return s.format(**params) if params else s
```

调用点由 `"message": "配置已保存"` 改为 `"message": i18n.T("msg.config.saved")`。

> 权衡：这保留了「后端返回可直接显示的成品文案」这个现有契约（前端不用改结构），
> 代价是后端要维护多语言表。相比之下前端映射表方案的漂移风险更大，故选此方案。

**语言从哪来**：`config.ini` 的 `[SYSTEM] language`，由设置页写入。
首次启动未设置时按系统区域推断（`zh*` → zh-CN，其余 → en）。

### 3.4 切换入口

「设置」页新增「语言 / Language」下拉（`zh-CN` / `en`），切换后：

1. 前端立即 `loadLang()` 重绘，无需刷新；
2. `POST /api/config` 写入 `language`，后端后续与该会话的响应即用新语言。

---

## 4. 分阶段实施路径

| 阶段 | 内容 | 预估 |
| --- | --- | --- |
| **P0**（已完成） | 用户文档双语（START_HERE / 使用手册，中英各一份） | ✅ |
| **P1** | 建 `i18n.js` + `zh-CN.json`，把前端 510 个片段**抽出为 key**（文案原样搬运，行为不变） | 中 |
| **P2** | 翻译 `en.json`（510 条） | 中（可外部协助） |
| **P3** | 后端 115 处 message 走 `i18n.T()`；导出包说明、安装器输出双语 | 中 |
| **P4** | 设置页语言下拉 + `config.ini` 持久化 + 系统区域推断 | 小 |
| **P5** | 加「key 一致性校验」到测试套件（见 5.3） | 小 |

**关键顺序**：**先 P1 后 P2**。若先翻译后抽 key，翻译好的文本会在抽 key 时被打散，
等于做两遍。P1 完成时界面行为与现在**完全一致**（只是文案来源变了），可独立验收。

---

## 5. 配套机制

### 5.1 每阶段都要守住的验收线

* 切换语言后**界面无中文残留**（可用脚本扫描渲染后的 DOM）。
* 未配置语言包时**回退到 zh-CN**，不出现空白界面。
* 语言切换**不丢失当前状态**（正在编辑的笔记、已输入的问题）。

### 5.2 存量兼容

已发布版本的用户 `config.ini` 里没有 `language` 键 —— 读取时缺省即「按系统区域推断」，
不要报错。这与项目现有的「配置项只增不减、缺失取默认值」约定一致。

### 5.3 key 一致性校验（防漂移）

加到测试套件中的静态检查：

```python
# 两份语言包的 key 集合必须完全一致
zh = set(json.load(open("app/web/i18n/zh-CN.json")))
en = set(json.load(open("app/web/i18n/en.json")))
assert zh == en, f"语言包 key 不一致：仅中文 {zh-en}；仅英文 {en-zh}"

# 源码里用到的 key 都必须存在于语言包（防止拼错 key 静默失败）
```

这条检查是这套方案能长期维护的关键 —— 没有它，半年后语言包必然与代码脱节。

### 5.4 命名与目录约定

| 对象 | 约定 |
| --- | --- |
| 语言代码 | BCP 47（`zh-CN`、`en`），不用 `zh_CN` / `cn` |
| 前端语言包 | `app/web/i18n/<lang>.json` |
| 后端语言包 | `app/core/i18n.py` 内的 `MSG` 字典 |
| 用户文档 | `START_HERE.txt`（中文）/ `START_HERE_EN.txt`（英文） |

> 文档命名目前是「中文无后缀、英文加 `_EN`」的不对称形式。之所以不用
> `START_HERE.zh-CN.txt`：中文是主交付语言且 `START_HERE.txt` 这个名字已被文档、
> 测试门禁（`tests/test_pilot_p0.py` 的 T5）和用户习惯引用，改名收益低于成本。
> 若将来语言超过两种，再统一迁移为带语言后缀的形式。

---

## 6. 工作量与风险

**总量**：约 625 个可翻译单元（前端 510 + 后端 115）。

**主要风险**

1. **漏网之鱼**：动态拼接的文案（如 `"已导入 " + name`）在静态扫描中容易漏。
   → P1 阶段用「渲染后扫描 DOM 是否还有中文」来兜底。
2. **占位符语序**：英文与中文语序不同，已用 `{name}` 占位而非拼接规避。
3. **PDF/Word 解析器等第三方报错**：其原始信息是英文的，**不建议翻译**
   —— 保持原文并在界面上加一句本地化的说明前缀即可，否则排障时无法搜索。
4. **翻译质量**：P2 的 510 条建议由母语者过一遍，机器翻译可作为初稿。

---

## 7. 结论

界面多语言是**可管理**的工程量（约 625 个单元），不是重构级任务。
建议按 P1 → P2 → P3 → P4 顺序推进，其中 **P1（抽 key，行为不变）是风险最低的起点**，
完成后可独立验收，也为后续所有语言打好了底子。
