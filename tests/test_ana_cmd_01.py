import os
import tempfile

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.analysis_service import FastAnalysisEngine, FastAnalysisService


def test_scenario_1_name_based_importance_calculation():
    score_doc = FastAnalysisEngine.calculate_score("최종_기획서.docx", ".docx", "C:\\ws\\최종_기획서.docx")
    score_memo = FastAnalysisEngine.calculate_score("임시_메모.txt", ".txt", "C:\\ws\\임시_메모.txt")

    assert score_doc > score_memo
    assert score_doc >= 65
    assert score_memo <= 20


def test_scenario_2_score_clamping_0_to_100():
    # Extremely low score case
    score_low = FastAnalysisEngine.calculate_score("임시_draft_temp_old_backup.txt", ".txt", "C:\\ws\\a\\b\\c\\d\\e\\f.txt")
    assert 0 <= score_low <= 100

    # Extremely high score case
    score_high = FastAnalysisEngine.calculate_score("최종_완료_기획_설계_spec_prd_master.docx", ".docx", "C:\\ws\\doc.docx")
    assert score_high == 100


def test_fast_analysis_service_db_update():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ana_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)

        ws = ws_repo.create("Ana WS", [tmpdir])
        ws_id = ws["workspace_id"]

        records = [
            {
                "file_id": "f1",
                "workspace_id": ws_id,
                "current_path": os.path.join(tmpdir, "최종_기획서.docx"),
                "original_path": os.path.join(tmpdir, "최종_기획서.docx"),
                "file_name": "최종_기획서.docx",
                "extension": ".docx",
                "size_bytes": 1024,
                "last_modified": 1.0,
                "parse_status": "pending",
                "importance_score": 0,
            },
            {
                "file_id": "f2",
                "workspace_id": ws_id,
                "current_path": os.path.join(tmpdir, "임시_노트.txt"),
                "original_path": os.path.join(tmpdir, "임시_노트.txt"),
                "file_name": "임시_노트.txt",
                "extension": ".txt",
                "size_bytes": 2048,
                "last_modified": 2.0,
                "parse_status": "pending",
                "importance_score": 0,
            },
        ]
        file_repo.bulk_upsert(records)

        service = FastAnalysisService(file_repo)
        results = service.run_fast_analysis(ws_id)

        assert len(results) == 2
        assert results[0]["file_id"] == "f1"  # Highest score first
        assert results[0]["importance_score"] > results[1]["importance_score"]

        # Check DB update
        db_files = file_repo.list_by_workspace(ws_id)
        f1_db = next(f for f in db_files if f["file_id"] == "f1")
        assert f1_db["importance_score"] == results[0]["importance_score"]

        db_mgr.close()
