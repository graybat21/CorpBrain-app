"""
INF-TEST-02 (issue #26) — telemetry isolation, all three DEC-15 layers.

TC-SEC-002 / TC-SEC-004 / REQ-NF-005 / REQ-NF-018 / CON-03.

`tests/test_inf_cmd_03.py` already covers NetworkGuard's whitelist decisions. This file adds the
three things it does not:

- **Layer 1 upgraded to a socket-level claim.** "EgressBlockedError was raised" is weaker than
  "no connection was made". A guard that raised *after* opening a socket would satisfy the old
  assertion and still leak a DNS query revealing which host the app tried to reach. These tests
  spy on `socket.getaddrinfo`/`create_connection` and assert zero activity.
- **Layer 2: a meta-test that the CI lint rule actually fires.** The rule existing in ruff.toml
  and the rule *working* are different claims, and DEC-15 rests on the second. A fixture module
  with a forbidden import is written to a temp dir and ruff is run on it for real.
- **Steady-state isolation (Scenario 1).** The full local pipeline runs with the socket layer
  under observation; anything outside `127.0.0.1` fails the test.

Scope, stated honestly: this is layers 1 and 2 plus a socket-level approximation of layer 3.
A real packet capture (the issue's "3층") needs elevated privileges and a provisioned Ollama, so
it cannot run in CI — `test_option_a_payloads_carry_no_pii_or_paths` covers the *payload* claims
that capture was meant to check, at the seam where the data is handed to the transport.
"""

import ast
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.backend.network_guard import EgressBlockedError, NetworkGuard

REPO_ROOT = Path(__file__).resolve().parent.parent

#: DEC-15's whitelist, restated here on purpose. If the code constant changes, this must change
#: too — and a reviewer then sees a security decision being edited rather than a refactor.
EXPECTED_WHITELIST = {
    "llm_local": {"127.0.0.1", "localhost"},
    "llm_cloud": {"api.anthropic.com"},
    "provisioning": {"github.com", "objects.githubusercontent.com", "ollama.com"},
}


