"""
RN-CMD-03 (issue #39) — 100% undo, and the ALREADY_UNDONE refusal.

Three gaps this closes:

1. `undo_rename` never read `Rename_History.status`, so a second undo of the same batch walked
   the same pairs again. Every file is already back at `old_path` by then, so
   `os.path.exists(new_path)` fails for all of them and the caller got per-file `FILE_NOT_FOUND`
   — an error describing a missing file when the truth is the work was already done. RenamePage
   has been reading `ALREADY_UNDONE` off `error_code` this whole time, and nothing produced it.
2. No `status='reverted'` / `undone_at` write, so nothing recorded that a batch had been undone.
3. Forward iteration, which breaks a chained batch (A→B, B→C).

AC S2 (deeplink integrity) is asserted through the real DeepLinkService rather than by reading
`current_path` directly — the claim is that clicking a wiki link still opens the file, and
DEC-08 makes that a `file_id` → `current_path` resolution, not a string comparison.
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


@pytest.fixture
def undo_env():
    """A workspace with two real files on disk, already scanned into File_Meta."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "undo.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Undo WS", [root])["workspace_id"]

            originals = []
            rows = []
            for name in ("기획서_초안.txt", "회의록.txt"):
                path = os.path.join(root, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"content of {name}")
                originals.append(path)
                rows.append({
                    "file_id": str(uuid.uuid4()),
                    "workspace_id": ws_id,
                    "current_path": path,
                    "original_path": path,
                    "file_name": name,
                    "extension": ".txt",
                    "size_bytes": 10,
                    "last_modified": 1700000000.0,
                    "parse_status": "pending",
                    "importance_score": 0,
                })
            file_repo.bulk_upsert(rows)

            service = RenameService(db_mgr=db_mgr)
            yield service, db_mgr, file_repo, ws_id, root, originals
        finally:
            db_mgr.close()


def _apply_a_batch(service, ws_id, root, originals):
    """Rename both files through the real apply path and return (history_id, new_paths)."""
    conn = service.db_mgr.get_connection()
    new_paths = []
    items = []
    for old_path in originals:
        new_path = os.path.join(root, f"2026-08_{os.path.basename(old_path)}")
        file_id = conn.execute(
            "SELECT file_id FROM File_Meta WHERE current_path = ?;", (old_path,)
        ).fetchone()["file_id"]
        items.append({"file_id": file_id, "old_path": old_path, "new_path": new_path})
        new_paths.append(new_path)

    history_id = str(uuid.uuid4())
    with service.db_mgr.transaction() as c:
        c.execute(
            """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
               VALUES (?, ?, ?, ?, 'applied');""",
            (history_id, ws_id, json.dumps(originals), json.dumps(new_paths)),
        )
    service.apply_rename(ws_id, items=items)
    return history_id, new_paths


# --- AC Scenario 1: 100% rollback --------------------------------------------------------


def test_scenario_1_undo_restores_disk_and_db_exactly(undo_env):
    """
    AC S1: the physical names and `File_Meta.current_path` return to exactly the originals.

    "100%" is asserted on both sides — disk and DB — because either alone can be right while the
    other drifts, and a DB that disagrees with disk is what produces broken deeplinks.
    """
    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    history_id, new_paths = _apply_a_batch(service, ws_id, root, originals)

    # Precondition: the rename really happened.
    assert all(os.path.exists(p) for p in new_paths)
    assert not any(os.path.exists(p) for p in originals)

    result = service.undo_rename(ws_id, history_id=history_id)

    assert result["status"] == "reverted"
    assert result["reverted_count"] == 2
    assert result["failed"] == []
    # Disk is back.
    for path in originals:
        assert os.path.exists(path), path
    for path in new_paths:
        assert not os.path.exists(path), path
    # DB is back, and the file content was never touched.
    db_paths = {r["current_path"] for r in file_repo.list_by_workspace(ws_id)}
    assert db_paths == set(originals)
    with open(originals[0], encoding="utf-8") as f:
        assert "기획서_초안" in f.read()


def test_undo_records_reverted_status_and_a_timestamp(undo_env):
    """The history row must say it was undone, and when (DEC-11 TEXT ISO-8601 UTC)."""
    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    history_id, _ = _apply_a_batch(service, ws_id, root, originals)

    service.undo_rename(ws_id, history_id=history_id)

    row = db_mgr.get_connection().execute(
        "SELECT status, undone_at FROM Rename_History WHERE history_id = ?;", (history_id,)
    ).fetchone()
    assert row["status"] == "reverted"
    assert row["undone_at"] is not None
    assert row["undone_at"].endswith("Z"), row["undone_at"]


