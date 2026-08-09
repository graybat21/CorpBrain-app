"""
ANA-FE-01 (issue #4) — importance-ranked file list.

The defect: the fast analysis computed `importance_score` and the UI rendered a coloured badge
for it, but `FileRepository.list_by_workspace` returned rows `ORDER BY file_name ASC`. So the
list was in dictionary order and only the badge colour varied — AC Scenario 1's "기획서(85)가
상단에" was not satisfied by anything, and the ranking the analysis produced was invisible.

Backend assertions are real. The frontend ones are static source checks, following
tests/test_ws_fe_01.py — there is no frontend test runner by decision. They prove the page does
not re-sort (which would fork the ranking) and that the Empty State carries a button; they do
not prove the rendered layout.
"""

import os
import re
import tempfile
import uuid
from pathlib import Path

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository

FILES_PAGE = Path(__file__).resolve().parent.parent / "src" / "frontend" / "pages" / "FilesPage.tsx"


def _code(path: Path) -> str:
    """Source with comments stripped — same rationale as tests/test_ws_fe_01.py::_code."""
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


@pytest.fixture
def repo_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "meta.db"))
        try:
            root = os.path.join(tmpdir, "root")
            os.makedirs(root)
            ws_id = WorkspaceRepository(db_mgr).create("Sort WS", [root])["workspace_id"]
            yield db_mgr, FileRepository(db_mgr), ws_id, root
        finally:
            db_mgr.close()


def _file_row(ws_id: str, root: str, name: str, score: int) -> dict:
    return {
        "file_id": str(uuid.uuid4()),
        "workspace_id": ws_id,
        "current_path": os.path.join(root, name),
        "original_path": os.path.join(root, name),
        "file_name": name,
        "extension": os.path.splitext(name)[1],
        "size_bytes": 100,
        "last_modified": 1700000000.0,
        "parse_status": "pending",
        "importance_score": score,
    }


# --- AC Scenario 1: importance descending -----------------------------------------------


def test_scenario_1_the_important_file_comes_first(repo_env):
    """
    AC S1 verbatim: 최종_기획서.docx(85) above 임시_메모.txt(20).

    Deliberately named so that the *old* ordering would put them the other way round —
    '임시_메모.txt' sorts before '최종_기획서.docx' by name in SQLite's byte order, so this test
    fails against `ORDER BY file_name ASC` rather than passing by coincidence.
    """
    db_mgr, file_repo, ws_id, root = repo_env
    file_repo.bulk_upsert([
        _file_row(ws_id, root, "임시_메모.txt", 20),
        _file_row(ws_id, root, "최종_기획서.docx", 85),
    ])

    rows = file_repo.list_by_workspace(ws_id)

    assert [r["file_name"] for r in rows] == ["최종_기획서.docx", "임시_메모.txt"]
    assert rows[0]["importance_score"] == 85


def test_the_whole_list_is_monotonically_descending(repo_env):
    """Not just the top row: every adjacent pair must be ordered (REQ-FUNC-012)."""
    db_mgr, file_repo, ws_id, root = repo_env
    scores = [12, 97, 45, 3, 78, 61, 100, 0]
    file_repo.bulk_upsert([
        _file_row(ws_id, root, f"doc{i}.txt", score) for i, score in enumerate(scores)
    ])

    returned = [r["importance_score"] for r in file_repo.list_by_workspace(ws_id)]

    assert returned == sorted(scores, reverse=True)


def test_equal_scores_fall_back_to_a_stable_name_order(repo_env):
    """
    Unanalysed files all sit at score 0, so a tiebreaker decides whether the list is stable.

    Without `file_name ASC` their relative order is whatever SQLite's scan produces, and the UI
    reshuffles rows between two identical requests — which reads as data changing on its own.
    """
    db_mgr, file_repo, ws_id, root = repo_env
    file_repo.bulk_upsert([
        _file_row(ws_id, root, "c.txt", 0),
        _file_row(ws_id, root, "a.txt", 0),
        _file_row(ws_id, root, "b.txt", 0),
    ])

    first = [r["file_name"] for r in file_repo.list_by_workspace(ws_id)]
    second = [r["file_name"] for r in file_repo.list_by_workspace(ws_id)]

    assert first == ["a.txt", "b.txt", "c.txt"]
    assert first == second


