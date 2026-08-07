import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional


class DatabaseManager:
    _local = threading.local()

    def __init__(self, db_path: Optional[str] = None, migrations_dir: Optional[str] = None):
        self._all_connections = set()
        self._lock = threading.Lock()

        if db_path is None:
            local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
            base_dir = Path(local_app_data) / "CorpBrain"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(base_dir / "corpbrain_meta.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        if migrations_dir is None:
            self.migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "migrations"))
        else:
            self.migrations_dir = os.path.abspath(migrations_dir)

        self.run_migrations()
        self.recover_interrupted_tasks()

    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            self._local.conn = conn
            with self._lock:
                self._all_connections.add(conn)
        return self._local.conn

    def close(self):
        with self._lock:
            for conn in list(self._all_connections):
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None
        import gc
        gc.collect()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.get_connection()
        conn.execute("BEGIN IMMEDIATE;")
        try:
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise

    def run_migrations(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA user_version;")
        current_version = cursor.fetchone()[0]

        mig_dir_path = os.path.abspath(self.migrations_dir)
        if not os.path.exists(mig_dir_path):
            return

        filenames = sorted([f for f in os.listdir(mig_dir_path) if f.startswith("v") and f.endswith(".sql")])
        for filename in filenames:
            sql_file_path = os.path.join(mig_dir_path, filename)
            try:
                version_num = int(filename.split("_")[0].replace("v", ""))
            except ValueError:
                continue

            if version_num > current_version:
                with open(sql_file_path, "r", encoding="utf-8") as f:
                    sql_script = f.read()
                cursor.executescript(sql_script)
                cursor.execute(f"PRAGMA user_version = {version_num};")
                conn.commit()
                conn.execute("PRAGMA wal_checkpoint(FULL);")
                current_version = version_num

    def recover_interrupted_tasks(self):
        """DEC-04: Transition any stranded 'running' tasks to 'interrupted' upon boot."""
        try:
            with self.transaction() as conn:
                conn.execute(
                    "UPDATE Async_Task SET status = 'interrupted', updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE status = 'running';"
                )
        except sqlite3.OperationalError:
            # If table doesn't exist yet before migration
            pass
