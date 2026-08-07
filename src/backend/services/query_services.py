import os
from typing import Any, Dict, List, Optional
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository


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

    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr

    def get_scan_summary(self, workspace_id: str) -> Dict[str, Any]:
        """
        Returns scanned file count, total size (MB), and estimated analysis time.
        Estimated time based on 100ms per file (avg fast analysis throughput).
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
            "estimated_analysis_seconds": estimated_seconds
        }


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
            return {"file_id": file_id, "is_broken": True, "reason": "NOT_FOUND_IN_DB"}

        current_path = row["current_path"]
        exists = os.path.exists(current_path)

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
        old_paths = json.loads(row["old_paths"]) if row["old_paths"] else []
        new_paths = json.loads(row["new_paths"]) if row["new_paths"] else []

        diff_list = []
        for op, np in zip(old_paths, new_paths):
            diff_list.append({
                "file_id": op.get("file_id"),
                "old_name": os.path.basename(op.get("path", "")),
                "new_name": np.get("new_name"),
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
            "error_code": error_code
        }
