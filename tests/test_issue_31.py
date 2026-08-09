"""
LLM-FE-02 (issue #31) — Ollama onboarding UI, and the backend gap it exposed.

Two kinds of assertion live here, and the split matters:

1. **Backend behaviour** (real tests). Building the UI revealed that `TaskRunner` recorded
   `result_json = NULL` on the failure path, so `provision_mode` died with the worker thread —
   and AC S3 needs exactly that field to decide whether a retry button may be shown. Those
   tests exercise the real code.

2. **Frontend structure** (static source assertions). There is no frontend test runner by
   decision (no Vitest, no jsdom), so the DEC-13 prohibitions the component must honour are
   checked by reading the source, following the pattern in tests/test_ws_fe_01.py. This proves
   the code does not contain a retry path for `detect_only` and does not merge the two model
   downloads; it does NOT prove the rendered pixels. The live check is the dev_serve round trip
   recorded in the PR body.
"""

import os
import re
import tempfile
from pathlib import Path

import pytest

from src.backend.config_manager import ConfigManager
from src.backend.db import DatabaseManager
from src.backend.repositories.task_repository import TaskRepository
from src.backend.services.provisioning_service import (
    MODE_DETECT_ONLY,
    ProvisioningError,
    ProvisioningService,
)
from src.backend.services.task_service import TaskRunner
from tests.test_llm_cmd_03_provisioning import FakeGuard, _tags

FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"
PANEL = FRONTEND / "components" / "LlmOnboardPanel.tsx"


def _code(path: Path) -> str:
    """
    Source with comments stripped — same helper rationale as tests/test_ws_fe_01.py.

    This component documents the very rules it obeys ("no retry button in detect_only"), so a
    raw substring scan would flag the documentation as the violation. Stripping comments first
    makes an assertion mean "the code does not do X" rather than "the file never mentions X".
    """
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


# --- Backend: the failure path must persist provisioning context ------------------------


@pytest.fixture
def config_mgr():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))
        try:
            yield cm
        finally:
            cm.close()


def test_a_failed_provisioning_persists_provision_mode(config_mgr):
    """
    The gap this issue exposed: without `provision_mode` in `result_json`, the UI cannot tell a
    closed network from a transient install failure — and DEC-13 forbids offering a retry in the
    first case. `TaskRunner.finish` used to write NULL on every failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            repo = TaskRepository(db_mgr)
            runner = TaskRunner(db_mgr, task_repo=repo)
            service = ProvisioningService(
                config_mgr, network_guard=FakeGuard(reachable=False, tags=_tags())
            )

            task = runner.submit("llm_onboard", lambda ctx: service.onboard("generation"))
            assert runner.wait(task["task_id"], timeout=30)

            row = repo.get(task["task_id"])
            assert row["status"] == "failed"
            assert row["error_code"] == "LLM_PROVISION_REQUIRED"

            result = repo.get_result(task["task_id"])
            assert result is not None, "a provisioning failure must persist its context"
            assert result["provision_mode"] == MODE_DETECT_ONLY
            assert result["purpose"] == "generation"
            # The offline instructions need the full requirement list, and the missing subset
            # drives the "필요한 모델" list.
            assert "nomic-embed-text" in result["required_models"]
            assert "qwen2.5:7b-instruct" in result["missing_models"]
        finally:
            for tid in list(runner.active_task_ids()):
                runner.wait(tid, timeout=10)
            db_mgr.close()


def test_the_failure_result_carries_no_paths_or_exception_text(config_mgr):
    """
    DEC-03: nothing a client reads may hold an absolute path or raw exception text.

    `reason` is deliberately a Korean message written for the user, not `str(exc)` of an OSError
    — which stringifies to the path it failed on.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            repo = TaskRepository(db_mgr)
            runner = TaskRunner(db_mgr, task_repo=repo)
            service = ProvisioningService(
                config_mgr, network_guard=FakeGuard(reachable=False, tags=None)
            )
            task = runner.submit("llm_onboard", lambda ctx: service.onboard("embedding"))
            assert runner.wait(task["task_id"], timeout=30)

            result = repo.get_result(task["task_id"])
            blob = str(result)
            for forbidden in ("C:\\", "/Users/", "/tmp/", "Traceback", ".ollama"):
                assert forbidden not in blob, f"{forbidden!r} leaked into a client-readable result"
        finally:
            for tid in list(runner.active_task_ids()):
                runner.wait(tid, timeout=10)
            db_mgr.close()


def test_provisioning_error_defaults_do_not_claim_a_mode():
    """
    A raise site that never reached `onboard`'s stamping must not assert a mode it cannot know.

    `provision_mode=None` renders as the generic failure branch; inventing 'assisted' there
    would show a retry button on a closed network, which is the DEC-13 violation.
    """
    err = ProvisioningError("실패")
    assert err.provision_mode is None
    assert err.task_result["provision_mode"] is None
    assert err.error_code == "LLM_PROVISION_REQUIRED"


