import os
import tempfile
import uuid
import pytest
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.deeplink_service import DeepLinkService


@pytest.fixture
def deeplink_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "dl_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)

        ws = ws_repo.create("DL WS", tmpdir)
        ws_id = ws["workspace_id"]

        f1_id = str(uuid.uuid4())
        f2_id = str(uuid.uuid4())

        file_repo.bulk_upsert([
            {
                "file_id": f1_id,
                "workspace_id": ws_id,
                "current_path": os.path.join(tmpdir, "doc1.md"),
                "original_path": os.path.join(tmpdir, "doc1.md"),
                "file_name": "doc1.md",
                "extension": ".md",
                "size_bytes": 100,
                "last_modified": 1.0,
            },
            {
                "file_id": f2_id,
                "workspace_id": ws_id,
                "current_path": os.path.join(tmpdir, "doc2.pdf"),
                "original_path": os.path.join(tmpdir, "doc2.pdf"),
                "file_name": "doc2.pdf",
                "extension": ".pdf",
                "size_bytes": 200,
                "last_modified": 2.0,
            },
        ])

        service = DeepLinkService(db_mgr, file_repo)
        yield service, file_repo, ws_id, f1_id, f2_id, tmpdir
        db_mgr.close()


def test_scenario_1_anchor_parsing(deeplink_setup):
    service, file_repo, ws_id, f1_id, f2_id, tmpdir = deeplink_setup
    wiki_text = f"이 문서는 [[file_id:{f1_id}]] 및 [[file_id:{f2_id}]]를 참고함."

    anchors = DeepLinkService.parse_anchors(wiki_text)
    assert len(anchors) == 2
    assert f1_id in anchors
    assert f2_id in anchors

    res = service.process_wiki_deeplinks(ws_id, wiki_text)
    assert res["anchor_count"] == 2
    assert set(res["valid_file_ids"]) == {f1_id, f2_id}


def test_scenario_2_late_binding_path_resolution(deeplink_setup):
    service, file_repo, ws_id, f1_id, f2_id, tmpdir = deeplink_setup

    initial_path = service.resolve_deeplink_path(ws_id, f1_id)
    assert initial_path == os.path.join(tmpdir, "doc1.md")

    # Simulate file rename / move in DB
    new_path = os.path.join(tmpdir, "renamed_doc1.md")
    file_repo.update_path(ws_id, f1_id, new_path)

    resolved_path = service.resolve_deeplink_path(ws_id, f1_id)
    assert resolved_path == new_path


def test_scenario_3_no_absolute_paths_in_mapping_json(deeplink_setup):
    service, file_repo, ws_id, f1_id, f2_id, tmpdir = deeplink_setup
    wiki_text = f"Anchor link [[file_id:{f1_id}]]"

    res = service.process_wiki_deeplinks(ws_id, wiki_text)
    mapping_str = str(res)

    assert "C:\\" not in mapping_str
    assert "doc1.md" not in mapping_str
    assert f1_id in mapping_str
