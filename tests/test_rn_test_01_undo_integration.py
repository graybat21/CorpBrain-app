"""
RN-TEST-01 (issue #43) — Undo integration at scale (TC-REL-003 / TC-SEC-005 / REQ-NF-009).

`tests/test_issue_39.py` covers the undo mechanism with two files. This adds what the AC actually
specifies and that file does not:

- **50 files** (REQ-NF-009's number), asserting 100% restoration on disk AND in the DB.
- **Partial failure**: 2 of 50 locked, so 48 revert and the failure list names the 2. The list is
  the deliverable here — a count alone cannot tell the user which documents to deal with.
- **TC-SEC-005**: the rename prompt for `C:\\Users\\hong\\기밀\\홍길동_주민등록증_900101-1234567.pdf`
  carries neither the RRN nor the account path.

"100%" is asserted on both sides deliberately. Disk-only would pass while `File_Meta.current_path`
drifted, and a DB that disagrees with disk is exactly what produces broken deeplinks — the failure
would surface later, in a different feature, as an unexplained grey badge.

Locking is simulated by patching `os.rename` for two specific paths rather than by taking a real
OS lock: `PermissionError` is what a locked file raises on Windows, and a real lock is
unavailable on macOS (flock does not block rename) so the test would silently pass by doing
nothing.
"""

import json
import os
import tempfile
import uuid

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.rename_service import RenameService
from tests.fakes import NoRetryResilience, RecordingLlmRouter

FILE_COUNT = 50


@pytest.fixture
def batch_env():
    """A workspace with 50 real files, scanned into File_Meta."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "undo.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Undo50 WS", [root])["workspace_id"]

            originals = []
            rows = []
            for i in range(FILE_COUNT):
                name = f"원본문서_{i:03d}.txt"
                path = os.path.join(root, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"내용 {i}")
                originals.append(path)
                rows.append({
                    "file_id": str(uuid.uuid4()), "workspace_id": ws_id,
                    "current_path": path, "original_path": path,
                    "file_name": name, "extension": ".txt",
                    "size_bytes": 8, "last_modified": os.path.getmtime(path),
                    "parse_status": "parsed", "importance_score": 0,
                })
            file_repo.bulk_upsert(rows)

            service = RenameService(db_mgr=db_mgr)
            yield service, file_repo, db_mgr, ws_id, root, originals
        finally:
            db_mgr.close()


def _apply_batch(service, ws_id, root, originals):
    """Rename all 50 through the real apply path; returns (history_id, new_paths)."""
    conn = service.db_mgr.get_connection()
    new_paths = [
        os.path.join(root, f"2026-08_{os.path.basename(p)}") for p in originals
    ]
    items = []
    for old_path, new_path in zip(originals, new_paths, strict=True):
        file_id = conn.execute(
            "SELECT file_id FROM File_Meta WHERE current_path = ?;", (old_path,)
        ).fetchone()["file_id"]
        items.append({"file_id": file_id, "old_path": old_path, "new_path": new_path})

    history_id = str(uuid.uuid4())
    with service.db_mgr.transaction() as tx:
        tx.execute(
            """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
               VALUES (?, ?, ?, ?, 'applied');""",
            (history_id, ws_id, json.dumps(originals), json.dumps(new_paths)),
        )
    applied = service.apply_rename(ws_id, items=items)
    assert applied["applied_count"] == FILE_COUNT, applied
    return history_id, new_paths


# --- AC Scenario 1: 50 files, 100% restored ----------------------------------------------


def test_scenario_1_fifty_files_are_fully_restored(batch_env):
    """
    AC S1 / REQ-NF-009: 50 files renamed, then undone, with every original path and name back.

    Asserted on disk AND in the DB. Disk alone would pass while `current_path` drifted, and a DB
    that disagrees with disk is what produces broken deeplinks — the failure would then surface in
    a different feature as an unexplained grey badge.
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    history_id, new_paths = _apply_batch(service, ws_id, root, originals)

    # Precondition: the rename really happened for all 50.
    assert all(os.path.exists(p) for p in new_paths)
    assert not any(os.path.exists(p) for p in originals)

    result = service.undo_rename(ws_id, history_id=history_id)

    assert result["status"] == "reverted"
    assert result["reverted_count"] == FILE_COUNT
    assert result["failed"] == []

    # Disk: every original back, no renamed leftovers.
    assert all(os.path.exists(p) for p in originals)
    assert not any(os.path.exists(p) for p in new_paths)

    # DB: current_path and file_name match the originals exactly.
    rows = file_repo.list_by_workspace(ws_id)
    assert len(rows) == FILE_COUNT
    assert {r["current_path"] for r in rows} == set(originals)
    assert {r["file_name"] for r in rows} == {os.path.basename(p) for p in originals}


