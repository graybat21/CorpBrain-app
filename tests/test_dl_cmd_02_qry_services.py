import os
import tempfile
from unittest.mock import patch

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.deeplink_service import DeepLinkService
from src.backend.services.query_services import (
    DeepLinkQueryService,
    ScanQueryService,
    WorkspaceQueryService,
)


@pytest.fixture
def qry_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "qry_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)

        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)

        ws_res = ws_repo.create("Query Test WS", [tmpdir])
        ws_id = ws_res["workspace_id"]

        # Create a real temp file for path existence tests
        f1 = os.path.join(tmpdir, "report.docx")
        with open(f1, "w") as f:
            f.write("CorpBrain document content")

        f1_id = "qry_file_001"
        file_repo.bulk_upsert([{
            "workspace_id": ws_id,
            "file_id": f1_id,
            "current_path": f1,
            "original_path": f1,
            "file_name": "report.docx",
            "extension": ".docx",
            "size_bytes": 1024 * 512,  # 512 KB
            "last_modified": 1700000000.0,
            "parse_status": "parsed",
            "importance_score": 80,
        }])

        yield db_mgr, ws_id, f1_id, f1, tmpdir
        db_mgr.close()


def test_scenario_1_deeplink_open_file_success(qry_setup):
    db_mgr, ws_id, f1_id, f1, tmpdir = qry_setup
    svc = DeepLinkService(db_mgr)

    # Patch the launcher shim, not `os.startfile`: the attribute does not exist off Windows,
    # so `patch("os.startfile")` raised AttributeError on a macOS/Linux dev host before the
    # service was routed through platform_compat. Patching where the service looks the symbol
    # up keeps this test host-independent and still proves the path is passed through verbatim.
    with patch("src.backend.services.deeplink_service.open_with_default_app") as mock_open:
        result = svc.open_file(ws_id, f1_id)
        assert result["status"] == "success"
        assert result["file_id"] == f1_id
        # The response carries the file NAME (issue #19): `opened_path` used to return the full
        # absolute path to the client, which is precisely what DEC-08 keeps off it. The path is
        # still asserted — via the mock, which is where it legitimately appears, since the OS call
        # is the one consumer that needs it.
        assert result["file_name"] == os.path.basename(f1)
        assert "opened_path" not in result
        mock_open.assert_called_once_with(f1)


def test_scenario_2_deeplink_open_not_found(qry_setup):
    db_mgr, ws_id, f1_id, f1, tmpdir = qry_setup
    svc = DeepLinkService(db_mgr)

    result = svc.open_file(ws_id, "non_existent_file_id")
    assert result["status"] == "error"
    assert result["error_code"] == "NOT_FOUND"


def test_scenario_3_deeplink_open_path_not_accessible(qry_setup):
    db_mgr, ws_id, f1_id, f1, tmpdir = qry_setup
    svc = DeepLinkService(db_mgr)

    # Delete the actual file to simulate broken link
    os.remove(f1)

    result = svc.open_file(ws_id, f1_id)
    assert result["status"] == "error"
    assert result["error_code"] == "PATH_NOT_ACCESSIBLE"


def test_scenario_4_deeplink_query_status(qry_setup):
    db_mgr, ws_id, f1_id, f1, tmpdir = qry_setup
    svc = DeepLinkQueryService(db_mgr)

    # File exists -> not broken
    result = svc.check_deeplink_status(ws_id, f1_id)
    assert result["is_broken"] is False
    assert result["file_name"] == "report.docx"

    # Delete file -> broken
    os.remove(f1)
    result2 = svc.check_deeplink_status(ws_id, f1_id)
    assert result2["is_broken"] is True
    assert result2["reason"] == "PATH_NOT_ACCESSIBLE"


def test_scenario_5_scan_summary_query(qry_setup):
    db_mgr, ws_id, f1_id, f1, tmpdir = qry_setup
    svc = ScanQueryService(db_mgr)

    summary = svc.get_scan_summary(ws_id)
    assert summary["file_count"] == 1
    assert summary["total_size_mb"] == pytest.approx(0.5, abs=0.01)  # 512 KB = 0.5 MB
    assert summary["estimated_analysis_seconds"] == pytest.approx(0.1, abs=0.01)


def test_scenario_6_workspace_query_list(qry_setup):
    db_mgr, ws_id, f1_id, f1, tmpdir = qry_setup
    svc = WorkspaceQueryService(db_mgr)

    workspaces = svc.list_workspaces()
    assert len(workspaces) >= 1
    ws_ids = [w["workspace_id"] for w in workspaces]
    assert ws_id in ws_ids

    # Single workspace detail
    detail = svc.get_workspace(ws_id)
    assert detail is not None
    assert detail["workspace_id"] == ws_id
