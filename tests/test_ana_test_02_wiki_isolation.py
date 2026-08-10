"""
ANA-TEST-02 (issue #10) — 1-Depth folder isolation in wiki generation (REQ-FUNC-014).

The claim: generating the wiki for `01_Frontend` must not pull a single chunk from `02_Backend`.
Nothing tested this, and the failure would be invisible — a leaked chunk produces a *plausible*
wiki, just one describing files the folder does not contain. The user has no way to notice, which
is what makes it worth a dedicated test rather than an assertion inside a broader one.

Run against a **real ChromaDB collection** with a real `where` filter, not a stubbed store. The
isolation is enforced entirely by Chroma's metadata filter, so a fake vector store would test the
fake. Only the embedding numbers are faked (`FakeEmbeddingFunction`, deterministic sha256) and the
LLM, which is replaced by a recorder that returns the prompt it was given — that inversion is what
lets the test inspect the *context* rather than the model's opinion of it.

The two folders use vocabularies with zero overlap so a leak is unambiguous: a Backend term
appearing in the Frontend prompt cannot be a coincidence of similar wording.
"""

import os
import tempfile
import uuid

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.vector_service import VectorDBManager
from src.backend.services.wiki_service import WikiGenerationService
from tests.fakes import FakeEmbeddingFunction, chroma_temp_dir

FRONTEND_TERMS = ["리액트", "컴포넌트", "타입스크립트", "스타일시트"]
BACKEND_TERMS = ["파이프라인", "마이그레이션", "인덱스", "커넥션풀"]


class PromptRecordingRouter:
    """
    Returns the prompt it was handed, so the caller can inspect the retrieved context.

    Inverted on purpose: the thing under test is *which chunks reached the prompt*, and asserting
    on generated prose would test the model. Returning the prompt makes the context observable
    without a live LLM.
    """

    def __init__(self):
        self.prompts: list = []

    def generate(self, prompt: str, max_tokens: int = 4000):
        self.prompts.append(prompt)
        return {
            "content": f"# 위키\n\n{prompt}",
            "usage": {"input_tokens": 10, "output_tokens": 20},
            "cost_usd": 0.0,
        }


@pytest.fixture
def two_folder_workspace():
    """
    A workspace with `01_Frontend` and `02_Backend`, each holding disjoint-vocabulary chunks in a
    real Chroma collection.
    """
    with chroma_temp_dir() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wiki.db"))
        try:
            root = os.path.join(tmpdir, "workspace")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Isolation WS", [root])["workspace_id"]

            vector_db = VectorDBManager(
                workspace_id=ws_id,
                persist_dir=os.path.join(tmpdir, "vectors"),
                embedding_function=FakeEmbeddingFunction(),
            )

            file_ids = {}
            for folder, terms in (("01_Frontend", FRONTEND_TERMS), ("02_Backend", BACKEND_TERMS)):
                folder_path = os.path.join(root, folder)
                os.makedirs(folder_path)
                file_path = os.path.join(folder_path, f"{folder}.md")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(" ".join(terms))

                file_id = str(uuid.uuid4())
                file_ids[folder] = file_id
                file_repo.bulk_upsert([{
                    "file_id": file_id, "workspace_id": ws_id,
                    "current_path": file_path, "original_path": file_path,
                    "file_name": f"{folder}.md", "extension": ".md",
                    "size_bytes": 50, "last_modified": 1700000000.0,
                    "parse_status": "parsed", "importance_score": 0,
                }])

                chunks = [
                    {
                        "chunk_id": f"{file_id}:{i}",
                        "chunk_index": i,
                        "text": f"{folder} 문서 {i}: {term} 관련 내용입니다.",
                        "char_length": 40,
                        "workspace_id": ws_id,
                        "folder_1depth": folder,
                    }
                    for i, term in enumerate(terms)
                ]
                vector_db.upsert_file_chunks(file_id, chunks)

            router = PromptRecordingRouter()
            service = WikiGenerationService(db_mgr, llm_router=router, vector_db=vector_db)
            yield service, router, vector_db, db_mgr, ws_id, file_ids
        finally:
            try:
                vector_db.close()
            finally:
                db_mgr.close()


# --- AC Scenario 1: neither folder's wiki contains the other's context --------------------


