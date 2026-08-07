import os
import tempfile
import pytest
from src.backend.db import DatabaseManager
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.workspace_service import WorkspaceService


@pytest.fixture
def workspace_service():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ws_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        repo = WorkspaceRepository(db_mgr=db_mgr)
        service = WorkspaceService(repo=repo)
        yield service, tmpdir
        db_mgr.close()


def test_scenario_1_valid_folder_workspace_creation(workspace_service):
    service, tmpdir = workspace_service
    folder_a = os.path.join(tmpdir, "docs_a")
    folder_b = os.path.join(tmpdir, "docs_b")
    os.makedirs(folder_a)
    os.makedirs(folder_b)

    ws = service.create_workspace("Test WS", [folder_a, folder_b])
    assert ws is not None
    assert ws["workspace_name"] == "Test WS"
    assert ws["workspace_id"] is not None

    all_ws = service.list_workspaces()
    assert len(all_ws) == 1
    assert all_ws[0]["workspace_id"] == ws["workspace_id"]


def test_scenario_2_invalid_path_raises_not_found(workspace_service):
    service, tmpdir = workspace_service
    fake_path = os.path.join(tmpdir, "non_existent_dir_999")

    with pytest.raises(FileNotFoundError):
        service.create_workspace("Invalid WS", [fake_path])

    all_ws = service.list_workspaces()
    assert len(all_ws) == 0


def test_scenario_3_dec_09_deletion_order(workspace_service):
    class MockVectorStore:
        def __init__(self):
            self.deleted_collections = []

        def delete_collection(self, name):
            self.deleted_collections.append(name)

    service, tmpdir = workspace_service
    mock_vs = MockVectorStore()
    service.vector_store = mock_vs

    os.makedirs(os.path.join(tmpdir, "folder_del"))
    ws = service.create_workspace("Delete WS", [os.path.join(tmpdir, "folder_del")])
    ws_id = ws["workspace_id"]

    success = service.delete_workspace(ws_id)
    assert success is True
    assert f"ws_{ws_id}" in mock_vs.deleted_collections

    assert service.get_workspace(ws_id) is None
