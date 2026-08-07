import os
import tempfile
import time
import pytest
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService
from src.backend.services.watcher_service import WatcherService, WatcherMode, CorpBrainWatcherHandler
from watchdog.events import FileModifiedEvent, FileMovedEvent


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

        watcher = WatcherService(db_mgr, file_repo)
        yield watcher, db_mgr, file_repo, ws_id, tmpdir, f1, f1_id
        watcher.close()
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
