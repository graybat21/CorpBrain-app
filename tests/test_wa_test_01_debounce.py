"""
WA-TEST-01 (issue #59) — watcher debouncing and event filtering (TC-WATCH-002).

`tests/test_wa_cmd_01_02_03.py` has one combined debounce/mtime test. This adds the edge cases the
issue's task breakdown names: the 500ms boundary from both sides, per-path independence, the
attribute-only touch filter, and the suppression flag that stops our own renames from feeding
back into the watcher.

Timing is driven by a patched clock rather than `time.sleep`. Sleeping would make the suite slower
*and* flakier — a 500ms assertion on a loaded CI runner is a coin toss — and the property under
test is "compares against the configured window", not "the OS scheduler is punctual". The one
thing a fake clock cannot prove is REQ-FUNC-024's real-world 1-second latency; that is called out
in the PR rather than faked with a generous sleep.
"""

import os
import tempfile
import uuid
from unittest.mock import patch

import pytest
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.watcher_service import CorpBrainWatcherHandler, WatcherService


@pytest.fixture
def handler_env():
    """A handler over a real workspace with one scanned file, and a real queue to observe."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wa.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Debounce WS", [root])["workspace_id"]

            doc = os.path.join(root, "보고서.docx")
            with open(doc, "w", encoding="utf-8") as f:
                f.write("초안")
            db_mtime = os.path.getmtime(doc)

            file_id = str(uuid.uuid4())
            file_repo.bulk_upsert([{
                "file_id": file_id, "workspace_id": ws_id,
                "current_path": doc, "original_path": doc,
                "file_name": "보고서.docx", "extension": ".docx",
                "size_bytes": 6, "last_modified": db_mtime,
                "parse_status": "parsed", "importance_score": 0,
            }])

            service = WatcherService(db_mgr, file_repo)
            handler = CorpBrainWatcherHandler(service, ws_id, debounce_ms=500)
            yield handler, service, doc, file_id, db_mtime, root
        finally:
            db_mgr.close()


def _drain(service) -> list:
    """Every queued event, removed. Asserting on a count alone hides *which* event landed."""
    items = []
    while not service.queue.empty():
        items.append(service.queue.get_nowait())
    return items


# --- AC Scenario 1: an attribute-only touch is filtered ---------------------------------


def test_scenario_1_an_attribute_only_touch_is_skipped(handler_env):
    """
    AC S1: the mtime did not advance, so nothing is queued.

    This is the case that keeps a `touch`, a backup tool, or an antivirus scan from triggering a
    full re-analysis of an unchanged document.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env

    # mtime equal to what the DB already recorded — an attribute change, not a content change.
    with patch("os.path.getmtime", return_value=db_mtime):
        handler.on_modified(FileModifiedEvent(doc))

    assert _drain(service) == [], "an unchanged file must not be enqueued"


def test_an_older_mtime_is_also_skipped(handler_env):
    """
    A restored-from-backup file can arrive with an *older* mtime.

    `<=`, not `==`: a strict equality check would treat a backup restore as a content change and
    re-analyse a document the DB already holds a newer version of.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env

    with patch("os.path.getmtime", return_value=db_mtime - 60):
        handler.on_modified(FileModifiedEvent(doc))

    assert _drain(service) == []


# --- AC Scenario 2: a real content change is queued -------------------------------------


def test_scenario_2_a_real_modification_is_enqueued(handler_env):
    """
    AC S2: the mtime advanced, so the event is queued for incremental re-analysis.

    Carries the existing `file_id` (DEC-08) — re-registering under a new id would orphan every
    deeplink and analytics row pointing at this file.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env

    with patch("os.path.getmtime", return_value=db_mtime + 10):
        handler.on_modified(FileModifiedEvent(doc))

    queued = _drain(service)
    assert len(queued) == 1
    assert queued[0]["event_type"] == "modified"
    assert queued[0]["file_id"] == file_id, "an existing file must keep its file_id (DEC-08)"
    assert queued[0]["path"] == doc


def test_an_unknown_file_is_enqueued_as_created(handler_env):
    """A file the DB has never seen is a creation, not a modification."""
    handler, service, doc, file_id, db_mtime, root = handler_env
    stranger = os.path.join(root, "외부문서.txt")
    with open(stranger, "w", encoding="utf-8") as f:
        f.write("new")

    handler.on_modified(FileModifiedEvent(stranger))

    queued = _drain(service)
    assert len(queued) == 1
    assert queued[0]["event_type"] == "created"
    assert queued[0]["file_id"] is None


# --- Debounce window --------------------------------------------------------------------


def test_a_second_event_inside_the_window_is_dropped(handler_env):
    """
    The infinite-event-loop guard: an editor writing a file in several chunks emits a burst.

    Without debouncing each write starts an analysis, and the analysis's own writes can emit more
    events — the CPU-pinning loop the constraint names.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env

    with patch("time.time", return_value=1000.0):
        assert handler._should_debounce(doc) is False, "the first event must pass"
    with patch("time.time", return_value=1000.2):  # +200ms, inside 500ms
        assert handler._should_debounce(doc) is True


def test_an_event_after_the_window_passes(handler_env):
    """The window must expire, or one burst would silence a path forever."""
    handler, service, doc, file_id, db_mtime, root = handler_env

    with patch("time.time", return_value=1000.0):
        handler._should_debounce(doc)
    with patch("time.time", return_value=1000.6):  # +600ms, outside 500ms
        assert handler._should_debounce(doc) is False


def test_the_boundary_is_exclusive_at_exactly_the_window(handler_env):
    """
    Exactly 500ms passes — the comparison is `< debounce_ms`.

    Pinned because an off-by-one here is invisible in normal use and only shows up as an
    occasional dropped event.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env

    with patch("time.time", return_value=1000.0):
        handler._should_debounce(doc)
    with patch("time.time", return_value=1000.5):
        assert handler._should_debounce(doc) is False


