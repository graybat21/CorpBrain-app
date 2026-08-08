import os

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.vector_service import DeepAnalysisService, VectorDBManager
from src.backend.services.workspace_service import WorkspaceService
from tests.fakes import FakeEmbeddingFunction, chroma_temp_dir


@pytest.fixture
def db_setup():
    # chroma_temp_dir, not TemporaryDirectory: this test opens a real Chroma client, and
    # Windows can hold chroma.sqlite3 open a moment past close() (issue #110).
    with chroma_temp_dir() as tmpdir:
        db_path = os.path.join(tmpdir, "ana2_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)

        ws_repo = WorkspaceRepository(db_mgr)
        ws_service = WorkspaceService(ws_repo)
        file_repo = FileRepository(db_mgr)

        ws = ws_service.create_workspace("Test WS", [tmpdir])
        ws_id = ws["workspace_id"]

        # Create sample files
        f1 = os.path.join(tmpdir, "doc1.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("CorpBrain Project Overview.\n" * 50)

        f2 = os.path.join(tmpdir, "doc2.md")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("# Architecture & Security\n" * 30)

        f_bad = os.path.join(tmpdir, "non_existent.txt")

        file_repo.bulk_upsert([
            {
                "workspace_id": ws_id,
                "file_id": "file_uuid_001",
                "current_path": f1,
                "original_path": f1,
                "file_name": "doc1.txt",
                "extension": ".txt",
                "size_bytes": 1024,
                "last_modified": 1700000000.0,
                "importance_score": 80,
                "parse_status": "pending",
            },
            {
                "workspace_id": ws_id,
                "file_id": "file_uuid_002",
                "current_path": f2,
                "original_path": f2,
                "file_name": "doc2.md",
                "extension": ".md",
                "size_bytes": 2048,
                "last_modified": 1700000000.0,
                "importance_score": 60,
                "parse_status": "pending",
            },
            {
                "workspace_id": ws_id,
                "file_id": "file_uuid_bad",
                "current_path": f_bad,
                "original_path": f_bad,
                "file_name": "non_existent.txt",
                "extension": ".txt",
                "size_bytes": 0,
                "last_modified": 1700000000.0,
                "importance_score": 10,
                "parse_status": "pending",
            },
        ])

        # Real ChromaDB PersistentClient against the tmpdir (DEC-06). Only the embedding
        # numbers are faked — the client, the cosine index and the `where` deletes are real.
        v_db = VectorDBManager(
            workspace_id=ws_id,
            persist_dir=db_mgr.vectors_dir,
            embedding_function=FakeEmbeddingFunction(),
        )
        service = DeepAnalysisService(db_mgr, vector_db=v_db)

        yield service, v_db, db_mgr, ws_id

        # close() BEFORE the TemporaryDirectory teardown: an open chroma.sqlite3 handle makes
        # Windows cleanup fail with PermissionError [WinError 32].
        v_db.close()
        db_mgr.close()


def test_scenario_1_deep_analysis_and_chunk_ids(db_setup):
    service, v_db, db_mgr, ws_id = db_setup

    file_rec = {
        "file_id": "file_uuid_001",
        "workspace_id": ws_id,
        "current_path": db_mgr.get_connection().cursor().execute(
            "SELECT current_path FROM File_Meta WHERE file_id = 'file_uuid_001';"
        ).fetchone()["current_path"],
        "extension": ".txt"
    }

    res = service.process_single_file(file_rec)
    assert res["parse_status"] == "parsed"
    assert res["chunk_count"] > 0

    chunks = v_db.get_file_chunks("file_uuid_001")
    assert len(chunks) == res["chunk_count"]
    # Verify DEC-09 chunk ID format: <file_id>:<chunk_index>.
    # Positional indexing is valid because get_file_chunks sorts by chunk_index — Chroma's
    # get() itself gives no ordering guarantee.
    assert chunks[0]["chunk_id"] == "file_uuid_001:0"
    assert chunks[1]["chunk_id"] == "file_uuid_001:1"


def test_scenario_2_vector_delete_before_upsert_sequence(db_setup):
    service, v_db, db_mgr, ws_id = db_setup

    file_rec = {
        "file_id": "file_uuid_002",
        "workspace_id": ws_id,
        "current_path": db_mgr.get_connection().cursor().execute(
            "SELECT current_path FROM File_Meta WHERE file_id = 'file_uuid_002';"
        ).fetchone()["current_path"],
        "extension": ".md"
    }

    # Initial run
    service.process_single_file(file_rec)
    count1 = v_db.count_chunks("file_uuid_002")

    # Re-run (Re-analysis)
    service.process_single_file(file_rec)
    count2 = v_db.count_chunks("file_uuid_002")

    # Ensures no orphan chunks accumulated
    assert count1 == count2


def test_scenario_3_batch_run_with_single_file_failure_isolation(db_setup):
    service, v_db, db_mgr, ws_id = db_setup

    batch_res = service.run_deep_analysis_batch(ws_id)

    # Issue #89: partial failure still returns status='completed' (the task finished).
    # HTTP 207 is decided by the API layer checking failed[].
    assert batch_res["status"] == "completed"
    assert batch_res["succeeded_count"] == 2
    assert len(batch_res["failed"]) == 1
    assert batch_res["failed"][0]["file_id"] == "file_uuid_bad"

    # Verify parse_status in SQLite
    conn = db_mgr.get_connection()
    c1 = conn.cursor().execute("SELECT parse_status FROM File_Meta WHERE file_id = 'file_uuid_001';").fetchone()[0]
    c_bad = conn.cursor().execute("SELECT parse_status FROM File_Meta WHERE file_id = 'file_uuid_bad';").fetchone()[0]

    assert c1 == "parsed"
    assert c_bad == "pending"  # Not raised to parsed