class SocketWatcher:
    """
    Records every DNS lookup and TCP connect attempt made while active.

    Patching `socket.getaddrinfo` and `socket.create_connection` rather than `socket.socket`:
    DEC-15 explicitly forbids monkey-patching the socket class at runtime because it breaks
    ChromaDB and the anthropic SDK unpredictably under PyInstaller. These two are the funnels
    urllib and httpx both go through, and patching them only inside a test changes nothing about
    the shipped app.
    """

    def __init__(self):
        self.events: list = []

    def __enter__(self):
        real_getaddrinfo = socket.getaddrinfo
        real_create_connection = socket.create_connection

        def watched_getaddrinfo(host, port, *args, **kwargs):
            self.events.append(("dns", host, port))
            return real_getaddrinfo(host, port, *args, **kwargs)

        def watched_create_connection(address, *args, **kwargs):
            self.events.append(("connect", address[0] if address else None, None))
            return real_create_connection(address, *args, **kwargs)

        self._patches = [
            patch.object(socket, "getaddrinfo", watched_getaddrinfo),
            patch.object(socket, "create_connection", watched_create_connection),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        return False

    @property
    def hosts(self) -> set:
        return {event[1] for event in self.events if event[1] is not None}

    def external_hosts(self) -> set:
        """Every contacted host that is not loopback."""
        loopback = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
        return {h for h in self.hosts if str(h) not in loopback}


# --- Layer 1: the whitelist blocks, and nothing reaches the socket -----------------------


@pytest.mark.parametrize(
    "purpose,url",
    [
        # AC S4 verbatim — the suffix-confusion attack exact matching exists to stop.
        ("llm_cloud", "https://api.anthropic.com.attacker.net/v1/messages"),
        ("llm_cloud", "https://notapi.anthropic.com/v1/messages"),
        ("llm_cloud", "https://api-anthropic.com/v1/messages"),
        ("llm_cloud", "https://example.com/v1/messages"),
        ("llm_local", "https://example.com/api/tags"),
        ("provisioning", "https://example.com/OllamaSetup.exe"),
        # A mismatched (purpose, destination) pair is blocked even though both halves are
        # individually whitelisted.
        ("provisioning", "https://api.anthropic.com/v1/messages"),
        ("llm_cloud", "http://127.0.0.1:11434/api/tags"),
    ],
)
def test_a_blocked_request_never_touches_the_socket_layer(purpose, url):
    """
    TC-SEC-004 layer 1, stated as strongly as it should be.

    "EgressBlockedError was raised" is not enough: a guard that raised *after* opening the socket
    would pass that, while still emitting a DNS query that tells an observer which host the app
    tried to reach. AC S4 says the capture must show no DNS and no TCP at all.
    """
    with SocketWatcher() as watcher:
        with pytest.raises(EgressBlockedError):
            NetworkGuard.post_json(purpose, url, {"probe": 1}, timeout=1)

        with pytest.raises(EgressBlockedError):
            NetworkGuard.get_json(purpose, url, timeout=1)

        with pytest.raises(EgressBlockedError):
            NetworkGuard.is_reachable(purpose, url, timeout=1)

    assert watcher.events == [], f"blocked request produced socket activity: {watcher.events}"


def test_the_whitelist_is_exactly_three_purposes():
    """
    DEC-15: three (purpose, destination) pairs, no more.

    Adding a fourth destination is a design-decision change requiring the DEC-15 table and
    REQ-NF-005 to be updated in the same change — so it must break a test, not slip through.
    """
    actual = {purpose: set(hosts) for purpose, hosts in NetworkGuard._ALLOWED.items()}
    assert actual == EXPECTED_WHITELIST, (
        "the egress whitelist changed. This is a DEC-15 design decision, not a refactor: "
        "update the DEC-15 table and REQ-NF-005 in the same change."
    )


def test_the_whitelist_is_a_code_constant_not_configuration():
    """
    DEC-15: a runtime-mutable whitelist is not a whitelist.

    Asserted structurally — the module must not read the allowlist from App_Config, an env var,
    or a settings file. Comments are stripped so the file's own documentation of this rule cannot
    satisfy the check.
    """
    source = (REPO_ROOT / "src" / "backend" / "network_guard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    # No os.environ / getenv / config lookups anywhere in the module.
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv"):
            pytest.fail("NetworkGuard must not read the whitelist from the environment")
        if isinstance(node, ast.Name) and node.id in ("ConfigManager",):
            pytest.fail("NetworkGuard must not read the whitelist from App_Config")

    # And `_ALLOWED` is assigned a literal, not built from a call.
    allowed = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", None) == "_ALLOWED"),
        None,
    )
    assert allowed is not None, "_ALLOWED not found"
    assert isinstance(allowed.value, ast.Dict), "_ALLOWED must be a literal dict"


def test_host_matching_is_case_insensitive_but_still_exact():
    """Uppercase must not be a bypass, and must not become a wildcard either."""
    assert NetworkGuard.validate_egress("llm_cloud", "https://API.ANTHROPIC.COM/v1") == "api.anthropic.com"
    with pytest.raises(EgressBlockedError):
        NetworkGuard.validate_egress("llm_cloud", "https://API.ANTHROPIC.COM.EVIL.NET/v1")


def test_a_blocked_attempt_logs_the_host_and_purpose_only(caplog):
    """
    DEC-15 log hygiene: the blocked host and purpose, never the request body.

    A blocked request often carries the payload that triggered it — for this app, a masked
    document chunk or a filename.
    """
    import logging

    secret_body = {"chunk": "홍길동 900101-1234567 계약 내용", "path": r"C:\Users\hong\문서"}
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(EgressBlockedError):
            NetworkGuard.post_json("llm_cloud", "https://evil.example.com/v1", secret_body, timeout=1)

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "evil.example.com" in logged, "the blocked host should be logged"
    assert "llm_cloud" in logged
    assert "900101-1234567" not in logged
    assert "홍길동" not in logged
    assert r"C:\Users" not in logged


# --- Layer 2: the CI lint rule actually fires (a meta-test) ------------------------------


@pytest.mark.parametrize(
    "forbidden_import",
    [
        "import requests",
        "import httpx",
        "import socket",
        "import urllib.request",
        "from urllib import request",
        "import websockets",
    ],
)
def test_the_ci_lint_rejects_a_forbidden_import(forbidden_import):
    """
    TC-SEC-004 layer 2. The rule existing and the rule *working* are different claims.

    DEC-15 requires this to block the merge, so a real ruff run on a real fixture is the only
    thing that proves it. A test asserting "TID is in ruff.toml" would pass against a
    misconfigured rule that never fires.

    The fixture lives in a temp dir but is checked with the repo's ruff.toml — writing it under
    `src/` would leave a lint violation in the tree if the test crashed midway.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        probe = Path(tmpdir) / "sneaky_service.py"
        probe.write_text(f"{forbidden_import}\n", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, "-m", "ruff", "check",
                "--config", str(REPO_ROOT / "ruff.toml"),
                "--no-cache",
                str(probe),
            ],
            capture_output=True,
            text=True,
            # issue #145: text=True alone decodes with the host ANSI codepage, so a non-ASCII
            # byte in ruff's output (a path, a quoted source line) kills the reader thread on a
            # cp949 host and `result.stdout` silently becomes None.
            encoding="utf-8",
            errors="replace",
        )

    assert result.returncode != 0, (
        f"the lint rule did not reject `{forbidden_import}`.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # `returncode != 0` alone is NOT sufficient, which a mutation run proved: with the TID rule
    # deleted from ruff.toml, an unused-import F401 still fails the file — so the exit code would
    # keep this test green while the DEC-15 rule was gone entirely. The banned-api code must be
    # the reason for the failure, and the message must name DEC-15 so a contributor learns what
    # to do instead of just that something is wrong.
    assert "TID251" in result.stdout, (
        f"the failure was not the DEC-15 banned-api rule:\n{result.stdout}"
    )
    # DEC-15 for the network libraries, DEC-04 for `websockets` — that one is banned because no
    # push channel exists by design, not because of egress. Either citation is correct; a message
    # with no decision reference is not, because it leaves a contributor guessing.
    assert "DEC-15" in result.stdout or "DEC-04" in result.stdout, (
        f"the ban message must cite the decision it enforces:\n{result.stdout}"
    )


def test_the_lint_permits_the_import_inside_network_guard():
    """
    The rule must have exactly one exemption, or NetworkGuard itself cannot be written.

    Asserted by linting the real file — an over-broad exemption would show up as this file being
    the only one that passes, which the forbidden-import AST sweep below then cross-checks.
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "ruff", "check",
            "--config", str(REPO_ROOT / "ruff.toml"),
            "--no-cache",
            str(REPO_ROOT / "src" / "backend" / "network_guard.py"),
        ],
        capture_output=True,
        text=True,
        # issue #145 — see the sibling call above.
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout


def test_no_shipped_module_outside_network_guard_imports_a_network_library():
    """
    The same claim as the lint, verified independently by AST.

    Defence in depth: if the ruff config were ever loosened, this still fails. `tests/` is
    excluded for the same reason ruff.toml excludes it — these tests patch urllib deliberately.
    """
    allowed = {REPO_ROOT / "src" / "backend" / "network_guard.py"}
    forbidden = {"requests", "httpx", "socket", "urllib.request", "websockets"}
    violations = []

    for path in (REPO_ROOT / "src").rglob("*.py"):
        if path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden or alias.name.split(".")[0] in {"requests", "httpx", "websockets"}:
                        violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in {"requests", "httpx", "websockets"} or node.module == "urllib.request":
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} from {node.module}")

    assert violations == [], f"DEC-15 violations: {violations}"


def _declared_requirements(filename: str) -> list:
    """
    Requirement names only — comments and version specifiers stripped.

    Scanning the raw file text was my first attempt and it produced a false positive:
    requirements.txt has a comment explaining which chromadb *transitives* are deliberately not
    hand-pinned, and it names `websockets`. A prose mention is not a dependency, and a security
    test that fails on documentation trains people to delete the documentation.
    """
    lines = (REPO_ROOT / filename).read_text(encoding="utf-8").splitlines()
    names = []
    for line in lines:
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        for separator in ("==", ">=", "<=", "~=", ">", "<", "[", ";"):
            line = line.split(separator)[0]
        names.append(line.strip().lower())
    return names


