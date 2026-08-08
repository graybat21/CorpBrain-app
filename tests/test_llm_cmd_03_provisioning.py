"""
LLM-CMD-03 / DEC-13 — Ollama provisioning (issue #29).

Note on naming: `tests/test_llm_cmd_03.py` already exists but tests DEC-16 retry policy despite
its filename, so this file carries the actual LLM-CMD-03 coverage rather than renaming that one
mid-branch.

What is faked and what is not (DECISION_LOG 재발방지 4)
------------------------------------------------------
Faked: the *network's answers* (is the installer host reachable, what does `GET /api/tags`
return) and `subprocess.run`. Everything that encodes a DEC-13 decision — mode selection,
required-model derivation from App_Config, the detect_only prohibition, failure classification —
is the real code path.

Subprocess is faked deliberately and the tests assert on **whether it was called at all**. That
inversion is the point: DEC-13's central rule is "in detect_only, never attempt an install", and
a spy that records zero calls is the only way to prove a negative.
"""

import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

import pytest

from src.backend.config_manager import ConfigManager
from src.backend.network_guard import EgressBlockedError, NetworkGuard
from src.backend.services.provisioning_service import (
    MODE_ASSISTED,
    MODE_DETECT_ONLY,
    ProvisioningError,
    ProvisioningService,
)


