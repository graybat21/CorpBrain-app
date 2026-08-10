"""
Async_Task persistence (DEC-04).

Task state lives in SQLite, never in an in-memory dict — that is what satisfies REQ-NF-011
(RPO/RTO). A dict would lose every in-flight task on a crash and leave the user with no way
to find out what had already been processed.

All SQL for Async_Task lives here (DEC-05). Progress is committed after each processed file,
so a kill -9 mid-batch leaves an accurate `processed_count` behind.
"""

import json
import uuid
from typing import Any, Dict, List, Optional

from src.backend.db import DatabaseManager

# DEC-04 enumerates the task types that return 202 + task_id. Kept as a frozenset so a typo
# in a caller fails loudly instead of silently creating a task type nothing polls for.
TASK_TYPES = frozenset({
    "scan",
    "analyze_fast",
    "analyze_deep",
    "llm_onboard",
    "rename_apply",
    "rename_undo",
    "reembed",  # issue #88: AC S3 consent flow
    "wiki_generate",  # issue #3: ANA-CMD-03
})

# 'queued'/'running' are the live states; the rest are terminal. 'interrupted' is only ever
# set by boot recovery (DatabaseManager.recover_interrupted_tasks) — a task never puts itself
# there, because a process that could write it would not have been interrupted.
TASK_STATUSES = frozenset({
    "queued",
    "running",
    "completed",
    "multi_status",
    "failed",
    "interrupted",
})

TERMINAL_STATUSES = frozenset({"completed", "multi_status", "failed"})


