"""
CorpBrain 출하 셸 엔트리포인트 — pywebview + WebView2, PyInstaller ``--onefile`` (DEC-01).

이 파일이 ``CorpBrain.exe`` 의 유일한 진입점이다. ``scripts/dev_serve.py`` 는 개발용 검증 실행기이며
번들에 들어가지 않는다 — 둘의 차이는 이 주석이 아니라 ``CorpBrain.spec`` 의 수집 목록이 정한다.

**DEC-01** — pywebview 가 OS 내장 WebView2(Edge Chromium)를 임베드하는 **단일 프로세스**. Python 이
호스트고 WebView 는 렌더러다. Electron·Tauri·Next.js·SSR·Node 런타임은 산출물에 들어가지 않는다.
React 번들은 **프리빌드 정적 SPA** 를 ``--add-data`` 로 내장하고 **HashRouter** 로 로드한다.
WebView2 Runtime 이 없으면 **Evergreen Bootstrapper 안내 다이얼로그 후 크래시 없이 종료**한다.

**DEC-02** — uvicorn 을 **창 생성 이전에** 데몬 스레드로 띄우고 ``127.0.0.1`` 전용 + ``port=0`` OS
할당 포트에 바인딩한 뒤, **``/api/v1/health`` 응답을 확인하고 나서** WebView 를 로드한다. 세션 토큰은
매 부팅 ``secrets.token_urlsafe(32)`` (``create_app`` 이 생성)이며 디스크·환경변수·로그에 기록하지
않는다. 포트도 토큰도 하드코딩하지 않는다 — 하드코딩이 `docs/loop/DECISION_LOG.md` 의 CORE #5 다.

**SPA 를 왜 ``file://`` 이 아니라 루프백 origin 에서 로드하는가.**
DEC-02 는 토큰 주입 수단으로 ``evaluate_js()`` **또는 초기 HTML 주입** 을 허용하고, CORS 는 "주입된
로컬 origin 으로만 제한" 하도록 정한다. SPA 를 API 와 같은 origin(``http://127.0.0.1:<port>/``)에서
서빙하면 **cross-origin 이 애초에 발생하지 않아** CORS 설정이 필요 없고, 토큰이 첫 HTML 안에 이미
들어 있어 React 의 첫 ``useEffect`` 호출과 주입 사이의 경합도 없다. ``file://`` 로드는 origin 이
``null`` 이 되어 허용 목록에 ``null`` 을 넣어야 하는데, 그것은 임의의 로컬 파일 페이지에 문을
열어주는 사실상의 와일드카드다.

  받아들이는 대가를 숨기지 않는다: ``/`` 는 토큰 검증을 거치지 않으므로 **이 포트에 도달할 수 있는
  같은 PC 의 프로세스는 ``/`` 를 읽어 토큰을 얻을 수 있다.** "랜덤 포트는 은닉 수단일 뿐 실질적
  방어선은 Bearer 토큰" 이라는 SRS §3.3 의 경고가 그대로 적용된다. ``file://`` + ``evaluate_js`` 로
  가면 이 표면은 사라지지만 위의 CORS 문제를 대신 떠안는다. 어느 쪽이든 같은 PC 의 다른 프로세스를
  완전히 막지는 못한다.

**egress 없음** — 이 모듈은 바깥으로 나가는 요청을 하나도 만들지 않는다. WebView2 부재 시에도
Evergreen Bootstrapper 를 **내려받지 않고 안내만 한다**. 자동 다운로드는 DEC-15 화이트리스트에 없는
네 번째 목적지가 되며, 그것은 코드 변경이 아니라 설계 결정 변경이다.
"""

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import uvicorn  # noqa: E402  - must follow the sys.path bootstrap above

from src.backend.api.app import create_app  # noqa: E402
from src.backend.db import DatabaseManager  # noqa: E402
from src.backend.utils.logging_setup import configure_logging  # noqa: E402

