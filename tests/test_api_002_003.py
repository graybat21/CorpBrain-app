import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from src.backend.api.app import create_app
from src.backend.db import DatabaseManager


@pytest.fixture
def api_client_extended():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "api_ext_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        auth_token = "test_bearer_ext_token"
        app = create_app(db_mgr, session_token=auth_token)
        client = TestClient(app)
        yield client, auth_token, tmpdir, app
        db_mgr.close()


def test_scan_and_fast_analysis_endpoints(api_client_extended):
    client, token, tmpdir, app = api_client_extended
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create workspace
    res = client.post("/api/v1/workspace", json={"workspace_name": "Ext WS", "root_paths": [tmpdir]}, headers=headers)
    assert res.status_code == 201
    ws_id = res.json()["data"]["workspace_id"]

    # Create a dummy file in tmpdir
    with open(os.path.join(tmpdir, "사업기획서_최종.docx"), "w", encoding="utf-8") as f:
        f.write("content")

    # 2. Trigger Scan
    res_scan = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
    assert res_scan.status_code == 200
    scan_data = res_scan.json()["data"]
    assert scan_data["scanned_count"] == 1
    assert scan_data["limit_reached"] is False

    # 3. Trigger Fast Analysis
    res_ana = client.post(f"/api/v1/workspace/{ws_id}/analysis/fast", headers=headers)
    assert res_ana.status_code == 200
    ana_data = res_ana.json()["data"]
    assert len(ana_data["items"]) == 1
    assert ana_data["items"][0]["importance_score"] >= 65


def test_llm_config_and_rename_endpoints(api_client_extended):
    client, token, tmpdir, app = api_client_extended
    headers = {"Authorization": f"Bearer {token}"}

    # GET LLM Config — is_healthy reflects a real probe, not a hardcoded value (DEC-13).
    # Default mode is Option A with no API key configured in a fresh DB, so it must be false.
    res_get = client.get("/api/v1/config/llm", headers=headers)
    assert res_get.status_code == 200
    health = res_get.json()["data"]
    assert health["mode"] == "Option A"
    assert health["api_key_configured"] is False
    assert health["is_healthy"] is False
    assert health["error_code"] == "API_KEY_NOT_CONFIGURED"
    # Daemon reachability is reported separately from the engine verdict (DEC-13).
    assert "daemon_online" in health
    assert "embedding_model_ready" in health
    assert "generation_model_ready" in health

    # POST Valid LLM Config
    res_post = client.post("/api/v1/config/llm", json={"llm_mode": "Option B"}, headers=headers)
    assert res_post.status_code == 200
    assert res_post.json()["data"]["llm_mode"] == "Option B"

    # POST Invalid LLM Config (Validation error 422)
    res_invalid = client.post("/api/v1/config/llm", json={"llm_mode": "InvalidMode"}, headers=headers)
    assert res_invalid.status_code == 422

    # Create WS & Generate Rename Diff
    res_ws = client.post("/api/v1/workspace", json={"workspace_name": "Rename WS", "root_paths": [tmpdir]}, headers=headers)
    ws_id = res_ws.json()["data"]["workspace_id"]

    res_rename = client.post(f"/api/v1/workspace/{ws_id}/rename/diff", headers=headers)
    assert res_rename.status_code == 200
    assert res_rename.json()["ok"] is True
