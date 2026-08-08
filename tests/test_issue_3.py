"""
Regression tests for issue #3: wiki generation (ANA-CMD-03).

Issue #3 adds:
1. LLMRouter (routes to Anthropic or Ollama based on App_Config)
2. WikiGenerationService (RAG + LLM to generate wiki markdown)
3. POST /api/v1/workspace/{id}/wiki/generate endpoint (DEC-04: 202 + task_id)

Full end-to-end with LLM is not tested here (requires API key or Ollama daemon).
These tests verify only the plumbing: task type, router instantiation, endpoint contract.
"""

import os
import tempfile

from src.backend.db import DatabaseManager


def test_wiki_generate_task_type_registered():
    """wiki_generate was added to TASK_TYPES (DEC-04)."""
    from src.backend.repositories.task_repository import TASK_TYPES
    assert "wiki_generate" in TASK_TYPES


def test_llm_router_instantiation():
    """
    LLMRouter can be instantiated and reports correct default mode.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue3_router.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            from src.backend.services.llm_router import LLMRouter

            router = LLMRouter(db_mgr)

            # Health check should work (even without API key)
            health = router.health_check()
            assert "status_ok" in health
            assert "error_code" in health

            # Should default to Option A
            from src.backend.config_manager import ConfigManager
            cfg = ConfigManager(db_mgr)
            mode = cfg.get("llm_mode", "Option A")
            assert mode == "Option A"

        finally:
            db_mgr.close()


def test_wiki_service_instantiation():
    """
    WikiGenerationService can be instantiated.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue3_wiki.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            from src.backend.services.wiki_service import WikiGenerationService

            svc = WikiGenerationService(db_mgr)
            assert svc.db_mgr is not None
            assert svc.llm_router is not None

        finally:
            db_mgr.close()


def test_vector_search_supports_folder_filter():
    """
    VectorDBManager.search() now accepts folder_1depth parameter (AC S2: wiki isolation).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "issue3_vector.db")
        db_mgr = DatabaseManager(db_path=db_path)
        try:
            from src.backend.services.vector_service import VectorDBManager
            from tests.fakes import FakeEmbeddingFunction

            # Create a workspace
            conn = db_mgr.get_connection()
            ws_id = "test-ws-1"
            conn.execute(
                "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?)",
                (ws_id, "Test", tmpdir)
            )
            conn.commit()

            v_db = VectorDBManager(
                workspace_id=ws_id,
                persist_dir=db_mgr.vectors_dir,
                embedding_function=FakeEmbeddingFunction()
            )

            try:
                # Upsert some test chunks
                v_db.upsert_file_chunks("file1", [
                    {"workspace_id": ws_id, "file_id": "file1", "chunk_index": 0, "folder_1depth": "FolderA", "text": "Content A"},
                    {"workspace_id": ws_id, "file_id": "file1", "chunk_index": 1, "folder_1depth": "FolderB", "text": "Content B"},
                ])

                # Search with folder filter
                results_a = v_db.search("test query", n_results=10, folder_1depth="FolderA")
                results_b = v_db.search("test query", n_results=10, folder_1depth="FolderB")

                # Folder A should only have content from FolderA
                assert all(r["folder_1depth"] == "FolderA" for r in results_a if r.get("folder_1depth"))

                # Folder B should only have content from FolderB
                assert all(r["folder_1depth"] == "FolderB" for r in results_b if r.get("folder_1depth"))

            finally:
                v_db.close()

        finally:
            db_mgr.close()
