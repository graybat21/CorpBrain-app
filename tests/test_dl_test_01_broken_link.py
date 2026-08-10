"""
DL-TEST-01 (issue #22) — broken-link detection at query time (TC-DL-003 / REQ-FUNC-022).

`tests/test_issue_19_20.py` asserts that a deleted file reports `is_broken: true`. This adds the
cases the AC names and that file does not: the **move** path with its logged mismatch, permission
errors reported rather than raised (REQ-NF-007), and the distinction DEC-08 turns on — an
**internal rename is by definition never a broken link**, because `file_id` resolves late.

AC S2's "로그에 경로 불일치가 기록된다" was **not implemented**: `query_services.py` had no logger
at all. Added, and the path goes to the log rather than the response — DEC-03/DEC-08 keep absolute
paths out of response bodies.

"Mock FS" is a real tempfile tree. The whole mechanism under test is `os.path.exists` against a
path read from SQLite, so patching the filesystem would leave nothing real in the test.
"""

import logging
import os
import tempfile
import uuid

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.query_services import DeepLinkQueryService


@pytest.fixture
def link_env():
    """A workspace with one live, anchored file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "dl.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Link WS", [root])["workspace_id"]

            path = os.path.join(root, "기획서.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# 기획")

            file_id = str(uuid.uuid4())
            file_repo.bulk_upsert([{
                "file_id": file_id, "workspace_id": ws_id,
                "current_path": path, "original_path": path,
                "file_name": "기획서.md", "extension": ".md",
                "size_bytes": 6, "last_modified": os.path.getmtime(path),
                "parse_status": "parsed", "importance_score": 0,
            }])

            yield DeepLinkQueryService(db_mgr), file_repo, db_mgr, ws_id, file_id, path, root
        finally:
            db_mgr.close()


# --- Baseline: a live file is not broken --------------------------------------------------


def test_a_live_file_is_not_broken(link_env):
    """
    The control case. Without it, a service that returned `is_broken: true` unconditionally would
    pass every other test in this file.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env

    status = service.check_deeplink_status(ws_id, file_id)

    assert status["is_broken"] is False
    assert status["reason"] is None
    assert status["file_name"] == "기획서.md"


# --- AC Scenario 1: deletion ------------------------------------------------------------


def test_scenario_1_a_deleted_file_reports_broken(link_env):
    """
    AC S1: delete the file on disk, call DL-QRY-01, get `is_broken: true`.

    The DB row stays — that is the point. The anchor is still valid and the row records what was
    there, so the wiki keeps its audit trail and the badge greys out rather than vanishing.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    os.unlink(path)

    status = service.check_deeplink_status(ws_id, file_id)

    assert status["is_broken"] is True
    assert status["reason"] == "PATH_NOT_ACCESSIBLE"
    # The row survived the file.
    assert file_repo.get_by_path(ws_id, path) is not None


def test_a_missing_db_row_is_broken_for_a_different_reason(link_env):
    """
    An anchor naming an unknown `file_id` is broken too, but distinguishably so.

    `NOT_FOUND_IN_DB` versus `PATH_NOT_ACCESSIBLE` matters for the user's next action: the first
    means the wiki outlived its source rows (a workspace deletion cascade), the second means one
    file moved. Collapsing them would leave both looking like "restore the file".
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env

    status = service.check_deeplink_status(ws_id, str(uuid.uuid4()))

    assert status["is_broken"] is True
    assert status["reason"] == "NOT_FOUND_IN_DB"
    # No filename or path can be reported for a row that does not exist.
    assert status.get("file_name") is None
    assert status.get("current_path") is None


# --- AC Scenario 2: the file moved, and the mismatch is logged ---------------------------


def test_scenario_2_an_externally_moved_file_reports_broken_and_logs(link_env, caplog):
    """
    AC S2: the file moved outside the app's knowledge, so the DB path no longer resolves.

    "Externally" is the whole distinction — the Watcher updates the row on a move it observes, so
    a broken link means the move happened while the app was not watching (app closed, or Watcher
    off). The mismatch is logged because that is the only record of which path was checked.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    elsewhere = os.path.join(root, "..", "moved.md")
    os.rename(path, elsewhere)

    with caplog.at_level(logging.WARNING):
        status = service.check_deeplink_status(ws_id, file_id)

    assert status["is_broken"] is True
    assert status["reason"] == "PATH_NOT_ACCESSIBLE"

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "path mismatch" in logged.lower(), "AC S2 requires the mismatch to be recorded"
    assert file_id in logged, "the log must identify which anchor broke"


def test_an_internal_rename_is_never_a_broken_link(link_env):
    """
    DEC-08's core claim: `file_id` resolves late, so a rename the app performed keeps the link.

    This is the case that separates late binding from a cached path. If the wiki stored paths, this
    would break — and our own rename feature would be the thing breaking it.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    renamed = os.path.join(root, "2026-08_기획서.md")
    os.rename(path, renamed)
    file_repo.update_path(ws_id, file_id, renamed)

    status = service.check_deeplink_status(ws_id, file_id)

    assert status["is_broken"] is False
    assert status["file_name"] == "2026-08_기획서.md"
    assert status["current_path"] == renamed


