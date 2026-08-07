import os
import sqlite3
import tempfile
import uuid
import pytest
from src.backend.db import DatabaseManager


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_corpbrain.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        yield db_mgr
        db_mgr.close()


def test_scenario_1_schema_creation_and_8_tables(temp_db):
    conn = temp_db.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "Workspace_Meta",
        "File_Meta",
        "Wiki_Content",
        "Rename_History",
        "Analytics_Log",
        "Watcher_Config",
        "App_Config",
        "Async_Task",
    }

    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    cursor.execute("PRAGMA user_version;")
    version = cursor.fetchone()[0]
    assert version >= 1


def test_scenario_2_pragmas_and_basic_crud(temp_db):
    conn = temp_db.get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode;")
    assert cursor.fetchone()[0].lower() == "wal"

    cursor.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1

    cursor.execute("PRAGMA busy_timeout;")
    assert cursor.fetchone()[0] == 5000

    ws_id = str(uuid.uuid4())
    with temp_db.transaction() as tx:
        tx.execute(
            "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
            (ws_id, "Test Workspace", "C:\\TestDir"),
        )

    cursor.execute("SELECT workspace_name FROM Workspace_Meta WHERE workspace_id = ?;", (ws_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["workspace_name"] == "Test Workspace"


def test_scenario_3_interrupted_task_recovery(temp_db):
    ws_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())

    with temp_db.transaction() as tx:
        tx.execute(
            "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
            (ws_id, "Test WS", "C:\\TestDir2"),
        )
        tx.execute(
            "INSERT INTO Async_Task (task_id, workspace_id, task_type, status) VALUES (?, ?, ?, ?);",
            (task_id, ws_id, "deep_analysis", "running"),
        )

    # Re-trigger recovery logic as happens at boot
    temp_db.recover_interrupted_tasks()

    conn = temp_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM Async_Task WHERE task_id = ?;", (task_id,))
    assert cursor.fetchone()["status"] == "interrupted"


def test_scenario_4_cascade_delete(temp_db):
    ws_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    wiki_id = str(uuid.uuid4())

    with temp_db.transaction() as tx:
        tx.execute(
            "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
            (ws_id, "Cascade WS", "C:\\CascadeDir"),
        )
        tx.execute(
            """INSERT INTO File_Meta 
               (file_id, workspace_id, current_path, original_path, file_name, extension, size_bytes, last_modified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
            (file_id, ws_id, "C:\\CascadeDir\\f1.txt", "C:\\CascadeDir\\f1.txt", "f1.txt", ".txt", 100, 1.0),
        )
        tx.execute(
            """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
               VALUES (?, ?, ?, ?);""",
            (wiki_id, ws_id, "folder1", "# Wiki Content"),
        )

    # Delete workspace
    with temp_db.transaction() as tx:
        tx.execute("DELETE FROM Workspace_Meta WHERE workspace_id = ?;", (ws_id,))

    conn = temp_db.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM File_Meta WHERE workspace_id = ?;", (ws_id,))
    assert cursor.fetchone()[0] == 0

    cursor.execute("SELECT COUNT(*) FROM Wiki_Content WHERE workspace_id = ?;", (ws_id,))
    assert cursor.fetchone()[0] == 0


def test_scenario_5_timestamp_utc_iso_format(temp_db):
    ws_id = str(uuid.uuid4())
    wiki_id = str(uuid.uuid4())

    with temp_db.transaction() as tx:
        tx.execute(
            "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
            (ws_id, "TS WS", "C:\\TSDir"),
        )
        tx.execute(
            """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
               VALUES (?, ?, ?, ?);""",
            (wiki_id, ws_id, "depth1", "# Original"),
        )

    conn = temp_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT created_at, updated_at FROM Wiki_Content WHERE wiki_id = ?;", (wiki_id,))
    row = cursor.fetchone()
    assert row["created_at"].endswith("Z")
    assert row["updated_at"].endswith("Z")
