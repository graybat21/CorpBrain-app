"""
Regression tests for issue #89: envelope alignment and HTTP 207 decisions.

Issue #89 reported that:
1. ANA-CMD-02 AC expected status='completed' on partial failure, but code returned 'multi_status'.
2. The same 'multi_status' label was shared between analysis and rename, so changing it would
   silently alter rename's HTTP contract.
3. Empty-list early return had a different schema (included processed_count).

**Fix:**
- Services now always return status='completed' (the task finished).
- HTTP 207 decision moved to API layer: check if result_json.failed[] is non-empty.
- Early return schema unified with process_file_batch return.
"""

import os
import uuid

from src.backend.db import DatabaseManager
from src.backend.services.llm_resilience_service import LLMResilienceService
from tests.fakes import chroma_temp_dir, insert_workspace


def test_partial_failure_returns_completed_with_failed_list():
    """
    Partial failure: some files succeeded, some failed. Service returns status='completed' and
    a non-empty failed[] list. This satisfies ANA-CMD-02 AC.
    """
    def process_fn(item):
        if item["file_id"] == "bad":
            raise ValueError("forced failure")
        return {"result": "ok"}

    files = [{"file_id": "good1"}, {"file_id": "bad"}, {"file_id": "good2"}]
    svc = LLMResilienceService(max_retries=1, backoff_base_sec=0.01)
    result = svc.process_file_batch(files, process_fn)

    assert result["status"] == "completed"
    assert result["succeeded_count"] == 2
    assert len(result["failed"]) == 1
    assert result["failed"][0]["file_id"] == "bad"
    assert "aborted_early" in result


def test_total_success_returns_completed_with_empty_failed():
    """All files succeeded: status='completed', failed=[]."""
    def process_fn(item):
        return {"result": "ok"}

    files = [{"file_id": "good1"}, {"file_id": "good2"}]
    svc = LLMResilienceService(max_retries=1, backoff_base_sec=0.01)
    result = svc.process_file_batch(files, process_fn)

    assert result["status"] == "completed"
    assert result["succeeded_count"] == 2
    assert len(result["failed"]) == 0


def test_empty_list_early_return_matches_batch_schema():
    """
    Issue #89 problem 2: empty-list early return must have the same schema as process_file_batch.
    """
    # chroma_temp_dir, not TemporaryDirectory: this test opens a real Chroma client, and
    # Windows can hold chroma.sqlite3 open a moment past close() (issue #110).
    with chroma_temp_dir() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "issue89.db"))
        try:
            from src.backend.services.vector_service import DeepAnalysisService, VectorDBManager
            from tests.fakes import FakeEmbeddingFunction

            ws_id = str(uuid.uuid4())
            conn = db_mgr.get_connection()
            insert_workspace(conn, ws_id, "test", tmpdir)

            v_db = VectorDBManager(
                workspace_id=ws_id,
                persist_dir=db_mgr.vectors_dir,
                embedding_function=FakeEmbeddingFunction()
            )
            svc = DeepAnalysisService(db_mgr, vector_db=v_db)

            # No unparsed files: early return triggers.
            result = svc.run_deep_analysis_batch(ws_id)

            # Must have the same keys as process_file_batch.
            assert result["status"] == "completed"
            assert result["succeeded_count"] == 0
            assert result["failed"] == []
            assert "aborted_early" in result
            # Issue #89: processed_count was in early return but not in batch return — now unified.
            assert "processed_count" not in result

            v_db.close()
        finally:
            db_mgr.close()
