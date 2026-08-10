import logging
import os
from typing import Any, Dict, List, Optional

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.task_repository import TaskRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository

logger = logging.getLogger("CorpBrain.QueryServices")


class WorkspaceQueryService:
    """WS-QRY-01: 전체 워크스페이스 목록 및 단일 상세 조회 (REQ-FUNC-001, 002)"""

    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr
        self.ws_repo = WorkspaceRepository(db_mgr)

    def list_workspaces(self) -> List[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Workspace_Meta ORDER BY created_at DESC;")
        return [dict(row) for row in cursor.fetchall()]

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Workspace_Meta WHERE workspace_id = ?;", (workspace_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


class ScanQueryService:
    """SCAN-QRY-01: 스캔 통계 조회 (REQ-FUNC-006)"""

    def __init__(self, db_mgr: DatabaseManager, task_repo: Optional[TaskRepository] = None):
        self.db_mgr = db_mgr
        self.task_repo = task_repo or TaskRepository(db_mgr)

    def get_scan_summary(self, workspace_id: str) -> Dict[str, Any]:
        """
        Returns scanned file count, total size (MB), and estimated analysis time.
        Estimated time based on 100ms per file (avg fast analysis throughput).

        `limit_reached` reports whether the most recent scan stopped at SCAN-CMD-02's 10,000-file
        guard (issue #64). It is read from `Async_Task`, not recomputed: whether the walk was
        truncated is a property of that scan run, and `COUNT(*) == 10000` cannot distinguish
        "truncated" from "the folder happens to hold exactly 10,000 files".

        Without this the dashboard had no way to know, and printed a hardcoded "10K Limit Guard
        정상" caption that stayed green on a truncated workspace — telling the user everything was
        indexed at the exact moment it was not.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) as file_count, COALESCE(SUM(size_bytes), 0) as total_bytes FROM File_Meta WHERE workspace_id = ?;",
            (workspace_id,)
        )
        row = cursor.fetchone()
        file_count = row["file_count"] if row else 0
        total_bytes = row["total_bytes"] if row else 0

        total_mb = round(total_bytes / (1024 * 1024), 2)
        estimated_seconds = round(file_count * 0.1, 1)  # 100ms per file

        return {
            "workspace_id": workspace_id,
            "file_count": file_count,
            "total_size_mb": total_mb,
            "estimated_analysis_seconds": estimated_seconds,
            "limit_reached": self._last_scan_hit_the_limit(workspace_id),
        }

    def _last_scan_hit_the_limit(self, workspace_id: str) -> bool:
        """
        True when the latest finished scan ended with `SCAN_LIMIT_REACHED`.

        Only the most recent scan counts: a user who narrows their root folders and rescans has
        fixed the problem, and a stale flag from the previous run would keep warning about a
        truncation that no longer exists. Unfinished scans are skipped for the same reason —
        their outcome is not yet known.
        """
        for task in self.task_repo.list_by_workspace(workspace_id, task_type="scan", limit=20):
            if task["status"] in ("queued", "running"):
                continue
            return task["error_code"] == "SCAN_LIMIT_REACHED"
        return False


class DeepLinkQueryService:
    """DL-QRY-01: 딥링크 대상 파일 현재 존재(Broken) 여부 검증 반환 (REQ-FUNC-022)"""

    def __init__(self, db_mgr: DatabaseManager, file_repo: Optional[FileRepository] = None):
        self.db_mgr = db_mgr
        self.file_repo = file_repo or FileRepository(db_mgr)

    def check_deeplink_status(self, workspace_id: str, file_id: str) -> Dict[str, Any]:
        """
        Checks if the file_id still maps to an accessible path on the filesystem.
        DEC-08 Late Binding: resolves current_path from DB at query time.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT current_path, file_name FROM File_Meta WHERE workspace_id = ? AND file_id = ?;",
            (workspace_id, file_id)
        )
        row = cursor.fetchone()

        if not row:
            # The anchor names a file_id the DB no longer has — a workspace deletion cascade, or a
            # wiki that outlived its source rows. Broken, and the reason distinguishes it from a
            # file that merely moved (REQ-FUNC-022).
            logger.info("[DL-QRY-01] Anchor references an unknown file_id: %s", file_id)
            return {"file_id": file_id, "is_broken": True, "reason": "NOT_FOUND_IN_DB"}

        current_path = row["current_path"]
        # `os.path.exists` swallows every OSError and returns False, which is the behaviour
        # REQ-NF-007 asks for here — a permission-denied or unreachable network path must report
        # "broken" rather than crash the wiki render. The cost is that "denied" and "deleted" are
        # indistinguishable; the reason code says PATH_NOT_ACCESSIBLE for exactly that reason.
        exists = os.path.exists(current_path)

        if not exists:
            # AC S2 (issue #22): the mismatch is recorded. Logged, not returned — DEC-03/DEC-08
            # keep absolute paths out of response bodies, and the local rolling log is where a
            # support case can see which path was checked.
            logger.warning(
                "[DL-QRY-01] Deeplink path mismatch for file_id %s: '%s' is no longer accessible",
                file_id,
                current_path,
            )

        return {
            "file_id": file_id,
            "file_name": row["file_name"],
            "current_path": current_path,
            "is_broken": not exists,
            "reason": None if exists else "PATH_NOT_ACCESSIBLE"
        }

    def check_bulk_deeplinks(self, workspace_id: str, file_ids: List[str]) -> List[Dict[str, Any]]:
        """Bulk check for multiple deeplink anchors."""
        return [self.check_deeplink_status(workspace_id, fid) for fid in file_ids]


