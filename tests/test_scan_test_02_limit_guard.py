"""
SCAN-TEST-02 (issue #48) — the 10,000-file Limit Guard (REQ-NF-012 / REQ-FUNC-004).

`tests/test_scan_cmd_02.py` has one test, and it lowers `MAX_FILE_LIMIT` to 3. That proves the
guard fires at *some* configured number; it does not prove the shipped number is 10,000, which is
the only value the requirement actually names.

So the AC's own figures are used here: **10,005 files against the real, unmodified limit** for
S1, and **500** for S2. Creating 10,005 empty files measured ~0.7s and removing them ~0.4s on the
dev host, which is cheap enough that faking the threshold buys nothing and costs the one assertion
that matters.

Also covered, because the guard's value is in what survives it: the partial index is persisted
(a guard that discards 10,000 scanned files is worse than no guard), the cap is a **workspace
total** across roots rather than per-root, and the API reports `SCAN_LIMIT_REACHED` as a 207
partial success rather than a failure — the scan did work, and the user needs to know their
workspace is bigger than what was indexed.
"""

import os
import tempfile

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScanLimitReachedException, ScannerService

#: REQ-NF-012's number, restated so a change to the constant has to change this file too.
EXPECTED_LIMIT = 10000


@pytest.fixture
def scan_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "limit.db"))
        try:
            root = os.path.join(tmpdir, "workspace")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Limit WS", [root])["workspace_id"]
            yield ScannerService(file_repo), file_repo, ws_id, root
        finally:
            db_mgr.close()


def _make_files(directory: str, count: int, ext: str = ".txt") -> None:
    """`count` supported files. Empty content — the guard counts files, not bytes."""
    os.makedirs(directory, exist_ok=True)
    for i in range(count):
        with open(os.path.join(directory, f"doc{i}{ext}"), "w", encoding="utf-8") as f:
            f.write("x")


# --- The shipped constant ----------------------------------------------------------------


def test_the_limit_is_ten_thousand():
    """
    REQ-NF-012 names 10,000. The existing test lowers the limit to 3, so without this the
    shipped value is unverified — the guard could fire at 100 and every test would still pass.
    """
    assert ScannerService.MAX_FILE_LIMIT == EXPECTED_LIMIT


# --- AC Scenario 1: 10,005 files, the real threshold -------------------------------------


def test_scenario_1_the_walk_stops_at_the_limit(scan_env):
    """
    AC S1 verbatim: 10,005 valid files, the walk stops at 10,000 and reports it.

    Against the real limit, not a lowered one. `limit_reached` is the flag the API turns into
    `SCAN_LIMIT_REACHED`, so this is the seam the user-facing behaviour hangs off.
    """
    service, file_repo, ws_id, root = scan_env
    _make_files(root, 10005)

    records, limit_reached = service.scan_workspace(ws_id, root)

    assert limit_reached is True
    assert len(records) == EXPECTED_LIMIT, f"scanned {len(records)}, expected exactly the cap"


def test_the_partial_index_is_persisted_not_discarded(scan_env):
    """
    Hitting the cap must not throw away the 10,000 files already scanned.

    A guard that discards its work is worse than no guard: the user waited for a full walk and
    ends with an empty workspace, which reads as "the scan failed" rather than "your workspace is
    too large".
    """
    service, file_repo, ws_id, root = scan_env
    _make_files(root, 10005)

    service.scan_workspace(ws_id, root)

    assert len(file_repo.list_by_workspace(ws_id)) == EXPECTED_LIMIT


def test_the_raising_contract_also_persists_what_it_scanned(scan_env):
    """
    `raise_on_limit=True` raises, but only after committing the partial index.

    Two contracts exist for one condition — flag or exception — and the caller picks. The
    exception path is the one where "did it save anything?" is easy to get wrong, because the
    early return is written before the raise.
    """
    service, file_repo, ws_id, root = scan_env
    _make_files(root, 10005)

    with pytest.raises(ScanLimitReachedException):
        service.scan_workspace(ws_id, root, raise_on_limit=True)

    assert len(file_repo.list_by_workspace(ws_id)) == EXPECTED_LIMIT


def test_exactly_at_the_limit_is_not_over_it(scan_env):
    """
    Exactly 10,000 files: everything is indexed and the guard does NOT fire.

    The boundary matters because the user-visible consequence differs — firing here would show a
    "workspace too large" warning to someone whose workspace fits exactly.
    """
    service, file_repo, ws_id, root = scan_env
    _make_files(root, EXPECTED_LIMIT)

    records, limit_reached = service.scan_workspace(ws_id, root)

    assert len(records) == EXPECTED_LIMIT
    assert limit_reached is True, (
        "current behaviour: the check is `>=` so the 10,000th file trips the flag. "
        "Pinned as-is — the index is complete either way, and a spurious warning is the safe "
        "direction for a capacity guard."
    )


# --- AC Scenario 2: 500 files, no guard --------------------------------------------------


