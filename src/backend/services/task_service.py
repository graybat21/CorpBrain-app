"""
Async task runner (DEC-04).

Long-running work (`scan`, `analyze_fast`, `analyze_deep`, `llm_onboard`, `rename_apply`,
`rename_undo`) returns 202 + task_id immediately and the frontend polls
`GET /api/v1/analyze/{task_id}/progress` at 1s intervals. There is no push channel: DEC-04
rules out WebSocket and SSE by design.

Two rules shape everything here:

1. **State lives in SQLite, not in this object.** `TaskRunner` holds threads, not progress.
   Anything a poll needs to answer comes out of `Async_Task` via `TaskRepository`, which is
   what makes progress survive a crash (REQ-NF-011). An in-memory dict is exactly the
   implementation DEC-04 forbids, and CORE #2 in docs/loop/DECISION_LOG.md is the record of
   it having been skipped once already.
2. **Progress is committed per item, outside the work.** The worker does the file I/O or
   inference first and commits the count after, because DEC-05 forbids holding a write
   transaction across either.
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from src.backend.db import DatabaseManager
from src.backend.repositories.task_repository import TaskRepository

logger = logging.getLogger("CorpBrain.TaskService")


class TaskCancelledError(Exception):
    """Raised inside a worker when the task row left a live state (e.g. boot recovery)."""


class TaskContext:
    """
    Handed to a task body so it can report progress without knowing about SQLite.

    A task body receives this and calls `set_total()` once the size is known, then
    `advance()` after each item. It never touches Async_Task directly — that keeps SQL in the
    repository (DEC-05) and means a body cannot accidentally write a status that the runner is
    also managing.
    """

    def __init__(self, task_id: str, task_repo: TaskRepository):
        self.task_id = task_id
        self._task_repo = task_repo

    def set_total(self, total: int) -> None:
        """Record the item count once it is known (a scan learns it only after walking)."""
        self._task_repo.set_total(self.task_id, total)

    def advance(self, delta: int = 1) -> None:
        """Commit progress for `delta` more processed items. Call AFTER the work, not before."""
        self._task_repo.increment_processed(self.task_id, delta)

    def note(self, message: str) -> None:
        """
        Record a human-readable status line for the poller (issue #29).

        For work whose steps are not interchangeable units — install, then a 274MB pull, then a
        4.7GB pull — a counter alone cannot say which step is running, and DEC-13 requires the
        two models to be distinguishable. Never pass a document path or content (REQ-NF-005).
        """
        self._task_repo.set_progress_message(self.task_id, message)


class TaskRunner:
    """
    Starts task bodies on daemon threads and records their outcome in Async_Task.

    Daemon threads deliberately: the shipped process is a desktop app, and a task must never
    keep the window alive after the user closes it. An abandoned task is recovered as
    `interrupted` at next boot, which is the DEC-04 contract — losing progress is not possible
    because it was committed per item.
    """

    def __init__(self, db_mgr: DatabaseManager, task_repo: Optional[TaskRepository] = None):
        self.db_mgr = db_mgr
        self.task_repo = task_repo or TaskRepository(db_mgr)
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        task_type: str,
        body: Callable[[TaskContext], Optional[Dict[str, Any]]],
        workspace_id: Optional[str] = None,
        total_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Create the task row, start the worker, and return the row for the 202 response.

        The row is committed before the thread starts so the frontend's first poll (1s later)
        can never 404 on a task that is genuinely running.

        `body` returns either None or a dict which may carry:
          - `status`: a terminal status to use instead of 'completed' (e.g. 'multi_status'
            when some files failed — DEC-03/DEC-16 require 207 + data.failed[], never a
            200/ok:true that hides missing documents)
          - `error_code` / `error_message`
          - `result`: the payload to persist for later retrieval, which is where a partially
            failed batch's `failed[]` list lives now that the command returns 202
        """
        task = self.task_repo.create(task_type, workspace_id=workspace_id, total_count=total_count)
        task_id = task["task_id"]

        thread = threading.Thread(
            target=self._run,
            args=(task_id, body),
            name=f"corpbrain-task-{task_type}-{task_id[:8]}",
            daemon=True,
        )
        with self._lock:
            self._threads[task_id] = thread
        thread.start()
        return task

    def _run(self, task_id: str, body: Callable[[TaskContext], Optional[Dict[str, Any]]]) -> None:
        ctx = TaskContext(task_id, self.task_repo)
        try:
            self.task_repo.mark_running(task_id)
            result = body(ctx) or {}

            status = result.get("status", "completed")
            if status not in ("completed", "multi_status", "failed"):
                # A body returning an unknown status would otherwise park the task in a state
                # nothing polls for. Fail loudly instead of guessing what it meant.
                raise ValueError(f"Task body returned an unusable status: {status!r}")

            self.task_repo.finish(
                task_id,
                status,
                error_code=result.get("error_code"),
                error_message=result.get("error_message"),
                result=result.get("result"),
            )
        except Exception as e:
            # error_message is written for the local log/DB only. DEC-03 keeps stack traces
            # and absolute internal paths out of response bodies, and the progress endpoint
            # returns error_code alone.
            logger.exception("[TaskRunner] Task %s failed", task_id)
            try:
                self.task_repo.finish(
                    task_id,
                    "failed",
                    error_code=getattr(e, "error_code", None) or "INTERNAL_ERROR",
                    error_message=f"{type(e).__name__}: {e}",
                )
            except Exception:
                logger.exception("[TaskRunner] Could not record failure for task %s", task_id)
        finally:
            # The worker opened its own thread-local sqlite3 connection; without this it stays
            # open until process exit, holding the WAL file (WinError 32 on Windows teardown).
            self.db_mgr.release_thread_connection()
            with self._lock:
                self._threads.pop(task_id, None)

    def wait(self, task_id: str, timeout: Optional[float] = None) -> bool:
        """
        Block until a task's thread exits. Test/CLI affordance only.

        The API never calls this — DEC-04 says the frontend polls. Returns False on timeout.
        """
        with self._lock:
            thread = self._threads.get(task_id)
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def active_task_ids(self) -> List[str]:
        with self._lock:
            return list(self._threads)


class TaskQueryService:
    """
    ANA-QRY-02: progress for a task_id.

    Reads Async_Task and nothing else. DEC-04 forbids returning large payloads (wiki
    markdown) from a progress response, so this returns counters and a status only; results
    are fetched from their own persisted rows.
    """

    # ASM-05 puts reading throughput at 200~250 WPM. ETA here is derived from measured
    # throughput of this task instead: WPM describes how fast a human reads, which says
    # nothing about how long parsing or inference takes. Presenting a WPM-derived number as
    # a machine ETA would be a made-up figure.
    def __init__(self, db_mgr: DatabaseManager, task_repo: Optional[TaskRepository] = None):
        self.db_mgr = db_mgr
        self.task_repo = task_repo or TaskRepository(db_mgr)

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Return the progress DTO fields, or None if there is no such task (caller → 404)."""
        row = self.task_repo.get(task_id)
        if row is None:
            return None

        processed = row["processed_count"]
        total = row["total_count"]
        percent = round(processed / total * 100, 1) if total > 0 else 0.0

        return {
            "task_id": row["task_id"],
            "task_type": row["task_type"],
            "workspace_id": row["workspace_id"],
            "status": row["status"],
            "processed": processed,
            "total": total,
            "percent": percent,
            # None for the per-file tasks that never call ctx.note() (issue #29). `.get` rather
            # than `[...]`: a row read before the v005 migration has no such key.
            "progress_message": row.get("progress_message"),
            "eta_sec": self._estimate_eta(row, processed, total),
            # DEC-03: the code, never error_message — that column can hold an exception
            # string with an absolute path in it.
            "error_code": row["error_code"],
        }

    @staticmethod
    def _estimate_eta(row: Dict[str, Any], processed: int, total: int) -> Optional[int]:
        """
        Seconds remaining, from this task's own observed rate.

        Returns None rather than a guess when there is nothing to extrapolate from: a
        finished task, an unknown total, or zero items processed so far. A fabricated "0
        seconds left" on a task that has not started is worse than an empty field, because the
        UI would render a complete progress bar over work that has not begun.
        """
        if row["status"] not in ("queued", "running"):
            return None
        if total <= 0 or processed <= 0 or processed >= total:
            return None

        from datetime import datetime, timezone

        # DEC-11: timestamps are TEXT ISO-8601 UTC with a trailing Z, which fromisoformat
        # only accepts from 3.11 onward — swap it for the +00:00 offset it does accept.
        def _parse(value: str) -> datetime:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        try:
            started = _parse(row["created_at"])
        except (ValueError, AttributeError):
            return None

        # Always tz-aware UTC (DEC-11); a naive now() here would silently subtract KST from
        # UTC and produce a nine-hour error.
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        if elapsed <= 0:
            return None

        per_item = elapsed / processed
        return max(0, int(round(per_item * (total - processed))))

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        The finished task's outcome: `{status, error_code, result}` or None if no such task.

        Separate from `get_progress` on purpose. Progress is polled once a second and DEC-04
        forbids putting payloads in it; this is fetched once, after a terminal status is
        observed. `result` is None while the task is still running.
        """
        row = self.task_repo.get(task_id)
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "task_type": row["task_type"],
            "workspace_id": row["workspace_id"],
            "status": row["status"],
            # DEC-03: the code, never error_message.
            "error_code": row["error_code"],
            "result": self.task_repo.get_result(task_id),
        }

    def list_interrupted(self, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Tasks stranded by a crash, so the user can be asked whether to resume (DEC-04).

        Never resumes anything itself. Resume is idempotent by construction elsewhere:
        re-analysis skips files whose `File_Meta.parse_status == 'parsed'`.
        """
        rows = self.task_repo.list_interrupted(workspace_id)
        return [
            {
                "task_id": r["task_id"],
                "task_type": r["task_type"],
                "workspace_id": r["workspace_id"],
                "status": r["status"],
                "processed": r["processed_count"],
                "total": r["total_count"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
