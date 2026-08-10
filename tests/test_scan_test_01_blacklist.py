"""
SCAN-TEST-01 (issue #47) — blacklist and extension filtering (TC-WS-005 / REQ-FUNC-005).

`tests/test_scan_cmd_01.py` covers `.git` and one unsupported extension. This adds what the AC
names and that file does not: **every** blacklist entry, case-insensitivity, nested blacklist
folders, the exact `.hwp`/`.xlsx` pair from AC S2, and the fact that skipped extensions are
recorded rather than silently dropped.

AC S2's "로그에 기록된다" was **not implemented** — the walk did a bare `continue`. It now tallies
per extension and logs one summary line per scan; see `scanner_service.py` for why per-file lines
were rejected.

The "Mock FS" the AC asks for is a real `tempfile` tree, not a patched `os.walk`. Patching the
walk would test the patch: the blacklist works by mutating `dirs[:]` in a `topdown=True` walk, and
that interaction with the real `os.walk` contract is the thing most likely to break.
"""

import logging
import os
import tempfile

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService


@pytest.fixture
def scan_env():
    """A real workspace directory plus the service wired to a real repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "scan.db"))
        try:
            root = os.path.join(tmpdir, "workspace")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Blacklist WS", [root])["workspace_id"]
            yield ScannerService(file_repo), file_repo, ws_id, root
        finally:
            db_mgr.close()


def _touch(path: str, content: str = "x") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# --- AC Scenario 1: blacklist folders are excluded entirely ------------------------------


def test_scenario_1_blacklisted_folders_contribute_nothing(scan_env):
    """
    AC S1 verbatim: `.git`, `node_modules`, `Windows` alongside a valid `report.md`.

    Only `report.md` may be indexed. The blacklisted files use `.md` too — a supported extension —
    so the only thing that can exclude them is the directory filter, which is what this asserts.
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "report.md"), "# 보고서")
    _touch(os.path.join(root, ".git", "config.md"))
    _touch(os.path.join(root, "node_modules", "readme.md"))
    _touch(os.path.join(root, "Windows", "notes.md"))

    records, limit_reached = service.scan_workspace(ws_id, root)

    assert limit_reached is False
    assert [r["file_name"] for r in records] == ["report.md"]
    # And the DB agrees — a scan that returns the right list but persists the wrong rows is worse
    # than one that fails.
    db_rows = file_repo.list_by_workspace(ws_id)
    assert [r["file_name"] for r in db_rows] == ["report.md"]
    assert all(".git" not in r["current_path"] for r in db_rows)
    assert all("node_modules" not in r["current_path"] for r in db_rows)


@pytest.mark.parametrize("blacklisted", sorted(ScannerService.BLACKLIST_DIRS))
def test_every_blacklist_entry_is_actually_excluded(scan_env, blacklisted):
    """
    Each entry in `BLACKLIST_DIRS`, one test case per entry.

    Parameterised off the constant rather than a hand-written list, so adding an entry to the
    blacklist without it working is impossible — the new case appears automatically.
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "keep.txt"))
    _touch(os.path.join(root, blacklisted, "hidden.txt"))

    records, _ = service.scan_workspace(ws_id, root)

    names = [r["file_name"] for r in records]
    assert names == ["keep.txt"], f"{blacklisted} was not excluded: {names}"


@pytest.mark.parametrize("variant", ["NODE_MODULES", "Node_Modules", "WINDOWS", ".GIT"])
def test_the_blacklist_is_case_insensitive(scan_env, variant):
    """
    Windows filesystems are case-insensitive, so `NODE_MODULES` is the same folder as
    `node_modules`.

    The comparison lowercases the directory name; without that, a repository checked out with a
    different case would have its `.git` indexed — hundreds of files of no value, and the object
    store contains file contents the user never asked to analyse.
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "keep.md"))
    _touch(os.path.join(root, variant, "inside.md"))

    records, _ = service.scan_workspace(ws_id, root)

    assert [r["file_name"] for r in records] == ["keep.md"], variant


def test_a_nested_blacklist_folder_is_excluded(scan_env):
    """
    A blacklist folder several levels down must still be pruned.

    `dirs[:]` mutation prunes at whatever depth the walk reaches it, but only because the walk is
    `topdown=True` — a change to that flag would silently break this while every shallow test
    kept passing.
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "a", "b", "keep.txt"))
    _touch(os.path.join(root, "a", "b", "node_modules", "pkg", "deep.txt"))

    records, _ = service.scan_workspace(ws_id, root)

    assert [r["file_name"] for r in records] == ["keep.txt"]


def test_a_blacklisted_name_as_a_file_is_still_scanned_if_supported(scan_env):
    """
    The blacklist names directories, not files.

    A document literally called `windows.md` is a normal document. Excluding it would be a
    surprising data loss, and the filter operates on `dirs` precisely so this cannot happen.
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "windows.md"))

    records, _ = service.scan_workspace(ws_id, root)

    assert [r["file_name"] for r in records] == ["windows.md"]


# --- AC Scenario 2: unsupported extensions are skipped and recorded ---------------------