logger = logging.getLogger("CorpBrain.Shell")

#: Window title and default geometry. Frameless, so the title never renders — it is what the
#: OS taskbar and Alt-Tab show.
WINDOW_TITLE = "CorpBrain"
WINDOW_SIZE = (1440, 900)
WINDOW_MIN_SIZE = (1024, 640)

#: The SPA's entry route. DEC-01 fixes client routing to the hash router, so the shell has to
#: name a hash route explicitly — loading a bare "/" would leave `window.location.hash` empty
#: and the first paint would depend on the SPA's fallback rather than on the shell's intent.
INITIAL_ROUTE = "#/dashboard"

#: Window background, painted before the WebView renders its first frame (issue #151).
#: pywebview defaults `background_color` to "#FFFFFF", so without this the user sees a white
#: flash on every launch before the dark SPA paints — the opposite of DEC-01's "네이티브 앱과
#: 같은 부드러운 전환".
#:
#: The value tracks `index.html`'s `<body class="bg-dark-bg">`, NOT the React root's
#: `bg-slate-950`: the body is what paints first, and it resolves to `dark.bg` in
#: tailwind.config.js. Keep the two in sync — a mismatch reintroduces the flash as a colour
#: shift instead of a white one.
WINDOW_BACKGROUND_COLOR = "#0f172a"

#: Seconds to wait for uvicorn to bind its socket, and then for /api/v1/health to answer.
SERVER_START_TIMEOUT_SEC = 15.0
HEALTH_TIMEOUT_SEC = 10.0

#: Exit codes. All of them are *clean* exits — the shell prints no traceback on any of these
#: paths, which is what DEC-01's "크래시 없이 종료" asks for.
EXIT_OK = 0
EXIT_RUNTIME_MISSING = 2
EXIT_SERVER_FAILED = 3
EXIT_BUNDLE_MISSING = 4

#: The WebView2 Runtime's Evergreen client id under EdgeUpdate. Stable and published by
#: Microsoft; it is the documented way to detect an installed runtime.
WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

#: Detection sentinel for hosts where the question does not apply. CON-01 makes Windows the only
#: shipped target, but development happens on macOS — returning a sentinel rather than None keeps
#: `python src/main.py` usable on the dev host without teaching the runtime check to lie about
#: Windows.
RUNTIME_NOT_APPLICABLE = "not-windows"

EVERGREEN_BOOTSTRAPPER_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"

RUNTIME_MISSING_TITLE = "CorpBrain — WebView2 Runtime 필요"
RUNTIME_MISSING_MESSAGE = (
    "CorpBrain 을 실행하려면 Microsoft Edge WebView2 Runtime 이 필요합니다.\n"
    "이 PC 에서 설치된 런타임을 찾지 못했습니다.\n\n"
    "아래 주소에서 'Evergreen Bootstrapper' 를 내려받아 설치한 뒤 다시 실행해 주세요.\n\n"
    f"    {EVERGREEN_BOOTSTRAPPER_URL}\n\n"
    "CorpBrain 은 사용자 동의 없이 어떤 파일도 내려받지 않으므로, 설치 파일은 직접 받아 주셔야 합니다.\n"
    "확인을 누르면 프로그램이 종료됩니다."
)


# --- 번들 리소스 -----------------------------------------------------------------------------


