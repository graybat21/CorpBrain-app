import os
import tempfile

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScanLimitReachedException, ScannerService


def test_scan_limit_reached_exception():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "scan_limit_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        ws_repo = WorkspaceRepository(db_mgr=db_mgr)
        file_repo = FileRepository(db_mgr=db_mgr)

        ws_dir = os.path.join(tmpdir, "ws_limit")
        os.makedirs(ws_dir)
        ws = ws_repo.create("Limit WS", [ws_dir])

        service = ScannerService(file_repo=file_repo)
        service.MAX_FILE_LIMIT = 3

        for i in range(5):
            with open(os.path.join(ws_dir, f"test_{i}.md"), "w") as f:
                f.write(f"content {i}")

        with pytest.raises(ScanLimitReachedException):
            service.scan_workspace(ws["workspace_id"], ws_dir, raise_on_limit=True)

        db_mgr.close()
