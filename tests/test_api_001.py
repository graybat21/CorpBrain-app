import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.backend.api.app import create_app
from src.backend.api.dtos import WorkspaceCreateReq
from src.backend.db import DatabaseManager


@pytest.fixture
def api_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "api_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        token = "test_bearer_token_12345"
        app = create_app(db_mgr=db_mgr, session_token=token)
        # TestClient must be used as a context manager: only then does it run the lifespan
        # shutdown that closes the Chroma client. Without it the DELETE test leaves
        # vectors/chroma.sqlite3 open and TemporaryDirectory cleanup fails on Windows
        # (PermissionError [WinError 32]).
        with TestClient(app) as client:
            yield client, token, tmpdir
        db_mgr.close()


def test_dto_validation():
    # Invalid empty workspace_name
    with pytest.raises(ValidationError):
        WorkspaceCreateReq(workspace_name="", root_paths=["C:\\valid_path"])

    # Invalid empty path element
    with pytest.raises(ValidationError):
        WorkspaceCreateReq(workspace_name="Valid Name", root_paths=[""])


def test_bearer_auth_middleware(api_client):
    client, token, tmpdir = api_client

    # No auth header -> 401
    res = client.get("/api/v1/workspace")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"

    # Wrong token -> 401
    res = client.get("/api/v1/workspace", headers={"Authorization": "Bearer wrong_token"})
    assert res.status_code == 401

    # Valid token -> 200
    res = client.get("/api/v1/workspace", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_workspace_api_crud(api_client):
    client, token, tmpdir = api_client
    headers = {"Authorization": f"Bearer {token}"}

    ws_dir = os.path.join(tmpdir, "ws_real")
    os.makedirs(ws_dir)

    # 1. Create Workspace
    payload = {"workspace_name": "API Workspace", "root_paths": [ws_dir]}
    res = client.post("/api/v1/workspace", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["ok"] is True
    ws_id = data["data"]["workspace_id"]
    assert ws_id is not None

    # 2. Get Workspace by ID
    res = client.get(f"/api/v1/workspace/{ws_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["workspace_name"] == "API Workspace"

    # 3. List Workspaces
    res = client.get("/api/v1/workspace", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["total"] == 1

    # 4. Delete Workspace
    res = client.delete(f"/api/v1/workspace/{ws_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["deleted"] is True

    # 5. Verify deleted
    res = client.get(f"/api/v1/workspace/{ws_id}", headers=headers)
    assert res.status_code == 404
