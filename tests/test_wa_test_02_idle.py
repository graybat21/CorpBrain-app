"""
WA-TEST-02 (issue #60) — idle-mode batch processing (TC-WATCH-004).

`WatcherMode.IDLE` existed as an enum value with **no behaviour**: it set `is_enabled=1` exactly
like `realtime` and processed events the same way. So the AC had nothing to test, and idle mode was
a label rather than a feature. The implementation lands with these tests.

Two decisions worth stating, because they are the kind a reader would otherwise assume were
oversights:

- **Activity is reported, not sniffed.** The backend cannot see keyboard or mouse input without an
  OS-level hook, and on Windows a global hook is indistinguishable from a keylogger to a security
  auditor (CON-03). `notify_user_activity()` is called by the frontend.
- **Time is injected.** REQ-FUNC-026's threshold is 5 minutes; a sleep-based test would take five
  minutes and still be flaky on a loaded runner. The DoD asks for "타이머 Mock 기반 재현 가능",
  which is this.
"""

import os
import tempfile
import uuid

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.watcher_service import WatcherMode, WatcherService

T0 = 1_700_000_000.0
FIVE_MINUTES = 300.0


class CountingAnalysis:
    """
    Stands in for DeepAnalysisService, recording which files it was asked to process.

    Only the analysis is faked — the queue, the idle decision, the interruption check and the
    per-workspace accounting are all real. Faking the queue would leave nothing under test.
    """

    def __init__(self):
        self.processed: list = []

    def process_single_file(self, record):
        self.processed.append(record.get("current_path"))
        return {"status": "ok", "chunks": 1}

    def delete_file_vectors(self, workspace_id, file_id):
        return None

    def update_folder_wiki(self, *args, **kwargs):
        return None


