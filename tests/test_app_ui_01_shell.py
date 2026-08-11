"""
APP-UI-01 / 이슈 #14 — 출하 셸(pywebview + WebView2 + PyInstaller `--onefile`) 검증.

**이 파일이 macOS 에서 증명하는 것과 증명하지 못하는 것.**

증명한다:
- WebView2 부재 분기가 안내 다이얼로그를 띄우고 **창을 만들지 않고** 예외 없이 종료한다.
- 부팅 순서가 DEC-02 그대로다 — 서버 → `/api/v1/health` 확인 → 런타임 확인 → 창.
- 포트·토큰이 하드코딩되어 있지 않다 (DECISION_LOG CORE #5 의 재발 방지).
- SPA 가 루프백 origin 에서 서빙되고 세션 브리지가 첫 HTML 에 주입된다.
- spec 파일이 `--onefile` 형태이며 SPA·migrations 를 수집한다.
- 해시 라우트 파싱이 셸의 진입 라우트와 일치한다.

증명하지 못한다 (Windows 전용 → `docs/review/WINDOWS_SMOKE_CHECKLIST.md`):
- 실제 WebView2 렌더, 프레임리스 창의 드래그 동작, `CorpBrain.exe` 의 단일 실행,
  레지스트리 탐지의 실제 반환값. PyInstaller 는 크로스 컴파일하지 않으므로 macOS 빌드는
  Windows exe 가 아니다.

런타임 탐지·다이얼로그·창 생성·이벤트 루프가 전부 `main()` 의 주입 인자인 이유가 이것이다.
주입 가능하지 않으면 위 분기들은 "Windows 에서 확인하겠다" 는 약속으로만 남는다.
"""

import re
import sys
from pathlib import Path

import pytest
import uvicorn

from src import main as shell

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = REPO_ROOT / "CorpBrain.spec"
MAIN_PY = REPO_ROOT / "src" / "main.py"
ROUTER_TS = REPO_ROOT / "src" / "frontend" / "router.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(path: Path) -> str:
    """
    Source with comments and docstrings removed.

    Needed because several assertions below are of the form "this identifier must not appear".
    A prose explanation of *why* `COLLECT` or `react-router` is absent contains the very string
    being searched for, so a raw read makes the file fail its own rule — the check would be
    testing the comments rather than the code.
    """
    text = _read(path)
    text = re.sub(r'"""(?:.|\n)*?"""', "", text)  # Python docstrings
    text = re.sub(r"/\*(?:.|\n)*?\*/", "", text)  # TS block comments
    text = re.sub(r"^\s*#.*$", "", text, flags=re.M)  # Python line comments
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)  # TS line comments
    return text