def test_debouncing_is_per_path_not_global(handler_env):
    """
    Two files changing together must both be seen.

    A global timestamp would let one busy file suppress every other change in the workspace —
    silently, since the events simply never arrive.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env
    other = os.path.join(root, "다른문서.txt")

    with patch("time.time", return_value=1000.0):
        assert handler._should_debounce(doc) is False
        assert handler._should_debounce(other) is False, "a different path must not be debounced"


def test_the_configured_window_is_honoured(handler_env):
    """
    `debounce_ms` comes from Watcher_Config, so a non-default value must actually be used.

    Asserted with 1000ms — the upper end of the 500~1000ms range the constraint allows.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env
    slow = CorpBrainWatcherHandler(service, handler.workspace_id, debounce_ms=1000)

    with patch("time.time", return_value=1000.0):
        slow._should_debounce(doc)
    with patch("time.time", return_value=1000.7):  # inside 1000ms, outside 500ms
        assert slow._should_debounce(doc) is True


# --- Suppression: our own writes must not feed back -------------------------------------


def test_suppressed_events_are_ignored_entirely(handler_env):
    """
    `suppress_events` exists so a rename we performed does not look like a user edit.

    Without it, applying a rename batch emits modify/move events that re-enqueue the same files,
    and the analysis those trigger writes again — the feedback loop the debouncer alone cannot
    stop, because each write is a genuinely new path.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env
    service.suppress_events = True

    with patch("os.path.getmtime", return_value=db_mtime + 100):
        handler.on_modified(FileModifiedEvent(doc))
    handler.on_created(FileCreatedEvent(os.path.join(root, "새파일.txt")))

    assert _drain(service) == [], "suppressed events must not reach the queue"


def test_directory_events_are_ignored(handler_env):
    """
    A directory has no content to analyse, and `os.path.getmtime` on one is meaningless here.

    watchdog emits a directory event for every file operation inside it, so not filtering these
    would double every event.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env

    event = FileModifiedEvent(root)
    event.is_directory = True
    handler.on_modified(event)

    created = FileCreatedEvent(root)
    created.is_directory = True
    handler.on_created(created)

    assert _drain(service) == []


def test_a_vanished_file_does_not_raise(handler_env):
    """
    A file deleted between the event and the mtime read is normal, not exceptional.

    `os.path.getmtime` raises OSError there; letting it propagate would kill the watchdog thread
    and silently end all watching for the session.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env
    ghost = os.path.join(root, "사라진파일.txt")

    handler.on_modified(FileModifiedEvent(ghost))  # must not raise

    assert _drain(service) == []


# --- Move events (DEC-08) ---------------------------------------------------------------


def test_a_move_updates_the_row_without_a_new_file_id(handler_env):
    """
    DEC-08: a move is a single-row UPDATE of `current_path` + `file_name`.

    Re-registering under a new file_id would orphan every deeplink and analytics row — and it
    would be invisible, because the wiki still renders and simply stops resolving.
    """
    handler, service, doc, file_id, db_mtime, root = handler_env
    moved_to = os.path.join(root, "이동된보고서.docx")
    os.rename(doc, moved_to)

    handler.on_moved(FileMovedEvent(doc, moved_to))

    rows = FileRepository(service.db_mgr).list_by_workspace(handler.workspace_id)
    assert len(rows) == 1, "a move must not create a second row"
    assert rows[0]["file_id"] == file_id
    assert rows[0]["current_path"] == moved_to
    assert rows[0]["file_name"] == "이동된보고서.docx"
    # A move is not a content change, so nothing needs re-analysis.
    assert _drain(service) == []


def test_a_file_moved_in_from_outside_is_registered_as_created(handler_env):
    """An unknown source path means the file arrived from outside the workspace."""
    handler, service, doc, file_id, db_mtime, root = handler_env
    outside = os.path.join(root, "..", "외부.txt")
    landed = os.path.join(root, "외부.txt")

    handler.on_moved(FileMovedEvent(outside, landed))

    queued = _drain(service)
    assert len(queued) == 1
    assert queued[0]["event_type"] == "created"
    assert queued[0]["path"] == landed


def test_a_move_with_no_destination_is_ignored(handler_env):
    """watchdog can emit a move event without `dest_path`; it carries nothing to act on."""
    handler, service, doc, file_id, db_mtime, root = handler_env

    event = FileMovedEvent(doc, "")
    handler.on_moved(event)

    assert _drain(service) == []
    rows = FileRepository(service.db_mgr).list_by_workspace(handler.workspace_id)
    assert rows[0]["current_path"] == doc, "the row must be untouched"
