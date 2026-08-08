"""
Issue #105 — multi-folder workspace merging.

`root_paths` with two folders stored only the first, and the scan walked only that one, so
every file in folders 2..N was dropped with no error and no warning. "2개 이상 로컬 폴더 병합"
is WS-CMD-01's own title and a PRD core feature.

These tests go through the real FastAPI app and a real SQLite file rather than asserting on the
service in isolation, because the defect survived a fully green unit suite and only surfaced
under a real HTTP call (DECISION_LOG 재발방지 5).
"""

import os
import tempfile
import uuid

from fastapi.testclient import TestClient

from src.backend.api.app import create_app
from src.backend.db import DatabaseManager
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService
from tests.task_polling import poll_until_done


def _two_root_dirs(base: str) -> tuple:
    """폴더 A 에 파일 1건, 폴더 B 에 파일 1건 (AC S1 Given)."""
    alpha = os.path.join(base, "알파")
    beta = os.path.join(base, "베타")
    os.makedirs(alpha)
    os.makedirs(beta)
    with open(os.path.join(alpha, "보고서.txt"), "w", encoding="utf-8") as f:
        f.write("알파 폴더 문서")
    with open(os.path.join(beta, "계약서.md"), "w", encoding="utf-8") as f:
        f.write("베타 폴더 문서")
    return alpha, beta


def _client(tmpdir: str):
    db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
    app = create_app(db_mgr=db_mgr)
    client = TestClient(app)
    token = app.state.session_token
    return db_mgr, app, client, {"Authorization": f"Bearer {token}"}


def test_scenario_1_two_folders_are_both_scanned():
    """
    AC S1: root_paths [A, B] -> File_Meta 2건, GET /file 2건.

    This is the exact reproduction from the issue body. Before the fix the response carried a
    single `root_path` and the scan reported total=1.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        alpha, beta = _two_root_dirs(tmpdir)
        db_mgr, app, client, headers = _client(tmpdir)
        try:
            res = client.post(
                "/api/v1/workspace",
                json={"workspace_name": "맥테스트", "root_paths": [alpha, beta]},
                headers=headers,
            )
            assert res.status_code == 201, res.text
            data = res.json()["data"]
            # Both roots come back, in the order they were submitted.
            assert len(data["root_paths"]) == 2
            assert [os.path.basename(p) for p in data["root_paths"]] == ["알파", "베타"]
            ws_id = data["workspace_id"]

            scan = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
            assert scan.status_code == 202, scan.text
            task_id = scan.json()["data"]["task_id"]
            progress = poll_until_done(client, headers, task_id)
            assert progress["status"] == "completed", progress
            assert progress["total"] == 2, progress

            listing = client.get(f"/api/v1/workspace/{ws_id}/file", headers=headers)
            assert listing.status_code == 200, listing.text
            names = sorted(item["file_name"] for item in listing.json()["data"]["items"])
            # The second folder's file is the one that used to vanish silently.
            assert names == ["계약서.md", "보고서.txt"], names
        finally:
            for tid in list(app.state.task_runner.active_task_ids()):
                app.state.task_runner.wait(tid, timeout=10)
            db_mgr.close()


def test_scenario_2_roots_persist_across_a_restart():
    """
    AC S2: reopening the database returns both roots.

    A second DatabaseManager over the same file is what "앱 재시작" means for persistence — the
    first manager is closed, so nothing is served from its connection or cache.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        alpha, beta = _two_root_dirs(tmpdir)
        db_path = os.path.join(tmpdir, "meta.db")

        first = DatabaseManager(db_path=db_path)
        try:
            ws = WorkspaceRepository(first).create("재시작", [alpha, beta])
            ws_id = ws["workspace_id"]
        finally:
            first.close()

        second = DatabaseManager(db_path=db_path)
        try:
            reopened = WorkspaceRepository(second).get_by_id(ws_id)
            assert reopened["root_paths"] == [alpha, beta]
        finally:
            second.close()


