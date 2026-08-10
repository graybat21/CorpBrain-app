# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller `--onefile` spec — 단일 `CorpBrain.exe` (DEC-01 / CON-02).

빌드 (순서 고정):
    npm ci && npm run build          # 1) React SPA 정적 번들 생성 (dist/)
    python -m PyInstaller --noconfirm CorpBrain.spec   # 2) exe 패키징

**순서를 바꾸면 안 되는 이유**: Vite 와 PyInstaller 가 둘 다 `dist/` 를 쓴다. `vite build` 는
`dist/` 를 **비우고** 시작하므로 먼저 패키징하면 그 결과물이 지워진다. 반대 순서는 안전하다 —
아래 `datas` 가 `dist` 를 통째로가 아니라 파일 단위로 수집하기 때문에, 같은 디렉터리에 있는
exe 가 다음 빌드에 섞여 들어가지 않는다.

`onefile=True` 는 `EXE(...)` 에 `a.binaries`/`a.datas` 를 직접 넘기고 `COLLECT` 를 쓰지 않는 형태로
표현된다. `COLLECT` 를 추가하면 그 순간 onedir 빌드가 되어 DEC-01 의 "단일 `.exe` 1개" 가 깨진다.

**Windows 산출물은 Windows 에서만 나온다.** PyInstaller 는 크로스 컴파일하지 않으므로 macOS 에서 이
spec 을 돌리면 macOS 실행 파일이 나온다. 그 실행이 증명하는 것은 "spec 이 파싱되고 의존성 수집이
성공한다" 까지이며, `CorpBrain.exe` 의 실제 동작은 `docs/review/WINDOWS_SMOKE_CHECKLIST.md` 로만
확인된다.
"""

import sys
from pathlib import Path

# SPECPATH is injected by PyInstaller and points at this file's directory.
REPO_ROOT = Path(SPECPATH).resolve()  # noqa: F821 - PyInstaller global
SPA_DIST = REPO_ROOT / "dist"
MIGRATIONS = REPO_ROOT / "migrations"

# Fail here rather than shipping an exe that opens a window onto a 404. The SPA is a build-time
# artifact (DEC-01: Node is a toolchain, never a runtime dependency), so its absence means step 1
# of the build was skipped — which is a mistake worth stopping for, not warning about.
if not (SPA_DIST / "index.html").is_file():
    raise SystemExit(
        "CorpBrain.spec: dist/index.html 이 없습니다. `npm ci && npm run build` 를 먼저 실행하세요."
    )
if not MIGRATIONS.is_dir():
    raise SystemExit("CorpBrain.spec: migrations/ 디렉터리를 찾을 수 없습니다.")

# `dist/` is also PyInstaller's own default output directory, so the SPA is collected file by
# file instead of as a whole tree. Collecting `dist` wholesale would fold a previous build's
# `CorpBrain.exe` into the next one, and the binary would double in size on every rebuild.
datas = [
    (str(SPA_DIST / "index.html"), "dist"),
    (str(SPA_DIST / "assets"), "dist/assets"),
    # DatabaseManager resolves migrations as `src/backend/../../migrations`, which under
    # --onefile is `sys._MEIPASS/migrations`. Without these the first boot on a clean machine
    # creates an empty database with user_version 0 and every query fails on a missing table.
    (str(MIGRATIONS), "migrations"),
]

hiddenimports = [
    # Imported lazily inside functions (`_LazyVectorStore`, `create_shell_window`) or by string,
    # so PyInstaller's static import graph does not reach them.
    "src.backend.services.vector_service",
    "webview",
    # uvicorn resolves its protocol implementations at runtime from a config string.
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

# Windows-only stdlib. Listing it unconditionally would make a macOS build fail on a module that
# does not exist there, and the WebView2 registry probe is Windows-only by definition.
if sys.platform == "win32":
    hiddenimports.append("winreg")

# Anaconda ships expat/openssl/libffi/liblzma/sqlite3/zlib/... as *loose* DLLs under
# <env>\Library\bin. The stdlib C-extensions that need them (pyexpat, _ssl, _ctypes, _lzma,
# sqlite3, ...) load them by name off PATH at import time, not via a linked reference PyInstaller
# can trace. So a --onefile build made from an Anaconda-based interpreter freezes fine but dies at
# startup with e.g. "ImportError: DLL load failed while importing pyexpat" — the import happens in
# a PyInstaller runtime hook, before main.py's logging is even configured, so nothing is logged and
# the exit code is a bare 1. Collecting the whole dir (it is small on this env — ~18MB) fixes all of
# them at once, which is the same reasoning the onedir profile used before the onefile conversion
# dropped it. Guarded on the dir existing so a clean (non-Anaconda) CPython build stays unaffected:
# there Library\bin does not exist and the stdlib DLLs are already where PyInstaller finds them.
binaries = []
_conda_lib_bin = Path(sys.base_prefix) / "Library" / "bin"
if _conda_lib_bin.is_dir():
    binaries.extend((str(_dll), ".") for _dll in sorted(_conda_lib_bin.glob("*.dll")))

a = Analysis(  # noqa: F821 - PyInstaller global
    [str(REPO_ROOT / "src" / "main.py")],
    pathex=[str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # DEC-01 forbids a shipped Node runtime; these are build-time or dev-only and must not be
    # dragged in by a transitive import. `scripts.dev_serve` in particular is the dev launcher
    # whose index route hands out the session token without authentication.
    excludes=[
        "scripts.dev_serve",
        "tkinter",
        "pytest",
        "_pytest",
        "IPython",
        "matplotlib",
        "notebook",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821 - PyInstaller global

exe = EXE(  # noqa: F821 - PyInstaller global
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CorpBrain",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=False: the shipped app is windowed. This is also why REQ-NF-014's rolling file log
    # exists — with no console, a `print` or an unhandled traceback goes nowhere at all.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# Deliberately no COLLECT(...) — see the module docstring. One file, one exe.
