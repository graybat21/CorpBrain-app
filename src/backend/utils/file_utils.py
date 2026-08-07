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