@pytest.fixture
def idle_env():
    """A workspace in idle mode with 10 real files already queued (AC S1's fixture)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "idle.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Idle WS", [root])["workspace_id"]

            analysis = CountingAnalysis()
            service = WatcherService(
                db_mgr, file_repo, deep_analysis_service=analysis, idle_threshold_sec=FIVE_MINUTES
            )

            # The files are created and enqueued BEFORE the mode is set, because
            # `update_config` starts a real watchdog observer on the root — and that observer
            # then sees this fixture's own writes and enqueues them a second time. Correct
            # product behaviour; wrong for a fixture that wants exactly 10 known events.
            paths = []
            for i in range(10):
                path = os.path.join(root, f"문서{i}.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"내용 {i}")
                file_repo.bulk_upsert([{
                    "file_id": str(uuid.uuid4()), "workspace_id": ws_id,
                    "current_path": path, "original_path": path,
                    "file_name": os.path.basename(path), "extension": ".txt",
                    "size_bytes": 5, "last_modified": os.path.getmtime(path),
                    "parse_status": "pending", "importance_score": 0,
                }])
                service.enqueue_file_event(ws_id, None, "modified", path)
                paths.append(path)

            service.update_config(ws_id, WatcherMode.IDLE.value)
            # Suppress the observer for the rest of the test: `process_single_file` does not write
            # to disk here, but the analysis in production does, and a live observer would turn
            # this into a feedback loop rather than a deterministic 10-item flush.
            service.suppress_events = True
            service.notify_user_activity(at=T0)
            yield service, ws_id, analysis, paths
        finally:
            for workspace in list(service._observers):
                service.stop_observing(workspace)
            db_mgr.close()


# --- AC Scenario 1: idle entry flushes the backlog ---------------------------------------


def test_scenario_1_ten_queued_events_flush_once_idle(idle_env):
    """
    AC S1: 5 minutes with no input, 10 accumulated events, all flushed in one pass.

    One pass, not one per poll — the point of idle mode is to do the work while the machine is
    free, and trickling it out would leave the backlog outliving the idle window.
    """
    service, ws_id, analysis, paths = idle_env
    assert service.queued_count(ws_id) == 10

    result = service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES)

    assert result["status"] == "flushed"
    assert result["processed"] == 10
    assert result["remaining"] == 0
    assert len(analysis.processed) == 10


def test_nothing_is_processed_before_the_threshold(idle_env):
    """
    Idle mode must not run while the user is working — that is the whole distinction from
    realtime, which is the other mode available.
    """
    service, ws_id, analysis, paths = idle_env

    result = service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES - 1)

    assert result["status"] == "not_idle"
    assert result["processed"] == 0
    assert result["remaining"] == 10
    assert analysis.processed == []


def test_the_threshold_boundary_is_inclusive(idle_env):
    """
    Exactly 5 minutes counts as idle (`>=`).

    Pinned because an exclusive comparison here would make the flush depend on poll jitter — it
    would work most of the time and occasionally wait an extra interval for no reason.
    """
    service, ws_id, analysis, paths = idle_env

    assert service.is_idle(now=T0 + FIVE_MINUTES) is True
    assert service.is_idle(now=T0 + FIVE_MINUTES - 0.001) is False


def test_reported_activity_resets_the_clock(idle_env):
    """A keystroke restarts the 5 minutes; otherwise idle would arrive mid-typing."""
    service, ws_id, analysis, paths = idle_env

    assert service.is_idle(now=T0 + FIVE_MINUTES) is True
    service.notify_user_activity(at=T0 + FIVE_MINUTES)
    assert service.is_idle(now=T0 + FIVE_MINUTES) is False
    assert service.is_idle(now=T0 + 2 * FIVE_MINUTES) is True


# --- AC Scenario 2: activity interrupts an in-flight flush -------------------------------


def test_scenario_2_activity_mid_flush_stops_processing(idle_env):
    """
    AC S2: the user starts typing partway through, so processing stops and the rest stays queued.

    The check runs before **each** item, not once at the start. A flush of ten documents can take
    minutes, and checking only up front would ignore input for that entire time — which is the
    behaviour this AC exists to forbid.
    """
    service, ws_id, analysis, paths = idle_env

    # Process 3, then the user returns.
    first = service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES, max_items=3)
    assert first["processed"] == 3
    assert first["remaining"] == 7

    service.notify_user_activity(at=T0 + FIVE_MINUTES)
    resumed = service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES)

    assert resumed["status"] == "not_idle"
    assert resumed["processed"] == 0
    assert resumed["remaining"] == 7, "the remaining events must stay queued, not be dropped"
    assert len(analysis.processed) == 3


def test_activity_during_a_flush_stops_it_mid_batch(idle_env):
    """
    The per-item check, exercised for real — activity arrives WHILE the loop is running.

    A mutation run exposed that the other AC S2 test does not cover this: it reports activity
    *between* calls, so removing the per-item re-check left it green. Interruption is asserted here
    by reporting activity from inside the analysis callback, which is the only way to land it
    mid-loop without threads.

    Without the per-item check the flush would process all 10 despite the user having returned
    after the 2nd — which on a real machine means minutes of contention the AC forbids.
    """
    service, ws_id, analysis, paths = idle_env
    now = T0 + FIVE_MINUTES

    original = analysis.process_single_file
    calls = {"n": 0}

    def interrupting(record):
        calls["n"] += 1
        result = original(record)
        if calls["n"] == 2:
            # The user touches the keyboard while item 2 is being analysed.
            service.notify_user_activity(at=now)
        return result

    analysis.process_single_file = interrupting

    result = service.flush_idle_queue(ws_id, now=now)

    assert result["status"] == "interrupted", "the flush must stop when activity is reported"
    assert result["processed"] == 2, f"processed {result['processed']} items after interruption"
    assert result["remaining"] == 8
    assert len(analysis.processed) == 2


def test_an_interrupted_flush_resumes_where_it_stopped(idle_env):
    """
    The queue is a backlog, not a snapshot: nothing may be lost to an interruption.

    Dropping the remainder would silently leave documents unanalysed, which the user would only
    discover as a wiki missing files.
    """
    service, ws_id, analysis, paths = idle_env

    service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES, max_items=4)
    service.notify_user_activity(at=T0 + FIVE_MINUTES)
    # ...the user goes away again.
    final = service.flush_idle_queue(ws_id, now=T0 + 2 * FIVE_MINUTES)

    assert final["status"] == "flushed"
    assert final["remaining"] == 0
    assert len(analysis.processed) == 10, "every queued file must eventually be processed"
    assert sorted(analysis.processed) == sorted(paths)


def test_a_flush_only_touches_its_own_workspace(idle_env):
    """
    The queue is process-wide, so a flush must not drain another workspace's events.

    Same defect class as the badge count in issue #58 — a shared queue read without a filter.
    """
    service, ws_id, analysis, paths = idle_env
    other_ws = WorkspaceRepository(service.db_mgr).create(
        "Other", [tempfile.mkdtemp()]
    )["workspace_id"]
    service.enqueue_file_event(other_ws, None, "modified", "/elsewhere/x.txt")

    result = service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES)

    assert result["processed"] == 10
    assert service.queued_count(other_ws) == 1, "another workspace's backlog was consumed"


def test_an_empty_queue_flushes_cleanly(idle_env):
    """Idle with nothing to do must report success, not an error or a hang."""
    service, ws_id, analysis, paths = idle_env
    service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES)

    again = service.flush_idle_queue(ws_id, now=T0 + FIVE_MINUTES)

    assert again["status"] == "flushed"
    assert again["processed"] == 0


def test_the_default_threshold_is_five_minutes():
    """
    REQ-FUNC-026's default, pinned so it cannot drift silently.

    The fixture injects it explicitly, so without this test the shipped default would be
    unverified.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "d.db"))
        try:
            service = WatcherService(db_mgr, FileRepository(db_mgr))
            assert service.idle_threshold_sec == 300.0
        finally:
            db_mgr.close()


