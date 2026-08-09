"""
Frontend IPC wiring contract tests (issue #91).

There is no test runner on the frontend side — no Vitest, no jsdom — and adding one was
explicitly ruled out of scope. So these assertions are static: they read the TypeScript sources
as text and compare them against the live OpenAPI schema. What that can and cannot prove:

  - PROVEN: the generated types match the schema; every /api/v1 route is typed; the client
    reads its token from the injected bridge rather than a literal or localStorage; no page
    still renders mock data; every API_PATHS key the client references exists.
  - NOT PROVEN: that a rendered page actually round-trips to the backend. Issue #91's
    "최소 1개 페이지 왕복 테스트" acceptance item stays unmet and is filed as a follow-up.

The live round trip is verified by hand through scripts/dev_serve.py, per rule 5 in
docs/loop/DECISION_LOG.md, and that output goes in the PR body.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend.api.app import create_app
from src.backend.db import DatabaseManager
from tests.task_polling import poll_until_done

SESSION_TOKEN = "test_ws_fe_01_token"
AUTH = {"Authorization": f"Bearer {SESSION_TOKEN}"}

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "src" / "frontend"
API_DIR = FRONTEND_DIR / "api"
PAGES_DIR = FRONTEND_DIR / "pages"
GENERATED_TYPES = API_DIR / "types.gen.ts"
CLIENT_TS = API_DIR / "client.ts"
STORE_TS = FRONTEND_DIR / "store" / "appStore.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(path: Path) -> str:
    """
    A source file with its comments stripped.

    The forbidden-API checks below must run against code, not prose. Every one of these files
    documents the rule it obeys — client.ts says the token is "never written to localStorage",
    and DEC-04's "no WebSocket or SSE" is quoted verbatim — so a raw substring scan flags the
    documentation as the violation. Stripping comments first is what makes the assertion mean
    "this file does not do X" instead of "this file does not mention X".

    Naive but sufficient: a `//` or `/* */` inside a string literal would be over-stripped, and
    these files have none. It only ever removes text, so it cannot create a false pass for code.
    """
    content = _read(path)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return re.sub(r"(?<![:'\"])//.*$", "", content, flags=re.MULTILINE)


@pytest.fixture
def api_client():
    """
    A real app against a throwaway DB — the schema under test is the shipped one.

    Teardown order matters on Windows: drain the task workers (each holds its own thread-local
    sqlite3 connection, and an open WAL reader blocks deleting the temp dir), then close the
    manager, then let the TemporaryDirectory go. Same reasoning as tests/test_api_002_003.py.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(
            db_path=os.path.join(tmpdir, "ws_fe_01.db"),
            migrations_dir=str(REPO_ROOT / "migrations"),
        )
        app = create_app(db_mgr, session_token=SESSION_TOKEN)
        try:
            # Context-manager form so the lifespan shutdown closes any Chroma client.
            with TestClient(app) as client:
                yield client, app, tmpdir
        finally:
            for task_id in app.state.task_runner.active_task_ids():
                app.state.task_runner.wait(task_id, timeout=15)
            db_mgr.close()


@pytest.fixture
def api_schema(api_client):
    _client, app, _tmpdir = api_client
    return app.openapi()


# --- (a) the generated types match the live schema ---------------------------------------


