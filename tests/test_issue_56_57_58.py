"""
WA-FE-01 / WA-FE-02 / WA-QRY-01 (issues #56, #57, #58) — watcher UI and its status query.

WA-QRY-01's endpoint existed but reported `queue.qsize()` — the **process-wide** queue. So a
workspace with one pending event showed three when two other workspaces were also busy, and that
number drives a badge the user reads as "my files". It was simply wrong, and AC S2 additionally
wants `queue_size: 0` while the watcher is off.

The backend fix is tested for real. The React halves are static source assertions, per
tests/test_ws_fe_01.py — there is no frontend test runner by decision. What they can prove: no
push channel, polling restraint, the four modes, failure feedback. What they cannot: that the
badge renders where a user would look.
"""

import os
import re
import tempfile
from pathlib import Path

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.watcher_service import WatcherService

FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"
CONTROL = FRONTEND / "components" / "WatcherControl.tsx"
TITLE_BAR = FRONTEND / "components" / "TitleBar.tsx"


def _code(path: Path) -> str:
    """Source with comments stripped — same rationale as tests/test_ws_fe_01.py::_code."""
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


@pytest.fixture
def watcher_env():
    """Two workspaces sharing one WatcherService, which is what exposed the bug."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wa.db"))
        try:
            root_a = os.path.join(tmpdir, "a")
            root_b = os.path.join(tmpdir, "b")
            os.makedirs(root_a)
            os.makedirs(root_b)
            repo = WorkspaceRepository(db_mgr)
            ws_a = repo.create("WS A", [root_a])["workspace_id"]
            ws_b = repo.create("WS B", [root_b])["workspace_id"]
            service = WatcherService(db_mgr, FileRepository(db_mgr))
            yield service, db_mgr, ws_a, ws_b
        finally:
            service.stop_all() if hasattr(service, "stop_all") else None
            db_mgr.close()


# --- WA-QRY-01: the queue count is per workspace (issue #58) -----------------------------


def test_the_queue_count_is_scoped_to_the_workspace(watcher_env):
    """
    The defect: `queue.qsize()` is process-wide, so B reported A's pending events as its own.

    Two workspaces on one service is the arrangement that shows it — a single-workspace test
    cannot distinguish a correct count from a global one.
    """
    service, db_mgr, ws_a, ws_b = watcher_env
    service.update_config(ws_a, "realtime")
    service.update_config(ws_b, "realtime")

    service.enqueue_file_event(ws_a, None, "created", "/x/1.txt")
    service.enqueue_file_event(ws_a, None, "created", "/x/2.txt")
    service.enqueue_file_event(ws_b, None, "created", "/y/1.txt")

    assert service.get_status(ws_a)["queued_items_count"] == 2
    assert service.get_status(ws_b)["queued_items_count"] == 1
    # The raw queue holds all three — which is exactly what used to be reported to both.
    assert service.queue.qsize() == 3


def test_scenario_2_a_disabled_watcher_reports_zero(watcher_env):
    """
    AC S2 (#58): `is_active: false`, `queue_size: 0`.

    Zero even if events are still sitting in the queue: nothing is draining them, so showing a
    backlog invites the user to wait for progress that will never come.
    """
    service, db_mgr, ws_a, ws_b = watcher_env
    service.update_config(ws_a, "realtime")
    service.enqueue_file_event(ws_a, None, "created", "/x/1.txt")
    assert service.get_status(ws_a)["queued_items_count"] == 1

    service.update_config(ws_a, "off")
    status = service.get_status(ws_a)

    assert status["is_enabled"] is False
    assert status["queued_items_count"] == 0


def test_scenario_1_the_status_reports_the_selected_mode(watcher_env):
    """AC S1 (#58): mode, activity and depth together."""
    service, db_mgr, ws_a, ws_b = watcher_env
    service.update_config(ws_a, "realtime")
    for i in range(3):
        service.enqueue_file_event(ws_a, None, "created", f"/x/{i}.txt")

    status = service.get_status(ws_a)

    assert status["mode"] == "realtime"
    assert status["is_enabled"] is True
    assert status["queued_items_count"] == 3
    assert status["workspace_id"] == ws_a


@pytest.mark.parametrize("mode,enabled", [
    ("manual", False),
    ("off", False),
    ("realtime", True),
    ("idle", True),
])
def test_all_four_modes_round_trip(watcher_env, mode, enabled):
    """
    REQ-FUNC-023's four modes, and which of them actually watch.

    `manual` and `off` are both inactive but distinct: manual means "analyse when I ask", off
    means "do not watch at all". Collapsing them would remove a user's ability to say either.
    """
    service, db_mgr, ws_a, ws_b = watcher_env
    service.update_config(ws_a, mode)

    status = service.get_status(ws_a)
    assert status["mode"] == mode
    assert status["is_enabled"] is enabled


def test_an_invalid_mode_is_rejected(watcher_env):
    """A typo must not silently disable watching."""
    service, db_mgr, ws_a, ws_b = watcher_env
    with pytest.raises(ValueError):
        service.update_config(ws_a, "realtme")


def test_the_status_endpoint_returns_the_scoped_count(watcher_env):
    """The route must use get_status; reading qsize() there was the original bug."""
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    service, db_mgr, ws_a, ws_b = watcher_env
    app = create_app(db_mgr, session_token="wa-token")
    headers = {"Authorization": "Bearer wa-token"}
    client = TestClient(app)

    # The app builds its own WatcherService, so enqueue through that one.
    app.state.watcher_service = service
    service.update_config(ws_a, "realtime")
    service.update_config(ws_b, "realtime")
    service.enqueue_file_event(ws_b, None, "created", "/y/1.txt")
    service.enqueue_file_event(ws_b, None, "created", "/y/2.txt")

    res = client.get(f"/api/v1/workspace/{ws_a}/watcher/status", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["queued_items_count"] == 0, "workspace A has no pending events of its own"

    res_b = client.get(f"/api/v1/workspace/{ws_b}/watcher/status", headers=headers)
    assert res_b.json()["data"]["queued_items_count"] == 2


# --- WA-FE-01 / WA-FE-02 (static) -------------------------------------------------------


def test_no_push_channel_is_used():
    """
    DEC-04: WebSocket and SSE do not exist by design. #57 explicitly rules out a broadcast
    receiver, so the update signal must come from a polling response.
    """
    code = _code(CONTROL)
    for banned in ("WebSocket", "EventSource", "socket.io", "sse"):
        assert banned not in code, f"{banned} violates DEC-04"
    assert "setInterval(" in code
    assert "clearInterval(" in code, "a leaked interval keeps polling after unmount"


def test_the_wiki_update_toast_comes_from_a_timestamp_comparison():
    """
    AC S1 (#57): a background update is detected by `updated_at` moving between polls.

    The first observation only records a baseline — announcing an update on page load would claim
    something happened when nothing did.
    """
    code = _code(CONTROL)
    assert "updated_at" in code
    assert "lastWikiUpdate" in code
    assert "위키가 최신화되었습니다" in code
    # The baseline guard must exist, or every first poll fires a toast.
    assert "lastWikiUpdate.current === null" in code


def test_polling_is_restrained_for_inactive_modes():
    """
    REQ-NF-002 caps idle cost. `manual`/`off` watch nothing, so polling them is pure waste.

    Also pins the interval: 3s, not DEC-04's 1s. That 1s is for a task the user is waiting on; an
    ambient badge at 1s triples the wakeups for no visible benefit.
    """
    code = _code(CONTROL)
    assert "ACTIVE_MODES" in code
    assert "STATUS_POLL_MS = 3000" in code
    assert "ACTIVE_MODES.has(" in code


def test_the_four_modes_are_offered():
    """REQ-FUNC-023: 수동/실시간/유휴/끄기, matching the backend enum exactly."""
    code = _code(CONTROL)
    for value in ("'off'", "'manual'", "'idle'", "'realtime'"):
        assert value in code, value
    for label in ("끄기", "수동", "유휴", "실시간"):
        assert label in code, label


def test_mode_change_calls_the_command_api_and_reports_both_outcomes():
    """
    AC S1 (#56) and the DoD: success AND failure get a toast.

    A silent failure leaves the select displaying a mode the backend never accepted, which is
    worse than an error — the user believes watching is on when it is not.
    """
    code = _code(CONTROL)
    assert "api.setWatcherConfig(" in code

    handler = code[code.index("const handleModeChange"):code.index("if (!currentWorkspace)")]
    assert "addToast('success'" in handler
    assert "addToast('error'" in handler
    assert "변경 실패" in handler


def test_a_failed_status_poll_does_not_toast():
    """
    The 3s poll must fail silently.

    A toast per failed poll would stack an identical error every 3 seconds while the backend is
    briefly unavailable, burying every other notification — the same mistake issue #31 fixed for
    the 5s health probe.
    """
    code = _code(CONTROL)
    poll_body = code[code.index("const poll = useCallback"):code.index("useEffect(() => {\n    if (!workspaceId)")]
    assert "catch {" in poll_body
    assert "addToast('error'" not in poll_body


def test_the_queue_badge_is_hidden_at_zero():
    """A permanent "0" beside the icon is noise; the badge is a signal or nothing."""
    code = _code(CONTROL)
    assert "queued > 0 &&" in code
    assert "queued_items_count" in code


def test_status_is_conveyed_as_text_not_only_colour():
    """
    A green/grey icon is unreadable for a colour-blind user and invisible to a screen reader.

    Separate from contrast — the criterion is "do not use colour as the only cue".
    """
    code = _code(CONTROL)
    assert "감시 중" in code
    assert "중지" in code
    assert "aria-label" in code


def test_the_control_is_mounted_in_the_header():
    """AC S2 (#56) puts the badge beside the watcher icon, visible from any page."""
    title_bar = _code(TITLE_BAR)
    assert "<WatcherControl />" in title_bar


def test_the_baseline_resets_when_the_workspace_changes():
    """
    Another workspace's timestamps say nothing about this one.

    Carrying them over would fire a spurious "위키가 최신화되었습니다" on every workspace switch.
    """
    code = _code(CONTROL)
    reset = code[code.index("useEffect(() => {\n    lastWikiUpdate.current = null"):]
    assert "[workspaceId]" in reset[:400]
