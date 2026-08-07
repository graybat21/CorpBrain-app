"""
Application data directory resolution (SRS §6.2 / DEC-06).

Single source of truth for where CorpBrain writes user data on Windows:

    %LocalAppData%\\CorpBrain\\
        corpbrain_meta.db     <- SQLite metadata (DEC-05)
        vectors/              <- ChromaDB PersistentClient store (DEC-06)

IMPORTANT: do NOT run these paths through ``file_utils.normalize_path()``. That helper
prepends the ``\\\\?\\`` long-path prefix, which is correct for the document files we
scan but breaks ChromaDB — its bundled sqlite3 and Rust filesystem layer do not
understand the extended-length syntax and fail with an opaque error.
"""

import os
from pathlib import Path

APP_DIR_NAME = "CorpBrain"
VECTORS_DIR_NAME = "vectors"
DB_FILE_NAME = "corpbrain_meta.db"


def get_app_data_dir(create: bool = True) -> Path:
    """
    Return ``%LocalAppData%\\CorpBrain``, creating it when ``create`` is True.

    LOCALAPPDATA is read at call time rather than import time so tests can redirect it
    with ``monkeypatch.setenv`` without needing a module reload.
    """
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    base_dir = Path(local_app_data) / APP_DIR_NAME
    if create:
        base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_db_path(create: bool = True) -> str:
    """Return the default SQLite metadata DB path (DEC-05)."""
    return str(get_app_data_dir(create=create) / DB_FILE_NAME)


def get_vectors_dir(create: bool = True) -> Path:
    """Return the default ChromaDB persist directory (DEC-06)."""
    vectors_dir = get_app_data_dir(create=create) / VECTORS_DIR_NAME
    if create:
        vectors_dir.mkdir(parents=True, exist_ok=True)
    return vectors_dir


def vectors_dir_for_db(db_path: str, create: bool = True) -> Path:
    """
    Return the vector store directory that belongs beside ``db_path``.

    Deriving the vector directory from the DB path (rather than always using
    ``%LocalAppData%``) is what lets a test point ``DatabaseManager`` at a temp dir and
    get a temp-dir vector store for free — no separate wiring, and no risk of a test
    writing into the real user profile.
    """
    vectors_dir = Path(db_path).parent / VECTORS_DIR_NAME
    if create:
        vectors_dir.mkdir(parents=True, exist_ok=True)
    return vectors_dir
