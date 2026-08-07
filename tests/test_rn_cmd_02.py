import os
import tempfile

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.rename_service import RenameService
from src.backend.services.scanner_service import ScannerService


@pytest.fixture
def rn_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "rn2_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)

        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)
        scanner = ScannerService(file_repo)

        ws_res = ws_repo.create("Rename Test WS", tmpdir)
        ws_id = ws_res["workspace_id"]

        f1 = os.path.join(tmpdir, "original_doc1.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("CorpBrain Rename Test Document 1.\n")

        f2 = os.path.join(tmpdir, "original_doc2.md")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("# Architecture Notes\n")

        # Scan workspace files
        scanner.scan_workspace(ws_id, tmpdir)

        # Retrieve scanned file IDs
        scanned = file_repo.list_by_workspace(ws_id)
        f1_rec = next(r for r in scanned if r["file_name"] == "original_doc1.txt")
        f2_rec = next(r for r in scanned if r["file_name"] == "original_doc2.md")

        f1_id = f1_rec["file_id"]
        f2_id = f2_rec["file_id"]

        # Create Wiki_Content referencing f1_id
        conn = db_mgr.get_connection()
        conn.execute(
            f"""INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
               VALUES ('wiki_uuid_001', ?, 'Tech', 'Reference link: [[{f1_id}:original_doc1.txt]]');""",
            (ws_id,)
        )

        rs = RenameService(db_mgr)
        yield rs, db_mgr, ws_id, tmpdir, f1, f2, f1_id, f2_id
        db_mgr.close()


def test_scenario_1_apply_rename_executes_os_rename_and_updates_file_meta(rn_setup):
    rs, db_mgr, ws_id, tmpdir, f1, f2, f1_id, f2_id = rn_setup

    new_f1 = os.path.join(tmpdir, "2026-08_original_doc1.txt")
    items = [{
        "file_id": f1_id,
        "old_path": f1,
        "new_path": new_f1
    }]

    res = rs.apply_rename(ws_id, items=items)

    assert res["status"] == "applied"
    assert res["applied_count"] == 1
    assert os.path.exists(new_f1)
    assert not os.path.exists(f1)

    # Verify File_Meta in SQLite (DEC-08: original_path MUST NOT change)
    conn = db_mgr.get_connection()
    row = conn.cursor().execute(f"SELECT current_path, original_path, file_name FROM File_Meta WHERE file_id = '{f1_id}';").fetchone()

    assert row["current_path"] == new_f1
    assert row["file_name"] == "2026-08_original_doc1.txt"
    assert row["original_path"] == f1  # Immutable original path preserved


def test_scenario_2_rename_does_not_break_deeplinks_or_wiki_contents(rn_setup):
    rs, db_mgr, ws_id, tmpdir, f1, f2, f1_id, f2_id = rn_setup

    new_f1 = os.path.join(tmpdir, "Renamed_Doc1.txt")
    items = [{"file_id": f1_id, "old_path": f1, "new_path": new_f1}]

    rs.apply_rename(ws_id, items=items)

    # DEC-08: Wiki_Content.markdown_content MUST be 100% byte-for-byte unchanged
    conn = db_mgr.get_connection()
    wiki_content = conn.cursor().execute("SELECT markdown_content FROM Wiki_Content WHERE wiki_id = 'wiki_uuid_001';").fetchone()[0]

    assert wiki_content == f"Reference link: [[{f1_id}:original_doc1.txt]]"


def test_scenario_3_apply_rename_partial_failure_isolation(rn_setup):
    rs, db_mgr, ws_id, tmpdir, f1, f2, f1_id, f2_id = rn_setup

    bad_path = os.path.join(tmpdir, "non_existent_file.txt")
    new_f2 = os.path.join(tmpdir, "Renamed_Doc2.md")

    items = [
        {"file_id": "rn_uuid_bad", "old_path": bad_path, "new_path": os.path.join(tmpdir, "new_bad.txt")},
        {"file_id": f2_id, "old_path": f2, "new_path": new_f2}
    ]

    res = rs.apply_rename(ws_id, items=items)

    assert res["status"] == "multi_status"
    assert res["applied_count"] == 1
    assert len(res["failed"]) == 1
    assert res["failed"][0]["file_id"] == "rn_uuid_bad"
    assert res["failed"][0]["error_code"] == "FILE_NOT_FOUND"


def test_scenario_4_undo_rename_reverts_physical_file_and_meta(rn_setup):
    rs, db_mgr, ws_id, tmpdir, f1, f2, f1_id, f2_id = rn_setup

    # First apply rename diff suggestions
    files = db_mgr.get_connection().cursor().execute("SELECT * FROM File_Meta WHERE workspace_id = ?;", (ws_id,)).fetchall()
    file_dicts = [dict(r) for r in files]
    # Called for its side effect: it writes the Rename_History row read just below.
    rs.process_rename_suggestions(ws_id, file_dicts)

    # Get generated Rename_History history_id
    conn = db_mgr.get_connection()
    hist_row = conn.cursor().execute("SELECT history_id FROM Rename_History WHERE workspace_id = ?;", (ws_id,)).fetchone()
    hist_id = hist_row["history_id"]

    # Apply rename
    items = []
    old_list = [f1, f2]
    new_list = [os.path.join(tmpdir, f"2026-08_{os.path.basename(p)}") for p in old_list]
    for old_p, new_p in zip(old_list, new_list, strict=True):
        c = conn.cursor().execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (old_p,)).fetchone()
        items.append({"file_id": c["file_id"], "old_path": old_p, "new_path": new_p})

    rs.apply_rename(ws_id, items=items)

    # Execute Undo Rename (RN-CMD-03)
    undo_res = rs.undo_rename(ws_id, history_id=hist_id)

    assert undo_res["status"] == "reverted"
    assert undo_res["reverted_count"] == 2
    assert os.path.exists(f1)
    assert os.path.exists(f2)

    # Verify File_Meta is restored to f1 and f2
    r1 = conn.cursor().execute(f"SELECT current_path FROM File_Meta WHERE file_id = '{f1_id}';").fetchone()[0]
    assert r1 == f1