def test_no_remote_telemetry_sdk_is_a_dependency():
    """
    DEC-15: no GA, Sentry, PostHog, or any remote crash reporter. Crash details go to the local
    log only.

    Checked against requirements.txt rather than installed packages: the shipped artifact is
    built from the pin files, so that is where a telemetry SDK would have to appear.
    """
    banned = {"sentry-sdk", "posthog", "mixpanel", "datadog", "ddtrace", "newrelic", "bugsnag",
              "google-analytics", "analytics-python", "segment-analytics-python"}
    for filename in ("requirements.txt", "requirements.lock.windows.txt", "requirements.lock.macos.txt"):
        declared = set(_declared_requirements(filename))
        offenders = declared & banned
        assert offenders == set(), f"{sorted(offenders)} in {filename} (DEC-15 forbids remote telemetry)"


def test_no_websocket_or_sse_dependency():
    """DEC-04: no push channel exists by design; the frontend polls."""
    banned = {"websockets", "sse-starlette", "python-socketio", "websocket-client", "aiohttp-sse"}
    # requirements.txt only: the lock files legitimately contain `websockets` as a chromadb
    # transitive. DEC-04 forbids CorpBrain from *using* a push channel, and a direct declaration
    # is what would show that intent — a transitive nobody imports is checked by the
    # forbidden-import sweep above instead.
    declared = set(_declared_requirements("requirements.txt"))
    offenders = declared & banned
    assert offenders == set(), f"{sorted(offenders)} violates DEC-04"


# --- Scenario 1: steady-state isolation --------------------------------------------------


def test_scenario_1_the_local_pipeline_contacts_nothing_but_loopback():
    """
    Scenario 1 / TC-SEC-002: scan → fast analysis → file list → deeplink status, with the socket
    layer watched. Any non-loopback host fails.

    Measured on an already-provisioned steady state, which is the distinction DEC-13 draws:
    provisioning downloads are a separate, user-initiated act and must not be judged here. This
    test never calls the onboarding path, so nothing it does could be one.

    Chroma and the LLM are not exercised — embedding needs a live Ollama, which CI does not have.
    What IS exercised is every path a user hits without an engine: the scan, the scoring, the
    queries, and the deeplink resolution. Those are also the paths most likely to acquire a
    stray outbound call, since none of them has any reason to make one.
    """
    import os
    import uuid

    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app
    from src.backend.db import DatabaseManager

    with tempfile.TemporaryDirectory() as tmpdir:
        root = os.path.join(tmpdir, "docs")
        os.makedirs(root)
        for name in ("기획서.txt", "회의록.md"):
            with open(os.path.join(root, name), "w", encoding="utf-8") as f:
                f.write("문서 내용입니다. 연락처 010-1234-5678")

        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        app = create_app(db_mgr, session_token="telemetry-token")
        headers = {"Authorization": "Bearer telemetry-token"}

        try:
            with SocketWatcher() as watcher, TestClient(app) as client:
                created = client.post(
                    "/api/v1/workspace",
                    json={"workspace_name": "격리테스트", "root_paths": [root]},
                    headers=headers,
                )
                ws_id = created.json()["data"]["workspace_id"]

                scan = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
                app.state.task_runner.wait(scan.json()["data"]["task_id"], timeout=30)

                fast = client.post(f"/api/v1/workspace/{ws_id}/analysis/fast", headers=headers)
                app.state.task_runner.wait(fast.json()["data"]["task_id"], timeout=30)

                client.get(f"/api/v1/workspace/{ws_id}/file", headers=headers)
                client.get(f"/api/v1/workspace/{ws_id}/scan/summary", headers=headers)
                client.get(f"/api/v1/workspace/{ws_id}/deeplink/status", headers=headers)
                client.get(f"/api/v1/workspace/{ws_id}/watcher", headers=headers)
                client.get(f"/api/v1/workspace/{ws_id}", headers=headers)
                client.get(f"/api/v1/analyze/{uuid.uuid4()}/progress", headers=headers)

            external = watcher.external_hosts()
            assert external == set(), (
                f"steady state contacted a non-loopback host: {sorted(external)}"
            )
        finally:
            for task_id in list(app.state.task_runner.active_task_ids()):
                app.state.task_runner.wait(task_id, timeout=15)
            db_mgr.close()


# --- Scenario 3: detect_only issues no installer request --------------------------------


