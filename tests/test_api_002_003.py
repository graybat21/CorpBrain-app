import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from src.backend.api.app import create_app
from src.backend.db import DatabaseManager
from tests.task_polling import poll_until_done


@pytest.fixture
def api_client_extended():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "api_ext_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        auth_token = "test_bearer_ext_token"
        app = create_app(db_mgr, session_token=auth_token)
        # Context manager form so the lifespan shutdown closes any Chroma client (see
        # test_api_001.py for the WinError 32 this prevents).
        with TestClient(app) as client:
            yield client, auth_token, tmpdir, app
        # A task worker holds its own thread-local sqlite3 connection, and on Windows an open
        # WAL reader blocks deleting the temp dir. Drain before closing so teardown is not a
        # race against a still-running task.
        for task_id in app.state.task_runner.active_task_ids():
            app.state.task_runner.wait(task_id, timeout=15)
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

    # 2. Trigger Scan — DEC-04: 202 + task_id, no result in the response body.
    res_scan = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
    assert res_scan.status_code == 202
    scan_task = res_scan.json()["data"]
    assert scan_task["task_type"] == "scan"
    assert scan_task["workspace_id"] == ws_id
    # The old synchronous shape is gone. Asserting its absence is what keeps a "convenience"
    # result field from creeping back in and giving the frontend a second, unspecified path.
    assert "scanned_count" not in scan_task

    scan_done = poll_until_done(client, headers, scan_task["task_id"])
    assert scan_done["status"] == "completed"
    # The scanned count is now read from the task's own counters, not from the POST response.
    assert scan_done["processed"] == 1
    assert scan_done["total"] == 1
    assert scan_done["percent"] == 100.0
    assert scan_done["error_code"] is None

    # 3. Trigger Fast Analysis — same contract.
    res_ana = client.post(f"/api/v1/workspace/{ws_id}/analysis/fast", headers=headers)
    assert res_ana.status_code == 202
    ana_task = res_ana.json()["data"]
    assert ana_task["task_type"] == "analyze_fast"

    ana_done = poll_until_done(client, headers, ana_task["task_id"])
    assert ana_done["status"] == "completed"
    assert ana_done["processed"] == 1

    # 4. The scores themselves come from their persisted rows, which is why the progress
    #    response is allowed to stay small (DEC-04).
    res_summary = client.get(f"/api/v1/workspace/{ws_id}/scan/summary", headers=headers)
    assert res_summary.status_code == 200
    assert res_summary.json()["data"]["file_count"] == 1

    files = app.state.scanner_service.file_repo.list_by_workspace(ws_id)
    assert len(files) == 1
    assert files[0]["importance_score"] >= 65


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
