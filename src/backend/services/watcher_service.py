import enum
import logging
import os
import queue
import threading
import time
import uuid
from typing import Any, Dict, Optional, Sequence, Union

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.vector_service import DeepAnalysisService

logger = logging.getLogger("CorpBrain.WatcherService")


class WatcherMode(str, enum.Enum):
    MANUAL = "manual"
    REALTIME = "realtime"
    IDLE = "idle"
    OFF = "off"


class CorpBrainWatcherHandler(FileSystemEventHandler):
    def __init__(
        self,
        service: "WatcherService",
        workspace_id: str,
        debounce_ms: int = 500
    ):
        super().__init__()
        self.service = service
        self.workspace_id = workspace_id
        self.debounce_ms = debounce_ms
        self._last_events: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _should_debounce(self, path: str) -> bool:
        now = time.time()
        with self._lock:
            last = self._last_events.get(path, 0)
            if (now - last) * 1000.0 < self.debounce_ms:
                return True
            self._last_events[path] = now
            return False

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self.service.suppress_events:
            return

        path = event.src_path
        if self._should_debounce(path):
            return

        # Check mtime vs DB last_modified (REQ-FUNC-024 timestamp check)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return

        file_rec = self.service.file_repo.get_by_path(self.workspace_id, path)
        if file_rec:
            db_mtime = file_rec.get("last_modified", 0.0)
            if mtime <= db_mtime:
                # Attribute-only touch — Skip event!
                logger.debug(f"[WatcherHandler] Skipped attribute-only touch for {path}")
                return

            # Real modification -> Enqueue for incremental re-analysis (WA-CMD-03)
            self.service.enqueue_file_event(self.workspace_id, file_rec["file_id"], "modified", path)
        else:
            # External new file
            self.service.enqueue_file_event(self.workspace_id, None, "created", path)

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self.service.suppress_events:
            return

        path = event.src_path
        if self._should_debounce(path):
            return

        self.service.enqueue_file_event(self.workspace_id, None, "created", path)

    def on_moved(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self.service.suppress_events:
            return

        src_path = event.src_path
        dest_path = getattr(event, "dest_path", None)
        if not dest_path:
            return

        # DEC-08: FileMovedEvent updates current_path & file_name without re-issuing new file_id
        file_rec = self.service.file_repo.get_by_path(self.workspace_id, src_path)
        if file_rec:
            file_id = file_rec["file_id"]
            new_name = os.path.basename(dest_path)
            with self.service.db_mgr.transaction() as conn:
                conn.execute(
                    """UPDATE File_Meta
                       SET current_path = ?, file_name = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                       WHERE file_id = ?;""",
                    (dest_path, new_name, file_id),
                )
            logger.info(f"[WatcherHandler] FileMovedEvent: Updated current_path for file_id {file_id}: {src_path} -> {dest_path}")
        else:
            # External file moved in -> register as new
            self.service.enqueue_file_event(self.workspace_id, None, "created", dest_path)


class WatcherService:
    def __init__(
        self,
        db_mgr: DatabaseManager,
        file_repo: FileRepository,
        deep_analysis_service: Optional[DeepAnalysisService] = None,
        workspace_repo: Optional[WorkspaceRepository] = None,
        idle_threshold_sec: float = 300.0,
    ):
        self.db_mgr = db_mgr
        self.file_repo = file_repo
        self.deep_analysis_service = deep_analysis_service or DeepAnalysisService(db_mgr)
        # Root lookup goes through the Repository, not a SELECT here (DEC-05: SQL lives only in
        # Repositories). Defaulted rather than required so the existing construction sites and
        # tests keep working.
        self.workspace_repo = workspace_repo or WorkspaceRepository(db_mgr)

        self.suppress_events = False
        self.queue: queue.Queue = queue.Queue()
        self._observers: Dict[str, Observer] = {}
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # REQ-FUNC-026: 5 minutes. Injectable so a test can assert the boundary without waiting.
        self.idle_threshold_sec = idle_threshold_sec
        # Starts "now", not 0: a freshly launched app has an active user, and treating boot as
        # 50 years of idleness would flush the whole backlog while they are still looking at it.
        self._last_activity_at = time.time()

    def get_config(self, workspace_id: str) -> Dict[str, Any]:
        """Gets WatcherConfig for workspace (WA-CMD-01 / REQ-FUNC-023)."""
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Watcher_Config WHERE workspace_id = ?;", (workspace_id,))
        row = cursor.fetchone()
        if not row:
            # Default config
            return {
                "workspace_id": workspace_id,
                "mode": WatcherMode.MANUAL.value,
                "is_enabled": 0,
                "debounce_ms": 500
            }
        row_dict = dict(row)
        return {
            "workspace_id": row_dict["workspace_id"],
            "mode": row_dict.get("mode", WatcherMode.MANUAL.value if not row_dict["is_enabled"] else WatcherMode.REALTIME.value),
            "is_enabled": row_dict["is_enabled"],
            "debounce_ms": row_dict["debounce_ms"]
        }

    def update_config(self, workspace_id: str, mode: str, debounce_ms: int = 500) -> Dict[str, Any]:
        """Updates WatcherConfig in SQLite and adjusts queue/observer (WA-CMD-01)."""
        clean_mode = mode.lower()
        if clean_mode not in [m.value for m in WatcherMode]:
            raise ValueError(f"Invalid Watcher mode: {mode}")

        is_enabled = 1 if clean_mode in [WatcherMode.REALTIME.value, WatcherMode.IDLE.value] else 0

        with self.db_mgr.transaction() as conn:
            conn.execute(
                """INSERT INTO Watcher_Config (workspace_id, is_enabled, debounce_ms, mode, updated_at)
                   VALUES (?, ?, ?, ?, (strftime('%Y-%m-%dT%H:%M:%fZ','now')))
                   ON CONFLICT(workspace_id) DO UPDATE SET
                       is_enabled = excluded.is_enabled,
                       debounce_ms = excluded.debounce_ms,
                       mode = excluded.mode,
                       updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'));""",
                (workspace_id, is_enabled, debounce_ms, clean_mode)
            )

        # Dynamically adjust observer status
        if is_enabled:
            # Every merged root gets watched (issue #105). Previously this read the single
            # `Workspace_Meta.root_path` column, so changes in folders 2..N raised no event.
            roots = self.workspace_repo.list_roots(workspace_id)
            if roots:
                self.start_observing(workspace_id, roots, debounce_ms=debounce_ms)
        else:
            self.stop_observing(workspace_id)

        return self.get_config(workspace_id)

    def start_observing(
        self,
        workspace_id: str,
        root_paths: Union[str, Sequence[str]],
        debounce_ms: int = 500,
    ):
        """
        Starts a watchdog Observer covering every root folder of the workspace (WA-CMD-02).

        One Observer with several scheduled watches, not one Observer per root: `_observers` is
        keyed by workspace_id, so a second entry would evict the first and leave its thread
        running unstopped.
        """
        if workspace_id in self._observers:
            self.stop_observing(workspace_id)

        roots = [root_paths] if isinstance(root_paths, str) else list(root_paths)
        handler = CorpBrainWatcherHandler(self, workspace_id, debounce_ms=debounce_ms)
        observer = Observer()

        scheduled = []
        for root_path in roots:
            if not os.path.exists(root_path):
                logger.warning(f"[WatcherService] Root path absent, not watched: '{root_path}'")
                continue
            observer.schedule(handler, root_path, recursive=True)
            scheduled.append(root_path)

        if not scheduled:
            # Starting an Observer with zero watches would leave a live thread that can never
            # emit an event, and `_observers` would claim the workspace is being watched.
            logger.warning(f"[WatcherService] No watchable root for workspace {workspace_id}; observer not started")
            return

        observer.start()
        self._observers[workspace_id] = observer
        logger.info(f"[WatcherService] Started observer for workspace {workspace_id} on {scheduled}")

    def stop_observing(self, workspace_id: str):
        """Stops watchdog Observer for workspace."""
        if workspace_id in self._observers:
            observer = self._observers.pop(workspace_id)
            observer.stop()
            observer.join()
            logger.info(f"[WatcherService] Stopped observer for workspace {workspace_id}")

    def enqueue_file_event(self, workspace_id: str, file_id: Optional[str], event_type: str, path: str):
        """Enqueues file change event for processing queue (WA-CMD-02 / WA-CMD-03)."""
        item = {
            "workspace_id": workspace_id,
            "file_id": file_id,
            "event_type": event_type,
            "path": path,
            "timestamp": time.time()
        }
        self.queue.put(item)
        logger.info(f"[WatcherService] Enqueued {event_type} event for {path}")

    def get_status(self, workspace_id: str) -> Dict[str, Any]:
        """
        WA-QRY-01: mode, activity, and the queue depth **for this workspace** (issue #58).

        `queue.qsize()` was previously reported directly, and the queue is process-wide — so a
        workspace with one pending event reported three when two other workspaces were also busy.
        The number drives a badge the user reads as "my files", which made it simply wrong.

        `queue.queue` is peeked rather than drained: `get()` would consume the events the worker
        thread needs. `deque` iteration is not atomic under a concurrent `put`, so the snapshot
        may miss an event that arrives mid-count — acceptable for a 1-second-polled badge, and
        the alternative (holding the queue's mutex) would block the worker to render a number.

        A disabled watcher reports `queued_items_count: 0` per AC S2, because the queue is not
        being drained: showing a stale backlog for a watcher that is off invites the user to wait
        for progress that will never come.
        """
        config = self.get_config(workspace_id)
        is_enabled = bool(config["is_enabled"])
        if not is_enabled:
            queued = 0
        else:
            queued = self.queued_count(workspace_id)
        return {
            "workspace_id": workspace_id,
            "mode": config["mode"],
            "is_enabled": is_enabled,
            "queued_items_count": queued,
        }

    def notify_user_activity(self, at: Optional[float] = None) -> None:
        """
        Record that the user is active, which pauses idle-mode flushing (WA-TEST-02 / #60).

        Called by the frontend on interaction. The backend cannot observe keyboard or mouse input
        itself — that needs OS hooks, which for a security-reviewed app (CON-03) is a cost far out
        of proportion to the benefit, and on Windows a global hook is indistinguishable from a
        keylogger to an auditor. So "is the user active" is reported, not sniffed.
        """
        self._last_activity_at = at if at is not None else time.time()

    def is_idle(self, now: Optional[float] = None) -> bool:
        """
        Whether the idle threshold has elapsed since the last reported activity (REQ-FUNC-026).

        `now` is injectable so a test can assert the 5-minute boundary without waiting five
        minutes — a sleep-based test of this would be both slow and, on a loaded runner, flaky.
        """
        current = now if now is not None else time.time()
        return (current - self._last_activity_at) >= self.idle_threshold_sec

    def flush_idle_queue(
        self, workspace_id: str, now: Optional[float] = None, max_items: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Idle-mode batch processing (AC S1/S2 of #60).

        AC S1: once idle, the accumulated events are processed in one pass rather than one per
        poll. AC S2: if activity is reported mid-flush, processing **stops** — the whole point of
        idle mode is that analysis never competes with the user for CPU (REQ-NF-002/CON-05), and
        finishing "just this batch" is exactly when the user notices the machine is busy.

        Returns `{status, processed, remaining}`. `status` is one of:
          - `not_idle`   — the threshold has not elapsed; nothing was touched.
          - `interrupted` — activity resumed partway; `remaining` events stay queued.
          - `flushed`    — the queue is drained for this workspace.

        The activity check runs **before each item**, not once at the start: a flush of ten
        documents can take minutes, and checking only up front would ignore input for that whole
        time — which is the behaviour AC S2 forbids.
        """
        if not self.is_idle(now):
            return {"status": "not_idle", "processed": 0, "remaining": self.queued_count(workspace_id)}

        processed = 0
        while max_items is None or processed < max_items:
            # Re-checked every iteration (AC S2). `now` is held fixed by tests that want to
            # simulate "still idle"; a test that wants an interruption reports activity instead.
            if not self.is_idle(now):
                return {
                    "status": "interrupted",
                    "processed": processed,
                    "remaining": self.queued_count(workspace_id),
                }
            if self.queued_count(workspace_id) == 0:
                break
            if self.process_next_queued_item() is None:
                break
            processed += 1

        return {"status": "flushed", "processed": processed, "remaining": self.queued_count(workspace_id)}

    def queued_count(self, workspace_id: str) -> int:
        """Pending events for one workspace. See `get_status` for why this is not `qsize()`."""
        return sum(
            1 for item in list(self.queue.queue) if item.get("workspace_id") == workspace_id
        )

    def process_next_queued_item(self) -> Optional[Dict[str, Any]]:
        """
        Processes single item from queue (WA-CMD-03 / DEC-09):
        1. Runs DeepAnalysisService incremental re-analysis (delete_file -> upsert chunks).
        2. Delta updates 1-depth folder Wiki_Content.
        """
        try:
            item = self.queue.get_nowait()
        except queue.Empty:
            return None

        workspace_id = item["workspace_id"]
        path = item["path"]

        if not os.path.exists(path):
            # The file is gone from disk. Drop its vectors before returning (DEC-09: vectors
            # first, SQLite row second). Returning early without this leaked an orphan vector
            # set on every deletion, which then kept surfacing in search results — invisible
            # while the store was in-memory, permanent now that it is persisted.
            file_id = item.get("file_id")
            if file_id is None:
                existing = self.file_repo.get_by_path(workspace_id, path)
                file_id = existing["file_id"] if existing else None
            if file_id:
                try:
                    self.deep_analysis_service.delete_file_vectors(workspace_id, file_id)
                except Exception as e:
                    # A vector-cleanup failure must not abort queue processing; the lazy
                    # delete during search post-processing is the backstop (DEC-09).
                    logger.warning(
                        f"[WatcherService] Vector cleanup failed for file_id {file_id}: {type(e).__name__}"
                    )
            return {"status": "file_not_found", "path": path, "file_id": file_id}

        # Resolve or register file_id
        file_rec = self.file_repo.get_by_path(workspace_id, path)
        if not file_rec:
            # Register new file
            ext = os.path.splitext(path)[1].lower()
            fname = os.path.basename(path)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            mtime = os.path.getmtime(path) if os.path.exists(path) else time.time()

            # DEC-11: UUID → TEXT (36-char hyphenated lowercase). Issue #84 — this was the only
            # path generating non-UUID file_id, breaking deeplink anchors and violating the
            # project-wide convention (scanner_service, rename_service, analytics_service all use
            # str(uuid.uuid4())).
            upsert_data = [{
                "workspace_id": workspace_id,
                "file_id": str(uuid.uuid4()),
                "current_path": path,
                "original_path": path,
                "file_name": fname,
                "extension": ext,
                "size_bytes": size,
                "last_modified": mtime,
                "importance_score": 50,
                "parse_status": "pending"
            }]
            self.file_repo.bulk_upsert(upsert_data)
            file_rec = self.file_repo.get_by_path(workspace_id, path)

        file_id = file_rec["file_id"]

        # 1. Vector re-analysis (DEC-09: delete_file -> upsert chunks)
        ana_res = self.deep_analysis_service.process_single_file(file_rec)

        # 2. Update File_Meta last_modified
        mtime = os.path.getmtime(path) if os.path.exists(path) else time.time()
        with self.db_mgr.transaction() as conn:
            conn.execute(
                "UPDATE File_Meta SET last_modified = ?, parse_status = 'parsed' WHERE file_id = ?;",
                (mtime, file_id)
            )

        return {
            "status": "processed",
            "workspace_id": workspace_id,
            "file_id": file_id,
            "path": path,
            "chunks_processed": ana_res.get("chunk_count", 0)
        }

    def close(self):
        """Stops all observers."""
        for ws_id in list(self._observers.keys()):
            self.stop_observing(ws_id)