class _RecordingDialog:
    """Stands in for the OS message box so the branch can run headless."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1


class _RecordingWindowFactory:
    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return object()


@pytest.fixture
def shell_env(tmp_path, monkeypatch):
    """
    A full boot with the real FastAPI app and a real uvicorn socket, but no GUI.

    Both the database and the log file are redirected into a temp dir. REQ-NF-004 asks for path
    isolation, and a test run must not write into the user's real `%LocalAppData%\\CorpBrain`.
    `create_app` skips `configure_logging` when it is handed a DatabaseManager for exactly this
    reason, but `main()` calls it directly — it owns the process — so the fixture has to stop it
    here or every test run would append to the user's real rolling log.
    """
    from src.backend.db import DatabaseManager

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<html><head><title>CorpBrain</title></head><body><div id='root'></div></body></html>",
        encoding="utf-8",
    )

    monkeypatch.setattr(shell, "spa_dist_dir", lambda: dist)
    monkeypatch.setattr(shell, "configure_logging", lambda: None)

    managers = []
    real_init = DatabaseManager.__init__

    def _isolated_init(self, db_path=None, migrations_dir=None):
        real_init(
            self,
            db_path=str(tmp_path / "shell.db"),
            migrations_dir=str(REPO_ROOT / "migrations"),
        )
        managers.append(self)

    monkeypatch.setattr(DatabaseManager, "__init__", _isolated_init)
    yield dist
    for manager in managers:
        manager.close()


# --- DEC-01: WebView2 부재 시 안내 후 graceful exit ---------------------------------------------


def test_missing_webview2_runtime_shows_guidance_and_exits_without_a_window(shell_env):
    """
    DEC-01: 런타임 부재 시 Evergreen Bootstrapper 안내 다이얼로그 후 **크래시 없이** 종료.

    세 가지를 동시에 단정한다 — 다이얼로그가 떴는가, **창이 만들어지지 않았는가**, 예외 없이
    종료 코드를 돌려주는가. 창 생성 여부를 빼면 "안내도 하고 창도 띄우는" 구현이 통과한다.
    """
    dialog = _RecordingDialog()
    window_factory = _RecordingWindowFactory()

    code = shell.main(
        [],
        runtime_detector=lambda: None,
        dialog=dialog,
        window_factory=window_factory,
        loop_runner=lambda: pytest.fail("the event loop must not start without a runtime"),
    )

    assert code == shell.EXIT_RUNTIME_MISSING
    assert dialog.calls == 1, "the guidance dialog must be shown exactly once"
    assert window_factory.urls == [], "no window may be created when WebView2 is absent"


def test_runtime_guidance_message_points_at_the_bootstrapper_without_downloading_it():
    """
    안내는 안내로 끝난다.

    DEC-15 의 화이트리스트는 `llm_local` / `llm_cloud` / `provisioning` 세 쌍뿐이고 Microsoft
    다운로드 호스트는 그 안에 없다. 부트스트래퍼를 자동으로 내려받는 구현은 코드 변경이 아니라
    **설계 결정 변경**이므로, 메시지에 주소를 적을 수는 있어도 셸이 요청을 보내서는 안 된다.
    """
    assert shell.EVERGREEN_BOOTSTRAPPER_URL in shell.RUNTIME_MISSING_MESSAGE

    source = _read(MAIN_PY)
    # The shell may name the URL in a message; it may not hand it to anything that fetches.
    for fetcher in ("urlretrieve", "urlopen", "webbrowser.open", "subprocess.", "os.startfile"):
        assert fetcher not in source, f"the shell must not invoke {fetcher} on the runtime-missing path"


def test_present_runtime_opens_a_window_at_the_hash_entry_route(shell_env):
    """정상 경로: 창이 셸이 정한 진입 해시 라우트로 열린다 (DEC-01 HashRouter)."""
    dialog = _RecordingDialog()
    window_factory = _RecordingWindowFactory()
    loop_calls = []

    code = shell.main(
        [],
        runtime_detector=lambda: "120.0.2210.91",
        dialog=dialog,
        window_factory=window_factory,
        loop_runner=lambda: loop_calls.append(True),
    )

    assert code == shell.EXIT_OK
    assert dialog.calls == 0
    assert loop_calls == [True]
    assert len(window_factory.urls) == 1

    url = window_factory.urls[0]
    assert url.startswith("http://127.0.0.1:"), "DEC-02: loopback only"
    assert url.endswith("#/dashboard"), "DEC-01: the SPA is entered through a hash route"


# --- DEC-02: 루프백 · OS 할당 포트 · 부팅 시 생성 토큰 -------------------------------------------


def test_server_binds_loopback_on_an_os_assigned_port(shell_env):
    """
    DEC-02 / DECISION_LOG CORE #5: 포트는 OS 가 정한다.

    실제로 소켓을 열고 그 포트를 되읽는다. 상수를 문자열로 확인하는 검사는 `port=0` 을 쓰면서도
    엉뚱한 인터페이스에 바인딩하는 구현을 통과시킨다.
    """
    from src.backend.db import DatabaseManager

    db_mgr = DatabaseManager()
    try:
        app = shell.create_app(db_mgr)
        server, thread, port = shell.start_api_server(app)
        try:
            assert port is not None, "the socket never bound"
            assert port != 0
            # 8000 is the literal CORE #5 recorded in DECISION_LOG.md.
            assert port != 8000, "the OS-assigned port must not be the old hardcoded 8000"
            host = server.servers[0].sockets[0].getsockname()[0]
            assert host == "127.0.0.1", "DEC-02 forbids binding anything but loopback"
            assert shell.wait_for_health(port), "/api/v1/health must answer before the window loads"
        finally:
            server.should_exit = True
            thread.join(timeout=5)
    finally:
        db_mgr.close()


def test_session_token_is_generated_per_boot_and_never_hardcoded():
    """DEC-02: 토큰은 매 부팅 `secrets.token_urlsafe(32)`. 소스에 상주하는 문자열이 아니다."""
    from src.backend.db import DatabaseManager

    tokens = set()
    managers = []
    try:
        for _ in range(2):
            manager = DatabaseManager(db_path=":memory:", migrations_dir=str(REPO_ROOT / "migrations"))
            managers.append(manager)
            tokens.add(shell.create_app(manager).state.session_token)
    finally:
        for manager in managers:
            manager.close()

    assert len(tokens) == 2, "two boots must not share a session token"
    for token in tokens:
        assert len(token) >= 32

    source = _read(MAIN_PY)
    assert "corpbrain_dev_session_token" not in source, "the CORE #5 literal token must not return"
    # A port literal in a connection call is the other half of CORE #5.
    assert not re.search(r"port\s*=\s*(?!0\b)\d+", source), "no port may be hardcoded"


def test_bridge_script_carries_the_token_and_cannot_break_out_of_its_tag():
    """
    DEC-02 초기 HTML 주입. `</script>` 를 담은 값이 태그를 조기 종료시키지 못해야 한다.

    토큰 자체는 URL-safe base64 라 `</` 를 만들 수 없지만, 이스케이프는 **주입 함수의 성질**이어야
    한다 — 나중에 이 브리지에 다른 값이 실릴 때 안전성이 그 값의 알파벳에 의존하면 안 된다.
    """
    script = shell.build_bridge_script("/", "tok</script><script>alert(1)</script>")
    assert "</script><script>" not in script
    assert "<\\/" in script

    injected = shell.inject_bridge("<html><head></head><body></body></html>", script)
    assert injected.index("window.__CORPBRAIN__") < injected.index("</head>")


def test_index_response_carries_the_bridge_and_api_routes_still_require_the_token(shell_env):
    """
    SPA 는 API 와 같은 origin 에서 서빙된다 — 그래서 CORS 설정이 필요 없다.

    같은 검사 안에서 `/api/v1/*` 가 여전히 401 인지 확인한다. SPA 마운트가 인증 미들웨어를
    가려버리는 것이 이 구조에서 가장 그럴듯한 실패 방식이기 때문이다 (DEC-02: 토큰 검증을
    우회하는 라우트를 추가하지 않는다).
    """
    from fastapi.testclient import TestClient

    from src.backend.db import DatabaseManager

    db_mgr = DatabaseManager()
    try:
        app = shell.create_app(db_mgr)
        token = app.state.session_token
        assert shell.mount_spa(app, token) is True

        with TestClient(app) as client:
            index = client.get("/")
            assert index.status_code == 200
            assert f'"token": "{token}"' in index.text or f'"token":"{token}"' in index.text
            assert index.headers["cache-control"] == "no-store"

            assert client.get("/api/v1/workspace").status_code == 401
            authorized = client.get("/api/v1/workspace", headers={"Authorization": f"Bearer {token}"})
            assert authorized.status_code == 200
    finally:
        db_mgr.close()


def test_window_does_not_open_when_health_never_answers(shell_env, monkeypatch):
    """
    DEC-02 부팅 순서: 창은 `/api/v1/health` 가 응답한 **뒤에만** 열린다.

    `wait_for_health` 를 직접 호출해 True 를 확인하는 것만으로는 부족하다 — 그 단정은
    `main()` 이 반환값을 무시하고 그냥 창을 열어도 그대로 통과한다(뮤테이션 M4 가 정확히 그것을
    통과시켰다). 여기서는 프로브를 실패로 고정하고 **창이 만들어지지 않는지** 를 본다.
    """
    monkeypatch.setattr(shell, "wait_for_health", lambda port, timeout_sec=None: False)
    window_factory = _RecordingWindowFactory()

    code = shell.main(
        [],
        runtime_detector=lambda: "120.0.0.0",
        dialog=_RecordingDialog(),
        window_factory=window_factory,
        loop_runner=lambda: pytest.fail("the event loop must not start before health answers"),
    )

    assert code == shell.EXIT_SERVER_FAILED
    assert window_factory.urls == [], "a window opened against a server that never answered"


def test_missing_spa_bundle_fails_with_a_message_instead_of_an_empty_window(tmp_path, monkeypatch):
    """번들이 없으면 창을 열지 않는다 — 404 를 렌더한 창은 진단 불가능한 실패다."""
    # Same log redirection as the `shell_env` fixture — `main()` configures logging before it
    # checks for the bundle, so even this early-exit path would touch the real log directory.
    monkeypatch.setattr(shell, "configure_logging", lambda: None)
    monkeypatch.setattr(shell, "spa_dist_dir", lambda: tmp_path / "absent")
    window_factory = _RecordingWindowFactory()

    code = shell.main(
        [],
        runtime_detector=lambda: "120.0.0.0",
        dialog=_RecordingDialog(),
        window_factory=window_factory,
        loop_runner=lambda: pytest.fail("the event loop must not start without a bundle"),
    )

    assert code == shell.EXIT_BUNDLE_MISSING
    assert window_factory.urls == []


# --- 콘솔 없는 실행 (issue #159) ---------------------------------------------------------------


def test_boot_survives_a_windowed_process_with_no_standard_streams(shell_env, monkeypatch):
    """
    issue #159: the shipped exe is built ``console=False``, so a double-clicked process has
    ``sys.stdout is None`` and ``sys.stderr is None``.

    uvicorn's default log config calls ``sys.stdout.isatty()`` inside its formatter, which made
    ``uvicorn.Config(...)`` raise ``ValueError: Unable to configure formatter 'default'`` — before
    the first ``logger.info``, so the app died with an "Unhandled exception in script" dialog, no
    window, no bound socket and an empty log. Every earlier check missed it because the exe was
    launched with redirected handles, which is not how a user starts it.

    Nulling both streams for the whole boot is the point of the test: a version that only nulls
    stdout would keep passing against a formatter that happens to read stderr instead.
    """
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    window_factory = _RecordingWindowFactory()
    code = shell.main(
        [],
        runtime_detector=lambda: "151.0.0.0",
        dialog=lambda: pytest.fail("the runtime is present; no guidance dialog is expected"),
        window_factory=window_factory,
        loop_runner=lambda: None,
    )

    assert code == shell.EXIT_OK
    assert len(window_factory.urls) == 1, "the window must still open without standard streams"


def test_uvicorn_is_not_allowed_to_rebuild_logging_around_stdout(shell_env, monkeypatch):
    """
    Pins the mechanism, not just the symptom: `uvicorn.Config` must be constructed with
    `log_config=None`.

    Without this, a future edit could restore the default config and the test above would still
    pass on a host where `sys.stdout` is merely monkeypatched to None but uvicorn's formatter is
    never actually exercised. Reading the kwarg off the real call keeps the two honest.
    """
    seen = {}
    real_config = uvicorn.Config

    def _spy(*args, **kwargs):
        seen.update(kwargs)
        return real_config(*args, **kwargs)

    monkeypatch.setattr(uvicorn, "Config", _spy)

    shell.main(
        [],
        runtime_detector=lambda: "151.0.0.0",
        dialog=lambda: None,
        window_factory=_RecordingWindowFactory(),
        loop_runner=lambda: None,
    )

    assert "log_config" in seen, "uvicorn.Config was called without log_config (issue #159)"
    assert seen["log_config"] is None, (
        f"log_config must be None so uvicorn does not touch sys.stdout; got {seen['log_config']!r}"
    )


# --- 창 생성 인자 (issue #151) -----------------------------------------------------------------


def _captured_create_window_kwargs(monkeypatch):
    """
    Call the real ``create_shell_window`` with a stand-in ``webview`` module and return the
    kwargs it passed.

    The function imports ``webview`` inside its body, so injecting a fake into ``sys.modules``
    intercepts the real call without a GUI toolkit being present. Asserting on the captured
    kwargs — rather than grepping main.py for a string — is what makes these tests fail if the
    argument is dropped: a source scan would still pass on a file that merely *mentions*
    ``background_color`` in a comment.
    """
    captured = {}

    class _FakeWebview:
        @staticmethod
        def create_window(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return object()

    monkeypatch.setitem(sys.modules, "webview", _FakeWebview)
    shell.create_shell_window("http://127.0.0.1:1234/#/dashboard")
    return captured


def test_the_window_is_created_with_an_explicit_dark_background(monkeypatch):
    """
    issue #151: pywebview defaults ``background_color`` to white, so a shell that omits it
    flashes white before the dark SPA paints.

    The assertion is on the value actually handed to ``create_window``, so removing the argument
    from the call fails here even though the constant would still exist in the module.
    """
    captured = _captured_create_window_kwargs(monkeypatch)

    assert "background_color" in captured["kwargs"], (
        "create_window was called without background_color — pywebview then defaults to #FFFFFF"
    )
    background = captured["kwargs"]["background_color"]
    assert background == shell.WINDOW_BACKGROUND_COLOR
    assert background.lower() != "#ffffff", "white is the default this issue exists to replace"


def test_the_window_background_matches_the_spa_first_paint_colour():
    """
    The shell's background must equal what `index.html` paints, or the flash becomes a colour
    shift instead of a white one.

    `<body class="bg-dark-bg">` is the first paint — not the React root's `bg-slate-950`, which
    only appears once the bundle has mounted. `bg-dark-bg` resolves through tailwind.config.js's
    `dark.bg`, so that file is the source of truth this pins against.
    """
    tailwind_config = _read(REPO_ROOT / "tailwind.config.js")
    dark_section = tailwind_config[tailwind_config.index("dark: {"):]
    match = re.search(r"bg:\s*'(#[0-9a-fA-F]{6})'", dark_section)
    assert match, "tailwind.config.js no longer defines dark.bg"

    assert shell.WINDOW_BACKGROUND_COLOR.lower() == match.group(1).lower(), (
        "shell window background drifted from index.html's body colour (tailwind dark.bg)"
    )

    # The body really is the element carrying that colour — if index.html stops using the class,
    # the assertion above would be pinning an unused token.
    assert 'class="bg-dark-bg' in _read(REPO_ROOT / "index.html")


def test_the_frameless_drag_contract_is_still_passed(monkeypatch):
    """
    Guards the arguments #151's change sits next to: adding a kwarg is an easy place to disturb
    the drag contract, and `easy_drag` defaulting back to True would make the whole window
    draggable (dragging a file row would move the window).
    """
    kwargs = _captured_create_window_kwargs(monkeypatch)["kwargs"]

    assert kwargs["frameless"] is True
    assert kwargs["easy_drag"] is False
    assert kwargs["text_select"] is True


# --- 네이티브 폴더 선택 js_api (issue #167) ---------------------------------------------------


def test_the_window_exposes_the_shell_js_api_bridge(monkeypatch):
    """
    A browser cannot open an OS folder dialog, so the shell must hand the SPA a `js_api` bridge
    with `select_folder`. Asserted on the object actually passed to `create_window`, so dropping
    the kwarg fails here.
    """
    kwargs = _captured_create_window_kwargs(monkeypatch)["kwargs"]

    assert "js_api" in kwargs, "create_window was called without js_api — the SPA gets no bridge"
    api = kwargs["js_api"]
    assert isinstance(api, shell.ShellApi)
    assert callable(getattr(api, "select_folder", None))


def test_select_folder_returns_the_chosen_path():
    """A folder dialog returns a sequence; select_folder hands the first entry back to the SPA."""
    api = shell.ShellApi(folder_dialog=lambda: [r"C:\Users\docto\문서\2026기술수요조사"])
    assert api.select_folder() == r"C:\Users\docto\문서\2026기술수요조사"


def test_select_folder_returns_none_when_cancelled_or_empty():
    """
    Cancel (None) and an empty selection both collapse to None, so the SPA checks one thing.

    Two cases in one test on purpose: an implementation that returned `result[0]` unconditionally
    would raise IndexError on `()` — this pins that the guard is real, not incidental.
    """
    assert shell.ShellApi(folder_dialog=lambda: None).select_folder() is None
    assert shell.ShellApi(folder_dialog=lambda: []).select_folder() is None


def test_select_folder_uses_the_active_window_and_the_folder_dialog_type(monkeypatch):
    """
    The default dialog opener targets the active pywebview window with the FOLDER dialog type.

    Exercised with a fake `webview` module so no GUI is created: proves the opener reads
    `webview.windows[0]` and calls `create_file_dialog(FileDialog.FOLDER)`, and returns None when
    no window exists yet.
    """
    calls = {}

    class _FakeWindow:
        def create_file_dialog(self, dialog_type):
            calls["dialog_type"] = dialog_type
            return (r"C:\picked",)

    class _FakeWebview:
        FileDialog = type("FileDialog", (), {"FOLDER": 20})
        windows = [_FakeWindow()]

    monkeypatch.setitem(sys.modules, "webview", _FakeWebview)
    assert shell._open_native_folder_dialog() == (r"C:\picked",)
    assert calls["dialog_type"] == 20

    # No window yet -> the dialog cannot be shown, and the opener says so rather than raising.
    _FakeWebview.windows = []
    assert shell._open_native_folder_dialog() is None


# --- 런타임 탐지 자체 --------------------------------------------------------------------------


def test_runtime_detection_is_not_applicable_off_windows():
    """
    macOS/Linux 에서는 레지스트리가 없으므로 탐지가 `None` 을 반환해서는 안 된다.

    `None` 은 "Windows 인데 런타임이 없다" 를 뜻하고, 그 값이 개발 호스트에서 나오면 개발자는
    존재하지도 않는 WebView2 를 설치하라는 안내를 받는다.
    """
    if sys.platform == "win32":
        pytest.skip("Windows host: detection reads the real registry")
    assert shell.detect_webview2_runtime() == shell.RUNTIME_NOT_APPLICABLE


def test_registry_probe_covers_both_hives_and_the_wow6432_view():
    """
    per-machine(64-bit) · per-machine · per-user 세 위치를 모두 본다.

    한 곳만 보는 구현은 멀쩡히 설치된 런타임을 "없음" 으로 보고하고, 그 결과 사용자는 필요 없는
    다운로드 페이지로 안내된다. macOS 에서 레지스트리를 읽을 수 없으므로 소스로 고정한다.
    """
    source = _read(MAIN_PY)
    assert "HKEY_LOCAL_MACHINE" in source
    assert "HKEY_CURRENT_USER" in source
    assert "WOW6432Node" in source
    assert shell.WEBVIEW2_CLIENT_GUID == "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


# --- PyInstaller spec -------------------------------------------------------------------------


def test_spec_file_exists_and_is_onefile():
    """
    DEC-01: `--onefile` → `CorpBrain.exe` 1개.

    `COLLECT(` 의 부재가 핵심 단정이다 — spec 에 COLLECT 를 추가하는 순간 onedir 빌드가 되고,
    산출물은 exe 하나가 아니라 디렉터리 한 벌이 된다.
    """
    assert SPEC_FILE.is_file(), "the repo must carry a PyInstaller spec (DECISION_LOG CORE #4)"
    spec = _code(SPEC_FILE)
    assert "COLLECT(" not in spec, "COLLECT turns this into a onedir build, breaking DEC-01"
    assert 'name="CorpBrain"' in spec
    assert "console=False" in spec


def test_spec_bundles_the_spa_and_the_migrations():
    """
    번들에 SPA 와 migrations 가 들어간다.

    migrations 누락은 조용한 실패다 — 첫 실행에서 `user_version 0` 인 빈 DB 가 만들어지고 모든
    쿼리가 "no such table" 로 죽는다. 개발 체크아웃에서는 리포에 파일이 있어서 드러나지 않는다.

    `datas` 항목 자체를 단정한다. "migrations 라는 낱말이 파일 어딘가에 있다" 는 검사는 설명 주석과
    변수 이름만으로도 통과하므로 수집 목록에서 항목을 빼도 살아남는다.
    """
    spec = _code(SPEC_FILE)
    assert '(str(SPA_DIST / "index.html"), "dist")' in spec
    assert '(str(SPA_DIST / "assets"), "dist/assets")' in spec
    assert '(str(MIGRATIONS), "migrations")' in spec
    # Collecting `dist` wholesale would fold the previous build's own exe into the next one.
    assert '(str(SPA_DIST), "dist")' not in spec


def test_built_archive_carries_the_spa_and_every_migration():
    """
    빌드 산출물이 있으면 spec 문자열이 아니라 **실제 아카이브 내용**으로 확인한다.

    spec 이 무엇을 적었는지와 exe 안에 무엇이 들어갔는지는 다른 사실이다. `dist/` 는 gitignore
    대상이라 신선한 체크아웃과 CI(파이썬 잡은 PyInstaller 를 돌리지 않는다)에서는 건너뛴다 —
    `test_index_html_references_no_external_origin` 이 같은 이유로 쓰는 방식이다.
    """
    from PyInstaller.archive.readers import CArchiveReader

    candidates = [REPO_ROOT / "dist" / "CorpBrain", REPO_ROOT / "dist" / "CorpBrain.exe"]
    built = next((path for path in candidates if path.is_file()), None)
    if built is None:
        pytest.skip("no packaged artifact in dist/ — run `python -m PyInstaller CorpBrain.spec`")

    # Normalise separators: PyInstaller's CArchive emits TOC member names with the host's path
    # separator, so on Windows (the shipping platform, where this test finally runs against a real
    # exe) the entries read "dist\index.html", not "dist/index.html". The assertions below are all
    # written with forward slashes, so collapse "\" to "/" once here rather than per assertion.
    entries = {name.replace("\\", "/") for name in CArchiveReader(str(built)).toc}

    assert "dist/index.html" in entries, "the SPA entry point is not inside the exe"
    assert any(name.startswith("dist/assets/") for name in entries), "SPA assets missing"

    on_disk = {path.name for path in (REPO_ROOT / "migrations").glob("v*.sql")}
    bundled = {name.split("/", 1)[1] for name in entries if name.startswith("migrations/")}
    assert on_disk == bundled, f"migrations missing from the bundle: {sorted(on_disk - bundled)}"

    # A rebuild must not swallow the previous build's own executable (see the spec's comment on
    # why `dist` is collected file by file rather than as a tree).
    assert not [n for n in entries if n.rsplit("/", 1)[-1] in ("CorpBrain", "CorpBrain.exe")]


def test_spec_excludes_the_dev_launcher():
    """
    `scripts/dev_serve.py` 는 번들에 들어가지 않는다.

    그 파일의 인덱스 라우트는 인증 없이 세션 토큰을 넘겨준다. 개발 호스트에서는 감수하는 성질이고
    출하 산출물에서는 아니다.

    `_code` 로 읽는 이유: 바로 위 주석이 같은 문자열을 담고 있어서, 원문을 훑으면 `excludes` 에서
    항목을 지워도 통과한다.
    """
    spec = _code(SPEC_FILE)
    excludes = spec[spec.index("excludes=[") : spec.index("]", spec.index("excludes=["))]
    assert '"scripts.dev_serve"' in excludes


# --- 해시 라우팅 -------------------------------------------------------------------------------


def test_hash_router_default_and_entry_route_agree():
    """
    셸이 여는 진입 해시와 라우터의 기본 라우트가 같은 탭을 가리킨다.

    두 상수가 어긋나면 창이 뜨자마자 한 번 리다이렉트되거나, 진입 라우트가 무시된다. 파이썬과
    TypeScript 양쪽에 하나씩 있는 값이라 어긋나도 어느 컴파일러도 잡지 못한다.
    """
    router = _read(ROUTER_TS)
    assert shell.INITIAL_ROUTE == "#/dashboard"
    assert "DEFAULT_TAB: ActiveTab = 'dashboard'" in router


def test_hash_router_is_dependency_free_and_handles_the_workspace_route():
    """
    `react-router-dom` 없이 구현되고, 이슈 #14 가 명시한 `#/workspace/:id` 를 파싱한다.

    package.json 까지 함께 보는 이유: 라우터 소스가 import 하지 않아도 의존성이 추가되어 있으면
    CLAUDE.md §4 의 승인 목록 위반이 남는다.
    """
    assert "react-router" not in _code(ROUTER_TS)
    assert "react-router" not in _read(REPO_ROOT / "package.json")

    router = _read(ROUTER_TS)
    assert "hashchange" in router, "the route must be driven by hashchange, not by store state"

    # Issue #14 lists `#/workspace/:id` beside `#/dashboard`, so the parser must handle both and
    # report the id — a router that only knows the six tab routes drops the id silently.
    assert "'workspace'" in router
    assert "workspaceId" in router
    # Structural, not behavioural: executing this TypeScript would need a JS test runner, and
    # docs/review/WINDOWS_SMOKE_CHECKLIST.md records that Vitest/jsdom was ruled out for this
    # project. The behaviour itself is a Windows smoke item (§3.0), not something proven here.


def test_sidebar_navigates_by_writing_the_hash():
    """
    사이드바가 스토어가 아니라 해시를 쓴다.

    `setActiveTab` 을 직접 부르면 화면은 바뀌지만 주소는 그대로여서, 해시는 장식이 되고 셸이 정한
    진입 라우트도 의미를 잃는다.
    """
    sidebar = _read(REPO_ROOT / "src" / "frontend" / "components" / "Sidebar.tsx")
    assert "navigateToTab(item.id)" in sidebar
    assert "setActiveTab(item.id)" not in sidebar


def test_app_subscribes_to_the_route_on_mount():
    """`hashchange` 는 최초 로드에서 발화하지 않으므로 구독 시점에 현재 해시를 한 번 적용해야 한다."""
    app_tsx = _read(REPO_ROOT / "src" / "frontend" / "App.tsx")
    assert "subscribeToRoute" in app_tsx
    router = _read(ROUTER_TS)
    subscribe = router[router.index("export function subscribeToRoute") :]
    assert "handler();" in subscribe, "the current hash must be applied without waiting for a change"


# --- 린트 예외의 범위 --------------------------------------------------------------------------


def test_http_client_import_is_confined_to_the_shell_entrypoint():
    """
    DEC-15 의 금지 목록에 `http.client` 를 추가했고, 예외는 `src/main.py` 하나다.

    ruff 설정만으로는 부족하다 — 예외 줄이 디렉터리 단위로 넓어지는 변경은 린트를 계속 통과한다.
    여기서 소스를 직접 훑어 예외의 범위를 고정한다.
    """
    ruff_toml = _read(REPO_ROOT / "ruff.toml")
    assert '"http.client".msg' in ruff_toml, "the ban must exist, or the exemption guards nothing"
    assert '"src/main.py" = ["TID251"]' in ruff_toml

    offenders = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        if path == MAIN_PY:
            continue
        if re.search(r"^\s*(import\s+http\.client|from\s+http\s+import\s+client)", _read(path), re.M):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"http.client imported outside the shell entrypoint: {offenders}"