def test_a_fresh_service_is_not_immediately_idle():
    """
    A just-launched app has an active user.

    Initialising the activity clock to 0 would make the first poll see ~50 years of idleness and
    flush the whole backlog while the user is still looking at the window.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "d.db"))
        try:
            service = WatcherService(db_mgr, FileRepository(db_mgr))
            assert service.is_idle() is False
        finally:
            db_mgr.close()


# --- The endpoint -----------------------------------------------------------------------


def test_the_endpoint_reports_activity_and_flushes(idle_env):
    """
    `active=true` pauses; `active=false` attempts a flush.

    Synchronous rather than a DEC-04 task: it processes a few items per call and the frontend is
    already polling, so a task id would add a second poll for nothing.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    service, ws_id, analysis, paths = idle_env
    app = create_app(service.db_mgr, session_token="idle-token")
    app.state.watcher_service = service
    client = TestClient(app)
    headers = {"Authorization": "Bearer idle-token"}

    # Reporting activity resets the clock and reports the untouched backlog.
    res = client.post(
        f"/api/v1/workspace/{ws_id}/watcher/idle-flush",
        params={"active": "true"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["status"] == "interrupted"
    assert data["remaining"] == 10
    assert analysis.processed == []

    # Without activity, the real clock has not reached the threshold either.
    res2 = client.post(
        f"/api/v1/workspace/{ws_id}/watcher/idle-flush", headers=headers
    )
    assert res2.json()["data"]["status"] == "not_idle"


def test_the_generated_api_path_key_is_a_valid_identifier():
    """
    A hyphenated route must not break the generated TypeScript.

    `/watcher/idle-flush` produced `POST_workspace_watcher_idle-flush`, which is a legal URL and an
    illegal TS identifier — so `tsc` failed with `TS1005: ',' expected` inside a GENERATED file.
    That reads as a generator bug rather than a routing choice and sends the reader to the wrong
    place, so the generator now normalises the key. Pinned here because the next hyphenated route
    would otherwise rediscover it.
    """
    import re as _re
    from pathlib import Path as _Path

    from scripts.gen_api_types import _path_key

    key = _path_key("post", "/api/v1/workspace/{workspace_id}/watcher/idle-flush")
    assert key == "POST_workspace_watcher_idle_flush"
    assert _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key), key

    # And every key actually emitted is a valid identifier.
    types = _Path(__file__).resolve().parent.parent / "src" / "frontend" / "api" / "types.gen.ts"
    for emitted in _re.findall(r"^  (\S+): \"", types.read_text(encoding="utf-8"), flags=_re.M):
        assert _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", emitted), emitted