def test_generated_types_match_openapi_schema():
    """
    `--check` regenerates from the live schema and diffs against the committed file.

    This is the enforcement the user's decision rests on: with no frontend test runner, a DTO
    change that is not regenerated has to fail *somewhere*, and this is that somewhere.
    """
    result = subprocess.run(
        # -X utf8 so the child's Korean output is UTF-8 rather than the console's cp949; without
        # it the decode below raises inside subprocess's reader thread and the real failure
        # message is replaced by a UnicodeDecodeError. errors="replace" keeps a mojibake byte
        # from turning a genuine mismatch report into a crash.
        [sys.executable, "-X", "utf8", str(REPO_ROOT / "scripts" / "gen_api_types.py"), "--check"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, (
        "src/frontend/api/types.gen.ts is stale relative to the OpenAPI schema. "
        "Run: python scripts/gen_api_types.py\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_generated_types_are_marked_do_not_edit():
    content = _read(GENERATED_TYPES)
    assert "GENERATED FILE — DO NOT EDIT" in content
    assert "export const API_PATHS" in content


def test_api_paths_keys_are_unique():
    """A duplicate key is TS1117; the generator raises on collision, this pins the outcome."""
    keys = re.findall(r"^  (\w+): \"", _read(GENERATED_TYPES), flags=re.MULTILINE)
    assert keys, "API_PATHS appears to be empty"
    assert len(keys) == len(set(keys)), f"duplicate API_PATHS keys: {sorted(keys)}"


def test_client_only_references_existing_api_paths():
    """A typo'd API_PATHS member would be a build error; this catches it without tsc."""
    declared = set(re.findall(r"^  (\w+): \"", _read(GENERATED_TYPES), flags=re.MULTILINE))
    referenced = set(re.findall(r"API_PATHS\.(\w+)", _read(CLIENT_TS)))
    assert referenced, "client.ts does not reference API_PATHS at all"
    assert referenced <= declared, f"unknown API_PATHS members: {sorted(referenced - declared)}"


# --- (b) every /api/v1 route is typed ----------------------------------------------------


def test_every_api_route_declares_a_response_model(api_schema):
    """
    An untyped route contributes an empty `{}` response schema, leaving the generator nothing
    to emit — the state the whole OpenAPI-as-SSOT approach was blocked on before this work.
    """
    untyped: list[str] = []
    for path, operations in api_schema["paths"].items():
        if not path.startswith("/api/v1"):
            continue
        for method, operation in operations.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            responses = operation.get("responses", {})
            # 202 is a success status here, not an anomaly: DEC-04 makes every long-running task
            # return 202 + task_id. Its schema is what the poller's types are generated from, so
            # it has to count as typed — checking only 200/201 would report those four routes as
            # missing a response_model when they declare one.
            success = next((responses[code] for code in ("200", "201", "202") if code in responses), None)
            if not success:
                untyped.append(f"{method.upper()} {path} (no 2xx response)")
                continue
            content = success.get("content", {}).get("application/json", {})
            if not content.get("schema"):
                untyped.append(f"{method.upper()} {path} (empty response schema)")
    assert not untyped, "routes without a response_model: " + ", ".join(untyped)


def test_every_api_route_is_reachable_from_api_paths(api_schema):
    """
    Every route is in the emitted table, so the frontend cannot be silently missing one.
    """
    declared_paths = set(re.findall(r": \"(/api/v1[^\"]*)\"", _read(GENERATED_TYPES)))
    schema_paths = {p for p in api_schema["paths"] if p.startswith("/api/v1")}
    assert schema_paths == declared_paths, (
        f"missing from API_PATHS: {sorted(schema_paths - declared_paths)}; "
        f"stale in API_PATHS: {sorted(declared_paths - schema_paths)}"
    )


def test_error_codes_used_by_the_client_are_dec_03_codes():
    """
    DEC-03 fixes the error-code vocabulary; adding one requires updating that table. The client
    synthesises codes for failures it detects locally, so those must come from the same set.
    """
    allowed = {
        "VALIDATION_FAILED", "UNAUTHORIZED", "NOT_FOUND", "PATH_NOT_ACCESSIBLE",
        "SCAN_LIMIT_REACHED", "LLM_UNAVAILABLE", "LLM_PROVISION_REQUIRED",
        "PII_MASKING_FAILED", "ALREADY_UNDONE", "INTERNAL_ERROR",
    }
    client_code = _code(CLIENT_TS)
    used = set(re.findall(r"code: '([A-Z_]+)'", client_code))
    used |= set(re.findall(r"code: \"([A-Z_]+)\"", client_code))
    assert used, "no error codes found in client.ts"
    assert used <= allowed, f"codes outside the DEC-03 table: {sorted(used - allowed)}"


# --- (c) the client handles the session token correctly (DEC-02 / DEC-12) ----------------


def test_client_reads_token_from_the_injected_bridge():
    content = _read(CLIENT_TS)
    assert "window.__CORPBRAIN__" in content, "the client must read the pywebview-injected bridge"
    assert "Bearer ${token}" in content


def test_client_never_persists_the_token():
    """
    DEC-02: the token is never written to disk. In a browser context that means no Web Storage
    and no cookie — a persisted token outlives the process whose lifetime is supposed to bound
    it, and it is readable by anything else running on the same origin.
    """
    forbidden = ["localStorage", "sessionStorage", "document.cookie", "indexedDB"]
    for source in (CLIENT_TS, STORE_TS, *sorted(PAGES_DIR.glob("*.tsx"))):
        content = _code(source)
        for needle in forbidden:
            assert needle not in content, f"{source.name} uses {needle}"


def test_client_has_no_hardcoded_token_or_port():
    """
    DEC-02 requires an OS-assigned random port and a per-boot token. A literal of either in the
    client is the CORE #5 defect that run_app.py was registered for, moved to the frontend.
    """
    content = _code(CLIENT_TS)
    assert "corpbrain_dev_session_token" not in content
    assert not re.search(r"127\.0\.0\.1:\d+", content), "hardcoded host:port in client.ts"
    assert not re.search(r"localhost:\d+", content), "hardcoded localhost:port in client.ts"
    # A `token = '...'` or `token: "..."` literal assignment, as opposed to reading the bridge.
    assert not re.search(r"token\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", content)


def test_api_key_is_not_retained_in_the_store_or_pages():
    """
    DEC-12: the key is decrypted only in memory immediately before a call and never echoed. The
    UI may collect it in a form field, but it must not reach the global store, where it would
    persist for the session and be readable by every component.
    """
    assert "api_key" not in _code(STORE_TS), "appStore must not hold an api_key"
    # The one place a key may appear is SettingsPage's own input state, cleared after the call.
    settings = _read(PAGES_DIR / "SettingsPage.tsx")
    assert "setApiKeyInput('')" in settings, "SettingsPage must clear the API key after saving"
    assert 'type="password"' in settings, "the API key field must not be rendered in clear text"


# --- (d) no mock data remains ------------------------------------------------------------


def test_no_mock_data_literals_remain_in_the_frontend():
    """
    The seeded workspace and file rows are gone. They are the reason #91 went unnoticed: a
    hardcoded row is indistinguishable from a real one on screen, so the UI looked wired.
    """
    fingerprints = [
        "ws-demo-001",
        "2026_전략기획_워크스페이스",
        "f1-uuid-111",
        "f2-uuid-222",
        "f3-uuid-333",
        "mockDiffList",
        "C:\\\\CorpBrain\\\\Workspace",
        "홍길동_주민등록증",
    ]
    sources = [STORE_TS, CLIENT_TS, FRONTEND_DIR / "App.tsx", *sorted(PAGES_DIR.glob("*.tsx"))]
    sources += sorted((FRONTEND_DIR / "components").glob("*.tsx"))
    offenders: list[str] = []
    for source in sources:
        content = _code(source)
        for needle in fingerprints:
            if needle in content:
                offenders.append(f"{source.name}: {needle}")
    assert not offenders, "mock data still present: " + ", ".join(offenders)


def test_store_initial_state_is_empty():
    """
    `workspaces: []` / `files: []`, not seeded rows. An empty list renders an empty state; a
    seeded one renders a lie.
    """
    content = _read(STORE_TS)
    assert re.search(r"^  workspaces: \[\],$", content, flags=re.MULTILINE)
    assert re.search(r"^  files: \[\],$", content, flags=re.MULTILINE)
    assert re.search(r"^  currentWorkspace: null,$", content, flags=re.MULTILINE)


def test_store_uses_generated_types_not_handwritten_shapes():
    """
    DEC-02: the OpenAPI schema is the SSOT. A locally-declared WorkspaceItem/FileItem shape is
    the parallel type definition that drifts from it.
    """
    content = _read(STORE_TS)
    assert "from '../api/types.gen'" in content
    assert not re.search(r"export interface (WorkspaceItem|FileItem)\b", content), (
        "appStore re-declares a wire shape instead of aliasing the generated one"
    )


def test_pages_call_the_client():
    """Every page that shows backend data must import the client, not fabricate the data."""
    for page in ("DashboardPage", "FilesPage", "RenamePage", "SettingsPage", "WikiPage"):
        content = _read(PAGES_DIR / f"{page}.tsx")
        assert "from '../api/client'" in content, f"{page} does not import the API client"


# --- DEC-04 / DEC-08 / DEC-15 wiring rules -----------------------------------------------


def test_polling_is_used_and_no_push_channel_exists():
    """DEC-04: 1s polling, and no WebSocket/SSE anywhere in the frontend."""
    client = _read(CLIENT_TS)
    assert "pollTask" in client
    assert "1000" in client, "the poll interval must be 1s (DEC-04)"

    for source in [CLIENT_TS, STORE_TS, *sorted(PAGES_DIR.glob("*.tsx"))]:
        content = _code(source)
        for needle in ("WebSocket", "EventSource", "socket.io"):
            assert needle not in content, f"{source.name} uses {needle} — DEC-04 forbids a push channel"


def test_deeplink_open_sends_only_file_id():
    """
    DEC-08: `os.startfile` targets are resolved server-side from `file_id`. A page that sent a
    path would be handing the server a caller-supplied target.
    """
    open_fn = re.search(r"export function openDeepLink\(.*?\n\}", _code(CLIENT_TS), flags=re.S)
    assert open_fn, "openDeepLink not found"
    assert "current_path" not in open_fn.group(0)

    for page in ("DashboardPage", "FilesPage", "WikiPage"):
        content = _code(PAGES_DIR / f"{page}.tsx")
        for call in re.findall(r"openDeepLink\([^)]*\)", content):
            assert "path" not in call, f"{page} passes a path to openDeepLink: {call}"


def test_frontend_has_no_absolute_url_in_code():
    """
    REQ-NF-005 / DEC-15: the SPA's only destination is the loopback API, reached through the
    injected relative base URL. An absolute URL in the frontend is either a hardcoded port
    (DEC-02) or an egress path that never passes NetworkGuard — neither is allowed.

    Comments are stripped first: they cite api.anthropic.com and 127.0.0.1:11434 to document
    what the *backend* does, and that documentation is not a request.
    """
    sources = [CLIENT_TS, STORE_TS, FRONTEND_DIR / "App.tsx", *sorted(PAGES_DIR.glob("*.tsx"))]
    sources += sorted((FRONTEND_DIR / "components").glob("*.tsx"))
    for source in sources:
        urls = re.findall(r"https?://[^\s\"'`)]+", _code(source))
        assert not urls, f"{source.name} contains an absolute URL in code: {urls}"


def test_index_html_references_no_external_origin():
    """
    DEC-15 / REQ-NF-005: the shipped `index.html` must not reference a remote origin.

    Checked separately from the .tsx sources because this file is what PyInstaller embeds — a
    `<link>` here is fetched on every launch by the shipped app, with no NetworkGuard in the
    path. Three Google Fonts tags were removed in this change; a DNS lookup for a font is still
    an outbound callout, and on a closed network it is a startup stall for nothing.
    """
    sources = [REPO_ROOT / "index.html", REPO_ROOT / "src" / "frontend" / "index.css"]
    # dist/ is the artifact PyInstaller embeds, and it is gitignored, so it may be absent on a
    # fresh checkout. Check it when it exists: the source being clean does not prove the build
    # is, and the build is what ships.
    built = REPO_ROOT / "dist" / "index.html"
    if built.is_file():
        sources.append(built)
    for source in sources:
        markup = _read(source)
        markup = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
        markup = re.sub(r"/\*.*?\*/", "", markup, flags=re.S)
        urls = re.findall(r"https?://[^\s\"'>]+", markup)
        assert not urls, f"{source} references an external origin: {urls}"


def test_client_unwraps_the_envelope_and_treats_207_as_partial():
    """DEC-03: 207 + ok:true is a partial success, not a failure and not a plain success."""
    content = _code(CLIENT_TS)
    assert "envelope.ok === false" in content
    assert "207" in content, "the client must recognise HTTP 207 (DEC-03 partial failure)"


def test_no_camel_case_conversion_layer():
    """
    DEC-03: snake_case at every layer. A conversion helper is the alias drift the rule exists to
    prevent — and it fails silently, by dropping a field rather than erroring.
    """
    for source in [CLIENT_TS, STORE_TS, *sorted(PAGES_DIR.glob("*.tsx"))]:
        content = _code(source)
        for needle in ("camelCase(", "toCamel", "snakeToCamel", "decamelize", "camelize"):
            assert needle not in content, f"{source.name} contains a case-conversion helper ({needle})"


# --- the new file-list endpoint ----------------------------------------------------------


def test_file_list_endpoint_omits_original_path(api_schema):
    """
    DEC-08 makes `original_path` immutable audit data and requires every open/existence check to
    use `current_path`. Not shipping it removes the chance of a component picking the stale one.
    """
    file_item = api_schema["components"]["schemas"]["FileItemRes"]
    assert "current_path" in file_item["properties"]
    assert "original_path" not in file_item["properties"]


def test_file_list_endpoint_round_trips(api_client):
    """
    The endpoint the Dashboard and Files pages read, over real HTTP.

    Rule 5 in docs/loop/DECISION_LOG.md wants a live call for any task that touches an endpoint.
    `GET .../file` is new in this change and is what `listFiles`/`refreshFiles` bind to, so it
    gets an actual round trip rather than a schema assertion.
    """
    client, _app, tmpdir = api_client
    Path(tmpdir, "사업기획서_최종.docx").write_text("content", encoding="utf-8")

    created = client.post(
        "/api/v1/workspace",
        json={"workspace_name": "FE WS", "root_paths": [tmpdir]},
        headers=AUTH,
    )
    assert created.status_code == 201
    ws_id = created.json()["data"]["workspace_id"]

    # Empty before a scan — an empty list, not an error. The store renders this as an empty
    # state, which is the behaviour that replaced the mock rows.
    empty = client.get(f"/api/v1/workspace/{ws_id}/file", headers=AUTH)
    assert empty.status_code == 200
    assert empty.json() == {
        "ok": True,
        "data": {"workspace_id": ws_id, "items": [], "total": 0},
        "error": None,
    }

    scan = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=AUTH)
    assert scan.status_code == 202
    assert poll_until_done(client, AUTH, scan.json()["data"]["task_id"])["status"] == "completed"

    listed = client.get(f"/api/v1/workspace/{ws_id}/file", headers=AUTH)
    assert listed.status_code == 200
    body = listed.json()
    assert body["ok"] is True
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert item["file_name"] == "사업기획서_최종.docx"
    assert "original_path" not in item
    # snake_case on the wire, no camelCase twin (DEC-03).
    assert "fileName" not in item


def test_file_list_rejects_a_missing_token(api_client):
    """DEC-02: no /api/v1 route bypasses the Bearer middleware, including a new one."""
    client, _app, _tmpdir = api_client
    res = client.get("/api/v1/workspace/does-not-matter/file")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_rename_diff_returns_history_id(api_client):
    """
    The frontend applies a diff by handing back `history_id` — DEC-08 keeps absolute paths off
    the client, so it cannot assemble the path pairs `apply_rename` takes. Before this change
    the DTO exposed neither, so RenamePage had no way to apply what it displayed.
    """
    client, _app, tmpdir = api_client
    Path(tmpdir, "기획안.txt").write_text("content", encoding="utf-8")
    created = client.post(
        "/api/v1/workspace",
        json={"workspace_name": "Rename FE WS", "root_paths": [tmpdir]},
        headers=AUTH,
    )
    ws_id = created.json()["data"]["workspace_id"]

    scan = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=AUTH)
    poll_until_done(client, AUTH, scan.json()["data"]["task_id"])

    diff = client.post(f"/api/v1/workspace/{ws_id}/rename/diff", headers=AUTH)
    assert diff.status_code == 200
    data = diff.json()["data"]
    assert data["history_id"], "rename diff must return the Rename_History id"
    assert len(data["items"]) == 1
    # `LLM_FAILED`, not `pending`: no LLM is reachable in a test process, and since issue #37
    # replaced the hardcoded `2026-08_` stub with a real call, a suggestion can no longer be
    # produced without one. That is the DEC-16 partial-failure contract — the file keeps its
    # original name and the batch continues — and asserting `pending` here would only be
    # asserting that a stub still exists. The status vocabulary itself is covered by
    # tests/test_issue_37.py; what this test owns is that the route returns the envelope with a
    # history_id and one item per file.
    item = data["items"][0]
    assert item["status"] in ("pending", "LLM_FAILED"), item
    assert item["old_name"] == "기획안.txt"
    if item["status"] == "LLM_FAILED":
        assert item["new_name"] == item["old_name"], "a failed suggestion must keep the original name"


# --- CORE #6: every error path reaches the client as the DEC-03 envelope -----------------
#
# `client.ts` unwraps `{ok, data, error}` exactly once and reads `error.code`. A raw FastAPI
# `{"detail": ...}` has no `ok` and no `error`, so the client would surface "알 수 없는 오류"
# for every validation failure — and #90's observation was that a 500 came back as the plain
# text "Internal Server Error", which is not even JSON. The handlers landed in 37d97ab; these
# tests are what keeps the client's error path from silently regressing.


def test_validation_failure_uses_the_envelope_and_names_the_field(api_client):
    """422 → VALIDATION_FAILED + the offending field, not Pydantic's `detail` list."""
    client, _app, _tmpdir = api_client
    res = client.post("/api/v1/workspace", json={"workspace_name": "no paths"}, headers=AUTH)
    assert res.status_code == 422
    body = res.json()
    assert body["ok"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_FAILED"
    assert body["error"]["field"] == "root_paths"
    assert "detail" not in body


def test_validation_failure_does_not_echo_the_submitted_value(api_client):
    """
    DEC-12: `POST /api/v1/config/llm` carries the API key, and Pydantic's `errors()` puts the
    rejected input in the error entry by default. Echoing it back would put the key in a
    response body — the one place DEC-12 names explicitly alongside logs.
    """
    client, _app, _tmpdir = api_client
    secret = "sk-ant-test-must-not-be-echoed"
    res = client.post("/api/v1/config/llm", json={"api_key": secret}, headers=AUTH)
    assert res.status_code == 422
    assert secret not in res.text


def test_not_found_uses_the_envelope(api_client):
    client, _app, _tmpdir = api_client
    res = client.get("/api/v1/workspace/00000000-0000-0000-0000-000000000000", headers=AUTH)
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_unhandled_exception_leaks_neither_a_path_nor_a_traceback(api_client):
    """
    The 500 path, forced by making a service raise the way a real `OSError` would.

    `str(OSError)` is the absolute path it failed on, which DEC-03 forbids in a response body.
    `raise_server_exceptions=False` is required: TestClient re-raises by default and would never
    exercise the handler at all.
    """
    client, app, _tmpdir = api_client

    def boom(*_args, **_kwargs):
        raise OSError(r"[WinError 5] Access is denied: 'C:\Users\docto\AppData\Local\CorpBrain'")

    app.state.ws_service.list_workspaces = boom
    bare = TestClient(app, raise_server_exceptions=False)
    res = bare.get("/api/v1/workspace", headers=AUTH)

    assert res.status_code == 500
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "C:\\Users" not in res.text
    assert "WinError" not in res.text
    assert "Traceback" not in res.text


# --- the dev launcher's session injection ------------------------------------------------


def test_dev_serve_injects_the_bridge_without_writing_it_to_disk():
    """
    dev_serve.py rewrites index.html in flight. It must not modify the build artifact: writing
    the token to dist/index.html would persist it to disk, which DEC-02 forbids.
    """
    content = _read(REPO_ROOT / "scripts" / "dev_serve.py")
    assert "window.__CORPBRAIN__" in content
    assert "read_text" in content, "index.html should be read per request, not written"
    assert "index_file.write_text" not in content
    assert "no-store" in content, "the injected index must not be cached across boots"
