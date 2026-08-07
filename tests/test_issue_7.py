"""
Tests for issue #7: ANA-QRY-01 wiki query endpoint.

Issue #7: return all wiki tabs (folder_1depth) for a workspace so the frontend can render
1-depth folder tabs with markdown content.
"""

import os
import tempfile
import uuid

from src.backend.db import DatabaseManager
from src.backend.services.query_services import WikiQueryService


def test_empty_workspace_returns_empty_tabs():
    """No wiki content: get_workspace_wiki returns []."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wiki.db"))
        try:
            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            conn.execute(
                "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
                (ws_id, "test-ws", tmpdir)
            )

            svc = WikiQueryService(db_mgr)
            tabs = svc.get_workspace_wiki(ws_id)

            assert tabs == []
        finally:
            db_mgr.close()


def test_multiple_tabs_ordered_by_folder_1depth():
    """Issue #7 AC S1: returns array ordered by folder_1depth."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wiki.db"))
        try:
            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            conn.execute(
                "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
                (ws_id, "test-ws", tmpdir)
            )

            # Insert in reverse order to test ORDER BY.
            wiki_02 = str(uuid.uuid4())
            wiki_01 = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
                   VALUES (?, ?, ?, ?);""",
                (wiki_02, ws_id, "02_BE", "# Backend\nSome backend docs")
            )
            conn.execute(
                """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
                   VALUES (?, ?, ?, ?);""",
                (wiki_01, ws_id, "01_FE", "# Frontend\nSome frontend docs")
            )

            svc = WikiQueryService(db_mgr)
            tabs = svc.get_workspace_wiki(ws_id)

            # AC S1: returns array (not dict), ordered by folder_1depth ascending.
            assert len(tabs) == 2
            assert tabs[0]["folder_1depth"] == "01_FE"
            assert tabs[0]["wiki_id"] == wiki_01
            assert "Frontend" in tabs[0]["markdown_content"]
            assert tabs[1]["folder_1depth"] == "02_BE"
            assert tabs[1]["wiki_id"] == wiki_02
            assert "Backend" in tabs[1]["markdown_content"]

            # Each tab has the required keys (DTO contract).
            for tab in tabs:
                assert "wiki_id" in tab
                assert "folder_1depth" in tab
                assert "markdown_content" in tab
                assert "created_at" in tab
                assert "updated_at" in tab
        finally:
            db_mgr.close()


def test_markdown_contains_file_id_anchors_not_paths():
    """DEC-08: markdown_content has [[file_id:<UUID>]] anchors, not absolute paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wiki.db"))
        try:
            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            conn.execute(
                "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
                (ws_id, "test-ws", tmpdir)
            )

            file_id = str(uuid.uuid4())
            wiki_id = str(uuid.uuid4())
            # Simulate ANA-CMD-03 output: markdown with [[file_id:<UUID>]] anchors.
            markdown = f"See [[file_id:{file_id}]] for details."
            conn.execute(
                """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
                   VALUES (?, ?, ?, ?);""",
                (wiki_id, ws_id, "01_Docs", markdown)
            )

            svc = WikiQueryService(db_mgr)
            tabs = svc.get_workspace_wiki(ws_id)

            assert len(tabs) == 1
            content = tabs[0]["markdown_content"]
            # DEC-08: anchor is file_id, not a path.
            assert f"[[file_id:{file_id}]]" in content
            # Never an absolute path in markdown.
            assert "C:\\" not in content
            assert tmpdir not in content
        finally:
            db_mgr.close()
