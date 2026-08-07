import logging
import os
import uuid
from typing import Any, Dict, List, Tuple

from src.backend.repositories.file_repository import FileRepository
from src.backend.utils.file_utils import normalize_path, safe_file_access

logger = logging.getLogger("CorpBrain.ScannerService")


class ScanLimitReachedException(Exception):
    """Raised when workspace scan file count reaches the 10,000 limit (SCAN-CMD-02)."""
    pass


class ScannerService:
    SUPPORTED_EXTENSIONS = {".md", ".docx", ".pdf", ".txt"}
    BLACKLIST_DIRS = {
        ".git",
        "node_modules",
        "windows",
        "$recycle.bin",
        "system volume information",
        ".antigravitycli",
        ".claude",
    }
    MAX_FILE_LIMIT = 10000

    def __init__(self, file_repo: FileRepository):
        self.file_repo = file_repo

    @safe_file_access(default_return=([], False))
    def scan_workspace(self, workspace_id: str, root_path: str, raise_on_limit: bool = False) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Recursively scan directory root_path for supported files,
        excluding blacklisted folders, up to 10,000 files limit.
        Returns (scanned_files_list, limit_reached_flag).
        """
        norm_root = normalize_path(root_path)
        if not os.path.exists(norm_root):
            return [], False

        scanned_records: List[Dict[str, Any]] = []
        limit_reached = False

        for current_dir, dirs, files in os.walk(norm_root, topdown=True):
            # Exclude blacklisted directories in-place
            dirs[:] = [d for d in dirs if d.lower() not in self.BLACKLIST_DIRS]

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    full_path = os.path.join(current_dir, fname)
                    norm_file_path = normalize_path(full_path)

                    try:
                        stat = os.stat(norm_file_path)
                        record = {
                            "file_id": str(uuid.uuid4()),
                            "workspace_id": workspace_id,
                            "current_path": norm_file_path,
                            "original_path": norm_file_path,
                            "file_name": fname,
                            "extension": ext,
                            "size_bytes": stat.st_size,
                            "last_modified": float(stat.st_mtime),
                            "parse_status": "pending",
                            "importance_score": 0,
                        }
                        scanned_records.append(record)
                    except (PermissionError, OSError) as e:
                        logger.warning(f"[SCAN-CMD-01] Skipping inaccessible file '{norm_file_path}': {e}")
                        continue

                    if len(scanned_records) >= self.MAX_FILE_LIMIT:
                        logger.warning(f"[SCAN-CMD-01] 10,000 file limit reached for workspace {workspace_id}")
                        limit_reached = True
                        if raise_on_limit:
                            # Bulk upsert what we got so far before raising
                            self.file_repo.bulk_upsert(scanned_records)
                            raise ScanLimitReachedException("File count limit of 10,000 reached for workspace")
                        break

            if limit_reached:
                break

        # Bulk upsert scanned records into DB
        self.file_repo.bulk_upsert(scanned_records)
        return scanned_records, limit_reached
