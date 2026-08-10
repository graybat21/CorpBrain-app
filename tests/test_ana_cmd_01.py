"""
TC-ANA-001 (issue #1 / ANA-CMD-01) — 파일명·경로 기반 고속 분석, REQ-FUNC-012.

Covers both AC scenarios plus the non-functional constraint:

- **S1** 이름 기반 중요도 산출 — `최종_기획서.docx` outranks `임시_메모.txt`.
- **S2** 다양한 파일명 패턴 10개가 모두 0~100 범위이고, **상위 3개가 하이라이트 대상으로 반환**된다.
- **NFC** 파일명 기반 분석이므로 **파일 I/O 없이** p95 < 100ms.

The p95 bound is asserted here rather than deferred to a benchmark script (contrast issue #25's
scan benchmark, which had to be split out): scoring is pure string arithmetic in the low
microseconds, so a 100ms ceiling carries a margin of several orders of magnitude and survives a
loaded shared runner. What actually protects the constraint is
`test_calculate_score_performs_no_file_io` — the moment scoring opens a file, the number stops
being a property of the code and starts being a property of the disk.
"""

import builtins
import os
import pathlib
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from src.backend.api.app import create_app
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.analysis_service import FastAnalysisEngine, FastAnalysisService

#: AC S2's "다양한 파일명 패턴 10개" — deliberately spread across the scoring inputs: every
#: extension in the base table plus an unknown one, high-priority and low-priority keywords,
#: both together, neither, and shallow vs. deep paths. A set of ten near-identical names would
#: satisfy the count while testing one code path.
TEN_PATTERNS = [
    ("최종_기획서.docx", ".docx", "C:\\ws\\최종_기획서.docx"),
    ("임시_메모.txt", ".txt", "C:\\ws\\임시_메모.txt"),
    ("설계_명세_v2.pdf", ".pdf", "C:\\ws\\설계\\설계_명세_v2.pdf"),
    ("README.md", ".md", "C:\\ws\\README.md"),
    ("scan.log", ".log", "C:\\ws\\logs\\scan.log"),
    ("draft_temp_old_backup_사본.txt", ".txt", "C:\\ws\\a\\b\\c\\d\\e\\draft_temp_old_backup_사본.txt"),
    ("master_plan_spec_prd_srs_최종_완료_기획_설계.docx", ".docx", "C:\\ws\\master.docx"),
    ("회의록.docx", ".docx", "C:\\ws\\2026\\08\\회의록.docx"),
    ("최종_임시_기획_draft.pdf", ".pdf", "C:\\ws\\최종_임시_기획_draft.pdf"),
    ("이름없는파일", "", "C:\\ws\\이름없는파일"),
]


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


# --- AC Scenario 2: 0~100 범위 + 상위 3개 반환 ---------------------------------------------


def test_scenario_2_ten_patterns_all_within_0_100():
    """AC S2 첫 절 — 다양한 파일명 패턴 10개가 모두 0~100 범위 안에 든다."""
    scores = [FastAnalysisEngine.calculate_score(name, ext, path) for name, ext, path in TEN_PATTERNS]

    assert len(scores) == 10
    for (name, _, _), score in zip(TEN_PATTERNS, scores, strict=True):
        assert 0 <= score <= 100, f"{name} scored {score}, outside 0~100"

    # A clamp that is never exercised proves nothing about the clamp. These two patterns are in
    # the set precisely because their raw arithmetic lands outside the range: the nine-keyword
    # .docx sums past 100, and the five-penalty .txt at depth 6 falls below 0.
    assert scores[6] == 100
    assert scores[5] == 0


def _record(file_id: str, file_name: str, score: int) -> dict:
    return {"file_id": file_id, "file_name": file_name, "importance_score": score}


def test_scenario_2_returns_exactly_top_three_in_rank_order():
    """AC S2 둘째 절 — 10개 중 상위 3개만, 중요도 내림차순으로 반환된다."""
    records = [_record(f"f{i}", f"문서{i}.docx", score) for i, score in enumerate([10, 95, 40, 77, 5, 88, 62, 33, 51, 20])]

    top = FastAnalysisEngine.select_top_ranked(records)

    assert top == ["f1", "f5", "f3"], "expected the 95/88/77 files, highest first"
    assert len(top) == FastAnalysisEngine.TOP_RANKED_LIMIT == 3


def test_top_ranked_excludes_unanalysed_zero_score_files():
    """
    A scanned-but-not-yet-analysed workspace has no 핵심 문서.

    Every row sits at 0 until fast analysis runs. Padding the list to three would have the
    dashboard label arbitrary files as 핵심 문서 before anything computed that judgement.
    """
    assert FastAnalysisEngine.select_top_ranked([_record("a", "a.txt", 0), _record("b", "b.txt", 0)]) == []
    # Fewer than the limit is a valid answer, not a reason to backfill with zeros.
    assert FastAnalysisEngine.select_top_ranked([_record("a", "a.txt", 0), _record("b", "b.txt", 7)]) == ["b"]


