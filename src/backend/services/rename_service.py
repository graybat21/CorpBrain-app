import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from src.backend.db import DatabaseManager
from src.backend.pii_filter import PIIFilter, PIIMaskingFailedException

logger = logging.getLogger("CorpBrain.RenameService")


class RenameService:
    INVALID_WIN_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|]')
    RESERVED_WIN_NAMES = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    }

    def __init__(self, db_mgr: DatabaseManager, pii_filter: Optional[PIIFilter] = None):
        self.db_mgr = db_mgr
        self.pii_filter = pii_filter or PIIFilter()

    @classmethod
    def build_prompt_context(cls, file_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build prompt context containing ONLY relative file info (DEC-17).
        Strictly excludes current_path, original_path, drive letters, user profile paths.
        """
        current_path = file_meta.get("current_path", "").replace("\\", "/")
        parts = [p for p in current_path.split("/") if p]
        
        folder_1depth = parts[-2] if len(parts) >= 2 else "root"
        depth_level = len(parts)

        return {
            "file_name": file_meta.get("file_name", ""),
            "extension": file_meta.get("extension", ""),
            "folder_1depth": folder_1depth,
            "depth_level": depth_level,
        }

    @classmethod
    def is_valid_windows_filename(cls, name: str) -> bool:
        """Validate Windows filename safety (DEC-17 / REQ-NF-007)."""
        if not name or len(name) > 255:
            return False

        # Invalid characters
        if cls.INVALID_WIN_CHARS_PATTERN.search(name):
            return False

        # Trailing space or dot
        if name.endswith(" ") or name.endswith("."):
            return False

        # Reserved Windows names
        base_name = name.split(".")[0].upper()
        if base_name in cls.RESERVED_WIN_NAMES:
            return False

        return True

    def process_rename_suggestions(
        self,
        workspace_id: str,
        files: List[Dict[str, Any]],
        mock_llm_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Processes file list for rename recommendations:
        1. Builds relative prompt context (no absolute path)
        2. Applies PIIFilter gate (DEC-17)
        3. Obtains LLM suggestion
        4. Rejects names containing leftover [PII:TYPE] tokens
        5. Validates Windows filename safety
        6. Saves Diff in Rename_History
        """
        diff_results = []
        old_paths_list = []
        new_paths_list = []

        for f in files:
            ctx = self.build_prompt_context(f)
            raw_prompt = f"Recommend standardized filename for file: {ctx['file_name']} in folder: {ctx['folder_1depth']}"

            try:
                masked_res = self.pii_filter.mask(raw_prompt)
                masked_prompt = masked_res.masked_text
            except PIIMaskingFailedException as e:
                logger.warning(f"[RN-CMD-01] PII masking failed for file: {e}")
                diff_results.append({
                    "file_id": f["file_id"],
                    "old_name": f["file_name"],
                    "new_name": f["file_name"],
                    "status": "PII_MASKING_FAILED",
                    "note": "PII 마스킹 실패 — 수동 확인 필요"
                })
                continue

            # Obtain LLM recommendation (mock or callback)
            if mock_llm_callback:
                suggested_name = mock_llm_callback(ctx["file_name"])
            else:
                # Default mock rule: format as 2026-08_Name
                suggested_name = f"2026-08_{ctx['file_name']}"

            # Check leftover [PII:TYPE] tokens (DEC-17)
            if "[PII:" in suggested_name:
                diff_results.append({
                    "file_id": f["file_id"],
                    "old_name": f["file_name"],
                    "new_name": f["file_name"],
                    "status": "PII_TOKEN_LEFT",
                    "note": "PII 포함 — 수동 확인 필요"
                })
                continue

            # Check Windows filename safety (DEC-17)
            if not self.is_valid_windows_filename(suggested_name):
                diff_results.append({
                    "file_id": f["file_id"],
                    "old_name": f["file_name"],
                    "new_name": f["file_name"],
                    "status": "INVALID_FILENAME",
                    "note": "유효하지 않은 파일명"
                })
                continue

            diff_results.append({
                "file_id": f["file_id"],
                "old_name": f["file_name"],
                "new_name": suggested_name,
                "status": "pending",
                "note": "추천 완료"
            })
            old_paths_list.append(f["current_path"])
            new_paths_list.append(os.path.join(os.path.dirname(f["current_path"]), suggested_name))

        # Save Diff history in DB
        history_id = str(uuid.uuid4())
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths)
                   VALUES (?, ?, ?, ?);""",
                (history_id, workspace_id, json.dumps(old_paths_list), json.dumps(new_paths_list)),
            )

        return diff_results