def resource_root() -> Path:
    """
    Root of the bundled data files.

    Under PyInstaller ``--onefile`` the archive is unpacked to a temp dir exposed as
    ``sys._MEIPASS``; from a source checkout it is the repo root. Every bundled path is resolved
    through here so that no caller has to know which of the two it is running in.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else REPO_ROOT


def spa_dist_dir() -> Path:
    """Directory holding the prebuilt SPA (`npm run build` output), bundled via ``--add-data``."""
    return resource_root() / "dist"


# --- WebView2 런타임 탐지 ---------------------------------------------------------------------


def detect_webview2_runtime() -> Optional[str]:
    """
    Installed WebView2 Runtime version, ``None`` if absent, ``RUNTIME_NOT_APPLICABLE`` off Windows.

    Reads the ``pv`` value under the Evergreen client key. Three locations are checked because a
    per-machine install on 64-bit Windows lands under ``WOW6432Node`` while a per-user install
    lands under HKCU — checking only one of them reports "missing" for a perfectly working
    runtime, which would send the user to a download page they do not need.
    """
    if sys.platform != "win32":
        return RUNTIME_NOT_APPLICABLE

    import winreg  # Windows-only stdlib; imported here so this module imports on the dev host.

    subkey = rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}"
    wow_subkey = rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}"
    candidates = (
        (winreg.HKEY_LOCAL_MACHINE, wow_subkey),
        (winreg.HKEY_LOCAL_MACHINE, subkey),
        (winreg.HKEY_CURRENT_USER, subkey),
    )

    for hive, path in candidates:
        try:
            with winreg.OpenKey(hive, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            # Key or value absent under this hive — try the next location. Narrow on purpose:
            # a bare except here would swallow a genuine registry permission problem and report
            # it as "runtime missing".
            continue
        # EdgeUpdate writes "0.0.0.0" for a client that is registered but not actually installed.
        if version and str(version) != "0.0.0.0":
            return str(version)
    return None


def show_runtime_missing_dialog(message: str = RUNTIME_MISSING_MESSAGE) -> None:
    """
    Tell the user the runtime is missing, then let the caller exit.

    Uses the OS message box rather than pywebview: the whole point of this path is that the
    WebView cannot start, so anything drawn *by* the WebView is unavailable. Falls back to
    stderr off Windows so the dev host still shows the branch when it is exercised.
    """
    if sys.platform == "win32":
        import ctypes

        MB_OK, MB_ICONERROR, MB_SETFOREGROUND = 0x0, 0x10, 0x10000
        ctypes.windll.user32.MessageBoxW(
            None, message, RUNTIME_MISSING_TITLE, MB_OK | MB_ICONERROR | MB_SETFOREGROUND
        )
    else:
        print(f"{RUNTIME_MISSING_TITLE}\n{message}", file=sys.stderr)


# --- SPA 서빙 및 세션 브리지 주입 --------------------------------------------------------------


def build_bridge_script(base_url: str, token: str) -> str:
    """
    The ``window.__CORPBRAIN__`` bridge tag, escaped so it cannot break out of its own script.

    ``base_url`` is ``/`` in the shipped shell: the SPA is served from the API's own origin, so
    relative URLs resolve against it and the OS-assigned port is never written into the markup.
    """
    payload = json.dumps({"baseUrl": base_url, "token": token})
    # json.dumps escapes quotes but not "</script>", which would close this tag early and turn
    # the rest of the token into page text.
    payload = payload.replace("</", "<\\/")
    return f"<script>window.__CORPBRAIN__ = {payload};</script>"


def inject_bridge(markup: str, script: str) -> str:
    """Place the bridge tag inside <head> so it runs before the SPA bundle does."""
    if "</head>" in markup:
        return markup.replace("</head>", f"  {script}\n  </head>", 1)
    return script + markup


def mount_spa(app, token: str, dist_dir: Optional[Path] = None) -> bool:
    """
    Serve the bundled SPA at ``/``, with the session bridge injected into index.html.

    Returns False when the bundle is absent so the caller can fail with a message instead of
    opening a window onto a 404.

    ``dist/index.html`` on disk is never rewritten: persisting a token to a file is exactly what
    DEC-02 forbids, and under ``--onefile`` that file lives in a temp dir that is deleted on
    exit — so a rewrite would be both a violation and useless.
    """
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    dist = dist_dir if dist_dir is not None else spa_dist_dir()
    index_file = dist / "index.html"
    if not index_file.is_file():
        return False

    markup = index_file.read_text(encoding="utf-8")
    script = build_bridge_script("/", token)
    injected = inject_bridge(markup, script)

    # Registered before the StaticFiles mount so the injected copy wins over the file on disk.
    @app.get("/", include_in_schema=False)
    def spa_index() -> HTMLResponse:
        # no-store: the token changes every boot, so a cached index would carry a dead one.
        return HTMLResponse(injected, headers={"Cache-Control": "no-store"})

    # Mounted last so it cannot shadow /api/v1/* or /docs.
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")
    return True


# --- 로컬 API 서버 부팅 ------------------------------------------------------------------------


def start_api_server(app, timeout_sec: float = SERVER_START_TIMEOUT_SEC):
    """
    Boot uvicorn on ``127.0.0.1`` with an OS-assigned port, in a daemon thread (DEC-02).

    Returns ``(server, thread, port)``, or ``(server, thread, None)`` if the socket never bound.
    The port is read back off the bound socket — never chosen, never stored, never defaulted.

    ``log_config=None`` is load-bearing, not a tidy-up (issue #159). uvicorn's default logging
    config is a dictConfig whose formatter runs ``sys.stdout.isatty()``. This app ships with
    ``console=False`` (see CorpBrain.spec), so a process launched without inherited standard
    handles — which is every double-click — has ``sys.stdout is None`` and that call raises
    ``AttributeError``, surfacing as ``ValueError: Unable to configure formatter 'default'``
    from this very constructor. The window then never opens and nothing reaches the log,
    because this runs before the first ``logger.info``.

    Passing ``None`` skips uvicorn's dictConfig entirely. Its records still land somewhere:
    ``configure_logging()`` attaches the rolling file handler to the **root** logger, so
    ``uvicorn.error`` / ``uvicorn.access`` propagate into it — the only sink a windowed app has
    (REQ-NF-014). uvicorn's own stdout handlers would have had nowhere to write regardless.
    """
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", log_config=None)
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, name="corpbrain-api", daemon=True)
    thread.start()

    deadline = time.monotonic() + timeout_sec
    while not server.started and time.monotonic() < deadline:
        if not thread.is_alive():
            return server, thread, None
        time.sleep(0.05)

    if not server.started:
        return server, thread, None

    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, port


def wait_for_health(port: int, timeout_sec: float = HEALTH_TIMEOUT_SEC) -> bool:
    """
    Poll ``GET /api/v1/health`` until it answers 200 (DEC-02: check health *before* loading).

    ``server.started`` only proves the socket is bound; it says nothing about whether the app
    can answer. Loading the WebView against a half-initialised app is how a user gets a blank
    window instead of an error.

    Uses stdlib ``http.client`` deliberately. DEC-15 routes **outbound external** egress through
    NetworkGuard and puts the DEC-02 loopback server explicitly outside its scope, so this probe
    is not a fourth destination. ``ruff.toml`` bans ``http.client`` everywhere except this file
    so that the exemption is a visible, reviewable line rather than a gap in the ban list.
    """
    import http.client

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
        try:
            conn.request("GET", "/api/v1/health")
            if conn.getresponse().status == 200:
                return True
        except OSError:
            # Server not accepting yet. Narrow on purpose — an OSError here means "not up",
            # while anything else is a real bug that should surface rather than spin.
            pass
        finally:
            conn.close()
        time.sleep(0.1)
    return False


# --- 창 생성 ---------------------------------------------------------------------------------


def create_shell_window(url: str):
    """
    The frameless pywebview window (DEC-01).

    ``frameless=True`` with ``easy_drag=False``: the app draws its own title bar, and dragging is
    delegated to the SPA's ``.pywebview-drag-region`` elements. ``easy_drag`` would make the
    whole window draggable, so a click-and-drag anywhere — over the file list, over a text
    selection — would move the window instead.

    ``background_color`` is passed explicitly (issue #151): pywebview's default is white, which
    flashes before the dark SPA paints. See ``WINDOW_BACKGROUND_COLOR``.

    Imported inside the function so that importing this module (as the tests do) does not pull in
    a GUI toolkit.
    """
    import webview

    return webview.create_window(
        WINDOW_TITLE,
        url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN_SIZE,
        frameless=True,
        easy_drag=False,
        text_select=True,
        background_color=WINDOW_BACKGROUND_COLOR,
    )


def run_webview() -> None:
    """
    Hand control to pywebview's event loop.

    ``http_server=False``: pywebview ships its own static file server, and letting it start would
    put a *second* HTTP listener in the process — one that never saw DEC-02's Bearer middleware.
    The SPA is served by our own app instead.
    """
    import webview

    webview.start(http_server=False, private_mode=True)


# --- 엔트리포인트 ----------------------------------------------------------------------------


def main(
    argv: Optional[list] = None,
    *,
    runtime_detector: Callable[[], Optional[str]] = detect_webview2_runtime,
    dialog: Callable[[], None] = show_runtime_missing_dialog,
    window_factory: Callable[[str], object] = create_shell_window,
    loop_runner: Callable[[], None] = run_webview,
) -> int:
    """
    Boot order, fixed by DEC-02: server → health → runtime check → window.

    Every side-effecting step is injectable. That is not decoration: the WebView2-missing branch
    is unreachable on the macOS dev host and untestable in CI, and DEC-01 makes its behaviour
    ("안내 후 크래시 없이 종료") a requirement. Injecting the detector is what lets that branch be
    pinned by a unit test instead of by a promise to check it later on Windows.
    """
    parser = argparse.ArgumentParser(description="CorpBrain desktop shell (pywebview + WebView2).")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="boot the server, verify health, then exit without opening a window",
    )
    args = parser.parse_args(argv)

    configure_logging()

    dist = spa_dist_dir()
    if not (dist / "index.html").is_file():
        logger.error("SPA bundle missing at %s", dist)
        print(
            "SPA 번들을 찾을 수 없습니다. 소스에서 실행 중이라면 `npm run build` 를 먼저 실행하세요.",
            file=sys.stderr,
        )
        return EXIT_BUNDLE_MISSING

    db_mgr = DatabaseManager()
    app = create_app(db_mgr)
    token = app.state.session_token  # secrets.token_urlsafe(32), generated by create_app
    mount_spa(app, token, dist)

    server, thread, port = start_api_server(app)
    if port is None:
        logger.error("uvicorn did not bind within %.0fs", SERVER_START_TIMEOUT_SEC)
        print("로컬 API 서버를 시작하지 못했습니다.", file=sys.stderr)
        return EXIT_SERVER_FAILED

    if not wait_for_health(port):
        logger.error("/api/v1/health did not answer within %.0fs", HEALTH_TIMEOUT_SEC)
        print("로컬 API 서버가 응답하지 않습니다.", file=sys.stderr)
        server.should_exit = True
        return EXIT_SERVER_FAILED

    # Port only — never the token. DEC-02 keeps the token out of the log file, and the rolling
    # log is plain text that survives on disk for 7 days.
    logger.info("Local API ready on 127.0.0.1:%d", port)

    runtime_version = runtime_detector()
    if runtime_version is None:
        # DEC-01: guidance dialog, then a clean exit. No download is attempted — that would be a
        # fourth egress destination (DEC-15).
        logger.error("WebView2 Runtime not found; showing the Evergreen Bootstrapper guidance.")
        dialog()
        server.should_exit = True
        return EXIT_RUNTIME_MISSING

    logger.info("WebView2 Runtime: %s", runtime_version)

    if args.check_only:
        server.should_exit = True
        return EXIT_OK

    window_factory(f"http://127.0.0.1:{port}/{INITIAL_ROUTE}")
    loop_runner()

    server.should_exit = True
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