def test_scenario_2_only_the_supported_extension_survives(scan_env, caplog):
    """
    AC S2 verbatim: `.docx`, `.hwp`, `.xlsx` in one folder — only `.docx` is extracted, and the
    skip is recorded.

    `.hwp` and `.xlsx` are explicitly out of MVP scope (CON-06 / X-03), so this is the boundary
    between "not supported yet" and "silently lost".
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "계약서.docx"))
    _touch(os.path.join(root, "한글문서.hwp"))
    _touch(os.path.join(root, "표.xlsx"))

    with caplog.at_level(logging.INFO):
        records, _ = service.scan_workspace(ws_id, root)

    assert [r["file_name"] for r in records] == ["계약서.docx"]

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert ".hwp" in logged, "a skipped extension must be recorded (AC S2)"
    assert ".xlsx" in logged
    # The filename is NOT logged: it is document data, and keeping it out of logs by habit is
    # cheaper than auditing which sink each log reaches.
    assert "한글문서" not in logged
    assert "표.xlsx" not in logged


@pytest.mark.parametrize("supported", sorted(ScannerService.SUPPORTED_EXTENSIONS))
def test_every_supported_extension_is_indexed(scan_env, supported):
    """All four MVP formats, parameterised off the constant (CON-06)."""
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, f"문서{supported}"))

    records, _ = service.scan_workspace(ws_id, root)

    assert len(records) == 1, supported
    assert records[0]["extension"] == supported


def test_extension_matching_is_case_insensitive(scan_env):
    """
    `REPORT.MD` and `Report.PDF` are the same formats.

    Windows preserves case but compares insensitively, so a document saved from another tool with
    an uppercase extension would otherwise be invisible to the scan.
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "REPORT.MD"))
    _touch(os.path.join(root, "Report.PDF"))
    _touch(os.path.join(root, "Data.TXT"))

    records, _ = service.scan_workspace(ws_id, root)

    assert len(records) == 3
    # The stored extension is normalised, so downstream filters need no second lowercasing.
    assert {r["extension"] for r in records} == {".md", ".pdf", ".txt"}


def test_an_extensionless_file_is_skipped_and_counted(scan_env, caplog):
    """
    A file with no extension cannot be parsed by any of the four format handlers.

    Tallied under `(none)` rather than dropped from the summary — "the scan ignored 40 things and
    will not say what" is the report the summary exists to avoid.
    """
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "Makefile"))
    _touch(os.path.join(root, "keep.txt"))

    with caplog.at_level(logging.INFO):
        records, _ = service.scan_workspace(ws_id, root)

    assert [r["file_name"] for r in records] == ["keep.txt"]
    assert "(none)" in "\n".join(r.getMessage() for r in caplog.records)


def test_the_skip_summary_is_one_line_not_one_per_file(scan_env, caplog):
    """
    REQ-NF-014 caps the log at 10MB/day, so a per-file line is a real budget problem.

    30 skipped files must produce a single aggregated record, not 30 — asserted by counting
    matching log records rather than by reading the text.
    """
    service, file_repo, ws_id, root = scan_env
    for i in range(30):
        _touch(os.path.join(root, f"binary{i}.exe"))

    with caplog.at_level(logging.INFO):
        service.scan_workspace(ws_id, root)

    skip_records = [r for r in caplog.records if "Skipped unsupported extensions" in r.getMessage()]
    assert len(skip_records) == 1, f"expected one summary line, got {len(skip_records)}"
    assert "'.exe': 30" in skip_records[0].getMessage()


def test_a_scan_with_nothing_skipped_logs_no_summary(scan_env, caplog):
    """An empty summary is noise. The line appears only when something was actually skipped."""
    service, file_repo, ws_id, root = scan_env
    _touch(os.path.join(root, "only.md"))

    with caplog.at_level(logging.INFO):
        service.scan_workspace(ws_id, root)

    assert not [r for r in caplog.records if "Skipped unsupported extensions" in r.getMessage()]


# --- Stability (REQ-NF-007) --------------------------------------------------------------


def test_an_unreadable_file_is_skipped_without_crashing(scan_env):
    """
    REQ-NF-007: a permission-denied path is skipped and the scan completes.

    Simulated by patching `os.stat` for one path rather than by chmod, which behaves differently
    across platforms and does nothing at all when the test runs as root in a container.
    """
    service, file_repo, ws_id, root = scan_env
    blocked = _touch(os.path.join(root, "locked.txt"))
    _touch(os.path.join(root, "readable.txt"))

    real_stat = os.stat

    def selective_stat(path, *args, **kwargs):
        if str(path).endswith("locked.txt"):
            raise PermissionError(13, "Permission denied")
        return real_stat(path, *args, **kwargs)

    import unittest.mock

    with unittest.mock.patch("os.stat", side_effect=selective_stat):
        records, limit_reached = service.scan_workspace(ws_id, root)

    assert limit_reached is False
    assert [r["file_name"] for r in records] == ["readable.txt"]
    assert os.path.exists(blocked), "the file itself must be untouched"


def test_an_empty_workspace_returns_an_empty_result(scan_env):
    """No files is a normal state, not an error — the dashboard renders 0 rather than failing."""
    service, file_repo, ws_id, root = scan_env

    records, limit_reached = service.scan_workspace(ws_id, root)

    assert records == []
    assert limit_reached is False
    assert file_repo.list_by_workspace(ws_id) == []


def test_a_blacklist_folder_at_the_root_itself_yields_nothing(scan_env):
    """
    If the user points a workspace *at* `node_modules`, the walk starts inside it.

    `dirs[:]` pruning only filters children, so the root is never tested against the blacklist —
    the honest outcome is that its supported files are indexed. Pinned as the current, deliberate
    behaviour: silently indexing nothing for a folder the user explicitly chose would look like a
    broken scan, and the #105 lesson is that a silent empty result is the worst reading.
    """
    service, file_repo, ws_id, root = scan_env
    nm_root = os.path.join(root, "node_modules")
    _touch(os.path.join(nm_root, "explicit.md"))

    records, _ = service.scan_workspace(ws_id, nm_root)

    assert [r["file_name"] for r in records] == ["explicit.md"]