def test_undo_leaves_original_path_untouched(undo_env):
    """
    DEC-08: `original_path` is immutable audit data — undo reverts `current_path` only.

    Rewriting it would erase where the file was first found, which is the one record that
    survives every rename.
    """
    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    before = {
        r["file_id"]: r["original_path"]
        for r in db_mgr.get_connection().execute(
            "SELECT file_id, original_path FROM File_Meta WHERE workspace_id = ?;", (ws_id,)
        ).fetchall()
    }
    history_id, _ = _apply_a_batch(service, ws_id, root, originals)
    service.undo_rename(ws_id, history_id=history_id)

    after = {
        r["file_id"]: r["original_path"]
        for r in db_mgr.get_connection().execute(
            "SELECT file_id, original_path FROM File_Meta WHERE workspace_id = ?;", (ws_id,)
        ).fetchall()
    }
    assert after == before


# --- ALREADY_UNDONE (the code RenamePage was already expecting) --------------------------


def test_a_second_undo_returns_already_undone(undo_env):
    """
    The gap this issue names: a repeated undo must refuse, not report FILE_NOT_FOUND.

    Before the fix the second pass re-walked the pairs, found nothing at `new_path`, and
    reported a per-file missing-file error — which describes the wrong problem.
    """
    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    history_id, _ = _apply_a_batch(service, ws_id, root, originals)
    service.undo_rename(ws_id, history_id=history_id)

    second = service.undo_rename(ws_id, history_id=history_id)

    assert second["error_code"] == "ALREADY_UNDONE"
    assert second["status"] == "already_undone"
    assert second["reverted_count"] == 0
    assert second["failed"] == [], "a refusal is not a per-file failure"
    assert second["undone_at"] is not None


def test_a_second_undo_does_not_touch_an_unrelated_new_file(undo_env):
    """
    The concrete harm the guard prevents.

    If the user creates a new file at one of the old `new_path` names after undoing, a second
    undo would rename *that* file — silently moving a document the batch never owned.
    """
    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    history_id, new_paths = _apply_a_batch(service, ws_id, root, originals)
    service.undo_rename(ws_id, history_id=history_id)

    # The user happens to create a file with the same name the rename had used.
    with open(new_paths[0], "w", encoding="utf-8") as f:
        f.write("완전히 다른 문서")

    service.undo_rename(ws_id, history_id=history_id)

    assert os.path.exists(new_paths[0]), "an unrelated file was moved by a repeat undo"
    with open(new_paths[0], encoding="utf-8") as f:
        assert f.read() == "완전히 다른 문서"


def test_a_partial_revert_is_not_flagged_reverted(undo_env):
    """
    A partial revert must stay retryable.

    Some files are still at their new names, so the batch is genuinely not undone. Flagging it
    would strand those files behind ALREADY_UNDONE with no way to finish.
    """
    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    history_id, new_paths = _apply_a_batch(service, ws_id, root, originals)

    # Remove one renamed file so its revert cannot succeed.
    os.unlink(new_paths[0])

    result = service.undo_rename(ws_id, history_id=history_id)

    assert result["status"] == "multi_status"
    assert len(result["failed"]) == 1
    row = db_mgr.get_connection().execute(
        "SELECT status, undone_at FROM Rename_History WHERE history_id = ?;", (history_id,)
    ).fetchone()
    assert row["status"] != "reverted"
    assert row["undone_at"] is None
    # And a retry is still permitted rather than refused.
    retry = service.undo_rename(ws_id, history_id=history_id)
    assert retry.get("error_code") != "ALREADY_UNDONE"


# --- AC Scenario 2: deeplinks still resolve after undo (DEC-08) --------------------------


def test_scenario_2_deeplinks_resolve_after_rename_then_undo(undo_env):
    """
    AC S2: the wiki link still opens the file, and reports `is_broken: false`.

    Asserted through the real DeepLinkService, because DEC-08's claim is that a `file_id`
    resolves late to whatever `current_path` currently says — a string comparison would not
    exercise that resolution. The wiki body is never rewritten by rename or undo.
    """
    from src.backend.services.query_services import DeepLinkQueryService

    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    file_id = db_mgr.get_connection().execute(
        "SELECT file_id FROM File_Meta WHERE current_path = ?;", (originals[0],)
    ).fetchone()["file_id"]

    # A wiki row anchored by file_id — the only allowed deeplink form (DEC-08).
    wiki_id = str(uuid.uuid4())
    markdown = f"기획 내용을 정리했습니다. [[file_id:{file_id}]]"
    with db_mgr.transaction() as c:
        c.execute(
            """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
               VALUES (?, ?, ?, ?);""",
            (wiki_id, ws_id, "docs", markdown),
        )

    history_id, _ = _apply_a_batch(service, ws_id, root, originals)
    service.undo_rename(ws_id, history_id=history_id)

    status = DeepLinkQueryService(db_mgr).check_deeplink_status(ws_id, file_id)
    assert status["is_broken"] is False, status
    # Late binding (DEC-08): the id resolved to the reverted path, not a cached one.
    assert status["current_path"] == originals[0]

    # The wiki body was never rewritten — rename and undo touch File_Meta only (DEC-08).
    stored = db_mgr.get_connection().execute(
        "SELECT markdown_content FROM Wiki_Content WHERE wiki_id = ?;", (wiki_id,)
    ).fetchone()["markdown_content"]
    assert stored == markdown
    assert root not in stored, "no absolute path may be persisted in wiki markdown"


