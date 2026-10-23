#!/usr/bin/env python3
"""Release Builder —— 把源码仓库组装成发布产物 dist/Kavira-vX.Y.Z-<platform>-<lang>/。

一次构建产出**两个发布根**（`--lang both`，默认）：

    dist/Kavira-v1.3.0-win-x64-zh/     ← 中文包：安装器界面中文 + 中文文档
    dist/Kavira-v1.3.0-win-x64-en/     ← 英文包：安装器界面英文 + 英文文档

两包**差异只在 (a) 安装器界面语言 (b) 随包文档语言**，其余（payload / LICENSES /
清单 / 校验）完全同源同版本。产物是**构建产物**，不进 Git（dist/ 已在 .gitignore）。

布局（`<lang>` ∈ {zh, en}）：
    dist/Kavira-v1.3.0-win-x64-<lang>/
    ├─ installer/
    │  ├─ install.py            (SSD 安装骨架，拷贝自 scripts/install_windows.py)
    │  ├─ install.bat           (Windows：自带嵌入式 Python 跑 install.py <子命令> --lang <lang>)
    │  └─ release_integrity.py  (介质校验唯一实现，随安装器同目录分发)
    ├─ payload/
    │  ├─ app/                  (拷贝自仓库 app/)
    │  ├─ python-runtime/       (拷贝自仓库 runtime/python-3.11-embed/)
    │  └─ embedding/            (随包嵌入资源，来自 vendor/cache/embedding/)
    ├─ docs/                    (开发者文档 + 中文技术参考)
    ├─ START_HERE.txt           (zh) / START_HERE_EN.txt (en)
    ├─ User-Manual-ZH.txt              (zh) / User-Manual.txt  (en)
    ├─ CHANGELOG.md / LICENSE   (两包都放)
    ├─ LICENSES/                (第三方分发许可清单，collect_licenses.py 生成)
    ├─ BUILD_INFO.json          (版本可追溯性，含 lang)
    ├─ RELEASE_MANIFEST.json    (机器可读清单：相对路径 / 固定排序 / 含 sha256)
    └─ SHA256SUMS               (传统校验和，由清单派生)

约定（V1 Freeze / A3 范围）：
- 不联网、不 pip、不下载任何 >100MB 资源。
- 版本号唯一来源：app.version.APP_VERSION（本文件不写版本字面量）。
- SHA256 定位是 **Integrity**（介质损坏检测），不是 Authenticity —— 不签名、不加密。
- BUILD_INFO 绝不含 用户名 / 绝对路径 / HOME / LOCALAPPDATA / IP / 机器标识 / key。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # scripts/
REPO = HERE.parent                                 # 仓库根

#: 放在发布包**根目录**的文档 —— 用户解压后第一眼看到的，只放他真正要用的。
#: 判据很简单：**这是给用户的，还是给开发者的？** 根目录只放前者。
#:
#: 双语发布：`dist/Kavira-v<ver>-<platform>-zh/` 与 `...-en/` 两个发布根，
#: **差异只在「安装器界面语言」与「随包文档语言」**。因此：
#:   · 语言档文档（上手说明 / 使用手册 / README / CONTRIBUTING）按 --lang 二选一；
#:   · 公共文档（CHANGELOG / LICENSE / SECURITY / 行为准则）与中文技术参考两包都放。
DOCS_ROOT_BY_LANG = {
    "zh": ("START_HERE.txt", "User-Manual-ZH.txt"),
    "en": ("START_HERE_EN.txt", "User-Manual.txt"),
}
#: 根目录·两包都放 —— 用户会关心「这一版改了什么」，许可证是合规必需
DOCS_ROOT_SHARED = ("CHANGELOG.md", "LICENSE")

#: 面向开发者 / 技术评审的仓库文档 —— **收进 docs/ 子目录**。
#: 为什么不放根目录：用户解压后看到 README / CONTRIBUTING / SECURITY / 行为准则
#: 一整套开源仓库文档，会误以为「这是要我读的说明书」，与「装完就能用」的目标相反；
#: 而且 README 讲的是从源码构建、跑测试、发版流程，对用户是纯噪音。
#: 它们对仓库协作和技术评审仍然必要，所以**只换位置、不删**。
DOCS_DEV_BY_LANG = {
    "zh": ("README.md", "CONTRIBUTING.md"),
    "en": ("README_EN.md", "CONTRIBUTING_EN.md"),
}
#: docs/ 开发者档·两包都放（语言中立的行为契约）
DOCS_DEV_SHARED = ("SECURITY.md", "CODE_OF_CONDUCT.md")

#: docs/ 技术参考（中文）—— 与界面语言无关，两包都放，保留中文原文
RELEASE_DOCS_DIR_FILES = (
    "DATA_CONTRACT_V1.md", "DEPENDENCY_LOCK.md", "design-and-implementation.md",
    "architecture.md", "test-report.md", "v1.3-baseline.md",
)


def _ensure_repo_on_path() -> None:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))


def _copytree_prune(src: Path, dst: Path) -> None:
    """拷贝目录，剔除 __pycache__ / *.pyc（发布物不该带解释器缓存）。"""
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        dirs_exist_ok=True,
    )


def _fail_build(msg: str) -> "None":
    print(f"[build] 错误：{msg}", file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# 各构建阶段
# ---------------------------------------------------------------------------
def _stage_payload(dist_root: Path) -> bool:
    """app/ + python-runtime/。返回 runtime 是否就位。"""
    payload = dist_root / "payload"
    if not (REPO / "app").is_dir():
        _fail_build(f"仓库 app/ 不存在，无法构建 payload：{REPO / 'app'}")
    _copytree_prune(REPO / "app", payload / "app")

    # 应用图标（客户版观感）：payload 根供安装器用；dist 根供「解压后文件夹」显示
    ico_src = REPO / "resources" / "kavira.ico"
    if ico_src.is_file():
        shutil.copy2(ico_src, payload / "Kavira.ico")
        shutil.copy2(ico_src, dist_root / "Kavira.ico")
        (dist_root / "desktop.ini").write_text(
            "[.ShellClassInfo]\r\nIconResource=Kavira.ico,0\r\n",
            encoding="utf-8")

    rt_src = REPO / "runtime" / "python-3.11-embed"
    rt_dst = payload / "python-runtime"
    if (rt_src / "python.exe").is_file():
        _copytree_prune(rt_src, rt_dst)
        return True
    return False


#: 嵌入资源：取件（maintainer）与构建（builder）是两个动作，构建**绝不联网**
EMBEDDING_CONTRACT = REPO / "resources" / "embedding" / "default.json"
EMBEDDING_CACHE = REPO / "vendor" / "cache" / "embedding"

#: stable 判定码（与 strict Gate 的错误码一一对应）
EMB_OK = "ok"
EMB_ARTIFACT_MISSING = "EMBEDDING_ARTIFACT_MISSING"
EMB_METADATA_INVALID = "EMBEDDING_METADATA_INVALID"
EMB_HASH_MISMATCH = "EMBEDDING_HASH_MISMATCH"
EMB_TOKENIZER_MISSING = "EMBEDDING_TOKENIZER_MISSING"
EMB_LICENSE_MISSING = "EMBEDDING_LICENSE_MISSING"


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _stage_embedding(dist_root: Path) -> dict:
    """把随包嵌入资源拷进 ``payload/embedding/``（**只做本地拷贝**）。

    返回 ``{staged, code, reason, id, build_info}``。
    构建期做一次**全量 SHA256**：构建不是每次启动，24MB 的一次性校验值得付；
    运行时则刻意不重算（见 app/core/embedder.py 的 load_embedding_resource）。
    """
    report: dict = {"staged": False, "code": EMB_OK, "reason": "",
                    "id": None, "build_info": None, "applicable": True}

    if not EMBEDDING_CONTRACT.is_file():
        # 仓库根本未声明嵌入能力（微型/玩具仓库、纯词法形态）：跳过，不强制随包。
        report.update(code=EMB_METADATA_INVALID,
                      reason=f"缺少资源契约 {EMBEDDING_CONTRACT.name}",
                      applicable=False)
        return report
    try:
        contract = json.loads(EMBEDDING_CONTRACT.read_text(encoding="utf-8"))
    except ValueError as exc:
        report.update(code=EMB_METADATA_INVALID, reason=f"资源契约无法解析：{exc}")
        return report
    if contract.get("format_version") != 1:
        report.update(code=EMB_METADATA_INVALID, reason="资源契约 format_version 不受支持")
        return report

    local = contract.get("local_files") or {}
    model_name = Path(str(local.get("model") or "model.onnx")).name
    tok_name = Path(str(local.get("tokenizer") or "tokenizer.json")).name
    wanted: dict[str, str] = {model_name: str(contract.get("artifact_sha256") or "")}
    for name, rec in (contract.get("tokenizer_files") or {}).items():
        wanted[name] = str(rec.get("sha256") or "")

    missing = [n for n in wanted if not (EMBEDDING_CACHE / n).is_file()]
    if missing:
        report.update(code=EMB_ARTIFACT_MISSING,
                      reason=(f"vendor/cache/embedding 缺件：{', '.join(sorted(missing))}"
                              "（先跑 scripts/fetch_embedding_resource.py）"))
        return report
    if tok_name not in wanted or not (EMBEDDING_CACHE / tok_name).is_file():
        report.update(code=EMB_TOKENIZER_MISSING, reason=f"缺少 tokenizer 文件 {tok_name}")
        return report

    dest = dist_root / "payload" / "embedding"
    dest.mkdir(parents=True, exist_ok=True)
    for name in sorted(wanted):
        src = EMBEDDING_CACHE / name
        actual = _sha256_file(src)
        if actual != wanted[name].lower():
            report.update(code=EMB_HASH_MISMATCH,
                          reason=f"{name}：SHA256 与契约不符（期望 {wanted[name][:16]}…，"
                                 f"实际 {actual[:16]}…）")
            return report
        shutil.copy2(src, dest / name)
    # 契约本体（运行时按 artifact.json 解析，不猜文件名）
    shutil.copy2(EMBEDDING_CONTRACT, dest / "artifact.json")

    report.update(
        staged=True, id=contract.get("id"),
        build_info={
            "id": contract.get("id"),
            "base_model": contract.get("base_model"),
            "artifact_source": contract.get("artifact_source"),
            "artifact_revision": contract.get("artifact_revision"),
            "precision": contract.get("precision"),
            "dimension": contract.get("dimension"),
            "artifact_sha256": str(contract.get("artifact_sha256") or "").lower(),
            "tokenizer_sha256": str(((contract.get("tokenizer_files") or {}).get(tok_name) or {})
                                    .get("sha256") or "").lower(),
        },
    )
    return report


def _installer_bat(subcmd: str, lang: str = "zh") -> str:
    """生成 installer/*.bat 的内容（**纯 ASCII**）。

    硬性约束（否则 cp936 宿主机上 .bat 内嵌中文会乱码）：
      · 本体只含 ASCII，中文提示一律由 Python 打印；
      · **不使用括号块** —— 括号内 `%VAR%` 在解析期展开会拿到过期值，用 label/goto 扁平结构。
    关键 UX（2026-09-20 修）：双击 .bat 时 Windows 给了它一个新控制台，**进程一退出窗口即关闭**；
    此前没有 `pause`，导致用户「输入路径回车后窗口就没了」，成功/报错全都看不见。
    现在无论成功失败都 `pause` 等待按键，用户能看到完整输出。

    ``lang`` 只决定传给 install.py 的 ``--lang``，从而选择**界面文案语言**；
    ``--lang`` 放在 ``%*`` 之前，用户仍可用 ``install.bat --lang en`` 覆盖。
    """
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        "if not exist \"..\\payload\\python-runtime\\python.exe\" goto media_missing\r\n"
        f"..\\payload\\python-runtime\\python.exe install.py {subcmd} --lang {lang} %*\r\n"
        "set RC=%ERRORLEVEL%\r\n"
        "if not \"%RC%\"==\"0\" goto failed\r\n"
        "echo.\r\n"
        "echo [OK] Done. Return code 0.\r\n"
        "goto hold\r\n"
        ":failed\r\n"
        "echo.\r\n"
        "echo [ERROR] Failed with exit code %RC%. Please read the message above.\r\n"
        "goto hold\r\n"
        ":hold\r\n"
        "echo.\r\n"
        "echo Press any key to close this window . . .\r\n"
        "pause >nul\r\n"
        "exit /b %RC%\r\n"
        ":media_missing\r\n"
        "echo MEDIA_CORRUPTED: payload\\python-runtime\\python.exe missing\r\n"
        "echo Press any key to close this window . . .\r\n"
        "pause >nul\r\n"
        "exit /b 5\r\n"
    )


def _stage_installer(dist_root: Path, lang: str = "zh") -> None:
    installer_dir = dist_root / "installer"
    installer_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "install_windows.py", installer_dir / "install.py")
    # 介质校验唯一实现：安装器同目录副本，避免「构建/校验」两套枚举漂移
    shutil.copy2(HERE / "release_integrity.py", installer_dir / "release_integrity.py")
    # ⚠ 两个 .bat 都必须带上**子命令**：install.py 是 subparsers 结构，
    #   `install.py --app-target X` 会被 argparse 当成「X 是子命令」而报 invalid choice
    #   （旧版 install.bat 写的是 `install.py %*`，缺 `install` 子命令 → 带参数的 CLI 用法一直是坏的）。
    #   同时固定 `--lang <lang>`：双击即得对应语言界面，无需用户记参数。
    (installer_dir / "install.bat").write_text(
        _installer_bat("install", lang), encoding="ascii")
    (installer_dir / "uninstall.bat").write_text(
        _installer_bat("uninstall", lang), encoding="ascii")
    if not (installer_dir / "install.py").is_file():
        _fail_build("installer/install.py 生成失败")
    if not (installer_dir / "release_integrity.py").is_file():
        _fail_build("installer/release_integrity.py 生成失败")


def _stage_docs(dist_root: Path, lang: str = "zh") -> int:
    """随包文档（白名单）—— **按语言包**决定放哪些。

    分三层，**按读者**归位而不是一股脑堆在根目录：
      1. 根目录 → 用户要用的（上手说明 / 使用手册 / 更新日志 / 许可证）
      2. docs/   → 开发者与评审要用的（README / 贡献指南 / 安全策略 / 行为准则）
      3. docs/   → 技术参考资料（架构、依赖锁、测试报告…）

    ``lang`` 是 ``"zh"`` / ``"en"``：语言档文档二选一（zh 包不带英文文档，反之亦然），
    公共文档与中文技术参考两包都放。文件不存在就跳过（仓库可能没写全），返回落盘数。

    MANIFEST 是**枚举实际文件**生成的，所以换位置/换语言不破坏完整性校验。
    """
    count = 0
    for name in DOCS_ROOT_BY_LANG[lang] + DOCS_ROOT_SHARED:
        src = REPO / name
        if src.is_file():
            shutil.copy2(src, dist_root / name)
            count += 1
    docs_dst = dist_root / "docs"
    for name in DOCS_DEV_BY_LANG[lang] + DOCS_DEV_SHARED:
        src = REPO / name
        if src.is_file():
            docs_dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, docs_dst / name)
            count += 1
    for name in RELEASE_DOCS_DIR_FILES:
        src = REPO / "docs" / name
        if src.is_file():
            docs_dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, docs_dst / name)
            count += 1
    return count


def _version_sources() -> dict:
    """schema / data format 的**唯一来源**，一律 import 现取，不写字面量。"""
    from app.core.migrations import CURRENT_SCHEMA_VERSION      # noqa: PLC0415
    from app.core.library import DATA_FORMAT_VERSION            # noqa: PLC0415
    return {"schema_version": CURRENT_SCHEMA_VERSION,
            "data_format_version": DATA_FORMAT_VERSION}


def _build_info(root: Path, platform: str, rt_ok: bool,
                embedding: dict | None = None, lang: str = "zh") -> dict:
    import release_integrity as ri                              # noqa: PLC0415

    lock = REPO / "requirements-release.lock"
    lock_sha = ri.sha256_file(lock) if lock.is_file() else None
    py_ver = ri.resolve_python_version(root / "payload" / "python-runtime") if rt_ok else None
    versions = _version_sources()
    info = ri.build_info(
        platform=platform,
        commit=ri.resolve_git_commit(REPO),
        python_version=py_ver,
        dependency_lock_sha256=lock_sha,
        schema_version=versions["schema_version"],
        data_format_version=versions["data_format_version"],
    )
    # §18：随包嵌入资源身份。只记「是什么字节」，**不记任何绝对路径**。
    info["embedding"] = embedding
    # 语言包身份：同一版本会产出 -zh / -en 两个发布根，BUILD_INFO 必须能区分
    info["lang"] = lang
    return info


def build(platform: str, output: Path, strict: bool = False,
          lang: str = "both") -> Path:
    """构建发布包。

    ``lang == "both"``（默认）→ 先 zh 后 en 各建一次，返回**最后一个**（en）的发布根；
    ``lang`` 为 ``"zh"`` / ``"en"`` → 只建该语言一个包。
    两个包同源同版本，差异只在安装器界面语言与随包文档语言。
    """
    langs = ("zh", "en") if lang == "both" else (lang,)
    dist_root: Path | None = None
    for one in langs:
        dist_root = _build_one(platform, output, strict=strict, lang=one)
    assert dist_root is not None          # langs 恒非空
    return dist_root


def _build_one(platform: str, output: Path, strict: bool = False,
               lang: str = "zh") -> Path:
    _ensure_repo_on_path()
    from app.version import APP_VERSION            # 唯一版本源  # noqa: PLC0415

    name = f"Kavira-v{APP_VERSION}-{platform}-{lang}"
    dist_root = output / name
    if dist_root.exists():
        shutil.rmtree(dist_root)

    rt_ok = _stage_payload(dist_root)
    if not rt_ok:
        if strict:
            _fail_build(f"严格模式：未找到嵌入式 Python "
                        f"{REPO / 'runtime' / 'python-3.11-embed'}。"
                        " 正式发布前请先 `python setup_runtime_windows.py`。")
        print(f"[build] 警告：未找到嵌入式 Python，跳过 python-runtime 拷贝。"
              " 正式发布前请先 `python setup_runtime_windows.py`。", file=sys.stderr)

    _stage_installer(dist_root, lang)
    doc_count = _stage_docs(dist_root, lang)
    dist_root.mkdir(parents=True, exist_ok=True)

    import collect_licenses as cl                               # noqa: PLC0415
    import release_integrity as ri                              # noqa: PLC0415

    # 1) LICENSES（只审实际随包内容；无运行时则记录 inventory_complete=false）
    licenses = cl.collect(
        dist_root / "payload" / "python-runtime",
        REPO / "requirements-release.lock",
        dist_root,
        python_version=ri.resolve_python_version(dist_root / "payload" / "python-runtime"),
    )

    # 1.5) 随包嵌入资源（**只做本地拷贝**，缺件绝不联网现下）
    emb = _stage_embedding(dist_root)
    if emb["staged"]:
        # 2) BUILD_INFO 带上 embedding 块（§18）
        info = _build_info(dist_root, platform, rt_ok, emb["build_info"], lang=lang)
    elif emb.get("applicable"):
        info = _build_info(dist_root, platform, rt_ok, None, lang=lang)
        msg = (f"[build] 嵌入资源未随包：{emb['code']} —— {emb['reason']}")
        if strict:
            print(msg, file=sys.stderr)
        else:
            print(msg + "（非 strict：允许不带嵌入资源）", file=sys.stderr)
    else:
        # 仓库未声明嵌入能力：不打印「未随包」告警（那是契约缺失导致的误报）
        info = _build_info(dist_root, platform, rt_ok, None, lang=lang)
    ri.write_build_info(dist_root, info)

    # 3) RELEASE_MANIFEST → 4) SHA256SUMS（同一套枚举，单一出口）
    _, manifest = ri.write_manifest(dist_root)
    ri.write_checksums(dist_root, manifest)

    # 5) 自校验：构建产物必须能通过自己的介质校验（否则「看起来成功」最危险）
    check = ri.verify_media(dist_root)

    if strict:
        _strict_gate(dist_root, rt_ok, info, licenses, manifest, check, doc_count, emb)

    print(f"{'BUILD OK' if strict else 'DEV BUILD OK（非正式发布）'} -> {dist_root}")
    print(f"  发布格式版本           {ri.FORMAT_VERSION}")
    print(f"  语言包                 {lang}")
    print(f"  文件数（清单）         {len(manifest['files'])}")
    print(f"  payload/app/           {(dist_root / 'payload' / 'app').is_dir()}")
    print(f"  payload/python-runtime/ {rt_ok}")
    print(f"  installer/              {(dist_root / 'installer' / 'install.py').is_file()}")
    print(f"  随包文档               {doc_count}")
    _summary = licenses["summary"]
    print(f"  第三方组件             {_summary['packages']}"
          f"（待复核 {_summary.get('review_required', 0)}"
          f" / 仅元数据 {_summary.get('metadata_only', 0)}）")
    if _summary.get("locked_missing"):
        print(f"  ⚠ LOCK_ENTRY_MISSING     {_summary['locked_missing']}")
    if _summary.get("version_mismatch"):
        # 发布构建从 lock 安装，正常应零差异；有差异说明 runtime 非由当前锁构建。
        # 非 strict 只是开发态提示；strict 下同一条件会以 RUNTIME_LOCK_MISMATCH 直接失败。
        print("  ⚠ RUNTIME_LOCK_MISMATCH  "
              + "；".join(_summary["version_mismatch"]))
    if _summary.get("required_metadata_only"):
        print("  ⚠ LICENSE_TEXT_MISSING   随包运行依赖缺许可原文："
              + "，".join(_summary["required_metadata_only"]))
    if _summary.get("vendor_problems"):
        print("  ⚠ VENDOR_LICENSE_INVALID " + "；".join(_summary["vendor_problems"]))
    print(f"  介质自校验             {check.code}"
          + (f" 失败 {len(check.failures)} 项" if check.failures else ""))
    return dist_root


def _strict_gate(dist_root: Path, rt_ok: bool, info: dict, licenses: dict,
                 manifest: dict, check, doc_count: int, emb: dict) -> None:
    """正式发布的完整门禁 —— 任一条件不满足即非零退出。

    每个条件带**稳定错误码**，便于 CI / 售后按码定位（不用去解析中文描述）：

        APP_MISSING / RUNTIME_MISSING / INSTALLER_MISSING
        BUILD_INFO_INCOMPLETE / MEDIA_SELFCHECK_FAILED
        LICENSES_INCOMPLETE / LOCK_ENTRY_MISSING
        **RUNTIME_LOCK_MISMATCH** —— 随包运行时与依赖锁版本不一致
        **LICENSE_TEXT_MISSING** —— 随包运行依赖只有元数据、缺许可原文
        **VENDOR_LICENSE_INVALID** —— vendor 许可原文库缺件/被改动
        LICENSE_REVIEW_REQUIRED_REMAINING —— 仍有无法确认许可的组件
        **EMBEDDING_ARTIFACT_MISSING / EMBEDDING_METADATA_INVALID /
        EMBEDDING_HASH_MISMATCH / EMBEDDING_TOKENIZER_MISSING /
        EMBEDDING_LICENSE_MISSING** —— 随包嵌入资源不可用
    """
    problems: list[tuple[str, str]] = []

    def need(ok: bool, code: str, detail: str) -> None:
        if not ok:
            problems.append((code, detail))

    summary = licenses.get("summary") or {}

    need((dist_root / "payload" / "app").is_dir(),
         "APP_MISSING", "缺少 payload/app/")
    need(rt_ok and (dist_root / "payload" / "python-runtime" / "python.exe").is_file(),
         "RUNTIME_MISSING", "缺少 payload/python-runtime/python.exe")
    need((dist_root / "installer" / "install.py").is_file(),
         "INSTALLER_MISSING", "缺少 installer/install.py")
    need((dist_root / "installer" / "install.bat").is_file(),
         "INSTALLER_MISSING", "缺少 installer/install.bat")
    need((dist_root / "installer" / "uninstall.bat").is_file(),
         "INSTALLER_MISSING", "缺少 installer/uninstall.bat")
    need(bool(info.get("git_commit")) and info.get("git_commit") != "unknown",
         "BUILD_INFO_INCOMPLETE", "BUILD_INFO.git_commit 未解析（版本不可追溯）")
    need(bool(info.get("python_version")),
         "BUILD_INFO_INCOMPLETE", "BUILD_INFO.python_version 未解析")
    need(bool(info.get("dependency_lock_sha256")),
         "BUILD_INFO_INCOMPLETE", "BUILD_INFO.dependency_lock_sha256 缺失（依赖锁不在仓库）")

    # A3.1 硬门禁 #1：BUILD_INFO 记录的是「这份 lock」的 SHA256，
    # 那么随包运行时就必须确实由这份 lock 构建 —— 否则可追溯性是假的。
    need(not summary.get("version_mismatch"),
         "RUNTIME_LOCK_MISMATCH",
         "随包运行时与依赖锁版本不一致（请按 lock 重建 runtime，禁止反向改 lock 迎合旧 runtime）："
         + "；".join(summary.get("version_mismatch") or []))

    # A3 门禁：许可清单
    need(bool(licenses.get("inventory_complete")),
         "LICENSES_INCOMPLETE", "LICENSES 清单不完整（inventory_complete=false）")
    need(not summary.get("vendor_problems"),
         "VENDOR_LICENSE_INVALID",
         "vendor 许可原文库不一致：" + "；".join(summary.get("vendor_problems") or []))
    need(not summary.get("locked_missing"),
         "LOCK_ENTRY_MISSING",
         "依赖锁条目未随包：" + ", ".join(summary.get("locked_missing") or []))
    need(not summary.get("required_metadata_only"),
         "LICENSE_TEXT_MISSING",
         "随包运行依赖只有元数据、缺许可原文（分发义务未闭）："
         + ", ".join(summary.get("required_metadata_only") or []))
    need(not summary.get("review_required"),
         "LICENSE_REVIEW_REQUIRED_REMAINING",
         f"{summary.get('review_required')} 个组件许可待人工复核"
         "（LICENSE_REVIEW_REQUIRED，V1 发布前必须清零）")

    # ---- A4.2b：随包嵌入资源（V1 标准能力，缺件即拒绝发布）----
    #   ⚠ 这里**永远不会**联网补件：取件是 maintainer 的独立动作。
    #     构建内偷偷下载会让「构建可复现」失效，也会让客户安装阶段的网络假设失真。
    #   - 资源契约（resources/embedding/default.json）声明了嵌入能力 ⇒ 必须随包且可校验；
    #   - 未声明（微型/玩具仓库、纯词法形态）⇒ 跳过，不强制（避免把「没用到嵌入」判红）。
    if emb.get("applicable", True):
        emb_code = emb.get("code") or EMB_OK
        need(emb_code == EMB_OK and bool(emb.get("staged")),
             emb_code or EMB_ARTIFACT_MISSING,
             f"随包嵌入资源不可用：{emb.get('reason') or '未知原因'}"
             "（先跑 scripts/fetch_embedding_resource.py）")
        need((dist_root / "payload" / "embedding" / "artifact.json").is_file(),
             EMB_METADATA_INVALID, "payload/embedding/artifact.json 缺失（运行时按它解析资源）")
        need((dist_root / "payload" / "embedding" / "model.onnx").is_file(),
             EMB_ARTIFACT_MISSING, "payload/embedding/model.onnx 缺失")
        need((dist_root / "payload" / "embedding" / "tokenizer.json").is_file(),
             EMB_TOKENIZER_MISSING, "payload/embedding/tokenizer.json 缺失")
        need(bool(info.get("embedding")),
             EMB_METADATA_INVALID, "BUILD_INFO.embedding 缺失（资源身份不可追溯）")
        # 模型许可必须随 Release 保留：BAAI MIT 原文 + PROVENANCE（如实记录「转换产物」关系）
        model_lic = dist_root / "LICENSES" / "models" / "bge-small-zh-v1.5"
        need((model_lic / "LICENSE").is_file() and (model_lic / "PROVENANCE.json").is_file(),
             EMB_LICENSE_MISSING,
             "LICENSES/models/bge-small-zh-v1.5/ 缺 LICENSE 或 PROVENANCE.json"
             "（base model MIT 声明必须随 Release 保留）")

    need(bool(manifest.get("files")), "MANIFEST_EMPTY", "RELEASE_MANIFEST 为空")
    need((dist_root / "SHA256SUMS").is_file(),
         "CHECKSUMS_MISSING", "缺少 SHA256SUMS")
    need(doc_count > 0, "DOCS_MISSING", "随包文档为 0（文档白名单与仓库不匹配）")
    need(check.ok, "MEDIA_SELFCHECK_FAILED",
         f"介质自校验未通过（{check.code}）：" + "；".join(check.failures[:5]))

    if problems:
        codes = " ".join(dict.fromkeys(c for c, _ in problems))
        print(f"[build] GATE FAILED codes={codes}", file=sys.stderr)
        _fail_build("严格模式门禁未通过 —— "
                    + " | ".join(f"{c}: {d}" for c, d in problems))


def _zip_packages(output: Path) -> list[Path]:
    """把 output 下每个发布根压成同名 ``.zip``（zip 内保留顶层目录名，解压即用）。

    此前 zip 是手工压的：既容易漏压，也容易把目录名压错一层。并进构建后
    ``--zip`` 一条命令即可出齐。只压**含 BUILD_INFO.json** 的目录，避免误压临时目录。
    """
    import os
    import time
    import zipfile

    made: list[Path] = []
    for d in sorted(p for p in output.iterdir() if p.is_dir()):
        if not (d / "BUILD_INFO.json").is_file():
            continue
        # 不能用 with_suffix：目录名里含版本号的点（如 Kavira-v1.4.0-win-x64-zh
        # 的 suffix 会被认成 ".0-win-x64-zh"），会把包名截成 Kavira-v1.4.zip
        out = d.parent / (d.name + ".zip")
        t0 = time.time()
        n = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for base, _dirs, files in os.walk(d):
                for f in files:
                    p = os.path.join(base, f)
                    z.write(p, os.path.relpath(p, output))
                    n += 1
        print(f"ZIP OK -> {out}  {n} files  {out.stat().st_size / 1048576:.1f} MB"
              f"  ({time.time() - t0:.1f}s)")
        made.append(out)
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description="Kavira Release Builder")
    ap.add_argument("--platform", default="win-x64")
    ap.add_argument("--output", default=str(REPO / "dist"), help="dist 根目录")
    ap.add_argument("--strict", action="store_true",
                    help="严格模式（正式发布）：app/runtime/installer/BUILD_INFO/"
                         "LICENSES/MANIFEST/SHA256SUMS/自校验 全通过才退出 0；"
                         "开发模式缺 runtime 仍可构建")
    ap.add_argument("--lang", choices=["zh", "en", "both"], default="both",
                    help="发布包语言：zh / en 各出一个发布根，both（默认）两个都出")
    ap.add_argument("--zip", action="store_true", dest="do_zip",
                    help="构建完成后把每个发布根压成同名 .zip（放在输出目录同级）")
    args = ap.parse_args()
    build(args.platform, Path(args.output).resolve(),
          strict=args.strict, lang=args.lang)
    if args.do_zip:
        _zip_packages(Path(args.output).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