def test_a_restored_file_stops_being_broken(link_env):
    """
    The check is at query time, not cached, so restoring the file heals the link with no
    re-analysis and no wiki regeneration.

    A cached `is_broken` flag would leave the badge grey until something invalidated it, and
    nothing would.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    os.unlink(path)
    assert service.check_deeplink_status(ws_id, file_id)["is_broken"] is True

    with open(path, "w", encoding="utf-8") as f:
        f.write("# 복구됨")

    assert service.check_deeplink_status(ws_id, file_id)["is_broken"] is False


# --- REQ-NF-007: access errors report, never crash --------------------------------------


def test_a_permission_error_reports_broken_rather_than_raising(link_env, monkeypatch):
    """
    REQ-NF-007: a file-access exception returns False rather than crashing.

    `os.path.exists` swallows every OSError by design, so this is inherited rather than written —
    which is exactly why it needs a test. The consequence is that "permission denied" and "deleted"
    are indistinguishable, and `PATH_NOT_ACCESSIBLE` is named for that ambiguity rather than
    claiming the file is gone.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env

    # Patch the OS-level stat that `os.path.exists` calls, NOT `exists` itself. Replacing
    # `exists` with a lambda returning False would assert nothing — it would test the lambda.
    # This makes the real `exists` meet a real PermissionError, which is the code path
    # REQ-NF-007 is about.
    real_stat = os.stat

    def denied(target, *args, **kwargs):
        if str(target) == path:
            raise PermissionError(13, "Permission denied")
        return real_stat(target, *args, **kwargs)

    monkeypatch.setattr(os, "stat", denied)

    status = service.check_deeplink_status(ws_id, file_id)

    assert status["is_broken"] is True, "an access error must report broken, not raise"
    assert status["reason"] == "PATH_NOT_ACCESSIBLE"


def test_a_directory_at_the_path_is_not_treated_as_a_live_file(link_env):
    """
    If the file was replaced by a directory of the same name, the link is not usable.

    Pinned as CURRENT behaviour, and it is wrong in a small way: `os.path.exists` returns True for
    a directory, so this reports not-broken and `os.startfile` would open a folder. Recorded here
    rather than silently fixed — changing it means choosing `os.path.isfile`, which also changes
    behaviour for symlinks and devices, and that is a judgement beyond this test-coverage issue.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    os.unlink(path)
    os.makedirs(path)

    status = service.check_deeplink_status(ws_id, file_id)

    assert status["is_broken"] is False, (
        "current behaviour: os.path.exists() is True for a directory. Reported in the PR as a "
        "known limitation rather than changed here."
    )


# --- Bulk checking (what the wiki page actually calls) ----------------------------------


def test_bulk_check_reports_each_anchor_independently(link_env):
    """
    A wiki page probes every anchor it renders, so one broken link must not colour the others.

    Returned in input order, because the caller zips the results against its own anchor list.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    second_path = os.path.join(root, "회의록.md")
    with open(second_path, "w", encoding="utf-8") as f:
        f.write("# 회의")
    second_id = str(uuid.uuid4())
    file_repo.bulk_upsert([{
        "file_id": second_id, "workspace_id": ws_id,
        "current_path": second_path, "original_path": second_path,
        "file_name": "회의록.md", "extension": ".md",
        "size_bytes": 6, "last_modified": os.path.getmtime(second_path),
        "parse_status": "parsed", "importance_score": 0,
    }])
    os.unlink(second_path)
    unknown_id = str(uuid.uuid4())

    results = service.check_bulk_deeplinks(ws_id, [file_id, second_id, unknown_id])

    assert [r["file_id"] for r in results] == [file_id, second_id, unknown_id]
    assert [r["is_broken"] for r in results] == [False, True, True]
    assert [r["reason"] for r in results] == [None, "PATH_NOT_ACCESSIBLE", "NOT_FOUND_IN_DB"]


def test_an_empty_bulk_request_returns_an_empty_list(link_env):
    """A wiki tab with no anchors is normal — it must not error or query anything."""
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env

    assert service.check_bulk_deeplinks(ws_id, []) == []


def test_a_file_id_from_another_workspace_is_not_found(link_env):
    """
    The lookup is scoped by `workspace_id`, so an anchor cannot resolve across workspaces.

    Without the scope, a wiki could resolve a file the user is not currently looking at — and
    `os.startfile` would then open a document from an unrelated workspace.
    """
    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    other_ws = WorkspaceRepository(db_mgr).create("Other", [tempfile.mkdtemp()])["workspace_id"]

    status = service.check_deeplink_status(other_ws, file_id)

    assert status["is_broken"] is True
    assert status["reason"] == "NOT_FOUND_IN_DB"


# --- The API surface (DoD: DL-FE-01 연동) ------------------------------------------------


def test_the_endpoint_returns_the_dto_the_badge_reads(link_env):
    """
    DoD ties this to DL-FE-01, whose badge reads `is_broken` off this endpoint.

    Asserted over the real route so the DTO shape is part of the contract (DEC-02/DEC-03), and
    checked for path leakage since DEC-08 keeps absolute paths off the client.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    service, file_repo, db_mgr, ws_id, file_id, path, root = link_env
    os.unlink(path)

    app = create_app(db_mgr, session_token="dl-test-token")
    client = TestClient(app)
    res = client.get(
        f"/api/v1/workspace/{ws_id}/deeplink/status",
        params={"file_id": file_id},
        headers={"Authorization": "Bearer dl-test-token"},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True, "a broken link is a successful query, not a failed one"
    assert body["data"]["is_broken"] is True
    assert body["data"]["reason"] == "PATH_NOT_ACCESSIBLE"
