"""
Regression tests for issue #5: wiki tab UI (ANA-FE-02).

Issue #5 adds the frontend wiki tab component that:
1. Fetches wiki tabs via GET /api/v1/workspace/{id}/wiki (ANA-QRY-01 from issue #7)
2. Renders 1-depth folder tabs with independent content (AC S1: folder isolation)
3. Renders markdown with [[file_id:UUID]] deeplink badges (AC S2)

This test verifies the API endpoint contract that the frontend consumes. UI rendering
is verified manually or through E2E tests (issue #94).
"""

import os
import tempfile

from src.backend.db import DatabaseManager
from tests.fakes import insert_workspace

# Test session token (same as other API tests)
SESSION_TOKEN = "test-token-for-issue-5"


def test_wiki_query_endpoint_returns_empty_tabs_for_new_workspace():
    """
    AC S1: Empty workspace returns empty tabs array.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue5_empty.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            from fastapi.testclient import TestClient

            from src.backend.api.app import create_app

            app = create_app(db_mgr, session_token=SESSION_TOKEN)
            client = TestClient(app)
            client.headers.update({"Authorization": f"Bearer {SESSION_TOKEN}"})

            # Create workspace
            ws_res = client.post(
                "/api/v1/workspace",
                json={"workspace_name": "Test", "root_paths": [tmpdir]},
            )
            assert ws_res.status_code in (200, 201)
            ws_id = ws_res.json()["data"]["workspace_id"]

            # Query wiki (no generation yet)
            wiki_res = client.get(f"/api/v1/workspace/{ws_id}/wiki")
            assert wiki_res.status_code == 200
            wiki_data = wiki_res.json()["data"]
            assert wiki_data["workspace_id"] == ws_id
            assert wiki_data["tabs"] == []

        finally:
            db_mgr.close()


def test_wiki_tabs_are_isolated_by_folder_1depth():
    """
    AC S1: Each folder_1depth gets its own independent tab.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue5_tabs.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            import uuid

            conn = db_mgr.get_connection()

            # Create workspace
            ws_id = str(uuid.uuid4())
            insert_workspace(conn, ws_id, "Test", tmpdir)

            # Insert wiki for two folders (current schema has no deeplink_mappings column)
            wiki_a_id = str(uuid.uuid4())
            wiki_b_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
                   VALUES (?, ?, ?, ?)""",
                (wiki_a_id, ws_id, "FolderA", "# Content A"),
            )
            conn.execute(
                """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
                   VALUES (?, ?, ?, ?)""",
                (wiki_b_id, ws_id, "FolderB", "# Content B"),
            )
            conn.commit()

            # Query wiki
            from fastapi.testclient import TestClient

            from src.backend.api.app import create_app

            app = create_app(db_mgr, session_token=SESSION_TOKEN)
            client = TestClient(app)
            client.headers.update({"Authorization": f"Bearer {SESSION_TOKEN}"})

            wiki_res = client.get(f"/api/v1/workspace/{ws_id}/wiki")
            assert wiki_res.status_code == 200
            tabs = wiki_res.json()["data"]["tabs"]

            assert len(tabs) == 2
            folders = {t["folder_1depth"] for t in tabs}
            assert folders == {"FolderA", "FolderB"}

            # Each tab has its own content
            tab_a = next(t for t in tabs if t["folder_1depth"] == "FolderA")
            tab_b = next(t for t in tabs if t["folder_1depth"] == "FolderB")
            assert "Content A" in tab_a["markdown_content"]
            assert "Content B" in tab_b["markdown_content"]
            assert "Content A" not in tab_b["markdown_content"]

        finally:
            db_mgr.close()


def test_markdown_contains_file_id_anchors_not_absolute_paths():
    """
    AC S2 / DEC-08: Markdown uses [[file_id:UUID]] anchors, not absolute paths.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue5_anchors.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            import uuid

            conn = db_mgr.get_connection()

            ws_id = str(uuid.uuid4())
            insert_workspace(conn, ws_id, "Test", tmpdir)

            file_id = str(uuid.uuid4())
            wiki_id = str(uuid.uuid4())

            # Wiki content with [[file_id:UUID]] anchor (DEC-08)
            markdown = f"# Test\n\nSee [[file_id:{file_id}]] for details."

            conn.execute(
                """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
                   VALUES (?, ?, ?, ?)""",
                (wiki_id, ws_id, "Docs", markdown),
            )
            conn.commit()

            # Query wiki
            from fastapi.testclient import TestClient

            from src.backend.api.app import create_app

            app = create_app(db_mgr, session_token=SESSION_TOKEN)
            client = TestClient(app)
            client.headers.update({"Authorization": f"Bearer {SESSION_TOKEN}"})

            wiki_res = client.get(f"/api/v1/workspace/{ws_id}/wiki")
            assert wiki_res.status_code == 200
            tabs = wiki_res.json()["data"]["tabs"]
            assert len(tabs) == 1

            content = tabs[0]["markdown_content"]

            # DEC-08: Only [[file_id:UUID]] format, no absolute paths
            assert f"[[file_id:{file_id}]]" in content
            assert "C:\\" not in content
            assert tmpdir not in content

        finally:
            db_mgr.close()

