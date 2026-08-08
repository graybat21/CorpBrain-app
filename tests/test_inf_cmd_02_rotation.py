"""
INF-CMD-02 / REQ-NF-014 — log rotation (TC-MAINT-001), issue #24.

The Config Export/Import half of INF-CMD-02 (REQ-NF-015 / TC-MAINT-002) is covered by
tests/test_inf_cmd_02.py and is not repeated here.

Policy under test is the SRS's, not the issue title's: REQ-NF-014 specifies daily rolling,
7 days retained, 10MB/day. Issue #24's title says "50MB/30일"; SRS §4.2 and CLAUDE.md §4 both
say 10MB/7일, so those are the figures implemented.

The load-bearing test in this file is
`test_a_logger_call_actually_reaches_the_file` — before this change there was no handler at all,
so every assertion about *rotation policy* could pass against a handler nothing was routed to.
"""

import logging
import os
import tempfile
import time

import pytest

from src.backend.utils.logging_setup import (
    BACKUP_DAY_COUNT,
    MAX_BYTES_PER_DAY,
    DailySizeCappedRotatingFileHandler,
    configure_logging,
    get_log_dir,
    get_log_file_path,
)


@pytest.fixture
def log_dir():
    """
    A temp log directory, with the root logger restored afterwards.

    Restoration matters more than usual here: `configure_logging` mutates the *root* logger,
    so a leaked handler would keep writing into a deleted temp dir for the rest of the session
    and every later test's log output would land in it.
    """
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
        for handler in list(root.handlers):
            if handler not in original_handlers:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(original_level)


def _log_file(tmpdir: str) -> str:
    return os.path.join(tmpdir, "corpbrain.log")


def test_a_logger_call_actually_reaches_the_file(log_dir):
    """
    The requirement this issue exists for: `logger.warning(...)` ends up on disk.

    Asserted through `logging.getLogger("CorpBrain.Whatever")` rather than the handler
    directly, because the defect was that no handler was attached to anything — a test that
    called `handler.emit()` would have passed the whole time.
    """
    configure_logging(log_dir=log_dir, force=True)

    logging.getLogger("CorpBrain.ScannerService").warning("스캔 대상 폴더 없음: %s", "알파")
    logging.getLogger("src.backend.api.app").error("unhandled")
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = open(_log_file(log_dir), encoding="utf-8").read()
    assert "스캔 대상 폴더 없음: 알파" in content
    assert "CorpBrain.ScannerService" in content
    # A `CorpBrain`-only handler would drop this one — api/app.py uses __name__, and its
    # unhandled-exception traceback is the single most important line in the file.
    assert "src.backend.api.app" in content


def test_scenario_1_rollover_on_size_and_logging_continues(log_dir):
    """
    AC S1: at the size cap the existing file is renamed and logging continues into a new one.

    Uses a small max_bytes rather than writing 10MB: the policy under test is "rolls at the
    cap", and the cap's *value* is asserted separately by
    `test_the_configured_policy_matches_req_nf_014`.
    """
    # backup_count is raised well above what this test triggers so that retention pruning is
    # not a confound: the claim here is "rotation loses nothing", and a deleted 8th-oldest
    # backup is retention working correctly, not loss. Pruning has its own test below.
    configure_logging(log_dir=log_dir, max_bytes=2048, backup_count=100, force=True)
    logger = logging.getLogger("CorpBrain.RotationTest")

    for i in range(200):
        logger.info("행 %d — %s", i, "x" * 80)
    for handler in logging.getLogger().handlers:
        handler.flush()

    rotated = [f for f in os.listdir(log_dir) if f.startswith("corpbrain.log.")]
    assert rotated, os.listdir(log_dir)

    # The live file exists, is under the cap, and is still being written to.
    live = _log_file(log_dir)
    assert os.path.exists(live)
    assert os.path.getsize(live) <= 2048

    logger.info("로테이션 후 기록")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert "로테이션 후 기록" in open(live, encoding="utf-8").read()

    # Nothing was lost: the first line is in one of the files.
    all_text = open(live, encoding="utf-8").read()
    for name in rotated:
        all_text += open(os.path.join(log_dir, name), encoding="utf-8").read()
    assert "행 0 " in all_text


def test_two_rollovers_in_one_day_do_not_overwrite_each_other(log_dir):
    """
    A second size-triggered roll on the same date must not clobber the first.

    TimedRotatingFileHandler names its target by date, so both rolls target
    `corpbrain.log.YYYY-MM-DD` and the parent implementation overwrites — turning the size cap
    into silent log loss, the opposite of its purpose.
    """
    configure_logging(log_dir=log_dir, max_bytes=1024, backup_count=BACKUP_DAY_COUNT, force=True)
    logger = logging.getLogger("CorpBrain.DoubleRoll")

    for i in range(400):
        logger.info("항목 %d — %s", i, "y" * 60)
    for handler in logging.getLogger().handlers:
        handler.flush()

    rotated = [f for f in os.listdir(log_dir) if f.startswith("corpbrain.log.")]
    assert len(rotated) >= 2, rotated
    # Distinct files, so distinct content — no pair is the same path written twice.
    sizes = [os.path.getsize(os.path.join(log_dir, f)) for f in rotated]
    assert all(size > 0 for size in sizes)