class TaskRepository:
    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr

    def create(
        self,
        task_type: str,
        workspace_id: Optional[str] = None,
        total_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Insert a task in 'queued' and return the row.

        The row must exist before the HTTP 202 is returned — if the response carried a
        task_id that was not yet committed, the frontend's first 1s poll would 404 against a
        task that is genuinely running.
        """
        if task_type not in TASK_TYPES:
            raise ValueError(f"Unknown task_type: {task_type}")

        task_id = str(uuid.uuid4())
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """INSERT INTO Async_Task (task_id, workspace_id, task_type, status, total_count)
                   VALUES (?, ?, ?, 'queued', ?);""",
                (task_id, workspace_id, task_type, total_count),
            )
        return self.get(task_id)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Async_Task WHERE task_id = ?;", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def mark_running(self, task_id: str, total_count: Optional[int] = None) -> None:
        """
        Move 'queued' -> 'running', optionally setting the now-known total.

        total_count is frequently unknown at create() time (a scan does not know the file
        count until it has walked the tree), so it is written here instead of being guessed.
        """
        if total_count is None:
            sql = """UPDATE Async_Task
                     SET status = 'running',
                         updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                     WHERE task_id = ?;"""
            params: tuple = (task_id,)
        else:
            sql = """UPDATE Async_Task
                     SET status = 'running',
                         total_count = ?,
                         updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                     WHERE task_id = ?;"""
            params = (total_count, task_id)

        with self.db_mgr.transaction() as conn:
            conn.execute(sql, params)

    def set_total(self, task_id: str, total_count: int) -> None:
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """UPDATE Async_Task
                   SET total_count = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                   WHERE task_id = ?;""",
                (total_count, task_id),
            )

    def increment_processed(self, task_id: str, delta: int = 1) -> None:
        """
        Commit progress for `delta` more processed items (DEC-04).

        Deliberately an in-SQL increment rather than read-modify-write: the worker thread and
        the polling request use different thread-local connections, and a read-modify-write
        would let a poll interleave and lose a count.

        Writes are kept short on purpose — DEC-05 forbids LLM inference or file I/O inside a
        write transaction, so the caller does the work first and commits the count after.
        """
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """UPDATE Async_Task
                   SET processed_count = processed_count + ?,
                       updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                   WHERE task_id = ?;""",
                (delta, task_id),
            )

    def set_progress_message(self, task_id: str, message: str) -> None:
        """
        Replace the task's human-readable status line (issue #29).

        Committed immediately, like `increment_processed`: a model pull runs for minutes with no
        counter movement, and a message buffered until the end would leave the 1s poll (DEC-04)
        showing nothing at all for the longest part of the task.

        Callers must not put a document path or content here — provisioning writes model names
        and percentages only (REQ-NF-005).
        """
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """UPDATE Async_Task
                   SET progress_message = ?,
                       updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                   WHERE task_id = ?;""",
                (message, task_id),
            )

    def finish(
        self,
        task_id: str,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Write a terminal status, plus the retrievable result.

        `error_message` is stored for local diagnosis only. DEC-03 forbids leaking stack
        traces or absolute internal paths in a response body, so the progress endpoint
        returns `error_code` and never this column.

        `result` is where a partially failed batch's `data.failed[]` survives (DEC-16): once
        the command returned 202 the failure list has nowhere else to live, and dropping it
        would leave the user believing every file succeeded.
        """
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Not a terminal status: {status}")

        with self.db_mgr.transaction() as conn:
            conn.execute(
                """UPDATE Async_Task
                   SET status = ?,
                       error_code = ?,
                       error_message = ?,
                       result_json = ?,
                       updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                   WHERE task_id = ?;""",
                (
                    status,
                    error_code,
                    error_message,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    task_id,
                ),
            )

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        The stored result payload, or None when the task has none yet.

        Returns None on unparseable JSON as well: a corrupted blob must not take down the
        result endpoint, and the task's status and counters remain readable regardless.
        """
        row = self.get(task_id)
        if row is None or not row.get("result_json"):
            return None
        try:
            return json.loads(row["result_json"])
        except json.JSONDecodeError:
            return None

    def list_by_workspace(
        self,
        workspace_id: str,
        task_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        # `rowid DESC` as the tiebreaker, same defect as issue #66's workspace listing:
        # `created_at` uses `strftime('%f')`, which is millisecond resolution, so a rescan
        # triggered right after a previous scan finished shares a timestamp with it and the
        # "latest task" was arbitrary. Issue #64 reads this to decide whether the last scan hit
        # the 10K guard, so an arbitrary winner meant the truncation warning could stick after a
        # clean rescan — or vanish after a truncated one. rowid is monotonic per insert.
        if task_type is None:
            cursor.execute(
                """SELECT * FROM Async_Task WHERE workspace_id = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?;""",
                (workspace_id, limit),
            )
        else:
            cursor.execute(
                """SELECT * FROM Async_Task WHERE workspace_id = ? AND task_type = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?;""",
                (workspace_id, task_type, limit),
            )
        return [dict(row) for row in cursor.fetchall()]

    def find_active(self, workspace_id: Optional[str], task_type: str) -> Optional[Dict[str, Any]]:
        """
        The live ('queued'/'running') task of this type for this workspace, if any.

        Backs duplicate-run prevention, which is what SRS §6.2.8 says the
        `(workspace_id, task_type)` index exists for. Without it a double-clicked button
        starts two concurrent scans writing the same File_Meta rows.

        `workspace_id=None` matches the workspace-independent tasks (`llm_onboard`, issue #29)
        via `IS NULL`. It needs its own branch because SQL's `= NULL` is never true, so the
        parameterised form would find nothing and happily start a second 4.7GB model download
        on every click — the duplicate-run bug this method exists to prevent.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        if workspace_id is None:
            cursor.execute(
                """SELECT * FROM Async_Task
                   WHERE workspace_id IS NULL AND task_type = ? AND status IN ('queued', 'running')
                   ORDER BY created_at DESC LIMIT 1;""",
                (task_type,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        cursor.execute(
            """SELECT * FROM Async_Task
               WHERE workspace_id = ? AND task_type = ? AND status IN ('queued', 'running')
               ORDER BY created_at DESC LIMIT 1;""",
            (workspace_id, task_type),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_interrupted(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Tasks stranded by a crash, for the "resume?" prompt.

        DEC-04 forbids auto-resuming these — the user is asked first, which is why this is a
        query and not a restart routine.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        if workspace_id is None:
            cursor.execute(
                "SELECT * FROM Async_Task WHERE status = 'interrupted' ORDER BY created_at DESC;"
            )
        else:
            cursor.execute(
                """SELECT * FROM Async_Task WHERE status = 'interrupted' AND workspace_id = ?
                   ORDER BY created_at DESC;""",
                (workspace_id,),
            )
        return [dict(row) for row in cursor.fetchall()]
