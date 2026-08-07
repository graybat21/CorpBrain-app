import json
import re
from typing import Any, Dict, List, Optional
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository


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
