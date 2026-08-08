import os
import tempfile
import time

import pytest
from watchdog.events import FileModifiedEvent, FileMovedEvent

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService
from src.backend.services.vector_service import DeepAnalysisService, VectorDBManager
from src.backend.services.watcher_service import CorpBrainWatcherHandler, WatcherService
from tests.fakes import FakeEmbeddingFunction


@pytest.fixture
def wa_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "wa_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)

        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)
        scanner = ScannerService(file_repo)

        ws_res = ws_repo.create("Watcher Test WS", tmpdir)
        ws_id = ws_res["workspace_id"]

        f1 = os.path.join(tmpdir, "watch_doc1.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("CorpBrain Watcher Initial Content 1.\n")

        scanner.scan_workspace(ws_id, tmpdir)
        scanned = file_repo.list_by_workspace(ws_id)
        f1_rec = next(r for r in scanned if r["file_name"] == "watch_doc1.txt")
        f1_id = f1_rec["file_id"]

        # Scenario 4 drives the real embedding path, so inject a workspace-bound manager over
        # a real Chroma store in the tmpdir. A default DeepAnalysisService would now build its
        # own manager and reach for the real Ollama daemon.
        v_db = VectorDBManager(
            workspace_id=ws_id,
            persist_dir=db_mgr.vectors_dir,
            embedding_function=FakeEmbeddingFunction(),
        )
        analysis = DeepAnalysisService(db_mgr, vector_db=v_db)
        watcher = WatcherService(db_mgr, file_repo, deep_analysis_service=analysis)

        yield watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id

        watcher.close()
        v_db.close()  # before TemporaryDirectory teardown (WinError 32)
        db_mgr.close()


def test_scenario_1_watcher_mode_config_persistence(wa_setup):
    watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id = wa_setup

    # Default is realtime from initial schema
    cfg0 = watcher.get_config(ws_id)
    assert cfg0["mode"] in ["realtime", "manual"]

    # Change to manual
    cfg_man = watcher.update_config(ws_id, mode="manual")
    assert cfg_man["mode"] == "manual"
    assert cfg_man["is_enabled"] == 0

    # Change to realtime
    cfg1 = watcher.update_config(ws_id, mode="realtime", debounce_ms=1000)
    assert cfg1["mode"] == "realtime"
    assert cfg1["is_enabled"] == 1
    assert cfg1["debounce_ms"] == 1000

    # Change to idle
    cfg2 = watcher.update_config(ws_id, mode="idle")
    assert cfg2["mode"] == "idle"

    # Change to off
    cfg3 = watcher.update_config(ws_id, mode="off")
    assert cfg3["mode"] == "off"
    assert cfg3["is_enabled"] == 0

    # Verify DB persistence
    conn = db_mgr.get_connection()
    row = conn.cursor().execute("SELECT is_enabled FROM Watcher_Config WHERE workspace_id = ?;", (ws_id,)).fetchone()
    assert row["is_enabled"] == 0


def test_scenario_2_watchdog_event_handler_debounce_and_mtime_touch_filtering(wa_setup):
    watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id = wa_setup

    # Set debounce_ms=0 to test mtime touch filtering without debouncing interference
    handler = CorpBrainWatcherHandler(watcher, ws_id, debounce_ms=0)
    evt = FileModifiedEvent(f1)

    # 1. Attribute touch with identical mtime -> Skip event
    handler.on_modified(evt)
    assert watcher.queue.qsize() == 0

    # 2. Actual file content modification with future mtime -> Enqueue
    with open(f1, "a", encoding="utf-8") as f:
        f.write("Appended line.\n")
    # Touch mtime in OS
    new_mtime = time.time() + 100.0
    os.utime(f1, (new_mtime, new_mtime))

    handler.on_modified(evt)
    assert watcher.queue.qsize() == 1

    item = watcher.queue.get()
    assert item["file_id"] == f1_id
    assert item["event_type"] == "modified"


def test_scenario_3_file_moved_event_preserves_file_id(wa_setup):
    watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id = wa_setup

    handler = CorpBrainWatcherHandler(watcher, ws_id)
    new_f1 = os.path.join(tmpdir, "moved_watch_doc1.txt")
    os.rename(f1, new_f1)

    move_evt = FileMovedEvent(f1, new_f1)
    handler.on_moved(move_evt)

    # DEC-08: Check File_Meta.current_path updated while preserving existing file_id
    conn = db_mgr.get_connection()
    row = conn.cursor().execute(f"SELECT current_path, file_name FROM File_Meta WHERE file_id = '{f1_id}';").fetchone()

    assert row["current_path"] == new_f1
    assert row["file_name"] == "moved_watch_doc1.txt"


def test_scenario_5_deleted_file_vectors_are_cleaned_up(wa_setup):
    """
    DEC-09: a file gone from disk must have its vectors dropped, not just be skipped.

    The old early-return leaked an orphan vector set on every deletion. That was invisible
    while the store was in-memory; with a persisted store the orphans keep surfacing in
    search results.
    """
    watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id = wa_setup
    vector_db = watcher.deep_analysis_service.vector_db

    with open(f1, "w", encoding="utf-8") as f:
        f.write("Content that will be indexed then deleted.\n" * 20)

    watcher.enqueue_file_event(ws_id, f1_id, "modified", f1)
    watcher.process_next_queued_item()
    assert vector_db.count_chunks(f1_id) > 0

    os.remove(f1)
    watcher.enqueue_file_event(ws_id, f1_id, "deleted", f1)
    res = watcher.process_next_queued_item()

    assert res["status"] == "file_not_found"
    assert vector_db.count_chunks(f1_id) == 0


def test_scenario_4_incremental_reanalysis_queue_processing(wa_setup):
    watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id = wa_setup

    with open(f1, "w", encoding="utf-8") as f:
        f.write("CorpBrain Deep Analysis Watcher Content Line 1.\n" * 20)

    watcher.enqueue_file_event(ws_id, f1_id, "modified", f1)
    assert watcher.queue.qsize() == 1

    res = watcher.process_next_queued_item()
    assert res["status"] == "processed"
    assert res["file_id"] == f1_id
    assert res["chunks_processed"] > 0

    # Verify parse_status updated in SQLite
    conn = db_mgr.get_connection()
    status = conn.cursor().execute(f"SELECT parse_status FROM File_Meta WHERE file_id = '{f1_id}';").fetchone()[0]
    assert status == "parsed"


def test_issue_84_watcher_registers_new_file_with_uuid(wa_setup):
    """
    Regression test for issue #84: watcher must use str(uuid.uuid4()) for file_id, not
    f"file_{timestamp}". The latter breaks deeplink anchors (which expect 36-char UUID) and
    violates DEC-11.
    """
    watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id = wa_setup

    # Create a new file that the watcher has never seen (scanner didn't pick it up).
    new_file = os.path.join(tmpdir, "watcher_new_file.txt")
    with open(new_file, "w", encoding="utf-8") as f:
        f.write("New file content")

    # Enqueue as a 'created' event — the watcher will register it in File_Meta.
    watcher.enqueue_file_event(ws_id, None, "created", new_file)
    result = watcher.process_next_queued_item()

    assert result["status"] == "processed"
    new_file_id = result["file_id"]

    # AC 1: file_id is a 36-char hyphenated lowercase UUID (DEC-11).
    import re
    uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    assert re.match(uuid_pattern, new_file_id), f"file_id '{new_file_id}' is not a valid UUID"

    # AC 2: deeplink anchor pattern can match it (issue #84 impact 1).
    # DeepLinkService.DEEPLINK_PATTERN is r"\[\[file_id:([0-9a-fA-F\-]{36})\]\]".
    # We'll test the extraction part: 36 chars, contains hyphens, hex+hyphens.
    assert len(new_file_id) == 36
    assert "-" in new_file_id
    # A timestamp-based id like "file_1754..." would fail both checks.

    # AC 3: the file is actually in File_Meta with that UUID.
    conn = db_mgr.get_connection()
    row = conn.cursor().execute(
        "SELECT file_id, file_name FROM File_Meta WHERE file_id = ?;", (new_file_id,)
    ).fetchone()
    assert row is not None
    assert row["file_name"] == "watcher_new_file.txt"
