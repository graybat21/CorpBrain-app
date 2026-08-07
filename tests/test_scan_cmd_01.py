import os
import tempfile

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService


@pytest.fixture
def scanner_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "scan_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        ws_repo = WorkspaceRepository(db_mgr=db_mgr)
        file_repo = FileRepository(db_mgr=db_mgr)

        ws_dir = os.path.join(tmpdir, "test_ws")
        os.makedirs(ws_dir)
        ws = ws_repo.create("Scan WS", ws_dir)

        service = ScannerService(file_repo=file_repo)
        yield service, file_repo, ws["workspace_id"], ws_dir
        db_mgr.close()


def test_scenario_1_blacklist_filtering(scanner_setup):
    service, file_repo, ws_id, ws_dir = scanner_setup

    # Create valid files
    with open(os.path.join(ws_dir, "doc1.md"), "w") as f:
        f.write("# Hello")
    with open(os.path.join(ws_dir, "data.txt"), "w") as f:
        f.write("text content")

    # Create blacklisted folder & unsupported file
    git_dir = os.path.join(ws_dir, ".git")
    os.makedirs(git_dir)
    with open(os.path.join(git_dir, "config.md"), "w") as f:
        f.write("git config")

    with open(os.path.join(ws_dir, "unsupported.exe"), "w") as f:
        f.write("binary")

    records, limit_reached = service.scan_workspace(ws_id, ws_dir)
    assert limit_reached is False
    assert len(records) == 2

    file_names = {r["file_name"] for r in records}
    assert file_names == {"doc1.md", "data.txt"}

    # Verify saved in DB
    db_records = file_repo.list_by_workspace(ws_id)
    assert len(db_records) == 2


def test_scenario_2_file_limit_guard(scanner_setup):
    service, file_repo, ws_id, ws_dir = scanner_setup

    # Temporarily set limit to 5 for test
    original_limit = service.MAX_FILE_LIMIT
    service.MAX_FILE_LIMIT = 5

    try:
        for i in range(10):
            with open(os.path.join(ws_dir, f"file_{i}.txt"), "w") as f:
                f.write(f"content {i}")

        records, limit_reached = service.scan_workspace(ws_id, ws_dir)
        assert limit_reached is True
        assert len(records) == 5
    finally:
        service.MAX_FILE_LIMIT = original_limit