class FakeGuard:
    """
    NetworkGuard stand-in that records every call and answers from canned state.

    Records `download_calls` so a test can assert an install was *not* attempted — the DEC-13
    prohibition that cannot be verified any other way.
    """

    def __init__(self, reachable: bool = True, tags: Optional[Dict[str, Any]] = None):
        self.reachable = reachable
        self.tags = tags
        self.reachability_calls: List[Dict[str, Any]] = []
        self.download_calls: List[Dict[str, Any]] = []
        self.get_json_calls: List[Dict[str, Any]] = []

    def is_reachable(self, purpose: str, url: str, timeout: float = 5.0) -> bool:
        self.reachability_calls.append({"purpose": purpose, "url": url, "timeout": timeout})
        return self.reachable

    def get_json(self, purpose: str, url: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        self.get_json_calls.append({"purpose": purpose, "url": url, "timeout": timeout})
        return self.tags

    def download_to_file(self, purpose, url, dest_path, timeout=30.0, progress_cb=None):
        self.download_calls.append({"purpose": purpose, "url": url})
        with open(dest_path, "wb") as f:
            f.write(b"fake-installer")
        return 14


@pytest.fixture
def config_mgr():
    """A ConfigManager on its own database, closed even if the test body raises."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))
        try:
            yield cm
        finally:
            cm.close()


def _tags(*names: str) -> Dict[str, Any]:
    return {"models": [{"name": n} for n in names]}


# --- Scenario 2: closed network, pre-provisioned (AC S2) --------------------------------


def test_scenario_2_detect_only_completes_without_downloading(config_mgr):
    """
    AC S2: installer unreachable + `nomic-embed-text` present -> completed, no download.

    The load-bearing assertion is `download_calls == []`. DEC-13's rule is that a closed
    network must never see an install attempt, and only a call-count of zero proves it.
    """
    guard = FakeGuard(reachable=False, tags=_tags("nomic-embed-text:latest"))
    service = ProvisioningService(config_mgr, network_guard=guard)

    result = service.onboard("embedding")

    assert result["status"] == "completed"
    assert result["result"]["provision_mode"] == MODE_DETECT_ONLY
    assert guard.download_calls == [], "detect_only must never attempt a download (DEC-13)"
    # Detection went through GET /api/tags on loopback only.
    assert [c["purpose"] for c in guard.get_json_calls] == ["llm_local"]


def test_detect_only_accepts_the_implicit_latest_tag(config_mgr):
    """
    `ollama pull nomic-embed-text` lists as `nomic-embed-text:latest`.

    An equality check would report a correctly pre-provisioned closed-network machine as
    missing its models — an unrecoverable dead end for a user who did everything right.
    """
    guard = FakeGuard(reachable=False, tags=_tags("nomic-embed-text:latest"))
    service = ProvisioningService(config_mgr, network_guard=guard)
    assert service.missing_models("embedding", ["nomic-embed-text:latest"]) == []


# --- Scenario 3: closed network, models absent (AC S3) ----------------------------------


def test_scenario_3_detect_only_fails_immediately_with_required_models(config_mgr):
    """
    AC S3: no retry, no wait. `LLM_PROVISION_REQUIRED` + the missing-model list.

    DEC-13 calls a task parked in "downloading" on a closed network a defect, because closed
    networks are A1's *default* environment, not an exception.
    """
    guard = FakeGuard(reachable=False, tags=_tags())  # daemon up, zero models
    service = ProvisioningService(config_mgr, network_guard=guard)

    with pytest.raises(ProvisioningError) as exc:
        service.onboard("generation")

    assert exc.value.error_code == "LLM_PROVISION_REQUIRED"
    # Both models named, so the admin knows exactly what to copy in.
    assert "nomic-embed-text" in exc.value.required_models
    assert "qwen2.5:7b-instruct" in exc.value.required_models
    assert guard.download_calls == []


def test_detect_only_absent_daemon_says_install_not_pull(config_mgr):
    """
    No daemon and no models are different failures and must not be conflated.

    `get_json` returning None means "no Ollama"; `{"models": []}` means "Ollama with nothing
    pulled". Telling a user with no Ollama to pull models sends them down a dead end.
    """
    guard = FakeGuard(reachable=False, tags=None)
    service = ProvisioningService(config_mgr, network_guard=guard)

    with pytest.raises(ProvisioningError) as exc:
        service.onboard("embedding")

    assert exc.value.error_code == "LLM_PROVISION_REQUIRED"
    assert "Ollama" in str(exc.value)
    assert guard.download_calls == []


def test_a_failed_provisioning_never_falls_back_to_option_a(config_mgr):
    """
    DEC-13's most serious prohibition: a provisioning failure must not switch to Option A.

    That would send document content to Anthropic without consent. Asserted on the persisted
    setting rather than on a comment, because this is the one failure whose cost is a
    confidentiality breach rather than an error message.
    """
    config_mgr.set("llm_mode", "Option B")
    guard = FakeGuard(reachable=False, tags=_tags())
    service = ProvisioningService(config_mgr, network_guard=guard)

    with pytest.raises(ProvisioningError):
        service.onboard("generation")

    assert config_mgr.get("llm_mode") == "Option B", "provisioning failure must not switch engines"


# --- Scenario 1: network available (AC S1) ----------------------------------------------


def test_scenario_1_assisted_installs_then_pulls(config_mgr, monkeypatch):
    """
    AC S1: reachable installer + absent Ollama -> assisted, install, then pull each model.

    `subprocess.run` is spied so the *order and arguments* are checked: the installer runs
    silently, then one `ollama pull` per missing model.
    """
    monkeypatch.setattr(
        "src.backend.services.provisioning_service.IS_WINDOWS", True
    )
    calls: List[List[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        # CREATE_NO_WINDOW is required by the issue's constraints so the packaged windowed app
        # never flashes a console.
        assert "creationflags" in kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    class ProgressiveGuard(FakeGuard):
        """Daemon absent at first probe, present with models after the install."""

        def __init__(self):
            super().__init__(reachable=True, tags=None)
            self._probe = 0

        def get_json(self, purpose, url, timeout=5.0):
            self.get_json_calls.append({"purpose": purpose, "url": url})
            self._probe += 1
            if self._probe == 1:
                return None          # before install
            if self._probe == 2:
                return _tags()       # installed, no models
            return _tags("nomic-embed-text", "qwen2.5:7b-instruct")

    guard = ProgressiveGuard()
    service = ProvisioningService(config_mgr, network_guard=guard)

    messages: List[str] = []
    result = service.onboard("generation", progress=messages.append)

    assert result["status"] == "completed"
    assert result["result"]["provision_mode"] == MODE_ASSISTED
    assert len(guard.download_calls) == 1
    assert guard.download_calls[0]["purpose"] == "provisioning"

    # Installer silently, then a pull per model.
    assert "/VERYSILENT" in calls[0]
    pulls = [c for c in calls if c[:2] == ["ollama", "pull"]]
    assert [c[2] for c in pulls] == ["nomic-embed-text", "qwen2.5:7b-instruct"]

    # DEC-13: the 274MB embedder and the 4.7GB generation model are named separately, never
    # summed into one download.
    joined = "\n".join(messages)
    assert "nomic-embed-text" in joined and "qwen2.5:7b-instruct" in joined
    assert "274MB" in joined and "4.7GB" in joined


def test_assisted_skips_pull_when_models_already_present(config_mgr, monkeypatch):
    """A machine that already has both models must not re-download 4.7GB."""
    monkeypatch.setattr("src.backend.services.provisioning_service.IS_WINDOWS", True)
    calls: List[List[str]] = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, **kw: calls.append(list(cmd)) or subprocess.CompletedProcess(cmd, 0, "", ""),
    )

    guard = FakeGuard(reachable=True, tags=_tags("nomic-embed-text", "qwen2.5:7b-instruct"))
    service = ProvisioningService(config_mgr, network_guard=guard)

    result = service.onboard("generation")

    assert result["status"] == "completed"
    assert guard.download_calls == []
    assert [c for c in calls if c[:2] == ["ollama", "pull"]] == []


# --- Model identity comes from App_Config (DEC-13) --------------------------------------


def test_model_ids_come_from_app_config_not_literals(config_mgr):
    """
    DEC-13 forbids hardcoding a model name. Changing App_Config must change what is required.
    """
    config_mgr.set("local_embedding_model", "custom-embedder")
    config_mgr.set("local_generation_model", "custom-generator")
    service = ProvisioningService(config_mgr, network_guard=FakeGuard())

    assert service.required_models("embedding") == ["custom-embedder"]
    assert service.required_models("generation") == ["custom-embedder", "custom-generator"]


def test_embedding_purpose_does_not_require_the_generation_model(config_mgr):
    """
    DEC-06: every user needs the embedder; only Option B needs the 4.7GB generator.

    Requiring both for `purpose='embedding'` would push a 4.7GB download onto an Option A user
    who never runs local inference.
    """
    service = ProvisioningService(config_mgr, network_guard=FakeGuard())
    required = service.required_models("embedding")
    assert required == ["nomic-embed-text"]
    assert "qwen2.5:7b-instruct" not in required


def test_generation_purpose_still_requires_the_embedder(config_mgr):
    """Option B searches with embeddings too (DEC-06), so 'generation' is a superset."""
    service = ProvisioningService(config_mgr, network_guard=FakeGuard())
    assert service.required_models("generation") == ["nomic-embed-text", "qwen2.5:7b-instruct"]


def test_unknown_purpose_is_rejected(config_mgr):
    service = ProvisioningService(config_mgr, network_guard=FakeGuard())
    with pytest.raises(ValueError):
        service.required_models("everything")


# --- Egress (DEC-15) --------------------------------------------------------------------


def test_mode_decision_probes_the_provisioning_purpose(config_mgr):
    """DEC-15: the reachability pre-check is tagged `provisioning`, HEAD, 5s (DEC-13)."""
    guard = FakeGuard(reachable=True, tags=_tags("nomic-embed-text"))
    service = ProvisioningService(config_mgr, network_guard=guard)

    assert service.decide_mode() == MODE_ASSISTED
    assert guard.reachability_calls[0]["purpose"] == "provisioning"
    assert guard.reachability_calls[0]["timeout"] == 5.0


def test_a_blocked_whitelist_does_not_silently_become_detect_only(config_mgr):
    """
    An EgressBlockedError must not be reported as "the network is down".

    Treating it as unreachable would convert a whitelist misconfiguration into a silent mode
    downgrade, and the operator would never learn the gate rejected them.
    """
    class BlockingGuard(FakeGuard):
        def is_reachable(self, purpose, url, timeout=5.0):
            raise EgressBlockedError("not whitelisted")

    service = ProvisioningService(config_mgr, network_guard=BlockingGuard())
    with pytest.raises(ProvisioningError) as exc:
        service.decide_mode()
    assert exc.value.error_code == "LLM_PROVISION_REQUIRED"


def test_the_installer_host_is_whitelisted_for_provisioning_only():
    """
    The real whitelist must admit the installer URL under `provisioning` and reject it for
    the other purposes — a mismatched (purpose, destination) pair is blocked too (DEC-15).
    """
    from src.backend.services.provisioning_service import OLLAMA_INSTALLER_URL

    assert NetworkGuard.validate_egress("provisioning", OLLAMA_INSTALLER_URL) == "ollama.com"
    for wrong_purpose in ("llm_cloud", "llm_local"):
        with pytest.raises(EgressBlockedError):
            NetworkGuard.validate_egress(wrong_purpose, OLLAMA_INSTALLER_URL)


def test_install_refuses_on_a_non_windows_host(config_mgr, monkeypatch):
    """
    The installer is a Windows .exe (DEC-01). A dev host refuses rather than pretending.

    A shim that "succeeded" without installing anything would make the assisted path
    untestable by construction and hide a real regression behind a green macOS run.
    """
    monkeypatch.setattr("src.backend.services.provisioning_service.IS_WINDOWS", False)
    guard = FakeGuard(reachable=True, tags=None)
    service = ProvisioningService(config_mgr, network_guard=guard)

    with pytest.raises(ProvisioningError) as exc:
        service.onboard("embedding")
    assert exc.value.error_code == "LLM_PROVISION_REQUIRED"


def test_a_failed_pull_does_not_retry(config_mgr, monkeypatch):
    """
    DEC-13/DEC-16: no unbounded retry. One failed `ollama pull` ends the task.

    Asserted by counting invocations — a retry loop would show more than one call for the
    same model.
    """
    monkeypatch.setattr("src.backend.services.provisioning_service.IS_WINDOWS", True)
    attempts: List[List[str]] = []

    def failing_run(cmd, **kwargs):
        attempts.append(list(cmd))
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "run", failing_run)
    guard = FakeGuard(reachable=True, tags=_tags())
    service = ProvisioningService(config_mgr, network_guard=guard)

    with pytest.raises(ProvisioningError) as exc:
        service.onboard("embedding")

    assert exc.value.error_code == "LLM_PROVISION_REQUIRED"
    pulls = [c for c in attempts if c[:2] == ["ollama", "pull"]]
    assert len(pulls) == 1, f"expected exactly one attempt, got {len(pulls)}"


# --- The endpoint (DEC-04) --------------------------------------------------------------


def _api():
    """The real app on a temp DB, so the route, envelope and task table all execute."""
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app
    from src.backend.db import DatabaseManager

    tmpdir = tempfile.mkdtemp()
    db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
    app = create_app(db_mgr, session_token="onboard-test-token")
    client = TestClient(app)
    return db_mgr, app, client, {"Authorization": "Bearer onboard-test-token"}


def test_onboard_endpoint_returns_202_and_a_task_id():
    """
    DEC-04: 202 + task_id immediately, never a synchronous result.

    A 4.7GB pull cannot be a request/response, and there is no push channel by design — so the
    response carries an id to poll and nothing else.
    """
    db_mgr, app, client, headers = _api()
    try:
        res = client.post("/api/v1/llm/onboard", json={"purpose": "embedding"}, headers=headers)
        assert res.status_code == 202, res.text
        body = res.json()
        assert body["ok"] is True
        assert body["data"]["task_type"] == "llm_onboard"
        assert body["data"]["task_id"]
    finally:
        for tid in list(app.state.task_runner.active_task_ids()):
            app.state.task_runner.wait(tid, timeout=15)
        db_mgr.close()


def test_onboard_records_provision_mode_in_the_task_result():
    """
    DEC-13 requires `provision_mode` persisted in `Async_Task.result_json`.

    Runs against the real network stack, so the recorded mode reflects this host: CI has no
    Ollama, so the task fails with LLM_PROVISION_REQUIRED — which is itself AC S3's contract
    and is asserted as such. Either way the mode must be one of the two known values, never
    absent, because a support case starts by asking which path ran.
    """
    db_mgr, app, client, headers = _api()
    try:
        res = client.post("/api/v1/llm/onboard", json={"purpose": "embedding"}, headers=headers)
        task_id = res.json()["data"]["task_id"]
        assert app.state.task_runner.wait(task_id, timeout=30)

        row = app.state.task_repo.get(task_id)
        assert row["status"] in ("completed", "failed")
        if row["status"] == "failed":
            # No Ollama on this host: terminal immediately, with the DEC-13 code. Never
            # 'running' — a task parked mid-provisioning is the defect DEC-13 names.
            assert row["error_code"] == "LLM_PROVISION_REQUIRED"
        else:
            result = app.state.task_repo.get_result(task_id)
            assert result["provision_mode"] in (MODE_ASSISTED, MODE_DETECT_ONLY)
    finally:
        for tid in list(app.state.task_runner.active_task_ids()):
            app.state.task_runner.wait(tid, timeout=15)
        db_mgr.close()


def test_onboard_rejects_an_unknown_purpose():
    """DEC-13 has exactly two purposes; anything else is a validation failure, not a default."""
    db_mgr, app, client, headers = _api()
    try:
        res = client.post("/api/v1/llm/onboard", json={"purpose": "everything"}, headers=headers)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_FAILED"
    finally:
        db_mgr.close()


def test_onboard_requires_the_bearer_token():
    """DEC-02: no /api/v1/* route bypasses the token middleware, new ones included."""
    db_mgr, app, client, _ = _api()
    try:
        res = client.post("/api/v1/llm/onboard", json={"purpose": "embedding"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"
    finally:
        db_mgr.close()


def test_a_second_onboard_click_reuses_the_live_task():
    """
    A double-clicked onboarding button must not start two 4.7GB downloads.

    `llm_onboard` has workspace_id=None, and SQL's `= NULL` is never true — so without
    TaskRepository.find_active's IS NULL branch this de-duplication silently does nothing.
    """
    from src.backend.repositories.task_repository import TaskRepository

    db_mgr, app, client, headers = _api()
    try:
        repo = TaskRepository(db_mgr)
        first = repo.create("llm_onboard")
        repo.mark_running(first["task_id"])

        found = repo.find_active(None, "llm_onboard")
        assert found is not None, "a live workspace-independent task must be findable"
        assert found["task_id"] == first["task_id"]

        res = client.post("/api/v1/llm/onboard", json={"purpose": "embedding"}, headers=headers)
        assert res.status_code == 202
        assert res.json()["data"]["task_id"] == first["task_id"]
    finally:
        for tid in list(app.state.task_runner.active_task_ids()):
            app.state.task_runner.wait(tid, timeout=15)
        db_mgr.close()


def test_progress_message_is_committed_while_the_task_runs():
    """
    The v005 column exists so a poller can see which model is downloading (DEC-13).

    Committed per call, like increment_processed: a model pull runs for minutes with no counter
    movement, so a buffered message would leave the 1s poll blank for the longest step.
    """
    from src.backend.repositories.task_repository import TaskRepository
    from src.backend.services.task_service import TaskQueryService

    tmpdir = tempfile.mkdtemp()
    from src.backend.db import DatabaseManager

    db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
    try:
        repo = TaskRepository(db_mgr)
        task = repo.create("llm_onboard")
        repo.mark_running(task["task_id"])
        repo.set_progress_message(task["task_id"], "모델 내려받기: nomic-embed-text (약 274MB)")

        # Read through a second manager: the message must be in SQLite, not in memory
        # (DEC-04 / REQ-NF-011), same standard as the counters.
        other = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            progress = TaskQueryService(other).get_progress(task["task_id"])
            assert progress["progress_message"] == "모델 내려받기: nomic-embed-text (약 274MB)"
        finally:
            other.close()
    finally:
        db_mgr.close()


# --- Redirect re-validation (DEC-15) ----------------------------------------------------


def test_a_redirect_off_the_whitelist_is_blocked_and_leaves_no_file(monkeypatch):
    """
    urllib follows redirects transparently, so a whitelisted host redirecting to an arbitrary
    one would smuggle egress past the gate — the exact hole DEC-15 exists to close.

    Also asserts the partial file is deleted: a truncated binary from an unvetted host must not
    remain on disk where the install step could execute it.
    """
    import urllib.request

    from src.backend.network_guard import NetworkGuard

    class FakeResponse:
        """A 200 whose final URL (post-redirect) is off the whitelist."""

        status = 200
        headers = {"Content-Length": "4"}

        def geturl(self):
            return "https://evil.example.com/OllamaSetup.exe"

        def read(self, _size=None):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse())

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "installer.exe")
        with pytest.raises(EgressBlockedError):
            NetworkGuard.download_to_file(
                "provisioning", "https://ollama.com/download/OllamaSetup.exe", dest
            )
        assert not os.path.exists(dest), "a blocked download must not leave a partial file"


def test_is_reachable_treats_a_non_2xx_answer_as_reachable(monkeypatch):
    """
    Some hosts reject HEAD with 405 while serving GET fine.

    The only question is "can I reach this host", so any HTTP answer counts — otherwise a
    405 on the installer URL would misclassify a networked PC as a closed network and skip a
    perfectly possible install.
    """
    import urllib.error
    import urllib.request

    def raise_405(*a, **kw):
        raise urllib.error.HTTPError(
            "https://ollama.com/download/OllamaSetup.exe", 405, "Method Not Allowed", {}, None
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_405)
    assert NetworkGuard.is_reachable(
        "provisioning", "https://ollama.com/download/OllamaSetup.exe"
    ) is True


def test_is_reachable_is_false_when_the_host_is_unroutable(monkeypatch):
    """A closed network typically blackholes, so the timeout IS the answer — False, not raise."""
    import urllib.error
    import urllib.request

    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **kw: (_ for _ in ()).throw(urllib.error.URLError("unreachable")),
    )
    assert NetworkGuard.is_reachable(
        "provisioning", "https://ollama.com/download/OllamaSetup.exe"
    ) is False


def test_is_reachable_still_raises_on_a_whitelist_violation():
    """
    A non-whitelisted host is a programming error, not "the network is down".

    Returning False here would let a whitelist misconfiguration silently become detect_only.
    """
    with pytest.raises(EgressBlockedError):
        NetworkGuard.is_reachable("provisioning", "https://api.anthropic.com/v1/messages")