def test_the_file_contents_are_untouched_by_the_round_trip(batch_env):
    """
    Rename and undo move files; they must never rewrite one.

    "100% restored" has to mean the bytes too — a rename implemented as copy+delete would pass
    every path assertion above while silently losing content on a partial write.
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    history_id, _ = _apply_batch(service, ws_id, root, originals)
    service.undo_rename(ws_id, history_id=history_id)

    for index, path in enumerate(originals):
        with open(path, encoding="utf-8") as f:
            assert f.read() == f"내용 {index}", path


def test_original_path_survives_the_round_trip(batch_env):
    """
    DEC-08: `original_path` is immutable audit data across rename AND undo.

    It is the one record of where a file was first found; rewriting it would erase the only
    fixed point in a file's history.
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    before = {
        r["file_id"]: r["original_path"] for r in file_repo.list_by_workspace(ws_id)
    }

    history_id, _ = _apply_batch(service, ws_id, root, originals)
    service.undo_rename(ws_id, history_id=history_id)

    after = {r["file_id"]: r["original_path"] for r in file_repo.list_by_workspace(ws_id)}
    assert after == before


# --- AC Scenario 2: 2 of 50 locked ------------------------------------------------------


def test_scenario_2_two_locked_files_leave_forty_eight_reverted(batch_env, monkeypatch):
    """
    AC S2 verbatim: 2 files locked by another process, 48 revert, the 2 are listed.

    The list is the deliverable — a count alone cannot tell the user which documents to close.
    `PermissionError` is what a locked file raises on Windows; a real OS lock is not portable
    (flock does not block rename on macOS), so a "real lock" test would pass by doing nothing.
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    history_id, new_paths = _apply_batch(service, ws_id, root, originals)

    locked_targets = {new_paths[7], new_paths[23]}
    real_rename = os.rename

    def locked_rename(src, dst, *args, **kwargs):
        if str(src) in locked_targets:
            raise PermissionError(13, "The process cannot access the file")
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "rename", locked_rename)
    result = service.undo_rename(ws_id, history_id=history_id)
    monkeypatch.undo()

    assert result["status"] == "multi_status", "a partial revert is not a plain success"
    assert result["reverted_count"] == FILE_COUNT - 2
    assert len(result["failed"]) == 2

    # The failure entries identify the files, and carry a code rather than a raw exception string.
    for entry in result["failed"]:
        assert entry["file_id"], entry
        assert entry["error_code"], entry
    assert {e["current_path"] for e in result["failed"]} == locked_targets

    # The 48 really moved; the 2 really did not.
    assert os.path.exists(new_paths[7]) and os.path.exists(new_paths[23])
    reverted = [p for i, p in enumerate(originals) if i not in (7, 23)]
    assert all(os.path.exists(p) for p in reverted)


def test_a_partial_revert_stays_retryable(batch_env, monkeypatch):
    """
    The 2 locked files must be recoverable after the user closes them.

    A partial revert must NOT be flagged `reverted`, or the remaining files are stranded behind
    ALREADY_UNDONE with no way to finish — the batch genuinely is not undone.
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    history_id, new_paths = _apply_batch(service, ws_id, root, originals)

    locked = {new_paths[7], new_paths[23]}
    real_rename = os.rename
    monkeypatch.setattr(
        os, "rename",
        lambda s, d, *a, **k: (_ for _ in ()).throw(PermissionError(13, "locked"))
        if str(s) in locked else real_rename(s, d, *a, **k),
    )
    service.undo_rename(ws_id, history_id=history_id)
    monkeypatch.undo()

    row = db_mgr.get_connection().execute(
        "SELECT status, undone_at FROM Rename_History WHERE history_id = ?;", (history_id,)
    ).fetchone()
    assert row["status"] != "reverted"
    assert row["undone_at"] is None

    # The lock is gone; a retry completes the job.
    retry = service.undo_rename(ws_id, history_id=history_id)
    assert retry.get("error_code") != "ALREADY_UNDONE"
    assert all(os.path.exists(p) for p in originals), "the retry must finish the remaining files"


