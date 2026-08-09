import logging
import os
import re
from typing import Any, Dict, List, Optional

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.utils.platform_compat import open_with_default_app

logger = logging.getLogger("CorpBrain.DeepLinkService")


class DeepLinkService:
    # Anchor pattern format: [[file_id:<UUID>]] (DEC-08)
    DEEPLINK_PATTERN = re.compile(r"\[\[file_id:([0-9a-fA-F\-]{36})\]\]")

    def __init__(self, db_mgr: DatabaseManager, file_repo: Optional[FileRepository] = None):
        self.db_mgr = db_mgr
        self.file_repo = file_repo or FileRepository(db_mgr)

    @classmethod
    def parse_anchors(cls, markdown_text: str) -> List[str]:
        """Extract all [[file_id:UUID]] file_ids from markdown text."""
        if not markdown_text:
            return []
        return cls.DEEPLINK_PATTERN.findall(markdown_text)

    def process_wiki_deeplinks(self, workspace_id: str, markdown_content: str) -> Dict[str, Any]:
        """
        Process wiki markdown deep links (DL-CMD-01 / DEC-08):
        - Parses [[file_id:<UUID>]] anchors
        - Validates file_id exists in File_Meta
        - Returns mapping dictionary containing file_ids (Late Binding - NO absolute paths)
        """
        extracted_file_ids = self.parse_anchors(markdown_content)
        valid_file_ids = []

        db_files = {f["file_id"]: f for f in self.file_repo.list_by_workspace(workspace_id)}

        for fid in extracted_file_ids:
            if fid in db_files:
                valid_file_ids.append(fid)

        # Ensure no absolute paths (C:\ or /) present in mapping data
        mapping_data = {
            "workspace_id": workspace_id,
            "valid_file_ids": list(set(valid_file_ids)),
            "anchor_count": len(valid_file_ids),
        }
        return mapping_data

    def resolve_deeplink_path(self, workspace_id: str, file_id: str) -> Optional[str]:
        """
        Late Binding Resolver (DEC-08):
        Looks up current_path from File_Meta in DB at click/query time.
        Even if file was renamed or moved, returns the latest current_path.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT current_path FROM File_Meta WHERE workspace_id = ? AND file_id = ?;",
            (workspace_id, file_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row["current_path"]

    def open_file(self, workspace_id: str, file_id: str) -> Dict[str, Any]:
        """
        DL-CMD-02 / REQ-FUNC-021 / DEC-08:
        Opens the file associated with file_id in the OS default application.
        - Only accepts file_id, never a raw path (path injection prevention).
        - Resolves current_path via Late Binding from File_Meta at call time.
        - Returns DEC-03 compliant error codes on failure.
        """
        path = self.resolve_deeplink_path(workspace_id, file_id)

        if path is None:
            return {
                "status": "error",
                "error_code": "NOT_FOUND",
                "message": f"file_id '{file_id}' not found in workspace '{workspace_id}'"
            }

        if not os.path.exists(path):
            # The path is logged, never returned (DEC-03 / DEC-08, issue #19). This message
            # reaches the client verbatim through the route, and it used to interpolate the
            # absolute path — leaking `C:\Users\<account>\...` to exactly the layer DEC-08 keeps
            # paths away from. The user cannot act on the path anyway; the file name can be
            # obtained from the deeplink status endpoint.
            logger.warning("[DL-CMD-02] Deeplink target missing for file_id %s", file_id)
            return {
                "status": "error",
                "error_code": "PATH_NOT_ACCESSIBLE",
                "message": "원본 파일을 찾을 수 없습니다. 파일이 이동되었거나 삭제되었습니다."
            }

        try:
            # os.startfile on the shipped Windows target; `open`/`xdg-open` on a dev host.
            # Every platform's failure arrives as OSError so the mapping below is uniform.
            open_with_default_app(path)
            return {
                "status": "success",
                "file_id": file_id,
                # The name, not the path (DEC-08). `basename` is applied here rather than at the
                # API layer so no caller of this service receives a path it might forward.
                "file_name": os.path.basename(path),
            }
        except OSError as e:
            # `str(e)` on an OSError stringifies to the path it failed on ("[Errno 2] No such
            # file or directory: 'C:\\Users\\...'"), so it cannot be returned either. The type
            # and the real message go to the local log (issue #24 made that a real file).
            logger.warning(
                "[DL-CMD-02] Failed to open file_id %s: %s: %s", file_id, type(e).__name__, e
            )
            return {
                "status": "error",
                "error_code": "PATH_NOT_ACCESSIBLE",
                "message": "파일을 열 수 없습니다. 권한 또는 연결 프로그램을 확인하세요."
            }