def test_retention_never_keeps_more_than_seven_backups(log_dir):
    """
    REQ-NF-014's "최대 7일 보관" is a hard ceiling, enforced by pruning on rotation.

    Without pruning, a chatty install accumulates a file per rotation forever, which is the
    disk-filling outcome the requirement exists to prevent.
    """
    configure_logging(log_dir=log_dir, max_bytes=512, backup_count=BACKUP_DAY_COUNT, force=True)
    logger = logging.getLogger("CorpBrain.Retention")

    for i in range(1500):
        logger.info("압박 %d — %s", i, "z" * 60)
    for handler in logging.getLogger().handlers:
        handler.flush()

    rotated = [f for f in os.listdir(log_dir) if f.startswith("corpbrain.log.")]
    assert len(rotated) <= BACKUP_DAY_COUNT, rotated


def test_the_configured_policy_matches_req_nf_014(log_dir):
    """
    The default handler is daily-rolling, 7 backups, 10MB — the SRS figures, not 50MB/30일.

    Pins the numbers so a later "cleanup" cannot quietly adopt the issue title's values, and
    documents which source won.
    """
    handler = configure_logging(log_dir=log_dir, force=True)

    assert isinstance(handler, DailySizeCappedRotatingFileHandler)
    assert handler.when == "MIDNIGHT"
    assert handler.backupCount == 7
    assert handler.max_bytes == 10 * 1024 * 1024
    assert MAX_BYTES_PER_DAY == 10 * 1024 * 1024
    assert BACKUP_DAY_COUNT == 7


def test_format_is_plain_text_readable_in_notepad(log_dir):
    """
    REQ-NF-014 requires a user to open the file in Notepad and paste it into a report.

    So: one record per line, a readable timestamp, no ANSI colour codes, and UTF-8 for the
    Korean messages the codebase actually logs.
    """
    configure_logging(log_dir=log_dir, force=True)
    logging.getLogger("CorpBrain.Format").warning("한글 메시지 확인")
    for handler in logging.getLogger().handlers:
        handler.flush()

    lines = open(_log_file(log_dir), encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    line = lines[0]
    assert "\x1b[" not in line, "ANSI escape in a file meant for Notepad"
    assert "한글 메시지 확인" in line
    assert "WARNING" in line
    # `2026-08-08 13:30:34` — sortable, and unambiguous in a pasted bug report.
    assert line[:4].isdigit() and line[4] == "-"


def test_configure_logging_is_idempotent(log_dir):
    """
    Reachable from both create_app and dev_serve.py, so a second call must not duplicate lines.

    Two handlers on the root logger would write every record twice, halving the effective size
    cap and making the file harder to read — quietly, since nothing errors.
    """
    first = configure_logging(log_dir=log_dir, force=True)
    second = configure_logging(log_dir=log_dir)
    assert first is second

    file_handlers = [
        h for h in logging.getLogger().handlers
        if isinstance(h, DailySizeCappedRotatingFileHandler)
    ]
    assert len(file_handlers) == 1

    logging.getLogger("CorpBrain.Idempotent").warning("한 번만")
    first.flush()
    assert open(_log_file(log_dir), encoding="utf-8").read().count("한 번만") == 1


def test_get_log_file_path_reports_the_live_file(log_dir):
    configure_logging(log_dir=log_dir, force=True)
    assert get_log_file_path() == _log_file(log_dir)


def test_log_dir_is_isolated_under_the_app_data_dir(monkeypatch, tmp_path):
    """
    REQ-NF-004: logs live beside the DB and the vector store under %LocalAppData%\\CorpBrain.

    Resolved via app_paths, so redirecting LOCALAPPDATA redirects logs — which is also what
    keeps a test run out of the developer's real profile.
    """
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(
        "src.backend.utils.platform_compat.get_local_app_data_dir",
        lambda: tmp_path,
    )

    resolved = get_log_dir()
    assert resolved.name == "logs"
    assert resolved.parent.name == "CorpBrain"
    assert str(tmp_path) in str(resolved)


def test_timestamps_are_utc(log_dir):
    """
    DEC-11 stores UTC and the frontend converts. A log in local time cannot be correlated
    against a DB row without knowing the developer's zone.
    """
    configure_logging(log_dir=log_dir, force=True)
    handler = get_log_file_path()
    assert handler is not None

    before = time.gmtime()
    logging.getLogger("CorpBrain.Clock").warning("시각 확인")
    for h in logging.getLogger().handlers:
        h.flush()

    line = open(_log_file(log_dir), encoding="utf-8").read()
    # Same UTC hour — a local-time formatter would differ by the host's offset (KST is +9).
    assert time.strftime("%Y-%m-%d %H", before) in line