def test_top_ranked_is_deterministic_when_scores_tie():
    """
    Ties break on file name, so two identical requests highlight the same three files.

    Without the tiebreaker the top set is whatever order the rows arrive in, and the UI reshuffles
    its highlight between two renders of unchanged data.
    """
    tied = [_record("f_c", "c.docx", 50), _record("f_a", "a.docx", 50), _record("f_b", "b.docx", 50)]

    assert FastAnalysisEngine.select_top_ranked(tied) == ["f_a", "f_b", "f_c"]
    assert FastAnalysisEngine.select_top_ranked(list(reversed(tied))) == ["f_a", "f_b", "f_c"]


# --- 비기능 제약: 파일 I/O 없이 p95 < 100ms -------------------------------------------------


def test_calculate_score_performs_no_file_io(monkeypatch):
    """
    Scoring reads the *name*, never the file. Asserted by making file access fail outright.

    This is the assertion that keeps the p95 budget meaningful — a scorer that peeks inside the
    document is bounded by disk latency, not by its own arithmetic, and the timing test below
    would then be measuring the runner's SSD.
    """
    def _forbidden(*args, **kwargs):
        raise AssertionError("fast analysis must not touch the filesystem (REQ-FUNC-012)")

    monkeypatch.setattr(builtins, "open", _forbidden)
    monkeypatch.setattr(os, "stat", _forbidden)
    monkeypatch.setattr(os.path, "exists", _forbidden)
    monkeypatch.setattr(pathlib.Path, "stat", _forbidden)
    monkeypatch.setattr(pathlib.Path, "exists", _forbidden)

    # Paths that do not exist on any host, so a stray access could not accidentally succeed.
    for name, ext, path in TEN_PATTERNS:
        assert 0 <= FastAnalysisEngine.calculate_score(name, ext, path) <= 100


@pytest.mark.parametrize("iterations", [200])
def test_calculate_score_p95_under_100ms(iterations):
    """AC 비기능 제약 — 파일명 기반 산출의 p95 < 100ms."""
    durations = []
    for _ in range(iterations):
        name, ext, path = TEN_PATTERNS[len(durations) % len(TEN_PATTERNS)]
        started = time.perf_counter()
        FastAnalysisEngine.calculate_score(name, ext, path)
        durations.append((time.perf_counter() - started) * 1000.0)

    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    assert p95 < 100.0, f"p95 {p95:.3f}ms exceeded the 100ms budget"


# --- AC S2 "반환된다": the ranking has to reach the UI, not just the service -----------------


def test_file_list_endpoint_returns_top_ranked_file_ids():
    """
    The top three surface on `GET /api/v1/workspace/{id}/file` as `top_ranked_file_ids`.

    SRS §6.1 API-002 put `top_files` on the POST, but DEC-04 fixed that response to
    `202 + task_id` with no payload — so the query endpoint is where the UI can read it.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(
            db_path=os.path.join(tmpdir, "top_ranked.db"),
            migrations_dir=os.path.join(os.path.dirname(__file__), "..", "migrations"),
        )
        token = "test_top_ranked_token"
        app = create_app(db_mgr, session_token=token)
        try:
            with TestClient(app) as client:
                headers = {"Authorization": f"Bearer {token}"}
                res = client.post(
                    "/api/v1/workspace",
                    json={"workspace_name": "Top WS", "root_paths": [tmpdir]},
                    headers=headers,
                )
                assert res.status_code == 201
                ws_id = res.json()["data"]["workspace_id"]

                file_repo = app.state.scanner_service.file_repo
                names = [f"문서{i}.docx" for i in range(10)]
                file_repo.bulk_upsert([
                    {
                        "file_id": f"tr{i}",
                        "workspace_id": ws_id,
                        "current_path": os.path.join(tmpdir, names[i]),
                        "original_path": os.path.join(tmpdir, names[i]),
                        "file_name": names[i],
                        "extension": ".docx",
                        "size_bytes": 10,
                        "last_modified": 1.0,
                        "parse_status": "pending",
                        "importance_score": score,
                    }
                    for i, score in enumerate([10, 95, 40, 77, 5, 88, 62, 33, 51, 20])
                ])

                body = client.get(f"/api/v1/workspace/{ws_id}/file", headers=headers).json()
                assert body["ok"] is True
                assert body["data"]["total"] == 10
                assert body["data"]["top_ranked_file_ids"] == ["tr1", "tr5", "tr3"]
                # The highlight ids must address rows the same response actually carries;
                # otherwise the UI highlights nothing and the bug is invisible.
                returned_ids = {item["file_id"] for item in body["data"]["items"]}
                assert set(body["data"]["top_ranked_file_ids"]) <= returned_ids
        finally:
            db_mgr.close()
