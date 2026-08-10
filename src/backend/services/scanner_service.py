import logging
import os
import uuid
from typing import Any, Dict, List, Sequence, Tuple, Union

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
    def scan_workspace(
        self,
        workspace_id: str,
        root_paths: Union[str, Sequence[str]],
        raise_on_limit: bool = False,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Recursively scan every root folder of a workspace for supported files,
        excluding blacklisted folders, up to 10,000 files total.
        Returns (scanned_files_list, limit_reached_flag).

        `root_paths` accepts a single path for the one-folder case, but the 10,000 limit is a
        **workspace total** across all roots (issue #105, consistent with SCAN-CMD-02): the cap
        exists to bound the work one scan does, and per-root budgets would let N folders index
        N x 10,000 files.
        """
        roots = [root_paths] if isinstance(root_paths, str) else list(root_paths)

        scanned_records: List[Dict[str, Any]] = []
        seen_paths: set = set()
        limit_reached = False
        # Per-extension tally of what the walk ignored (AC S2, issue #47). Shared across roots so
        # the summary describes the whole scan rather than the last folder.
        skipped_extensions: Dict[str, int] = {}

        try:
            # The limit raises out of _walk_root, so it aborts the remaining roots here too —
            # the 10,000 budget is shared, not per-root.
            for root_path in roots:
                norm_root = normalize_path(root_path)
                if not os.path.exists(norm_root):
                    # A root that vanished between workspace creation and this scan. Skipping it
                    # is right — the other folders are still indexable — but it is never silent:
                    # a silent skip is precisely the #105 failure mode.
                    logger.warning(f"[SCAN-CMD-01] Root path no longer exists, skipped: '{norm_root}'")
                    continue
                self._walk_root(
                    workspace_id, norm_root, scanned_records, seen_paths, skipped_extensions
                )
        except ScanLimitReachedException:
            if raise_on_limit:
                # Persist what the walk did collect before propagating, so the partial index
                # survives the exception.
                self.file_repo.bulk_upsert(scanned_records)
                raise
            limit_reached = True

        if skipped_extensions:
            logger.info(
                "[SCAN-CMD-01] Skipped unsupported extensions for workspace %s: %s",
                workspace_id,
                dict(sorted(skipped_extensions.items())),
            )

        # Bulk upsert scanned records into DB
        self.file_repo.bulk_upsert(scanned_records)
        return scanned_records, limit_reached

    def _walk_root(
        self,
        workspace_id: str,
        norm_root: str,
        scanned_records: List[Dict[str, Any]],
        seen_paths: set,
        skipped_extensions: Dict[str, int],
    ) -> None:
        """
        Walk one root, appending to the shared `scanned_records` budget.

        Raises ScanLimitReachedException on hitting the 10,000 cap so that `scan_workspace`
        decides between the raising and the flag-returning contract in one place — and so the
        cap stops the *remaining roots* too, not just this one.
        """
        for current_dir, dirs, files in os.walk(norm_root, topdown=True):
            # Exclude blacklisted directories in-place
            dirs[:] = [d for d in dirs if d.lower() not in self.BLACKLIST_DIRS]

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in self.SUPPORTED_EXTENSIONS:
                    # AC S2 (issue #47) requires skipped extensions to be recorded. Counted per
                    # extension and logged once at the end of the scan, NOT one line per file:
                    # a 10,000-file workspace with a node_modules-like tree would emit thousands
                    # of lines and eat the 10MB/day rolling-log budget (REQ-NF-014) on data that
                    # is only useful in aggregate — "what did the scan ignore, and how much".
                    #
                    # The extension is recorded, never the filename: a filename is document data
                    # and CON-03/REQ-NF-005 keep it out of anything that leaves the machine, so
                    # keeping logs free of it by habit is the cheaper discipline.
                    if ext:
                        skipped_extensions[ext] = skipped_extensions.get(ext, 0) + 1
                    else:
                        skipped_extensions["(none)"] = skipped_extensions.get("(none)", 0) + 1
                    continue

                full_path = os.path.join(current_dir, fname)
                norm_file_path = normalize_path(full_path)

                # Two roots may nest (the user picks a folder and its parent), which would
                # otherwise produce two records for one file — a duplicate that
                # UNIQUE(workspace_id, current_path) turns into a bulk_upsert conflict, and
                # that inflates the scanned count the dashboard shows.
                if norm_file_path in seen_paths:
                    continue

                try:
                    stat = os.stat(norm_file_path)
                except (PermissionError, OSError) as e:
                    logger.warning(f"[SCAN-CMD-01] Skipping inaccessible file '{norm_file_path}': {e}")
                    continue

                seen_paths.add(norm_file_path)
                scanned_records.append({
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
                })

                if len(scanned_records) >= self.MAX_FILE_LIMIT:
                    logger.warning(f"[SCAN-CMD-01] 10,000 file limit reached for workspace {workspace_id}")
                    raise ScanLimitReachedException("File count limit of 10,000 reached for workspace")
