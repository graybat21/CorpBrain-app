import functools
import logging
import os
import sys
from typing import Any, Callable, Optional

logger = logging.getLogger("CorpBrain.FileUtils")


def normalize_path(path_str: str) -> str:
    """Normalize path and apply Windows extended-length prefix (\\\\?\\) if needed for MAX_PATH."""
    if not path_str:
        return path_str

    abs_path = os.path.abspath(path_str)

    if sys.platform == "win32":
        if not abs_path.startswith("\\\\?\\") and not abs_path.startswith("\\\\.\\"):
            if len(abs_path) >= 240:
                if abs_path.startswith("\\\\"):
                    # UNC path: \\server\share -> \\?\UNC\server\share
                    return "\\\\?\\UNC" + abs_path[1:]
                else:
                    return "\\\\?\\" + abs_path

    return abs_path


def derive_folder_1depth(path_str: str) -> str:
    """
    Derive the immediate parent folder name from a path, or ``"root"`` if there isn't one.

    ``folder_1depth`` is not a ``File_Meta`` column — it exists only on ``Wiki_Content``
    (``v001_initial_schema.sql``), so every other consumer derives it from ``current_path``.
    Two of them need it for different reasons and must agree:

    - ``RenameService.build_prompt_context`` — the *only* path fragment DEC-17 permits in an
      outbound prompt (never the full path, drive letter, or UNC server name).
    - ``VectorDBManager`` chunk metadata — required by DEC-06, and likewise the only path
      fragment DEC-08 permits in vector metadata.

    Extracted verbatim from the RenameService implementation so the two cannot drift.
    """
    normalized = (path_str or "").replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    return parts[-2] if len(parts) >= 2 else "root"


def safe_file_access(default_return: Any = None):
    """Decorator to intercept OS/File errors (PermissionError, OSError, etc.) and log warning instead of crashing."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (PermissionError, OSError, FileNotFoundError) as e:
                path_info = args[0] if args else kwargs.get("path", "unknown")
                logger.warning(f"[INF-CMD-01] OS File Exception intercepted on '{path_info}': {e}")
                return default_return
        return wrapper
    return decorator
