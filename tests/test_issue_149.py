"""
Regression for issue #149 — Watcher_Config.mode missing on databases that predate the column.

The `mode` column was added by editing v001 rather than shipping a migration (a DEC-05
violation), so a database created before that edit is stuck without the column even though its
`user_version` has advanced. Enabling the watcher then wrote to `mode` and raised
`sqlite3.OperationalError: table Watcher_Config has no column named mode` -> HTTP 500.

v008 backfills `mode` via a table rebuild that works whether or not the source table already has
the column. These tests reproduce the exact pre-migration state — a Watcher_Config WITHOUT `mode`
at user_version=7 — because the *current* v001 already carries `mode`, so a DB built from today's
migrations would not reproduce the bug at all.
"""

import os
import shutil
import sqlite3
import tempfile
import uuid

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.services.watcher_service import WatcherService

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")


def _migration_versions(mig_dir):
    return sorted(
        int(f.split("_")[0].lstrip("v"))
        for f in os.listdir(mig_dir)
        if f.startswith("v") and f.endswith(".sql")
    )


def _watcher_columns(db_mgr):
    conn = db_mgr.get_connection()
    return [r[1] for r in conn.execute("PRAGMA table_info(Watcher_Config);")]


def _build_pre_mode_db(tmpdir):
    """
    Produce a database in the exact broken state issue #149 describes: every migration up to v007
    applied (user_version=7) but Watcher_Config lacking the `mode` column, with one live row.

    Built from the REAL v001..v007 files (not a hand-written schema) so it cannot drift from what
    shipped, then the `mode` column is surgically removed to recreate the pre-edit v001 shape that
    old installs actually carry. Returns the workspace_id of the seeded row.
    """
    db_path = os.path.join(tmpdir, "pre_mode.db")

    # 1) Real migrations v001..v007 -> user_version=7 (today's v001 includes `mode`).
    v1_v7_dir = os.path.join(tmpdir, "migrations_v1_v7")
    os.makedirs(v1_v7_dir)
    for f in os.listdir(MIGRATIONS_DIR):
        if f.endswith(".sql") and int(f.split("_")[0].lstrip("v")) <= 7:
            shutil.copy(os.path.join(MIGRATIONS_DIR, f), v1_v7_dir)
    DatabaseManager(db_path=db_path, migrations_dir=v1_v7_dir).close()

    workspace_id = str(uuid.uuid4())

    # 2) Recreate the pre-02abae2 Watcher_Config (no `mode`) and seed a row. isolation_level=None
    #    so the PRAGMA statements run in autocommit exactly like db.py's migration runner does.
    raw = sqlite3.connect(db_path, isolation_level=None)
    try:
        raw.executescript(
            f"""
            INSERT INTO Workspace_Meta (workspace_id, workspace_name)
            VALUES ('{workspace_id}', 'issue-149 레거시');

            PRAGMA foreign_keys = OFF;
            CREATE TABLE Watcher_Config_pre_mode (
                workspace_id TEXT PRIMARY KEY REFERENCES Workspace_Meta(workspace_id) ON DELETE CASCADE,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                debounce_ms INTEGER NOT NULL DEFAULT 500,
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            INSERT INTO Watcher_Config_pre_mode (workspace_id, is_enabled, debounce_ms, updated_at)
            SELECT workspace_id, is_enabled, debounce_ms, updated_at FROM Watcher_Config;
            DROP TABLE Watcher_Config;
            ALTER TABLE Watcher_Config_pre_mode RENAME TO Watcher_Config;
            PRAGMA foreign_keys = ON;

            INSERT INTO Watcher_Config (workspace_id, is_enabled, debounce_ms)
            VALUES ('{workspace_id}', 1, 500);
            """
        )
        raw.execute("PRAGMA wal_checkpoint(FULL);")
    finally:
        raw.close()

    # Sanity: the fixture really is the broken state, or the tests below prove nothing.
    assert "mode" not in _pragma_columns(db_path, "Watcher_Config")
    assert _user_version(db_path) == 7
    return db_path, workspace_id


def _pragma_columns(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table});")]
    finally:
        conn.close()


def _user_version(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA user_version;").fetchone()[0]
    finally:
        conn.close()


def test_v008_backfills_mode_on_a_database_that_predates_the_column():
    """The core regression: a mode-less DB gains `mode` and the write that used to 500 succeeds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, workspace_id = _build_pre_mode_db(tmpdir)

        healed = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
        try:
            conn = healed.get_connection()

            # user_version advanced to the newest migration, and the column now exists.
            assert conn.execute("PRAGMA user_version;").fetchone()[0] == _migration_versions(MIGRATIONS_DIR)[-1]
            assert "mode" in _watcher_columns(healed)

            # The seeded is_enabled=1 row got a mode consistent with the service invariant.
            row = conn.execute(
                "SELECT is_enabled, mode FROM Watcher_Config WHERE workspace_id = ?;",
                (workspace_id,),
            ).fetchone()
            assert row["is_enabled"] == 1
            assert row["mode"] == "realtime"

            # The exact statement that raised OperationalError before now writes cleanly.
            with healed.transaction() as tx:
                tx.execute(
                    "UPDATE Watcher_Config SET mode = 'idle' WHERE workspace_id = ?;",
                    (workspace_id,),
                )
            assert conn.execute(
                "SELECT mode FROM Watcher_Config WHERE workspace_id = ?;", (workspace_id,)
            ).fetchone()["mode"] == "idle"
        finally:
            healed.close()


def test_watcher_update_config_no_longer_500s_after_backfill():
    """
    The service-level crash site: WatcherService.update_config writes `mode`, which raised
    OperationalError -> HTTP 500 on a pre-mode DB. 'idle' with a root-less workspace exercises the
    write without starting a watchdog observer (list_roots is empty, so start_observing is skipped).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, workspace_id = _build_pre_mode_db(tmpdir)
        healed = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
        try:
            svc = WatcherService(healed, FileRepository(healed))
            cfg = svc.update_config(workspace_id, "idle", debounce_ms=700)
            assert cfg["mode"] == "idle"
            # get_config returns is_enabled as SQLite INTEGER 0/1; the bool cast lives in the API
            # layer (_watcher_config_res), so compare against the int here.
            assert cfg["is_enabled"] == 1
            assert cfg["debounce_ms"] == 700
            assert svc.get_config(workspace_id)["mode"] == "idle"
        finally:
            healed.close()


def test_a_fresh_database_is_unaffected_by_v008():
    """v008 must not break the fresh path: a DB built from all migrations keeps `mode` and writes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "fresh.db")
        fresh = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
        try:
            assert "mode" in _watcher_columns(fresh)
            workspace_id = str(uuid.uuid4())
            with fresh.transaction() as tx:
                tx.execute(
                    "INSERT INTO Workspace_Meta (workspace_id, workspace_name) VALUES (?, ?);",
                    (workspace_id, "fresh"),
                )
            svc = WatcherService(fresh, FileRepository(fresh))
            cfg = svc.update_config(workspace_id, "manual")
            assert cfg["mode"] == "manual"
            assert cfg["is_enabled"] == 0
        finally:
            fresh.close()
