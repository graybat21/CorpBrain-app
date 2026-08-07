import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from src.backend.utils.app_paths import get_db_path, vectors_dir_for_db

logger = logging.getLogger("CorpBrain.DatabaseManager")


class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None, migrations_dir: Optional[str] = None):
        # Per-instance rather than a class attribute: `_local` used to be shared by every
        # DatabaseManager, so two managers pointing at different db_path values in the same
        # thread handed out the SAME connection — the second silently read and wrote the
        # first one's database. Harmless while each test closed its manager before the next
        # was built; not harmless now that DEC-04 task workers run concurrently.
        self._local = threading.local()
        self._all_connections = set()
        self._lock = threading.Lock()

        if db_path is None:
            self.db_path = get_db_path()
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        if migrations_dir is None:
            self.migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "migrations"))
        else:
            self.migrations_dir = os.path.abspath(migrations_dir)

        self.run_migrations()
        self.recover_interrupted_tasks()

    @property
    def vectors_dir(self) -> str:
        """
        ChromaDB persist directory for this database (DEC-06).

        Derived from ``db_path`` rather than always resolving ``%LocalAppData%`` so that a
        DatabaseManager pointed at a temp dir also gets a temp-dir vector store. Vectors and
        metadata must stay co-located: they reference each other by ``file_id`` and a
        mismatched pair looks like mass orphan vectors (DEC-09).
        """
        return str(vectors_dir_for_db(self.db_path))

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

    def release_thread_connection(self):
        """
        Close and forget only the calling thread's connection.

        A DEC-04 worker thread must call this when it finishes, or its sqlite3 connection
        lives until process exit — WAL readers hold the -wal file open, which on Windows
        blocks deleting the database directory (WinError 32) and in the app keeps a stale
        snapshot alive. `close()` cannot do this job: sqlite3 connections may not be closed
        from a thread other than the one that opened them.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            return
        with self._lock:
            self._all_connections.discard(conn)
        self._local.conn = None
        try:
            conn.close()
        except sqlite3.Error:
            # Already closed, or closed from the wrong thread. Not worth propagating from a
            # cleanup path, but never swallowed silently.
            logger.debug("Thread connection close failed; it was already unusable.", exc_info=True)

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
        """
        DEC-04: transition tasks stranded by a crash to 'interrupted' at boot.

        Covers 'queued' as well as 'running'. A queued task is one whose row was committed
        before the 202 was returned but whose worker never started — leaving it 'queued'
        means it stays live forever, so the frontend polls a task that will never advance and
        `list_interrupted()` never offers it for resume.

        Never auto-resumes: the user is asked first (DEC-04). This only relabels state.
        """
        try:
            with self.transaction() as conn:
                conn.execute(
                    "UPDATE Async_Task SET status = 'interrupted', updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE status IN ('running', 'queued');"
                )
        except sqlite3.OperationalError:
            # If table doesn't exist yet before migration
            pass
