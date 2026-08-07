import enum
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
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
        deep_analysis_service: Optional[DeepAnalysisService] = None
    ):
        self.db_mgr = db_mgr
        self.file_repo = file_repo
        self.deep_analysis_service = deep_analysis_service or DeepAnalysisService(db_mgr)

        self.suppress_events = False
        self.queue: queue.Queue = queue.Queue()
        self._observers: Dict[str, Observer] = {}
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

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
            ws_meta = conn.cursor().execute("SELECT root_path FROM Workspace_Meta WHERE workspace_id = ?;", (workspace_id,)).fetchone()
            if ws_meta and os.path.exists(ws_meta["root_path"]):
                self.start_observing(workspace_id, ws_meta["root_path"], debounce_ms=debounce_ms)
        else:
            self.stop_observing(workspace_id)

        return self.get_config(workspace_id)

    def start_observing(self, workspace_id: str, root_path: str, debounce_ms: int = 500):
        """Starts watchdog Observer for workspace directory (WA-CMD-02)."""
        if workspace_id in self._observers:
            self.stop_observing(workspace_id)

        handler = CorpBrainWatcherHandler(self, workspace_id, debounce_ms=debounce_ms)
        observer = Observer()
        observer.schedule(handler, root_path, recursive=True)
        observer.start()
        self._observers[workspace_id] = observer
        logger.info(f"[WatcherService] Started observer for workspace {workspace_id} on {root_path}")

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

            upsert_data = [{
                "workspace_id": workspace_id,
                "file_id": f"file_{int(time.time()*1000)}",
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