class RenameQueryService:
    """RN-QRY-01: 생성된 파일명 Diff(Old/New) 매핑 리스트 반환 (REQ-FUNC-015)"""

    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr

    def get_pending_rename_diff(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Returns the most recent 'pending' Rename_History entries with old/new name diff.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT history_id, old_paths, new_paths, status, created_at
               FROM Rename_History WHERE workspace_id = ? AND status = 'pending'
               ORDER BY created_at DESC LIMIT 1;""",
            (workspace_id,)
        )
        row = cursor.fetchone()
        if not row:
            return []

        import json
        # old_paths/new_paths are JSON arrays of path strings: ["C:\\path\\a.txt", ...]
        # (stored by RenameService.generate_rename_diff L165-166, not as object arrays).
        old_paths = json.loads(row["old_paths"]) if row["old_paths"] else []
        new_paths = json.loads(row["new_paths"]) if row["new_paths"] else []

        diff_list = []
        # strict=True: both lists come from the same Rename_History row and are written in
        # lockstep, so a length mismatch is corruption — truncating it silently would hand the
        # user a diff that is missing rows.
        for old_p, new_p in zip(old_paths, new_paths, strict=True):
            # Fetch file_id from File_Meta by current_path. Same pattern as
            # RenameService.apply_rename_diff L206 — the stored history has paths only, so file_id
            # must be re-resolved. A moved/deleted file since the diff was generated will have no
            # matching row; we include it with file_id=None so the frontend can show "file missing".
            c = conn.cursor()
            c.execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (old_p,))
            r = c.fetchone()
            diff_list.append({
                "file_id": r["file_id"] if r else None,
                "old_name": os.path.basename(old_p),
                "new_name": os.path.basename(new_p),
                "history_id": row["history_id"],
                "status": row["status"]
            })
        return diff_list


class LlmQueryService:
    """LLM-QRY-01: 선택된 엔진(Cloud/Ollama) 연결 상태 확인 (Health Check) (REQ-FUNC-011, DEC-12, DEC-13)"""

    # Ollama exposes its installed-model list here (DEC-13). Loopback only.
    OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"

    def __init__(self, db_mgr: DatabaseManager, network_guard: Optional[Any] = None):
        from src.backend.config_manager import ConfigManager
        self.db_mgr = db_mgr
        self.config_mgr = ConfigManager(db_mgr)
        # DEC-15: all egress goes through NetworkGuard. Default to the real guard rather
        # than None so the validated path is what actually runs in production.
        if network_guard is None:
            from src.backend.network_guard import NetworkGuard
            network_guard = NetworkGuard
        self.network_guard = network_guard

    def check_health(self) -> Dict[str, Any]:
        mode = self.config_mgr.get("llm_mode", "Option A")
        api_key_configured = self.config_mgr.is_api_key_configured()

        embed_model = self.config_mgr.get("local_embedding_model", "nomic-embed-text")
        gen_model = self.config_mgr.get("local_generation_model", "qwen2.5:7b-instruct")
        embedding_timeout = float(self.config_mgr.get("llm_health_timeout", "5"))

        # DEC-13: the embedding model is required by EVERY user, including Option A
        # (DEC-06 routes all embeddings through local Ollama), so the tag list is always
        # queried regardless of mode. Egress is validated by NetworkGuard (DEC-15).
        tags = self.network_guard.get_json(
            "llm_local", self.OLLAMA_TAGS_URL, timeout=embedding_timeout
        )

        daemon_online = tags is not None
        installed_models = [m.get("name", "") for m in (tags or {}).get("models", [])]

        embedding_model_ready = any(embed_model in m for m in installed_models)
        generation_model_ready = any(gen_model in m for m in installed_models)

        if mode == "Option A":
            # Option A does not need the local generation model, but it still needs the
            # embedding model for deep analysis. Report both facts separately so the UI can
            # say "cloud is fine, deep analysis is not" (AC Scenario 3).
            self.network_guard.validate_egress("llm_cloud", "https://api.anthropic.com")
            status_ok = api_key_configured
            if not api_key_configured:
                error_code = "API_KEY_NOT_CONFIGURED"
            elif not embedding_model_ready:
                error_code = "LLM_PROVISION_REQUIRED"
            else:
                error_code = None
        else:
            status_ok = daemon_online and embedding_model_ready and generation_model_ready
            if not daemon_online:
                error_code = "LLM_UNAVAILABLE"
            elif not (embedding_model_ready and generation_model_ready):
                error_code = "LLM_PROVISION_REQUIRED"
            else:
                error_code = None

        return {
            "mode": mode,
            "api_key_configured": api_key_configured,
            "daemon_online": daemon_online,
            "status_ok": status_ok,
            "embedding_model_ready": embedding_model_ready,
            "generation_model_ready": generation_model_ready,
            "error_code": error_code,
            # DEC-16 / issue #30: the settings screen must render the price reference date next
            # to the figures. Read from App_Config, never fetched — a price table over the
            # network would be a fourth egress destination (DEC-15).
            "cloud_price_input_per_mtok": float(self.config_mgr.get("cloud_price_input_per_mtok", "3.00")),
            "cloud_price_output_per_mtok": float(self.config_mgr.get("cloud_price_output_per_mtok", "15.00")),
            "cloud_price_updated_at": self.config_mgr.get("cloud_price_updated_at", ""),
        }


class WikiQueryService:
    """
    ANA-QRY-01: 1-Depth 폴더별로 분리 가공된 위키 마크다운 구조 반환.

    Wiki_Content는 workspace_id + folder_1depth UNIQUE 제약을 갖고, 각 행이 하나의 폴더 탭에
    대응한다. 이 서비스는 해당 워크스페이스의 전체 위키를 조회해 폴더명 → 마크다운 맵으로 반환한다.
    """

    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr

    def get_workspace_wiki(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Return all wiki tabs for a workspace as [{folder_1depth, markdown_content, wiki_id}, ...].

        Issue #7 AC S1: returns an array (not a dict) so the frontend can control tab order.
        Each item has folder_1depth (the tab label), markdown_content (the rendered text), and
        wiki_id (for potential future updates/deletion).

        DEC-08: markdown_content contains [[file_id:<UUID>]] anchors, never absolute paths.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT wiki_id, folder_1depth, markdown_content, created_at, updated_at
               FROM Wiki_Content
               WHERE workspace_id = ?
               ORDER BY folder_1depth ASC;""",
            (workspace_id,)
        )
        rows = cursor.fetchall()
        return [
            {
                "wiki_id": r["wiki_id"],
                "folder_1depth": r["folder_1depth"],
                "markdown_content": r["markdown_content"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
