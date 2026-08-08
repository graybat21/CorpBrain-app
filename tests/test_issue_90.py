"""
Regression tests for issue #90: GET .../rename/diff always 500.

Issue #90 reported that RenameQueryService.get_pending_rename_diff queries Rename_History.status,
but that column never existed in the v001 schema. Additionally, the method tried to call .get()
on the stored path strings as if they were dicts. Both are fixed by:
  - Migration v003 adds the status column with DEFAULT 'pending'.
  - RenameService.generate_rename_diff now INSERTs status='pending'.
  - RenameService.apply_rename_diff now UPDATEs status to 'applied' or 'multi_status'.
  - RenameQueryService.get_pending_rename_diff now correctly parses the JSON string arrays and
    re-resolves file_id from File_Meta by current_path (same pattern as apply_rename_diff L206).

What these tests prove:
  - The schema migration runs cleanly and adds the status column.
  - Generating a diff persists status='pending' and the query returns it.
  - Applying a diff updates the row to status='applied'.
  - The returned diff structure matches PendingRenameDiffItemRes (file_id, old_name, new_name,
    history_id, status).
  - A file that was deleted between generate and query shows file_id=None rather than crashing.
"""

import os
import tempfile
import uuid

from src.backend.db import DatabaseManager
from src.backend.services.query_services import RenameQueryService
from src.backend.services.rename_service import RenameService
from tests.fakes import insert_workspace


def test_status_column_exists_after_migration():
    """Migration v003 adds Rename_History.status with DEFAULT 'pending'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "issue90.db"))
        try:
            conn = db_mgr.get_connection()
            # PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk).
            cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(Rename_History);")}
            assert "status" in cols
            assert cols["status"]["type"] == "TEXT"
            assert cols["status"]["notnull"] == 1  # NOT NULL
            assert cols["status"]["dflt_value"] == "'pending'"
        finally:
            db_mgr.close()


def test_generate_diff_persists_status_pending():
    """RenameService.generate_rename_diff writes status='pending' to the DB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "issue90.db"))
        try:
            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            insert_workspace(conn, ws_id, "test-ws", tmpdir)
            file_id = str(uuid.uuid4())
            file_path = os.path.join(tmpdir, "old_name.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("test")
            conn.execute(
                """INSERT INTO File_Meta (file_id, workspace_id, current_path, original_path, file_name,
                   extension, size_bytes, last_modified) VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
                (file_id, ws_id, file_path, file_path, "old_name.txt", ".txt", 4, 0.0)
            )

            svc = RenameService(db_mgr)
            # Mock the LLM call — we're testing DB persistence, not inference.
            def fake_llm(filename):
                return "suggested_name.txt"

            files = [{
                "file_id": file_id,
                "file_name": "old_name.txt",
                "current_path": file_path,
                "extension": ".txt"
            }]
            svc.generate_rename_diff(ws_id, files, mock_llm_callback=fake_llm)

            # Check the Rename_History row.
            cursor = conn.cursor()
            cursor.execute("SELECT status, old_paths, new_paths FROM Rename_History WHERE workspace_id = ?;", (ws_id,))
            row = cursor.fetchone()
            assert row is not None
            assert row["status"] == "pending"
            # The paths are JSON string arrays, not object arrays.
            import json
            old_paths = json.loads(row["old_paths"])
            new_paths = json.loads(row["new_paths"])
            assert isinstance(old_paths, list)
            assert isinstance(old_paths[0], str)
            assert old_paths[0] == file_path
            assert new_paths[0].endswith("suggested_name.txt")
        finally:
            db_mgr.close()


def test_get_pending_rename_diff_returns_correct_structure():
    """RenameQueryService.get_pending_rename_diff returns the DTO-compatible structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "issue90.db"))
        try:
            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            insert_workspace(conn, ws_id, "test-ws", tmpdir)
            file_id = str(uuid.uuid4())
            file_path = os.path.join(tmpdir, "old.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("test")
            conn.execute(
                """INSERT INTO File_Meta (file_id, workspace_id, current_path, original_path, file_name,
                   extension, size_bytes, last_modified) VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
                (file_id, ws_id, file_path, file_path, "old.txt", ".txt", 4, 0.0)
            )

            # Manually insert a pending Rename_History row (bypassing LLM).
            import json
            history_id = str(uuid.uuid4())
            new_path = os.path.join(tmpdir, "new.txt")
            conn.execute(
                """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
                   VALUES (?, ?, ?, ?, ?);""",
                (history_id, ws_id, json.dumps([file_path]), json.dumps([new_path]), "pending")
            )

            svc = RenameQueryService(db_mgr)
            diff = svc.get_pending_rename_diff(ws_id)

            assert len(diff) == 1
            item = diff[0]
            # PendingRenameDiffItemRes fields: file_id, old_name, new_name, history_id, status.
            assert item["file_id"] == file_id
            assert item["old_name"] == "old.txt"
            assert item["new_name"] == "new.txt"
            assert item["history_id"] == history_id
            assert item["status"] == "pending"
        finally:
            db_mgr.close()


def test_apply_updates_status_to_applied():
    """RenameService.apply_rename_diff updates the row status to 'applied' on success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "issue90.db"))
        try:
            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            insert_workspace(conn, ws_id, "test-ws", tmpdir)
            file_id = str(uuid.uuid4())
            old_path = os.path.join(tmpdir, "old.txt")
            with open(old_path, "w", encoding="utf-8") as f:
                f.write("test")
            conn.execute(
                """INSERT INTO File_Meta (file_id, workspace_id, current_path, original_path, file_name,
                   extension, size_bytes, last_modified) VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
                (file_id, ws_id, old_path, old_path, "old.txt", ".txt", 4, 0.0)
            )

            import json
            history_id = str(uuid.uuid4())
            new_path = os.path.join(tmpdir, "new.txt")
            conn.execute(
                """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
                   VALUES (?, ?, ?, ?, ?);""",
                (history_id, ws_id, json.dumps([old_path]), json.dumps([new_path]), "pending")
            )

            svc = RenameService(db_mgr)
            result = svc.apply_rename(ws_id, items=None, history_id=history_id)

            assert result["status"] == "applied"
            assert result["applied_count"] == 1

            # Check the DB row was updated.
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM Rename_History WHERE history_id = ?;", (history_id,))
            row = cursor.fetchone()
            assert row["status"] == "applied"
        finally:
            db_mgr.close()


def test_missing_file_shows_file_id_none_not_crash():
    """A file deleted between generate and query returns file_id=None, not AttributeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "issue90.db"))
        try:
            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            insert_workspace(conn, ws_id, "test-ws", tmpdir)

            # Insert a Rename_History row referencing a path with no File_Meta row.
            import json
            history_id = str(uuid.uuid4())
            phantom_path = os.path.join(tmpdir, "phantom.txt")
            conn.execute(
                """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
                   VALUES (?, ?, ?, ?, ?);""",
                (history_id, ws_id, json.dumps([phantom_path]), json.dumps([os.path.join(tmpdir, "new.txt")]), "pending")
            )

            svc = RenameQueryService(db_mgr)
            diff = svc.get_pending_rename_diff(ws_id)

            assert len(diff) == 1
            assert diff[0]["file_id"] is None  # Not a crash, just None.
            assert diff[0]["old_name"] == "phantom.txt"
            assert diff[0]["status"] == "pending"
        finally:
            db_mgr.close()
