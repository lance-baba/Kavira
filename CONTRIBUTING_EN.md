# Contributing

[English](CONTRIBUTING_EN.md) | [中文](CONTRIBUTING.md)

Thanks for your interest in improving Kavira. The defining constraint of this project is
**portability and zero-install** — every change has to survive that test.

---

## Get it running first

```bash
python -m pip install -r requirements.txt
python tests/test_suite.py          # should print a pass count and 0 failures
python app/launcher.py --no-browser --port 28765
```

Then open <http://127.0.0.1:28765>.

Windows users who want to build a distributable version with the embedded runtime:

```bash
python setup_runtime_windows.py             # standard build (includes onnxruntime / tokenizers)
python scripts/fetch_embedding_resource.py  # a **separate** step: fetch the model bytes per contract (large files are not in Git)
```

> Fetching and building are two distinct actions: `fetch` may use the network, while
> `build_release.py --strict` **never** touches the network (missing files = failure).
> Customer installation involves 0 network access; at runtime it only calls
> `Tokenizer.from_file(local tokenizer.json)`.

---

## Must pass before you commit

```bash
python tests/test_suite.py
```

CI runs the same suite on **5 lanes**; both chains are mandatory:

- **4-lane matrix (development-environment compatibility)**: `Linux + Windows × Python 3.11 + 3.13`
  driven by the runner's system Python, with dependencies installed from `requirements-release.lock`
  (**which includes `onnxruntime` / `tokenizers`**).
- **1 Windows Portable lane (the real product shape)**: `setup_runtime_windows.py` builds the
  self-contained embedded runtime (**without `--with-onnx` by default, so the release shape has no
  `onnxruntime`**), then runs, in order: runtime health check → **fetch**
  (`scripts/fetch_embedding_resource.py`) → the same suite with the embedded interpreter →
  `scripts/build_release.py --strict` as a stage gate (`RUNTIME_LOCK_MISMATCH=0` /
  `LOCK_ENTRY_MISSING=0`) → startup smoke. Any failed gate exits non-zero.

**A failure on any platform must make the workflow actually fail** — never make a lane
non-blocking just to keep the badge green.

**Trigger policy**: the full 5 lanes run only on manual `workflow_dispatch` and on `v*` tags.
Ordinary pushes to `main` intentionally do **not** trigger it (GitHub serves here as code backup +
rollback points, not as a per-commit release gate). Do not add `push.branches` back just to make the
badge move.

Embedding-related cases need the model bytes (large files are not in Git): the 4 matrix lanes do
**not** fetch them, so those cases are recorded as **SKIP** (we never disguise "I did not fetch
locally" as a product defect); the Portable lane **does** fetch first, and a failed fetch fails that
job. The "degradation chain when the embedding source is unavailable" is additionally verified
directly (simulated) by the D / E cases in `tests/test_embedding_a42b.py`, rather than relying on
dependencies actually being missing.

Please add tests along with new features. Build test material **in code at runtime** where
possible (see the hand-written xref PDF in `tests/test_converters.py` and the OOXML
generated with `zipfile`), and do not commit binary sample files.

---

## Hard constraints (read before changing code)

These were settled after hitting real problems; rolling them back reintroduces real failures:

1. **Zero frameworks** — the service layer is the standard-library `http.server`.
   Pulling in a web framework would blow up the runtime size immediately.
2. **Zero CDN on the front end** — `app/web/index.html` is a single-file vanilla JS app;
   the only external resource is `vendor/d3.v7.min.js`. It must work on a fully offline USB stick.
3. **No drive-letter binding** — all paths are derived in `core/paths.py` anchored on
   `__file__`. Drive letters change between machines, so **absolute paths must never be persisted**.
4. **Source of truth separated from the index** — `data/notes/*.md` is the only asset;
   `data/cache.db` must be fully rebuildable at any time. No design may make `cache.db` a requirement.
5. **Degrade rather than crash** — every external capability (embedding source / LLM /
   extractor / vector extension) needs a degradation chain, and the console must be able to
   state which path was actually taken.
6. **Warnings graded by "does the user need to act"** — self-healing progress goes into
   `notes` (run details on the settings page); only things requiring user action go into
   `warnings` (the top banner).
7. **HTTP response headers are latin-1 only** — never put a Chinese filename directly into a
   header; encode it per RFC 6266 with `filename*=UTF-8''…`.
8. **One single dependency manifest** — every install entry point reads `requirements.txt`;
   do not add hard-coded lists elsewhere.

For the fuller set of technical constraints and lessons learned, see
[`docs/design-and-implementation.md`](docs/design-and-implementation.md).

---

## About dependencies

- Before adding a dependency, ask: **can the standard library do this instead?** Runtime size
  is one of this project's core metrics.
- `docs/design-and-implementation.md` records the size cost of each dependency.
- `onnxruntime` / `tokenizers` are now **standard runtime dependencies** (local semantic search
  is a V1 standard capability), listed in `requirements.txt` and pinned exactly by the lock;
  still calculate the size cost before adding anything new.
- **Model bytes do not enter Git**: only `revision / sha256 / size` are pinned in
  `resources/embedding/default.json`, and `scripts/fetch_embedding_resource.py` fetches them
  with per-file verification.
- Note the criterion is "**does it need a model**", not "how many formats does it support":
  `.docx` / `.pptx` / `.xlsx` / `.epub` can all be parsed with the standard library
  `zipfile` + `xml.etree`, with zero dependencies.

---

## PR requirements

- One PR does one thing; avoid mixing "incidental refactor" with "new feature".
- Commit messages should describe **why** the change was made, not just what changed.
- If you change behaviour, update `README.md` / `README_EN.md` or `docs/` accordingly.
- When adding files, make sure `data/`, `config.ini` and `runtime/` are not added to version control.

## Reporting issues

Please include:

- OS and Python version
- Reproduction steps
- The actual degradation path from "Settings → Run Details" in the console (this usually
  points straight at the root cause)
- Relevant log excerpts

For security issues, do not open a public issue — see [`SECURITY.md`](SECURITY.md).