def test_scenario_1_the_frontend_wiki_contains_no_backend_term(two_folder_workspace):
    """
    AC S1: generate `01_Frontend`, assert no Backend-only keyword appears.

    Asserted on the **retrieved context** (the prompt), not the produced markdown. A leak that
    reached the prompt is a leak even if the model happened not to quote it — checking the output
    alone would let the bug pass whenever the summary was terse.
    """
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    service._generate_wiki_for_folder(ws_id, "01_Frontend")

    assert len(router.prompts) == 1
    prompt = router.prompts[0]
    for term in BACKEND_TERMS:
        assert term not in prompt, f"Backend term '{term}' leaked into the Frontend wiki context"
    # And the folder's own content did arrive — an empty context would pass the check above
    # while producing a useless wiki.
    assert any(term in prompt for term in FRONTEND_TERMS), prompt


def test_scenario_1_the_backend_wiki_contains_no_frontend_term(two_folder_workspace):
    """The mirror direction. Isolation that only holds one way is not isolation."""
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    service._generate_wiki_for_folder(ws_id, "02_Backend")

    prompt = router.prompts[0]
    for term in FRONTEND_TERMS:
        assert term not in prompt, f"Frontend term '{term}' leaked into the Backend wiki context"
    assert any(term in prompt for term in BACKEND_TERMS)


def test_the_persisted_wiki_rows_stay_separate(two_folder_workspace):
    """
    Two folders produce two `Wiki_Content` rows, and neither body carries the other's terms.

    `UNIQUE(workspace_id, folder_1depth)` means a folder mix-up would overwrite rather than
    duplicate — the tab would silently show another folder's summary.
    """
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    service._generate_wiki_for_folder(ws_id, "01_Frontend")
    service._generate_wiki_for_folder(ws_id, "02_Backend")

    rows = db_mgr.get_connection().execute(
        "SELECT folder_1depth, markdown_content FROM Wiki_Content WHERE workspace_id = ? ORDER BY folder_1depth;",
        (ws_id,),
    ).fetchall()

    assert [r["folder_1depth"] for r in rows] == ["01_Frontend", "02_Backend"]
    frontend_body, backend_body = rows[0]["markdown_content"], rows[1]["markdown_content"]
    for term in BACKEND_TERMS:
        assert term not in frontend_body, term
    for term in FRONTEND_TERMS:
        assert term not in backend_body, term


def test_the_retrieval_filter_is_what_enforces_isolation(two_folder_workspace):
    """
    Isolation lives in the vector search's `folder_1depth` filter, so test that directly.

    The wiki tests above could pass for the wrong reason — a retrieval that returned nothing would
    also contain no foreign terms. This pins that the filter selects the right chunks rather than
    just excluding the wrong ones.
    """
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    frontend_chunks = service._retrieve_chunks(ws_id, "01_Frontend", limit=50)
    backend_chunks = service._retrieve_chunks(ws_id, "02_Backend", limit=50)

    assert len(frontend_chunks) == len(FRONTEND_TERMS)
    assert len(backend_chunks) == len(BACKEND_TERMS)
    assert all(c["file_id"] == file_ids["01_Frontend"] for c in frontend_chunks)
    assert all(c["file_id"] == file_ids["02_Backend"] for c in backend_chunks)


def test_a_third_folder_does_not_widen_either_side(two_folder_workspace):
    """
    Adding a folder must not loosen the existing two.

    A filter built by exclusion ("everything except the other folder") would break here, while an
    inclusive filter keeps working — and the two are indistinguishable with only two folders.
    """
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace
    third_id = str(uuid.uuid4())
    vector_db.upsert_file_chunks(third_id, [{
        "chunk_id": f"{third_id}:0",
        "chunk_index": 0,
        "text": "03_Infra 문서: 쿠버네티스 배포 설정",
        "char_length": 25,
        "workspace_id": ws_id,
        "folder_1depth": "03_Infra",
    }])

    frontend_chunks = service._retrieve_chunks(ws_id, "01_Frontend", limit=50)

    assert len(frontend_chunks) == len(FRONTEND_TERMS)
    assert all("쿠버네티스" not in c["text"] for c in frontend_chunks)