def test_the_api_returns_the_ranked_order(repo_env):
    """
    The ordering must survive the route, not just the repository.

    DEC-03 makes this response the contract, so a page that renders `items` in order gets the
    ranking for free — which is why the sort lives here and not in the component.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    db_mgr, file_repo, ws_id, root = repo_env
    file_repo.bulk_upsert([
        _file_row(ws_id, root, "zzz_low.txt", 10),
        _file_row(ws_id, root, "aaa_high.txt", 90),
    ])

    app = create_app(db_mgr, session_token="sort-token")
    client = TestClient(app)
    res = client.get(
        f"/api/v1/workspace/{ws_id}/file", headers={"Authorization": "Bearer sort-token"}
    )

    assert res.status_code == 200, res.text
    names = [item["file_name"] for item in res.json()["data"]["items"]]
    assert names == ["aaa_high.txt", "zzz_low.txt"]


def test_fast_analysis_scores_then_the_list_reorders(repo_env):
    """
    End to end: the ranking appears only after analysis, and then it holds.

    Before analysis every score is 0 and the list is alphabetical; after it, the ranking leads.
    That transition is the feature — a test that seeded scores directly would not show it.
    """
    from src.backend.services.analysis_service import FastAnalysisService

    db_mgr, file_repo, ws_id, root = repo_env
    for name in ("메모.txt", "2026_사업계획서_최종.docx"):
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            f.write("x")
    file_repo.bulk_upsert([
        _file_row(ws_id, root, "메모.txt", 0),
        _file_row(ws_id, root, "2026_사업계획서_최종.docx", 0),
    ])

    FastAnalysisService(file_repo).run_fast_analysis(ws_id)

    rows = file_repo.list_by_workspace(ws_id)
    scores = {r["file_name"]: r["importance_score"] for r in rows}
    # The scorer must actually separate them, or the ordering claim is untested.
    assert scores["2026_사업계획서_최종.docx"] > scores["메모.txt"], scores
    assert rows[0]["file_name"] == "2026_사업계획서_최종.docx"


# --- Frontend structure (static) --------------------------------------------------------


def test_the_page_does_not_re_sort_the_list():
    """
    The ranking has one owner (the query). A `.sort()` in the page would fork it.

    Two sort implementations drift — and the component's copy would silently win on screen,
    which is how a backend ordering fix could appear not to work at all.
    """
    code = _code(FILES_PAGE)
    assert ".sort(" not in code, "ordering belongs in FileRepository, not the component"
    # `filter` is order-preserving, which is what lets search narrow without reordering.
    assert "files.filter(" in code


def test_the_empty_state_offers_a_run_button():
    """
    AC S2: "고속 분석을 실행하세요" plus an actual button.

    Text alone is an instruction, not an affordance. The two empty branches must stay distinct —
    a search that matched nothing must not offer a rescan as though the workspace were empty.
    """
    code = _code(FILES_PAGE)
    assert "고속 분석을 실행하세요" in code or "고속 분석을 실행" in code
    assert "검색 조건에 맞는 파일이 없습니다" in code

    start = code.index("filteredFiles.length === 0 &&")
    empty_block = code[start:]
    assert "<button" in empty_block, "the empty state must carry a run button (AC S2)"
    assert "handleRunScan" in empty_block


def test_the_list_is_windowed_without_a_new_dependency():
    """
    "1,000건 가상 스크롤" met with a scroll handler, not react-window.

    CLAUDE.md §4 forbids an unjustified dependency, and a new runtime package also enters the
    PyInstaller-embedded bundle (DEC-01). Asserted together with package.json so a later
    `npm install react-window` cannot quietly satisfy this by another route.
    """
    code = _code(FILES_PAGE)
    assert "visibleFiles.map(" in code, "the table must render the window, not the full list"
    assert "onScroll=" in code
    assert "VISIBLE_STEP" in code

    package_json = (Path(__file__).resolve().parent.parent / "package.json").read_text(encoding="utf-8")
    for forbidden in ("react-window", "react-virtualized", "react-virtuoso", "@tanstack/react-virtual"):
        assert forbidden not in package_json, f"{forbidden} was added without justification (CLAUDE.md §4)"


def test_the_importance_badge_keeps_its_gradient():
    """REQ-FUNC-012: a 0~100 score shown with graded colour, not a single flat badge."""
    code = _code(FILES_PAGE)
    assert "importance_score >= 70" in code
    assert "importance_score >= 40" in code
    assert "amber" in code and "blue" in code
