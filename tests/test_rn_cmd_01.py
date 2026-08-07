import os
import tempfile
import pytest
from src.backend.db import DatabaseManager
from src.backend.pii_filter import PIIFilter
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.rename_service import RenameService


@pytest.fixture
def rename_service():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "rn_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        ws_repo = WorkspaceRepository(db_mgr)
        ws = ws_repo.create("RN WS", tmpdir)
        service = RenameService(db_mgr=db_mgr)
        yield service, ws["workspace_id"], tmpdir
        db_mgr.close()


def test_scenario_1_build_prompt_context_no_absolute_path():
    file_meta = {
        "file_name": "보고서.docx",
        "extension": ".docx",
        "current_path": "C:\\Users\\doctor\\OneDrive\\문서\\CorpBrain\\reports\\보고서.docx",
    }
    ctx = RenameService.build_prompt_context(file_meta)

    assert "current_path" not in ctx
    assert "C:" not in str(ctx)
    assert "doctor" not in str(ctx)
    assert ctx["file_name"] == "보고서.docx"
    assert ctx["folder_1depth"] == "reports"


def test_scenario_2_pii_masking_before_llm(rename_service):
    service, ws_id, tmpdir = rename_service
    pii_filename = "홍길동_주민등록증_900101-1234567.pdf"

    files = [
        {
            "file_id": "f1",
            "file_name": pii_filename,
            "extension": ".pdf",
            "current_path": os.path.join(tmpdir, pii_filename),
        }
    ]

    res = service.process_rename_suggestions(ws_id, files)
    assert len(res) == 1
    assert res[0]["status"] == "pending"


def test_scenario_3_pii_token_leftover_rejection(rename_service):
    service, ws_id, tmpdir = rename_service
    files = [
        {
            "file_id": "f2",
            "file_name": "id_card.pdf",
            "extension": ".pdf",
            "current_path": os.path.join(tmpdir, "id_card.pdf"),
        }
    ]

    # Mock LLM returning a string with [PII:RRN]
    def mock_bad_llm(old_name):
        return "[PII:RRN]_card.pdf"

    res = service.process_rename_suggestions(ws_id, files, mock_llm_callback=mock_bad_llm)
    assert len(res) == 1
    assert res[0]["status"] == "PII_TOKEN_LEFT"
    assert "PII 포함" in res[0]["note"]
    assert res[0]["new_name"] == "id_card.pdf"  # Original name kept


def test_scenario_4_invalid_windows_filename(rename_service):
    assert RenameService.is_valid_windows_filename("CON.txt") is False
    assert RenameService.is_valid_windows_filename("invalid?.pdf") is False
    assert RenameService.is_valid_windows_filename("trailing_space.txt ") is False
    assert RenameService.is_valid_windows_filename("valid_report.docx") is True