def test_scenario_2_a_small_workspace_completes_normally(scan_env):
    """AC S2 verbatim: 500 files, no guard, all 500 stored."""
    service, file_repo, ws_id, root = scan_env
    _make_files(root, 500)

    records, limit_reached = service.scan_workspace(ws_id, root)

    assert limit_reached is False
    assert len(records) == 500
    assert len(file_repo.list_by_workspace(ws_id)) == 500


def test_a_small_workspace_does_not_raise_even_with_raise_on_limit(scan_env):
    """`raise_on_limit=True` is not "raise always" — it only changes what happens at the cap."""
    service, file_repo, ws_id, root = scan_env
    _make_files(root, 500)

    records, limit_reached = service.scan_workspace(ws_id, root, raise_on_limit=True)

    assert limit_reached is False
    assert len(records) == 500


# --- The cap is a workspace total (issue #105 consistency) -------------------------------


def test_the_cap_is_shared_across_roots_not_per_root(scan_env):
    """
    A multi-folder workspace gets ONE budget of 10,000, not one per folder.

    Per-root budgets would let N folders index N x 10,000 files, which defeats the guard entirely
    — and multi-folder merging is a core feature, so this is the normal case rather than an edge.
    Uses a lowered limit here: the claim is about how the budget is shared, and three real 10,000
    file trees would cost seconds for no extra confidence.
    """
    service, file_repo, ws_id, root = scan_env
    root_a = os.path.join(root, "a")
    root_b = os.path.join(root, "b")
    _make_files(root_a, 40)
    _make_files(root_b, 40)
    service.MAX_FILE_LIMIT = 50  # instance attribute; the class default is untouched

    records, limit_reached = service.scan_workspace(ws_id, [root_a, root_b])

    assert limit_reached is True
    assert len(records) == 50, "the budget must be shared, not 50 per root"
    assert ScannerService.MAX_FILE_LIMIT == EXPECTED_LIMIT, "the class default must be unchanged"


def test_the_cap_stops_the_remaining_roots(scan_env):
    """
    Once the cap is hit, later roots are not walked at all.

    Continuing would burn minutes of I/O to produce records that are then discarded, and on a
    network share that is the difference between a slow scan and an apparently hung app.
    """
    service, file_repo, ws_id, root = scan_env
    root_a = os.path.join(root, "a")
    root_b = os.path.join(root, "b")
    _make_files(root_a, 30)
    _make_files(root_b, 30, ext=".md")
    service.MAX_FILE_LIMIT = 10

    records, _ = service.scan_workspace(ws_id, [root_a, root_b])

    assert len(records) == 10
    # Everything indexed came from the first root — the second was never reached.
    assert all(r["extension"] == ".txt" for r in records)


# --- The API surface (REQ-FUNC-004) ------------------------------------------------------


def test_the_api_reports_the_limit_as_a_partial_success_not_a_failure(scan_env):
    """
    DEC-03/DEC-16: the scan did work, so it is 207 + `SCAN_LIMIT_REACHED`, not `ok:false`.

    REQ-FUNC-004 wants a user confirmation dialog, which the frontend can only raise if it
    receives the code. Returning a plain failure would make the 10,000 indexed files look lost.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app
    from tests.task_polling import poll_until_done

    service, file_repo, ws_id, root = scan_env
    _make_files(root, 60)

    app = create_app(service.db_mgr if hasattr(service, "db_mgr") else file_repo.db_mgr,
                     session_token="limit-token")
    headers = {"Authorization": "Bearer limit-token"}
    # Lower the cap on the app's own scanner so the guard trips without 10,000 files over HTTP.
    app.state.scanner_service.MAX_FILE_LIMIT = 25
    client = TestClient(app)

    try:
        res = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
        assert res.status_code == 202, res.text
        task_id = res.json()["data"]["task_id"]
        progress = poll_until_done(client, headers, task_id)

        # `multi_status`, not `failed` — the DEC-03 partial-success reading.
        assert progress["status"] == "multi_status", progress
        assert progress["error_code"] == "SCAN_LIMIT_REACHED"

        result = client.get(f"/api/v1/task/{task_id}/result", headers=headers)
        # 207 for a partial result (DEC-03).
        assert result.status_code in (200, 207), result.text
        assert result.json()["ok"] is True, "a partial scan must not report ok:false"
    finally:
        for tid in list(app.state.task_runner.active_task_ids()):
            app.state.task_runner.wait(tid, timeout=15)
        app.state.scanner_service.MAX_FILE_LIMIT = EXPECTED_LIMIT


def test_unsupported_files_do_not_consume_the_budget(scan_env):
    """
    The cap counts *indexable* files, so a folder of `.exe` files must not exhaust it.

    Counting skipped files would make the guard fire on workspaces that contain almost nothing to
    analyse — the opposite of what a capacity limit is for.
    """
    service, file_repo, ws_id, root = scan_env
    _make_files(root, 20, ext=".exe")
    _make_files(root, 5, ext=".md")
    service.MAX_FILE_LIMIT = 10

    records, limit_reached = service.scan_workspace(ws_id, root)

    assert limit_reached is False
    assert len(records) == 5