def test_a_successful_task_still_persists_its_result(config_mgr):
    """The success path must not regress while the failure path was being fixed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            repo = TaskRepository(db_mgr)
            runner = TaskRunner(db_mgr, task_repo=repo)
            service = ProvisioningService(
                config_mgr,
                network_guard=FakeGuard(reachable=False, tags=_tags("nomic-embed-text")),
            )
            task = runner.submit("llm_onboard", lambda ctx: service.onboard("embedding"))
            assert runner.wait(task["task_id"], timeout=30)

            assert repo.get(task["task_id"])["status"] == "completed"
            assert repo.get_result(task["task_id"])["provision_mode"] == MODE_DETECT_ONLY
        finally:
            for tid in list(runner.active_task_ids()):
                runner.wait(tid, timeout=10)
            db_mgr.close()


# --- Frontend structure (static) --------------------------------------------------------


def test_the_panel_polls_progress_and_uses_no_push_channel():
    """DEC-04: 1s polling via pollTask; WebSocket/SSE do not exist by design."""
    code = _code(PANEL)
    assert "api.onboardLlm(" in code
    assert "api.pollTask(" in code, "progress must come from polling, not the POST response"
    for forbidden in ("WebSocket", "EventSource", "socket.io"):
        assert forbidden not in code, f"{forbidden} violates DEC-04"
    # The POST response carries a task_id only — reading a percentage off it is the mistake the
    # issue's Task Breakdown calls out explicitly.
    assert "accepted.percent" not in code
    assert "accepted.progress" not in code


def test_the_panel_renders_the_two_models_separately():
    """
    AC S4 / DEC-13: two rows, never one summed percentage.

    Asserted by the presence of both model names with their own size hints, and by the absence
    of any arithmetic combining two progress values.
    """
    code = _code(PANEL)
    assert "nomic-embed-text" in code
    assert "qwen2.5:7b-instruct" in code
    assert "274MB" in code and "4.7GB" in code
    # A merged bar would need to add or average two numbers; nothing here does.
    assert not re.search(r"embedding\w*\s*\+\s*generation", code, re.I)
    assert not re.search(r"\(\s*\w*[Pp]ercent\w*\s*\+\s*\w*[Pp]ercent\w*\s*\)\s*/\s*2", code)


def test_detect_only_has_no_retry_button():
    """
    AC S3 / DEC-13's sharpest rule: a closed network gets no retry button.

    The retry `<button>` must sit inside the `!isClosedNetwork` branch. Verified structurally —
    the closed-network block is extracted and searched for a button, because "the file contains
    one button somewhere" is not the claim.
    """
    code = _code(PANEL)
    assert "isClosedNetwork" in code, "the two failure modes must be distinguished"

    start = code.index("isClosedNetwork && (")
    # The closed-network JSX ends where the sibling `!isClosedNetwork` branch begins.
    end = code.index("!isClosedNetwork && (", start)
    closed_block = code[start:end]

    assert "<button" not in closed_block, "detect_only must not offer a retry button (DEC-13)"
    # It must instead carry the manual procedure and the model list.
    assert "폐쇄망" in closed_block
    assert ".ollama\\models" in closed_block or ".ollama" in closed_block
    assert "missingModels" in closed_block

    retry_block = code[end:]
    assert "<button" in retry_block, "an assisted failure must offer a retry (DoD)"


def test_the_panel_states_the_network_use_and_its_boundary():
    """
    DEC-13 / REQ-NF-005: say that provisioning uses the internet, AND that documents do not go.

    Stating only the first frightens the user out of a feature they need; stating only the
    second is the concealment a security review is meant to catch. Both, or neither is honest.
    """
    code = _code(PANEL)
    assert "인터넷" in code
    assert "문서 내용과 파일 경로는 전송되지 않습니다" in code
    assert "127.0.0.1" in code


def test_the_embedding_requirement_is_surfaced_to_option_a_users():
    """
    DEC-06 파급: Option A needs the embedder too, so an unready state must explain itself.

    Without this an Option A user sees deep analysis fail with no stated cause — the panel is
    mounted unconditionally in SettingsPage for the same reason.
    """
    code = _code(PANEL)
    assert "embedding_model_ready" in code
    assert "심층 분석을 실행할 수 없습니다" in code
    assert "Option A" in code

    settings = _code(FRONTEND / "pages" / "SettingsPage.tsx")
    assert "<LlmOnboardPanel" in settings
    # Gating the panel on Option B would hide the embedder requirement from Option A users.
    assert not re.search(r"llmMode === 'Option B'\s*&&\s*<LlmOnboardPanel", settings)


def test_health_is_polled_on_the_five_second_interval():
    """AC S2: the ✅/❌ icon must follow a daemon that dies after page load."""
    code = _code(PANEL)
    assert "HEALTH_POLL_MS" in code
    assert "5000" in code
    assert "setInterval(" in code
    assert "clearInterval(" in code, "a leaked interval keeps polling after unmount"


def test_the_poll_is_aborted_on_unmount():
    """
    A resolved poll must not call setState on an unmounted component.

    Without the abort the loop also keeps polling for its full 10-minute budget after the user
    navigates away.
    """
    code = _code(PANEL)
    assert "AbortController(" in code
    assert ".abort()" in code
    assert "signal:" in code