def test_a_folder_with_no_chunks_generates_no_wiki_row(two_folder_workspace):
    """
    An empty folder is skipped, not written as an empty wiki.

    A blank tab reads as "analysis produced nothing useful"; no tab reads as "nothing here to
    analyse", which is the truth.
    """
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    service._generate_wiki_for_folder(ws_id, "99_Empty")

    assert router.prompts == [], "no LLM call may be made for an empty folder"
    rows = db_mgr.get_connection().execute(
        "SELECT COUNT(*) FROM Wiki_Content WHERE workspace_id = ? AND folder_1depth = '99_Empty';",
        (ws_id,),
    ).fetchone()[0]
    assert rows == 0


def test_the_prompt_carries_no_absolute_path(two_folder_workspace):
    """
    DEC-08/DEC-17: the RAG prompt is an Option A transmission path, so no path may ride along.

    The chunk metadata holds `folder_1depth` (a bare name) precisely so the prompt can name the
    folder without naming its location.
    """
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    service._generate_wiki_for_folder(ws_id, "01_Frontend")

    prompt = router.prompts[0]
    assert "/var/folders" not in prompt and "C:\\" not in prompt
    assert "/Users/" not in prompt
    # The folder NAME is allowed and needed — it is the documented allowance.
    assert "01_Frontend" in prompt


def test_generating_the_whole_workspace_keeps_folders_apart(two_folder_workspace):
    """
    The batch path (`generate_wiki_for_workspace`) must isolate exactly as the per-folder path
    does — it is the one users actually invoke, and it loops over folders discovered from vector
    metadata rather than from a caller-supplied list.
    """
    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    result = service.generate_wiki_for_workspace(ws_id)

    assert len(router.prompts) == 2, result
    by_folder = {}
    for prompt in router.prompts:
        folder = "01_Frontend" if "01_Frontend" in prompt else "02_Backend"
        by_folder[folder] = prompt
    assert set(by_folder) == {"01_Frontend", "02_Backend"}
    for term in BACKEND_TERMS:
        assert term not in by_folder["01_Frontend"], term
    for term in FRONTEND_TERMS:
        assert term not in by_folder["02_Backend"], term


# --- The schema defect this issue uncovered ----------------------------------------------


def test_the_deeplink_mappings_column_exists():
    """
    Regression guard for the defect found while writing this file (v007).

    `wiki_service._save_wiki` writes `deeplink_mappings` on both its INSERT and UPDATE branch, but
    no migration created the column — so wiki generation failed 100% of the time with
    `sqlite3.OperationalError`. Same defect class as issue #90's `Rename_History.status`: a service
    writing a column the schema never had, surviving because no test reached that line.

    Asserted against a freshly migrated database rather than against the migration text, so a
    migration that exists but does not apply still fails.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "schema.db"))
        try:
            columns = [
                row[1]
                for row in db_mgr.get_connection().execute("PRAGMA table_info(Wiki_Content);")
            ]
            assert "deeplink_mappings" in columns, columns
        finally:
            db_mgr.close()


def test_the_saved_mappings_hold_file_ids_and_no_paths(two_folder_workspace):
    """
    DEC-08: the mapping maps an index to a `file_id`, and never carries an absolute path.

    A cached path is exactly what the rename feature invalidates, which is why the anchor format
    is `[[file_id:UUID]]` and the mapping stores ids.
    """
    import json

    service, router, vector_db, db_mgr, ws_id, file_ids = two_folder_workspace

    service._generate_wiki_for_folder(ws_id, "01_Frontend")

    row = db_mgr.get_connection().execute(
        "SELECT deeplink_mappings FROM Wiki_Content WHERE workspace_id = ? AND folder_1depth = ?;",
        (ws_id, "01_Frontend"),
    ).fetchone()
    assert row["deeplink_mappings"] is not None, "the mapping must be persisted, not dropped"

    mappings = json.loads(row["deeplink_mappings"])
    assert mappings, "an anchored wiki must record at least one mapping"
    for value in mappings.values():
        # Every value is a file_id belonging to this folder — never a path.
        assert value == file_ids["01_Frontend"], value
    blob = row["deeplink_mappings"]
    assert "/" not in blob and "\\" not in blob, "no path may be persisted in deeplink_mappings"