def test_the_failure_list_carries_no_exception_text(batch_env, monkeypatch):
    """
    DEC-03: a failure entry holds `file_id` + `error.code`, never a raw exception string.

    An OSError stringifies to the path it failed on, so echoing it would put an absolute path in
    something the frontend renders.
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    history_id, new_paths = _apply_batch(service, ws_id, root, originals)

    real_rename = os.rename
    monkeypatch.setattr(
        os, "rename",
        lambda s, d, *a, **k: (_ for _ in ()).throw(PermissionError(13, "locked"))
        if str(s) == new_paths[0] else real_rename(s, d, *a, **k),
    )
    result = service.undo_rename(ws_id, history_id=history_id)
    monkeypatch.undo()

    entry = result["failed"][0]
    assert entry["error_code"] == "PermissionError"
    # The code names the type; the message must not be a traceback or carry the account path.
    assert "Traceback" not in str(entry)
    assert "/Users/" not in str(entry.get("error_message", ""))


# --- AC Scenario 3: TC-SEC-005 -----------------------------------------------------------


def test_scenario_3_the_rename_prompt_leaks_neither_pii_nor_the_account_path(batch_env):
    """
    AC S3 / TC-SEC-005 verbatim, with the AC's own path:
    `C:\\Users\\hong\\기밀\\홍길동_주민등록증_900101-1234567.pdf`.

    Inspects the transmitted payload, not the returned name. A test asserting on the suggestion
    would pass even while the prompt carried the RRN — which is how the `\\b`-boundary leak in
    issue #37 survived for as long as it did.
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    rrn = "900101-1234567"
    filename = f"홍길동_주민등록증_{rrn}.pdf"
    windows_path = f"C:\\Users\\hong\\기밀\\{filename}"

    router = RecordingLlmRouter(reply="2026-08_신분증_사본.pdf")
    secure_service = RenameService(
        db_mgr=db_mgr, llm_router=router, resilience=NoRetryResilience()
    )
    secure_service.process_rename_suggestions(ws_id, [{
        "file_id": "f-sec", "file_name": filename, "extension": ".pdf",
        "current_path": windows_path,
    }])

    assert len(router.prompts) == 1
    payload = router.prompts[0]

    # The RRN is absent and replaced by the type token.
    assert rrn not in payload
    assert "[PII:RRN]" in payload
    # No account path, drive letter, or the confidential folder's full location.
    assert "C:\\Users\\hong" not in payload
    assert "C:\\" not in payload
    assert "Users" not in payload
    assert windows_path not in payload
    # The 1-depth folder name alone IS the documented allowance.
    assert "기밀" in payload


def test_a_prompt_for_fifty_files_leaks_nothing_across_the_batch(batch_env):
    """
    TC-SEC-005 at batch scale: 50 prompts, none carrying a path.

    One clean prompt does not prove fifty are clean — the masking gate runs per file, so a
    per-file branch could leak on a subset (an unusual filename, a masking failure fallback).
    """
    service, file_repo, db_mgr, ws_id, root, originals = batch_env
    router = RecordingLlmRouter(reply="2026-08_문서.txt")
    secure_service = RenameService(
        db_mgr=db_mgr, llm_router=router, resilience=NoRetryResilience()
    )

    files = [
        {
            "file_id": f"f{i}", "file_name": os.path.basename(path), "extension": ".txt",
            "current_path": path,
        }
        for i, path in enumerate(originals)
    ]
    secure_service.process_rename_suggestions(ws_id, files)

    assert len(router.prompts) == FILE_COUNT
    for payload in router.prompts:
        assert root not in payload, "an absolute path reached a prompt"
        assert "/Users/" not in payload
        assert "C:\\" not in payload
