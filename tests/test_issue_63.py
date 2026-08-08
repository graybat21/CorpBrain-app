"""
Regression tests for issue #63: workspace creation modal (WS-FE-02).

Issue #63 adds a workspace creation modal UI that:
1. Accepts workspace name + 2+ folder paths
2. Calls POST /api/v1/workspace
3. Shows success/error Toast feedback

This test verifies the API endpoint contract. UI modal rendering is verified manually.
The OS native folder picker integration is deferred to pywebview shell implementation (issue #14).
"""

import os
import tempfile

from src.backend.db import DatabaseManager

SESSION_TOKEN = "test-token-for-issue-63"


def test_create_workspace_with_multiple_paths():
    """
    AC S1: Multiple folder selection and creation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue63.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            from fastapi.testclient import TestClient

            from src.backend.api.app import create_app

            app = create_app(db_mgr, session_token=SESSION_TOKEN)
            client = TestClient(app)
            client.headers.update({"Authorization": f"Bearer {SESSION_TOKEN}"})

            folder_a = os.path.join(tmpdir, "FolderA")
            folder_b = os.path.join(tmpdir, "FolderB")
            os.makedirs(folder_a)
            os.makedirs(folder_b)

            # Create workspace with 2 paths
            res = client.post(
                "/api/v1/workspace",
                json={
                    "workspace_name": "Multi-Folder Test",
                    "root_paths": [folder_a, folder_b],
                },
            )

            assert res.status_code in (200, 201)
            data = res.json()["data"]
            assert data["workspace_name"] == "Multi-Folder Test"
            assert data["workspace_id"]

        finally:
            db_mgr.close()


def test_create_workspace_validation_fails_empty_name():
    """
    Client-side validation: workspace name required.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue63_validation.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            from fastapi.testclient import TestClient

            from src.backend.api.app import create_app

            app = create_app(db_mgr, session_token=SESSION_TOKEN)
            client = TestClient(app)
            client.headers.update({"Authorization": f"Bearer {SESSION_TOKEN}"})

            folder = os.path.join(tmpdir, "Folder")
            os.makedirs(folder)

            # Empty workspace name
            res = client.post(
                "/api/v1/workspace",
                json={"workspace_name": "", "root_paths": [folder]},
            )

            # Backend validation should catch this
            assert res.status_code == 422  # Validation error

        finally:
            db_mgr.close()


def test_create_workspace_invalid_path_error():
    """
    AC S2: Invalid path error handling (404).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue63_invalid.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            from fastapi.testclient import TestClient

            from src.backend.api.app import create_app

            app = create_app(db_mgr, session_token=SESSION_TOKEN)
            client = TestClient(app)
            client.headers.update({"Authorization": f"Bearer {SESSION_TOKEN}"})

            # Non-existent path
            fake_path = os.path.join(tmpdir, "NonExistentFolder")

            res = client.post(
                "/api/v1/workspace",
                json={"workspace_name": "Test", "root_paths": [fake_path]},
            )

            # Should fail with error
            assert res.status_code != 200
            # Error code should indicate path issue
            if res.status_code >= 400:
                error = res.json().get("error", {})
                assert error.get("code") in (
                    "NOT_FOUND",
                    "PATH_NOT_ACCESSIBLE",
                    "VALIDATION_FAILED",
                )

        finally:
            db_mgr.close()
