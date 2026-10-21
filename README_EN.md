# Kavira · A Knowledge Base in Your Pocket

[English](README_EN.md) | [中文](README.md)

> A **Local-First, portable personal knowledge base with a hybrid RAG Q&A engine**, carried on a USB stick or any removable drive.
> Your data belongs to you, 100%: articles and notes live as standard Markdown on your own filesystem, and SQLite is only a high-performance index cache.
>
> The version number has a single source of truth in `app/version.py` and is not duplicated here.

[![tests](https://github.com/lance-baba/Kavira/actions/workflows/tests.yml/badge.svg)](https://github.com/lance-baba/Kavira/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue)
![license](https://img.shields.io/badge/license-MIT-green)

📖 **Docs** (written in Chinese): [Architecture](docs/architecture.md) ·
[Design & Implementation (defect root causes, measured sizes)](docs/design-and-implementation.md) ·
[Test Report](docs/test-report.md) ·
[Changelog](CHANGELOG.md) ·
[Contributing](CONTRIBUTING_EN.md) ·
[Code of Conduct](CODE_OF_CONDUCT.md) ·
[Security Policy](SECURITY.md)

---

## 1. Quick Start

### Windows (installer release)

Unzip the release package, open `installer\`, and double-click `install.bat`:

```text
installer\install.bat
```

By default it installs to `%LOCALAPPDATA%\Kavira\App` and creates a "Kavira"
shortcut on your desktop. When installation finishes it prints exactly two lines:

```text
[install] Installed to: <location>
[install] Library folder: <location>
```

(The Chinese package `*-zh` prints the same two lines in Chinese.)

> **Note:** the web UI currently ships in Chinese only; an English UI is planned.

**Where your data actually lives** (the easiest thing to get wrong): the data
location follows the install location.

| Install location | Data directory |
| --- | --- |
| Machine default (`%LOCALAPPDATA%\Kavira\App`) | `Documents\Kavira-Data` |
| Custom location (another drive / USB stick) | `Kavira-Data` **next to** the install location |

In other words, when you install onto a USB stick the application and your data
travel together — unplug the stick and you take everything with you; plug it into
another computer and it still works. This rule is decided by
`_default_library_target()` in `scripts/install_windows.py`, and is then pinned at
runtime into a `library_path.txt` marker inside the App, so every entry point
reads the same data location.

You can check the current location any time under "Settings → Data Directory"
(Settings → Data Directory), and migrate it elsewhere. Migration **copies** existing data in
full and verifies it file by file; the old location keeps a copy until you
confirm and delete it yourself (`app/core/datadir.py`).

Your browser opens `http://127.0.0.1:28765` automatically.

- **Stop the service**: "Safe Exit" in the top-right corner of the UI
  (recommended — it performs a WAL checkpoint), or double-click `stop-windows.bat`.
- **Need to troubleshoot**: double-click `start-windows-debug.bat` (keeps the
  console window so you can see the startup banner and errors). Either way, logs
  are written to `kavira.log` in the data directory.
- ⚠ There is no console window by default, so **closing the browser does not stop
  the service**; stop it with one of the two methods above before unplugging the drive.

> **Release package size**: the core runtime bundles a self-contained Python
> interpreter and all dependencies. The heaviest single item, `babel` (32MB),
> comes from `courlan` upstream in the `trafilatura` dependency chain — it hard-references
> `babel.Locale` at import time, and measured removal crashes immediately, so it cannot be trimmed.
> Local semantic search (`onnxruntime` + `tokenizers`) is a **standard capability**,
> shipped in the package; the embedding model `bge-small-zh-v1.5` INT8 is about **23.3MB**
> (selection rationale in `docs/EMBEDDING_ARTIFACT_SELECTION.md`).
> When any embedding capability is missing, the system degrades step by step through
> `local_onnx → ollama → api → pure FTS5` without affecting startup.

> **Running tests**: `runtime/python-3.11-embed/python.exe tests/test_suite.py`
> The last line prints machine-readable `TOTAL=… PASS=… SKIP=… FAIL=…` (counts vary
> with the network environment, so they are not hand-written into the docs; see
> GitHub Actions for the full status).
> (Python 3.11.9 + SQLite 3.45.1 + FTS5 + sqlite-vec are all ready inside the
> self-contained runtime.)

### macOS / Linux (minimal bootstrap)
```bash
chmod +x start-macos.command start-linux.sh
./start-macos.command          # macOS: double-click also works
./start-linux.sh               # Linux
```
Host Python 3.10+ is required. The scripts detect dependencies automatically and
print a one-line terminal install hint when something is missing.

### Command-line options
```
--host 127.0.0.1     listen address
--port 28765         starting port (auto +1 when occupied, up to 10 attempts)
--no-browser         do not open the browser automatically
--no-sync            do not start incremental external-file sync
```

---

## 2. Adding Content to the Knowledge Base (three ways)

| Way | How | Notes |
| :--- | :--- | :--- |
| **① Drag files into the UI** | "Clip" page → drop files into the dashed box (or click to choose) | **Automatically converted to Markdown and indexed**; 20+ formats, see the table below |
| **② Capture a web page** | "Clip" page → paste the article URL → "Fetch & Index" | Static blogs preferred; dynamic pages automatically fall back to a snapshot + paste guide |
| **③ Drop into a folder** | Copy `.md` / `.txt` straight into `data/notes/` | Indexed automatically within 15 seconds. **Works best with Obsidian**: open `data/notes` as a vault |

### Supported formats (all converted to Markdown, then indexed)

| Category | Formats | Conversion |
| :--- | :--- | :--- |
| Text & notes | `.txt` `.log` `.ini` `.conf` `.env` `.md` `.rst` `.org` | Direct read (auto-detects UTF-8 / GB18030 / Big5) |
| Office documents | `.docx` `.docm` `.pptx` `.pptm` `.xlsx` `.xlsm` | Standard library OOXML parsing: heading levels → `#`, tables → Markdown tables, PPT split per slide |
| PDF | `.pdf` | `pdfminer.six` primary (preserves paragraph structure) + `pypdf` fallback (**scanned documents need OCR and are not supported**) |
| Web & email | `.html` `.htm` `.xhtml` `.mhtml` `.eml` | Body text extracted by trafilatura |
| Data & config | `.csv` `.tsv` `.json` `.jsonl` `.yaml` `.yml` `.toml` `.xml` | CSV→table, JSON/YAML→code block, XML→hierarchical outline |
| Code | `.py` `.js` `.ts` `.java` `.go` `.rs` `.c` `.cpp` `.sh` `.sql` and 50+ more | Wrapped into a code block in the corresponding language |
| E-books | `.epub` | All chapters extracted in spine order |
| Subtitles | `.srt` `.vtt` `.ass` `.lrc` | Timeline stripped, dialogue kept |
| RTF | `.rtf` | Lossy extraction of visible text |

> **Explicitly unsupported**: legacy binary Office (`.doc` `.ppt` `.xls`), images,
> audio and video — these all need OCR / speech-to-text **models**, and the models
> alone would push the release package from 122MB to gigabytes, which conflicts with
> this project's "USB-portable, zero-install" positioning. Please re-save with
> Office/WPS in a newer format first.
> For the full set of trade-offs (which formats need models, which can be handled by
> the standard library), see [Design & Implementation](docs/design-and-implementation.md).

### Original-layout preview (three views on the note page)

> **Offline archive**: when clipping a web page, its CSS / images / fonts are fetched
> into a local resource pool (`data/assets/`, de-duplicated by URL hash), so the
> "Original" view **restores the full layout even offline** and browsing makes no
> requests to any external site. Size guardrails: ≤ 512KB per resource, ≤ 5MB per page,
> adjustable under `[CRAWLER]` in `config.ini`; oversized images are replaced by a
> placeholder that preserves the original dimensions. Scripts are not downloaded
> (the preview sandbox disallows scripts by design).

On import, **the original file is kept in `data/originals/`**; a switcher in the
top-right of the note page toggles three views:

| View | Content | Purpose |
| :--- | :--- | :--- |
| **Rendered** | Markdown rendered to HTML (heading levels / tables / lists / code blocks) | Everyday reading, no more "one big monospaced blob" |
| **Original** | PDF → the browser's **built-in PDF viewer**; web page → sandboxed iframe restoring the layout; image → displayed directly | Restores the original look. Web pages are isolated with `sandbox=""`; scripts, forms and pop-ups are all disabled |
| **Source** | The raw Markdown text | Inspect conversion results, apply manual fixes |

- The originals service supports **HTTP Range** (`206 Partial Content`), so large PDFs
  can be loaded in segments and paged through quickly.
- Chinese filenames are encoded with **RFC 6266** dual fields (ASCII fallback name +
  `filename*=UTF-8''…`), so they do not fail due to HTTP headers being latin-1 only.
- Plain Markdown / plain text imports keep no original (the note *is* the original);
  the "Original" button is greyed out in that case.
- Originals share the same stem as the note, so a renamed note can still be traced back.

> The source of truth is `data/notes/*.md`; `data/cache.db` is only an index that can be
> rebuilt at any time. You can also read and write those Markdown files directly with
> Obsidian / Typora / VS Code — the system syncs incrementally.

## 3. Directory Structure

```
Kavira/
├── start-windows.bat            # Windows entry (no console window by default; UTF-8 code page locked)
├── start-windows-debug.bat       # Troubleshooting entry: keeps the console for the banner and errors
├── stop-windows.bat            # Stops the windowless service (prefers graceful /api/system/shutdown)
├── issue-license.bat              # Licensor-only: issue activation codes (double-click = guided mode)
├── start-macos.command          # macOS entry (permission and dependency detection)
├── start-linux.sh               # Linux entry
├── setup_runtime_windows.py    # Embedded runtime installer / health check / release verifier / cleanup
├── config.ini                  # Main config (plaintext; generated on first run)
├── requirements.txt
├── runtime/                    # [Windows release only] embedded Python 3.11 + prebuilt deps
│   └── python-3.11-embed/
│       ├── python.exe
│       ├── python311._pth      # Key patch: unblocks import site + relative dependency dirs
│       └── Lib/site-packages/  # sqlite_vec / onnxruntime / tokenizers / trafilatura / lxml / pyyaml
├── resources/embedding/        # In-package embedding resource contract, default.json (**bytes never enter Git**)
├── vendor/cache/embedding/     # Model bytes fetched by the maintainer (gitignored; copied locally at build time)
├── app/
│   ├── launcher.py             # Self-healing launcher: port avoidance / WAL recovery / graceful-exit hooks
│   ├── server.py               # Standard-library HTTP server and routing (incl. SSE transport)
│   ├── api/                    # Business API domain modules (thin dispatch, zero protocol change)
│   │   ├── system.py           # /api/status · /api/system/{rebuild-index,rebuild-vectors,shutdown}
│   │   ├── config.py           # /api/config (GET redacted · POST save)
│   │   ├── diagnostics.py      # /api/diagnostics
│   │   ├── search.py           # /api/search
│   │   ├── ask.py              # /api/chat/completions(SSE) · /api/ai/test · /api/ollama/models
│   │   ├── library.py          # /api/notes* · /api/notes/import · /api/import/formats
│   │   ├── license.py          # /api/license/{status,device-code,activate,clear} (offline licensing)
│   │   └── capture.py          # /api/capture/{url,duplicate}
│   ├── core/
│   │   ├── paths.py            # Relative path resolution (no drive-letter binding)
│   │   ├── config.py           # config.ini reading/writing and default template
│   │   ├── db.py               # SQLite schema / WAL recovery / signature guard
│   │   ├── chunker.py          # Parent-Child chunker
│   │   ├── embedder.py         # Embedding source resolution + AVX2 instruction-set guard
│   │   ├── search.py           # FTS5 Trigram + short-word LIKE fallback + vectors + RRF
│   │   ├── indexer.py          # Document-level indexing pipeline / orphan chunk reclamation
│   │   ├── crawler.py          # Web capture and degradation matrix
│   │   ├── llm.py              # Dual-mode AI gateway + SSE streaming
│   │   ├── sync.py             # exFAT dual-fingerprint incremental sync
│   │   ├── net_util.py         # Standard-library HTTP (proxy / certifi / UTF-8)
│   │   ├── license.py          # Offline machine-bound licensing (device fingerprint + Ed25519 verify-only)
│   │   ├── license_pubkey.py   # Built-in public key (sole trust root; private key in tools/, never shipped)
│   │   └── context.py          # Application context assembly
│   └── web/
│       ├── index.html          # Console shell (zero framework / zero CDN)
│       ├── app.css             # Styles
│       └── app.js              # Front-end logic (ask / clip / notes / settings)
├── data/                       # The user's core assets
│   ├── notes/                  # Single source of truth: hand-written and clipped Markdown
│   ├── snapshots/              # Raw HTML snapshots of degraded pages
│   └── cache.db                # Derived index (fully rebuildable)
├── tests/
│   ├── test_suite.py           # Unified automated test entry (isolated data dir, never touches the real library)
│   ├── smoke_core.py           # Core-path smoke test
│   └── test_license_offline.py # Offline licensing unit tests (standalone, not wired into test_suite)
└── tools/license_generator/    # Licensor issuing tools (genkey.py / license_gen.py; see its README)
                                #   The private key lives only here, never in Git, never in the release package
```

---

## 4. Core Capabilities

| Capability | Implementation notes |
| :--- | :--- |
| **Works out of the box** | Embedded Python 3.11 + prebuilt wheels on Windows; no registry writes, no pollution of the host environment |
| **Dual-track AI** | `auto` probes Ollama (60s health cache) → cloud OpenAI-compatible API → pure-offline FTS5 retrieval; never crashes |
| **Hybrid RAG** | FTS5 Trigram lexical + `sqlite-vec` vector nearest neighbours + RRF fusion; Top-5 parent chunks go into the prompt |
| **Short-word recall** | Single CJK characters, `AI`, `C#` and similar short queries automatically fall back to `LIKE '%kw%'`; 100% recall |
| **Precise sourcing** | Answers carry `[^n]` superscripts; hovering shows the parent chunk's source file and a snippet of the original text |
| **Coexistence with external editors** | 15s polling + exFAT dual fingerprint (including equal-length edit hash comparison); read and write freely with Obsidian/Typora |
| **Media safety** | WAL + `synchronous=NORMAL` to suppress write amplification; startup recovery + graceful exit keep the main database consistent after unplugging |
| **Offline licensing** | Ed25519 one-machine-one-code: SHA-256 device fingerprint, fully offline signature verification, invalid after moving machines; the client only embeds the public key, while the private key and issuing tools live in `tools/` (not shipped). Unactivated = **restricted mode**: browse / local search / drag-in / paste-to-import work; **web capture and AI Q&A require activation** |

---

## 5. Configuration Essentials (`config.ini`)

```ini
[AI]
provider = auto                      ; auto / ollama / api / offline
api_base_url = https://api.deepseek.com/v1
api_key =                            ; stored in plaintext — do not leave a high-balance key on a shared device
api_chat_model = deepseek-chat       ; cloud model name (only used when going through the cloud)
ollama_host = http://127.0.0.1:11434
ollama_chat_model =                  ; empty = not selected: pick a local model under "Settings → AI"
embedding_source = local_onnx        ; local_onnx / ollama / api / local_hash
embedding_dim = 512
```

### Three layers of AI capability — missing any layer does not break basic use

| Layer | Capability | Dependency |
| :--- | :--- | :--- |
| **Level 1 Basic knowledge base** | Start / import / view / FTS retrieval / return citations | **No AI dependency at all** |
| **Level 2 Local semantic search** | Vector recall (`local_onnx` → `ollama` → `api`, degrading step by step) | An embedding source is available; otherwise it degrades to pure FTS5 |
| | `local_onnx` uses the in-package **bge-small-zh-v1.5 INT8** (about 23.3MB; standard capability, works out of the box, no network) | `onnxruntime` + `tokenizers` + `resources/embedding/` |
| **Level 3 Generative chat** | Natural-language summarised answers | **A local Ollama model you choose**, or a configured cloud API |

**There is no default chat model.** The application will not pick one for you or
auto-select the first local model — while `ollama_chat_model` is empty the status is
`selection_required`, and you choose explicitly on the settings page.
Readiness states at a glance: `no_runtime` (Ollama not installed) / `no_model`
(Ollama online but no models) / `selection_required` (models exist but none selected) /
`model_missing` (the selected model was deleted) / `ready` (can chat). `provider` only
becomes `ollama` when the state is `ready`.

> **When no chat model is available**: the application does **not** error out or block —
> retrieval, citations and importing all keep working; Q&A automatically becomes
> "pure offline retrieval answers" (`provider=offline`) and is clearly labelled as not
> having called a large model.

> **Vector-space signature guard**: `sys_meta.embedding_signature` in the database
> records the embedding model and dimension. If you change the model or dimension in the
> config, the console shows a persistent yellow warning and **blocks vector recall**
> until you click "Settings → Rebuild Vector Index".

---

## 6. Testing

```bash
python tests/test_suite.py     # chunking / retrieval / gateway / destructive / data safety / atomic writes / structural upgrade / security boundaries
                               # last line prints TOTAL/PASS/SKIP/FAIL; network cases are SKIP when offline, the total stays the same
python tests/test_suite.py --fast   # fast mode: skips the "real release build + install/reinstall" segment of A1/A2/A3/A4.2b
                                    # (use it for daily changes — seconds to minutes); **always run the full suite without --fast before a release**
python tests/smoke_core.py     # core-path smoke test (4 query groups)
python setup_runtime_windows.py --check           # runtime health check (interpreter / _pth / can the dependency packages run)
python setup_runtime_windows.py --verify          # release integrity verification ("can this USB stick be delivered?")
python setup_runtime_windows.py --verify --json   # same, JSON output for CI consumption
python setup_runtime_windows.py --clean           # clean build junk (__pycache__ / .pyc)
python setup_runtime_windows.py --clean --dry-run # preview what would be removed, delete nothing
```

The tests cover automatable equivalents of TC-01 / 03 / 04 / 05;
TC-02 (physically unplugging the drive mid-write) must be performed manually on a real
exFAT USB stick.

---

## 7. Security & Compliance Notes

- `config.ini` stores keys in **plaintext** and travels with the USB stick — clear
  `api_key` before lending the device out.
- Capture targets static blogs and technical articles only; dynamic SPAs and strongly
  anti-scraping sites trigger a transparent fallback, and no anti-bot countermeasures
  are attempted.
- All network access happens only when you actively click "Fetch" or start a Q&A;
  the rest of the time it is fully offline.

---

[English](README_EN.md) | [中文](README.md)
