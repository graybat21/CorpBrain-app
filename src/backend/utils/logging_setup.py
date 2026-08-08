"""
Application log file configuration (INF-CMD-02 / REQ-NF-014).

Until this module existed, no handler was ever attached to the root logger — every
``logger.info``/``warning``/``exception`` call in the codebase went to Python's "last resort"
handler, which prints ``WARNING`` and above to stderr and discards the rest. In a packaged
windowed exe (DEC-01, PyInstaller ``--onefile`` with no console) stderr goes nowhere, so a
crash left **no diagnostic trace at all** — while ``api/app.py`` was simultaneously relying on
"the traceback goes to the local log" as the reason it is safe to keep it out of the DEC-03
response body. That promise is what this module makes true.

Policy — REQ-NF-014, not the issue title
----------------------------------------
Issue #24's title says "50MB/30일", but SRS §4.2 REQ-NF-014 specifies **daily rolling, max 7
days retained, max 10MB per day**, and CLAUDE.md §4 (DEC-15) repeats "Plain text, max 7 days,
10MB/day". Two of the three sources agree and they are the higher-precedence ones, so the SRS
figures are implemented. The discrepancy is called out in the PR rather than silently resolved.

Both halves of the requirement are enforced, which needs slightly more than one stock handler:

- ``TimedRotatingFileHandler`` gives daily rolling + a 7-file backup count, but has no size
  cap: one runaway loop can write gigabytes into a single day's file.
- ``RotatingFileHandler`` caps size but never rolls on a date, so a quiet install keeps one
  file forever and "7일 보관" is never honoured.

``DailySizeCappedRotatingFileHandler`` below is a ``TimedRotatingFileHandler`` subclass that
also rolls when the current file exceeds ``max_bytes`` — the smallest change that satisfies
both clauses, versus adding a dependency for what is ~20 lines.

Format is plain text, deliberately: REQ-NF-014 requires a user to open the file in Notepad and
paste it into a bug report. JSON lines would be a better machine format and a worse one for
that, which is the actual requirement.
"""

import logging
import logging.handlers
import os
import time
from pathlib import Path
from typing import Optional

from src.backend.utils.app_paths import get_app_data_dir

#: REQ-NF-014: 일별 최대 10MB.
MAX_BYTES_PER_DAY = 10 * 1024 * 1024

#: REQ-NF-014: 최대 7일 보관. Counted in rotated files, so 7 backups + the live file.
BACKUP_DAY_COUNT = 7

LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "corpbrain.log"

#: Plain text, one record per line, no colour codes — the file is read in Notepad
#: (REQ-NF-014). Milliseconds are kept because DEC-04 progress bugs are ordering bugs.
LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


class DailySizeCappedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Rolls at midnight **or** when the file passes ``max_bytes``, whichever comes first.

    ``shouldRollover`` is the only method overridden: the parent's time check runs first, then
    the size check is added. Rotation itself, the ``.YYYY-MM-DD`` suffix and backup pruning are
    all inherited, so this stays a policy change rather than a reimplementation.
    """

    def __init__(self, filename, max_bytes: int = MAX_BYTES_PER_DAY, **kwargs):
        self.max_bytes = max_bytes
        super().__init__(filename, **kwargs)

    def shouldRollover(self, record: logging.LogRecord) -> int:  # noqa: N802 - stdlib name
        if super().shouldRollover(record):
            return 1
        if self.max_bytes <= 0:
            return 0
        if self.stream is None:
            self.stream = self._open()
        # Measure the record's own length rather than only the current file size: checking the
        # size *after* writing would let a single large record exceed the cap before anything
        # rotates, which is what the cap exists to prevent.
        message_length = len(self.format(record)) + len(self.terminator)
        self.stream.seek(0, os.SEEK_END)
        return 1 if self.stream.tell() + message_length > self.max_bytes else 0

    def getFilesToDelete(self):
        """
        Prune by count the way the parent does, but tolerate a size-triggered same-day roll.

        Two rotations in one day would both want ``corpbrain.log.2026-08-08``; the parent
        overwrites, silently losing the earlier chunk. `doRollover` below disambiguates with a
        counter suffix, and the parent's own matcher does not recognise those names — so this
        widens the match to include them.
        """
        dir_name, base_name = os.path.split(self.baseFilename)
        prefix = base_name + "."
        candidates = [
            os.path.join(dir_name, f)
            for f in os.listdir(dir_name)
            if f.startswith(prefix) and f != base_name
        ]
        if self.backupCount <= 0 or len(candidates) <= self.backupCount:
            return []
        # Oldest first by mtime, not by name: a same-day counter suffix does not sort
        # chronologically against a plain date.
        candidates.sort(key=os.path.getmtime)
        return candidates[: len(candidates) - self.backupCount]

    def rotation_filename(self, default_name: str) -> str:
        """
        Append ``.1``, ``.2``, … when the dated target already exists.

        Without this, the second size-triggered rotation of the same day overwrites the first
        one's file and the 10MB cap turns into silent log loss — the opposite of the intent.
        """
        name = super().rotation_filename(default_name)
        if not os.path.exists(name):
            return name
        counter = 1
        while os.path.exists(f"{name}.{counter}"):
            counter += 1
        return f"{name}.{counter}"


def get_log_dir(create: bool = True) -> Path:
    """
    ``%LocalAppData%\\CorpBrain\\logs`` — beside the DB and the vector store (REQ-NF-004).

    Resolved through ``app_paths`` rather than computed here so all user-data paths keep one
    source of truth, and so a test redirecting ``LOCALAPPDATA`` redirects logs too.
    """
    log_dir = get_app_data_dir(create=create) / LOG_DIR_NAME
    if create:
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def configure_logging(
    log_dir: Optional[str] = None,
    level: int = logging.INFO,
    max_bytes: int = MAX_BYTES_PER_DAY,
    backup_count: int = BACKUP_DAY_COUNT,
    force: bool = False,
) -> logging.Handler:
    """
    Attach the rolling file handler to the root logger. Idempotent.

    Called once at process start, before the API server thread and the WebView (DEC-01/DEC-02),
    so that a failure during boot is already being recorded.

    Idempotent because it is reachable from both ``create_app`` and ``scripts/dev_serve.py``:
    configuring twice would duplicate every line in the file. Pass ``force=True`` to rebuild
    against a different directory (tests do this).

    Returns the handler so a caller can report the path it is writing to.

    A handler is attached to the **root** logger rather than to a ``CorpBrain`` logger:
    modules here use both ``logging.getLogger("CorpBrain.X")`` and ``logging.getLogger(__name__)``
    (i.e. ``src.backend.api.app``), and a ``CorpBrain``-only handler would silently drop the
    latter — including ``api/app.py``'s unhandled-exception traceback, the single most important
    line in the file.
    """
    global _configured
    root = logging.getLogger()

    if _configured and not force:
        for existing in root.handlers:
            if isinstance(existing, DailySizeCappedRotatingFileHandler):
                return existing

    if force:
        for existing in list(root.handlers):
            if isinstance(existing, DailySizeCappedRotatingFileHandler):
                root.removeHandler(existing)
                existing.close()

    target_dir = Path(log_dir) if log_dir is not None else get_log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    handler = DailySizeCappedRotatingFileHandler(
        str(target_dir / LOG_FILE_NAME),
        max_bytes=max_bytes,
        when="midnight",
        backupCount=backup_count,
        encoding="utf-8",
        delay=False,
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    # UTC, matching DEC-11's storage rule: a support log correlated against DB timestamps in a
    # different zone costs more time than the KST convenience saves. The frontend converts.
    handler.formatter.converter = time.gmtime
    handler.setLevel(level)

    root.addHandler(handler)
    # Only raise the root level, never lower it: a caller that already set DEBUG for a
    # debugging session should not be turned back down by this function.
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    _configured = True
    return handler


def get_log_file_path() -> Optional[str]:
    """The live log file's path, or None when logging has not been configured yet."""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, DailySizeCappedRotatingFileHandler):
            return handler.baseFilename
    return None