def test_scenario_3_legacy_single_root_is_migrated():
    """
    AC S3: a v001 row's root_path moves into Workspace_Root without loss.

    The v001-only starting state is built from the shipped migration file; the cross-version
    upgrade path itself is asserted in
    tests/test_ana_qry_02.py::test_v002_upgrades_an_existing_v001_database_without_data_loss.
    """
    import shutil

    migrations_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "migrations")
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        v001_only = os.path.join(tmpdir, "m_v001")
        os.makedirs(v001_only)
        shutil.copy(os.path.join(migrations_dir, "v001_initial_schema.sql"), v001_only)
        db_path = os.path.join(tmpdir, "legacy.db")

        ws_id = str(uuid.uuid4())
        old = DatabaseManager(db_path=db_path, migrations_dir=v001_only)
        try:
            with old.transaction() as tx:
                tx.execute(
                    "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
                    (ws_id, "구버전", "/legacy/root"),
                )
        finally:
            old.close()

        upgraded = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        try:
            conn = upgraded.get_connection()
            # The column is gone, so no consumer can accidentally keep reading root #1 from it.
            columns = [r[1] for r in conn.execute("PRAGMA table_info(Workspace_Meta);")]
            assert "root_path" not in columns
            assert WorkspaceRepository(upgraded).list_roots(ws_id) == ["/legacy/root"]
        finally:
            upgraded.close()


def test_root_rows_cascade_on_workspace_delete():
    """
    Workspace_Root.workspace_id is ON DELETE CASCADE (issue #105 / DEC-05).

    Without the cascade, deleting a workspace would leave orphan root rows that the UNIQUE
    constraint then blocks from being re-registered.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        alpha, beta = _two_root_dirs(tmpdir)
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            repo = WorkspaceRepository(db_mgr)
            ws_id = repo.create("삭제 대상", [alpha, beta])["workspace_id"]
            conn = db_mgr.get_connection()
            assert conn.execute("SELECT COUNT(*) FROM Workspace_Root;").fetchone()[0] == 2

            assert repo.delete(ws_id) is True
            assert conn.execute("SELECT COUNT(*) FROM Workspace_Root;").fetchone()[0] == 0

            # Re-registering the same folders must now succeed.
            repo.create("재등록", [alpha, beta])
        finally:
            db_mgr.close()


def test_duplicate_root_paths_are_collapsed_not_rejected():
    """
    The same folder submitted twice is one root, not a 500.

    The OS folder picker lets a user add the same directory twice, and a trailing separator
    normalises to the same path — either would hit UNIQUE(workspace_id, root_path) and fail the
    whole creation over what the user meant as one folder.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        alpha, _ = _two_root_dirs(tmpdir)
        db_mgr, app, client, headers = _client(tmpdir)
        try:
            res = client.post(
                "/api/v1/workspace",
                json={"workspace_name": "중복", "root_paths": [alpha, alpha + os.sep]},
                headers=headers,
            )
            assert res.status_code == 201, res.text
            assert res.json()["data"]["root_paths"] == [alpha]
        finally:
            db_mgr.close()


def test_scan_limit_is_a_workspace_total_not_per_root():
    """
    SCAN-CMD-02's 10,000 cap bounds the workspace, not each folder.

    Per-root budgets would let N folders index N x 10,000 files, which defeats the purpose of
    the guard. Asserted with a lowered MAX_FILE_LIMIT so the test does not create 10,001 files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        roots = []
        for name in ("r1", "r2"):
            d = os.path.join(tmpdir, name)
            os.makedirs(d)
            for i in range(3):
                with open(os.path.join(d, f"f{i}.txt"), "w", encoding="utf-8") as f:
                    f.write("x")
            roots.append(d)

        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            from src.backend.repositories.file_repository import FileRepository

            ws_id = WorkspaceRepository(db_mgr).create("상한", roots)["workspace_id"]
            scanner = ScannerService(FileRepository(db_mgr))
            scanner.MAX_FILE_LIMIT = 4  # instance attribute; the class default is untouched

            records, limit_reached = scanner.scan_workspace(ws_id, roots)
            assert limit_reached is True
            # Stopped at the shared budget, not at 4 files per root (which would be 6 or 8).
            assert len(records) == 4, [r["file_name"] for r in records]
        finally:
            db_mgr.close()


def test_nested_roots_do_not_double_register_a_file():
    """
    A user may pick a folder and its parent. That file must yield one File_Meta row.

    Two records for one path collide on UNIQUE(workspace_id, current_path) and inflate the
    scanned count the dashboard reports.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.backend.repositories.file_repository import FileRepository

        parent = os.path.join(tmpdir, "부모")
        child = os.path.join(parent, "자식")
        os.makedirs(child)
        with open(os.path.join(child, "문서.txt"), "w", encoding="utf-8") as f:
            f.write("한 번만")

        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            ws_id = WorkspaceRepository(db_mgr).create("중첩", [parent, child])["workspace_id"]
            scanner = ScannerService(FileRepository(db_mgr))
            records, _ = scanner.scan_workspace(ws_id, [parent, child])
            assert len(records) == 1, [r["current_path"] for r in records]
        finally:
            db_mgr.close()
