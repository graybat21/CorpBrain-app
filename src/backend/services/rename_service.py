import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from src.backend.db import DatabaseManager
from src.backend.pii_filter import PIIFilter, PIIMaskingFailedException
from src.backend.utils.file_utils import derive_folder_1depth

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
        # The history row written by the most recent process_rename_suggestions call, read back
        # by generate_rename_diff. Per-instance rather than returned from
        # process_rename_suggestions so that method's List return type is unchanged for its
        # three existing callers.
        self._last_history_id: Optional[str] = None

    @classmethod
    def build_prompt_context(cls, file_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build prompt context containing ONLY relative file info (DEC-17).
        Strictly excludes current_path, original_path, drive letters, user profile paths.
        """
        current_path = file_meta.get("current_path", "").replace("\\", "/")
        parts = [p for p in current_path.split("/") if p]

        folder_1depth = derive_folder_1depth(current_path)
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

    def generate_rename_diff(
        self,
        workspace_id: str,
        files: List[Dict[str, Any]],
        mock_llm_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        `process_rename_suggestions` plus the `history_id` of the row it wrote.

        The API layer needs that id: DEC-08 keeps absolute paths off the client, so the frontend
        cannot assemble the `items` list `apply_rename` takes and must hand back the id instead.
        The id was previously reachable only by re-querying Rename_History, which would put SQL
        outside a Repository (DEC-05) or make the client guess the newest row.
        """
        items = self.process_rename_suggestions(workspace_id, files, mock_llm_callback)
        return {"items": items, "history_id": self._last_history_id}

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
                # DEC-17: the same PIIFilter gate as analysis chunks. The masked text is not
                # bound to a name here because the current LLM call is a local mock; when a
                # real Option A call replaces mock_llm_callback, masked_res.masked_text is
                # what must be sent — never raw_prompt.
                self.pii_filter.mask(raw_prompt)
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
        self._last_history_id = history_id

        return diff_results

    def apply_rename(
        self,
        workspace_id: str,
        items: Optional[List[Dict[str, Any]]] = None,
        history_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes OS-level physical file rename and updates SQLite File_Meta (RN-CMD-02 / DEC-08 / DEC-05).
        - Updates File_Meta.current_path and file_name per file commit (DEC-05).
        - Leaves original_path and Wiki_Content untouched (DEC-08).
        - Handles file locks/errors via partial failure (HTTP 207).
        """
        if not items and history_id:
            conn = self.db_mgr.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT old_paths, new_paths FROM Rename_History WHERE history_id = ?;", (history_id,))
            row = cursor.fetchone()
            if row:
                old_list = json.loads(row["old_paths"])
                new_list = json.loads(row["new_paths"])
                items = []
                # strict=True: the two JSON arrays are written together in
                # process_rename_suggestions, so unequal lengths mean a corrupted history row.
                for old_p, new_p in zip(old_list, new_list, strict=True):
                    # Fetch file_id from File_Meta by current_path == old_p
                    c = conn.cursor()
                    c.execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (old_p,))
                    r = c.fetchone()
                    if r:
                        items.append({"file_id": r["file_id"], "old_path": old_p, "new_path": new_p})

        if not items:
            return {"status": "completed", "applied_count": 0, "failed": []}

        succeeded = []
        failed = []

        for item in items:
            file_id = item["file_id"]
            old_path = item["old_path"]
            new_path = item["new_path"]
            new_name = os.path.basename(new_path)

            if not os.path.exists(old_path):
                failed.append({
                    "file_id": file_id,
                    "old_path": old_path,
                    "new_path": new_path,
                    "error_code": "FILE_NOT_FOUND",
                    "error_message": "원본 파일이 존재하지 않습니다."
                })
                continue

            try:
                # 1. Physical OS Rename
                os.rename(old_path, new_path)

                # 2. Update File_Meta current_path and file_name per file commit (DEC-05 / DEC-08)
                with self.db_mgr.transaction() as conn:
                    conn.execute(
                        """UPDATE File_Meta
                           SET current_path = ?, file_name = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                           WHERE file_id = ?;""",
                        (new_path, new_name, file_id),
                    )
                succeeded.append({"file_id": file_id, "old_path": old_path, "new_path": new_path})
                logger.info(f"[RenameService] Renamed file {file_id}: {old_path} -> {new_path}")
            except Exception as e:
                logger.error(f"[RenameService] OS Rename failed for file {file_id}: {e}")
                failed.append({
                    "file_id": file_id,
                    "old_path": old_path,
                    "new_path": new_path,
                    "error_code": type(e).__name__,
                    "error_message": str(e)
                })

        status = "applied" if not failed else "multi_status"
        return {
            "status": status,
            "applied_count": len(succeeded),
            "succeeded": succeeded,
            "failed": failed
        }

    def undo_rename(self, workspace_id: str, history_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reverts OS physical file names to old_paths based on Rename_History (RN-CMD-03 / DEC-08).
        - Reverts File_Meta.current_path and file_name.
        - Leaves original_path and Wiki_Content untouched (DEC-08).
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()

        if history_id:
            cursor.execute("SELECT history_id, old_paths, new_paths FROM Rename_History WHERE history_id = ?;", (history_id,))
        else:
            cursor.execute(
                "SELECT history_id, old_paths, new_paths FROM Rename_History WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 1;",
                (workspace_id,)
            )

        row = cursor.fetchone()
        if not row:
            return {"status": "no_history", "reverted_count": 0, "failed": []}

        hist_id = row["history_id"]
        old_list = json.loads(row["old_paths"])
        new_list = json.loads(row["new_paths"])

        succeeded = []
        failed = []

        # strict=True — same paired-array invariant as apply_rename.
        for old_path, new_path in zip(old_list, new_list, strict=True):
            old_name = os.path.basename(old_path)
            # Find file_id by current_path == new_path
            cursor.execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (new_path,))
            file_row = cursor.fetchone()
            file_id = file_row["file_id"] if file_row else "unknown"

            if not os.path.exists(new_path):
                failed.append({
                    "file_id": file_id,
                    "current_path": new_path,
                    "target_path": old_path,
                    "error_code": "FILE_NOT_FOUND",
                    "error_message": "원복할 대상 파일이 존재하지 않습니다."
                })
                continue

            try:
                # 1. OS Rename back to old_path
                os.rename(new_path, old_path)

                # 2. Update File_Meta current_path and file_name (DEC-08)
                if file_id != "unknown":
                    with self.db_mgr.transaction() as c:
                        c.execute(
                            """UPDATE File_Meta
                               SET current_path = ?, file_name = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                               WHERE file_id = ?;""",
                            (old_path, old_name, file_id),
                        )
                succeeded.append({"file_id": file_id, "reverted_path": old_path})
            except Exception as e:
                failed.append({
                    "file_id": file_id,
                    "current_path": new_path,
                    "target_path": old_path,
                    "error_code": type(e).__name__,
                    "error_message": str(e)
                })

        status = "reverted" if not failed else "multi_status"
        return {
            "history_id": hist_id,
            "status": status,
            "reverted_count": len(succeeded),
            "succeeded": succeeded,
            "failed": failed
        }