# --- Ordering ---------------------------------------------------------------------------


def test_a_chained_batch_is_undone_in_reverse_order(undo_env):
    """
    A batch whose targets chain must be undone last-first (LIFO).

    `apply_rename` walks `items` in list order, so a chain that applies cleanly is
    `[b→c, a→b]`: b vacates before a needs it. Undoing that in the *same* order would try
    `c→b` while the file formerly at `a` still occupies `b`, and SQLite rejects the
    `UNIQUE(workspace_id, current_path)` write. Reverse order frees each target first.

    Constructed by hand because `process_rename_suggestions` derives each new name from its own
    file and so never produces a chain — but a user-approved diff can, and this is the ordering
    that makes it revertible.
    """
    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    a = os.path.join(root, "a.txt")
    b = os.path.join(root, "b.txt")
    c = os.path.join(root, "c.txt")
    with open(a, "w", encoding="utf-8") as f:
        f.write("A")
    with open(b, "w", encoding="utf-8") as f:
        f.write("B")

    rows = []
    for path in (a, b):
        rows.append({
            "file_id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "current_path": path,
            "original_path": path,
            "file_name": os.path.basename(path),
            "extension": ".txt",
            "size_bytes": 1,
            "last_modified": 1700000000.0,
            "parse_status": "pending",
            "importance_score": 0,
        })
    file_repo.bulk_upsert(rows)

    conn = db_mgr.get_connection()
    a_id = conn.execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (a,)).fetchone()["file_id"]
    b_id = conn.execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (b,)).fetchone()["file_id"]

    # Chain in the order apply_rename can actually execute: b vacates, then a takes its place.
    history_id = str(uuid.uuid4())
    with db_mgr.transaction() as tx:
        tx.execute(
            """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
               VALUES (?, ?, ?, ?, 'applied');""",
            (history_id, ws_id, json.dumps([b, a]), json.dumps([c, b])),
        )
    applied = service.apply_rename(
        ws_id,
        items=[
            {"file_id": b_id, "old_path": b, "new_path": c},
            {"file_id": a_id, "old_path": a, "new_path": b},
        ],
    )
    assert applied.get("failed") == [], applied
    assert os.path.exists(b) and os.path.exists(c) and not os.path.exists(a)

    result = service.undo_rename(ws_id, history_id=history_id)

    assert result["failed"] == [], result["failed"]
    assert result["status"] == "reverted"
    with open(a, encoding="utf-8") as f:
        assert f.read() == "A"
    with open(b, encoding="utf-8") as f:
        assert f.read() == "B"
    assert not os.path.exists(c)


# --- The endpoint (DEC-03 / DEC-04) -----------------------------------------------------


def test_the_endpoint_reports_already_undone_as_a_failed_task(undo_env):
    """
    DEC-03 lists ALREADY_UNDONE as a standard code, and RenamePage reads it off `error_code`
    after polling. So it must be a *failed* task, not a completed one with the status buried in
    `result` — otherwise the frontend's error branch never fires.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    service, db_mgr, file_repo, ws_id, root, originals = undo_env
    history_id, _ = _apply_a_batch(service, ws_id, root, originals)
    service.undo_rename(ws_id, history_id=history_id)

    app = create_app(db_mgr, session_token="undo-token")
    headers = {"Authorization": "Bearer undo-token"}
    client = TestClient(app)
    try:
        res = client.post(
            f"/api/v1/workspace/{ws_id}/rename/undo",
            json={"history_id": history_id},
            headers=headers,
        )
        assert res.status_code == 202, res.text
        task_id = res.json()["data"]["task_id"]
        assert app.state.task_runner.wait(task_id, timeout=20)

        progress = client.get(f"/api/v1/analyze/{task_id}/progress", headers=headers).json()["data"]
        assert progress["status"] == "failed"
        assert progress["error_code"] == "ALREADY_UNDONE"
    finally:
        for tid in list(app.state.task_runner.active_task_ids()):
            app.state.task_runner.wait(tid, timeout=10)