def test_scenario_3_detect_only_makes_no_download_request():
    """
    Scenario 3: on a closed network, one HEAD reachability probe and nothing more.

    Asserted by counting calls on a recording guard — the reachability probe must happen exactly
    once (it is what decides the mode), and the download must happen zero times. Also asserts no
    Anthropic fallback, which DEC-13 names as the worst available outcome.
    """
    import os

    from src.backend.config_manager import ConfigManager
    from src.backend.db import DatabaseManager
    from src.backend.services.provisioning_service import ProvisioningError, ProvisioningService

    class ClosedNetworkGuard:
        def __init__(self):
            self.reachability_probes = []
            self.downloads = []
            self.json_calls = []

        def is_reachable(self, purpose, url, timeout=5.0):
            self.reachability_probes.append((purpose, url))
            return False

        def get_json(self, purpose, url, timeout=5.0):
            self.json_calls.append((purpose, url))
            return {"models": []}

        def download_to_file(self, *args, **kwargs):
            self.downloads.append(args)
            raise AssertionError("detect_only must never download (DEC-13)")

        def post_json(self, purpose, url, payload, timeout):
            raise AssertionError(f"no POST may happen here: {purpose} {url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "prov.db"))
        try:
            guard = ClosedNetworkGuard()
            service = ProvisioningService(ConfigManager(db_mgr), network_guard=guard)

            with pytest.raises(ProvisioningError) as exc:
                service.onboard("generation")

            assert exc.value.error_code == "LLM_PROVISION_REQUIRED"
            assert len(guard.reachability_probes) == 1, guard.reachability_probes
            assert guard.reachability_probes[0][0] == "provisioning"
            assert guard.downloads == []
            # Detection went to loopback only — no Anthropic fallback (DEC-13's worst outcome).
            assert all(purpose == "llm_local" for purpose, _ in guard.json_calls), guard.json_calls
            assert not any("anthropic" in url for _, url in guard.json_calls)
        finally:
            db_mgr.close()


# --- Scenario 2: both Option A payloads are clean ---------------------------------------


def test_option_a_payloads_carry_no_pii_or_paths():
    """
    Scenario 2 / TC-SEC-005: BOTH Option A transmission paths, checked at the transport seam.

    The issue asks for a packet capture; that needs privileges CI does not have, so this asserts
    the same claims one layer in — on the payload handed to the transport. If the payload is
    clean there, the packet cannot carry it.

    Rename is included deliberately. DEC-17 exists because "it is only a filename" was the
    reasoning that would have excluded it, and `홍길동_연봉계약서_2026.docx` carries a name, a
    document type and a date in one line.
    """
    import os

    from src.backend.db import DatabaseManager
    from src.backend.pii_filter import PIIFilter
    from src.backend.repositories.workspace_repository import WorkspaceRepository
    from src.backend.services.rename_service import RenameService

    rrn = "900101-1234567"
    phone = "010-1234-5678"

    # --- path 1: an analysis chunk ---
    chunk = f"계약자 홍길동, 주민번호 {rrn}, 연락처 {phone}"
    masked_chunk = PIIFilter().mask(chunk)
    assert rrn not in masked_chunk.masked_text
    assert phone not in masked_chunk.masked_text
    assert "[PII:RRN]" in masked_chunk.masked_text
    assert "***" not in masked_chunk.masked_text, "a digit-count-preserving mask is forbidden"

    # --- path 2: a rename prompt ---
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "rn.db"))
        try:
            ws_id = WorkspaceRepository(db_mgr).create("payload", [tmpdir])["workspace_id"]
            captured = []

            class Recorder:
                def generate(self, prompt, max_tokens=200):
                    captured.append(prompt)
                    return {"content": '{"suggested_name": "2026-08_계약서.pdf"}'}

            class Once:
                def execute_with_retry(self, func, file_id, is_transient_error=None):
                    return func()

            service = RenameService(db_mgr=db_mgr, llm_router=Recorder(), resilience=Once())
            filename = f"홍길동_연봉계약서_{rrn}.pdf"
            unc_path = r"\\fileserver\share\인사\계약"
            service.process_rename_suggestions(ws_id, [{
                "file_id": "f1",
                "file_name": filename,
                "extension": ".pdf",
                "current_path": os.path.join(unc_path, filename),
            }])

            payload = captured[0]
            # No PII.
            assert rrn not in payload
            assert "[PII:RRN]" in payload
            # No absolute path, drive letter, account directory, or UNC prefix (DEC-17).
            assert unc_path not in payload
            assert "\\\\" not in payload
            assert "C:\\" not in payload
            assert "Users" not in payload
            assert tmpdir not in payload
        finally:
            db_mgr.close()
