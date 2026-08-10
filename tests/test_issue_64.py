"""
WS-FE-03 (issue #64) — scan summary binding and the 10,000-file guard notice
(REQ-FUNC-003, 004 / SCAN-CMD-02 / DEC-03 / DEC-04).

**The AC was written before DEC-04.** It asks for a `400` caught at "추가 버튼" time and shown in an
"에러 다이얼로그" via an "Axios Interceptor". None of the three survives current spec:

- DEC-04 made scan asynchronous, so the workspace is created successfully and the 10K guard fires
  later, during 1s polling, as `multi_status` + `SCAN_LIMIT_REACHED` (HTTP 207).
- DEC-03 reserves `400`/`VALIDATION_FAILED` for validation failures. A folder holding more than
  10,000 files is not invalid input — the scan succeeded and produced a usable partial index.
- CLAUDE.md §6 mandates non-blocking Toasts for polling outcomes, and there is no Axios in the
  project (a fetch wrapper).

So the AC's *intent* — "tell the user their folder was too big, and do not leave the UI claiming
success" — is implemented over the polling path instead. Recorded as the deliberate reading.

What this file pins down are three defects found while implementing it, each of the
"gate exists but guards nothing" shape:

1. `FilesPage.handleRunScan` checked `scanDone.status === 'failed'` only, so `multi_status` fell
   straight through to `addToast('success', '스캔 및 중요도 분석 완료')`. The guard fired, the
   backend reported it, and the UI said 완료.
2. `DashboardPage` printed the hardcoded string "10K Limit Guard 정상 (정상 탐색)" — green on a
   truncated workspace, on the one tile a user would check to find out.
3. `ScanSummaryRes` had no way to express the guard state at all, so (2) could not be fixed in the
   UI alone.
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.task_repository import TaskRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.query_services import ScanQueryService

FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"
DASHBOARD = FRONTEND / "pages" / "DashboardPage.tsx"
FILES_PAGE = FRONTEND / "pages" / "FilesPage.tsx"


def _code(path: Path) -> str:
    """Source with comments stripped — same rationale as tests/test_ws_fe_01.py::_code.

    Load-bearing here: the rationale comments in both pages quote the very strings this file
    asserts are gone ("10K Limit Guard 정상 (정상 탐색)"), so a substring check against raw source
    would pass on the comment while the defect sat in the JSX.
    """
    import re

    content = path.read_text(encoding="utf-8")
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


@pytest.fixture
def env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "scan64.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            ws_id = WorkspaceRepository(db_mgr).create("WS64", [root])["workspace_id"]
            yield db_mgr, ws_id, root
        finally:
            db_mgr.close()


def _finish_scan(db_mgr, ws_id: str, status: str, error_code: str | None) -> str:
    """Record a finished scan task, the way the real endpoint's `body()` result would.

    `create` returns the whole row, not the id — passing the dict straight into `mark_running`
    raises `sqlite3.InterfaceError` on parameter binding.
    """
    repo = TaskRepository(db_mgr)
    task_id = repo.create("scan", workspace_id=ws_id)["task_id"]
    repo.mark_running(task_id, total_count=1)
    repo.finish(task_id, status=status, error_code=error_code)
    return task_id


# --- limit_reached comes from the scan run, not from a row count ---------------------------


def test_a_clean_scan_reports_the_guard_as_not_reached(env):
    """The control case: nothing truncated, so the dashboard may show its green caption."""
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="completed", error_code=None)

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is False


def test_a_truncated_scan_reports_the_guard_as_reached(env):
    """
    `multi_status` + `SCAN_LIMIT_REACHED` must surface as `limit_reached: True`.

    This is the field the whole issue turns on — without it the UI cannot distinguish a fully
    indexed workspace from a truncated one, and defaults to claiming success.
    """
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="multi_status", error_code="SCAN_LIMIT_REACHED")

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is True


def test_a_workspace_that_was_never_scanned_is_not_reported_as_truncated(env):
    """
    No scan history means no truncation claim.

    `True` here would warn about a limit on a workspace the user has not scanned yet — a warning
    they cannot act on and cannot clear.
    """
    db_mgr, ws_id, root = env

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is False


def test_a_rescan_clears_a_previous_truncation(env):
    """
    Only the latest finished scan counts.

    A user who narrows their root folders and rescans has fixed the problem. A sticky flag from the
    old run would keep warning forever, which trains the user to ignore the warning — so the next
    real truncation goes unnoticed.
    """
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="multi_status", error_code="SCAN_LIMIT_REACHED")
    _finish_scan(db_mgr, ws_id, status="completed", error_code=None)

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is False


def test_a_rescan_can_also_re_raise_the_truncation(env):
    """The mirror of the previous test: narrowing folders that are still too big keeps warning."""
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="completed", error_code=None)
    _finish_scan(db_mgr, ws_id, status="multi_status", error_code="SCAN_LIMIT_REACHED")

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is True


def test_a_running_scan_does_not_mask_the_last_finished_outcome(env):
    """
    An in-flight scan has no outcome yet, so the previous verdict stands.

    Treating `running` as "not truncated" would blank the warning the moment the user clicks
    rescan — before the new scan has learned anything.
    """
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="multi_status", error_code="SCAN_LIMIT_REACHED")
    repo = TaskRepository(db_mgr)
    running = repo.create("scan", workspace_id=ws_id)["task_id"]
    repo.mark_running(running, total_count=999)

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is True


def test_a_failed_scan_is_not_a_truncation(env):
    """
    `failed` with some other code must not read as "too many files".

    Conflating them would tell the user to shrink their folder when the real problem was, say, a
    permission error — sending them to fix the wrong thing.
    """
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="failed", error_code="PATH_NOT_ACCESSIBLE")

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is False


def test_another_workspaces_truncation_does_not_leak(env):
    """Scoped by `workspace_id` — a big workspace must not mark a small one as truncated."""
    db_mgr, ws_id, root = env
    other = WorkspaceRepository(db_mgr).create("Other64", [tempfile.mkdtemp()])["workspace_id"]
    _finish_scan(db_mgr, other, status="multi_status", error_code="SCAN_LIMIT_REACHED")

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is False
    assert ScanQueryService(db_mgr).get_scan_summary(other)["limit_reached"] is True


def test_the_analysis_task_type_is_not_consulted(env):
    """
    Only `task_type='scan'` decides truncation — a later analysis must not overwrite the verdict.

    The real sequence: scan truncates at 10,000, then fast analysis runs over those files and
    finishes cleanly. Analysis is the newer task, so a query without the `task_type` filter reads
    *its* outcome and reports `limit_reached: False` — silently clearing a truncation warning that
    is still true, because something unrelated succeeded afterwards.

    Ordered this way deliberately. The first version of this test used a *failed* analysis with
    `LLM_UNAVAILABLE`, which returns False under both the correct and the filterless query — so it
    passed with the filter removed. Caught by mutation testing.
    """
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="multi_status", error_code="SCAN_LIMIT_REACHED")
    repo = TaskRepository(db_mgr)
    analysis = repo.create("analyze_fast", workspace_id=ws_id)["task_id"]
    repo.mark_running(analysis, total_count=5)
    repo.finish(analysis, status="completed", error_code=None)

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is True


def test_a_partially_failed_analysis_is_not_a_file_count_truncation(env):
    """
    The mirror direction: `multi_status` on an *analysis* means per-file LLM failures (DEC-16), not
    that the folder was too big.

    Without the `task_type` filter this would report a 10,000-file truncation and send the user off
    to shrink a workspace that was fully indexed.
    """
    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="completed", error_code=None)
    repo = TaskRepository(db_mgr)
    analysis = repo.create("analyze_fast", workspace_id=ws_id)["task_id"]
    repo.mark_running(analysis, total_count=5)
    repo.finish(analysis, status="multi_status", error_code="LLM_UNAVAILABLE")

    assert ScanQueryService(db_mgr).get_scan_summary(ws_id)["limit_reached"] is False


# --- The counts the dashboard binds ------------------------------------------------------


def test_the_summary_still_carries_the_counts_the_tile_renders(env):
    """
    AC Task Breakdown: '스캔된 파일 수', 용량 등 수치 바인딩.

    Asserted alongside `limit_reached` because the new field must not have displaced them.
    """
    db_mgr, ws_id, root = env
    file_repo = FileRepository(db_mgr)
    for i in range(3):
        path = os.path.join(root, f"doc{i}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("x" * 1024)
        file_repo.bulk_upsert([{
            "file_id": str(uuid.uuid4()), "workspace_id": ws_id,
            "current_path": path, "original_path": path,
            "file_name": f"doc{i}.md", "extension": ".md",
            "size_bytes": 1024, "last_modified": 1700000000.0,
            "parse_status": "parsed", "importance_score": 10,
        }])

    summary = ScanQueryService(db_mgr).get_scan_summary(ws_id)

    assert summary["file_count"] == 3
    assert summary["total_size_mb"] == 0.0  # 3KB rounds to 0.0 MB at 2dp
    assert summary["estimated_analysis_seconds"] == 0.3
    assert summary["workspace_id"] == ws_id


# --- Real HTTP, per DECISION_LOG 재발방지 5 ------------------------------------------------


def test_the_endpoint_returns_limit_reached_over_real_http(env):
    """
    DECISION_LOG 재발방지 5: an endpoint change needs a real HTTP call as DoD evidence.

    A service-level test would pass even if the field were dropped by the DTO — `ScanSummaryRes`
    is what actually crosses the wire, and Pydantic silently discards unknown keys.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    db_mgr, ws_id, root = env
    _finish_scan(db_mgr, ws_id, status="multi_status", error_code="SCAN_LIMIT_REACHED")

    app = create_app(db_mgr, session_token="tok64")
    client = TestClient(app)
    res = client.get(
        f"/api/v1/workspace/{ws_id}/scan/summary",
        headers={"Authorization": "Bearer tok64"},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["limit_reached"] is True


def test_the_field_is_in_the_openapi_contract(env):
    """
    DEC-02: the generated schema is the contract SSOT, so the frontend type comes from here.

    Also guards the regeneration step — `types.gen.ts` is derived, and a missing schema field
    would make the TS type silently optional-and-absent.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    db_mgr, ws_id, root = env
    app = create_app(db_mgr, session_token="tok64")
    TestClient(app)

    properties = app.openapi()["components"]["schemas"]["ScanSummaryRes"]["properties"]
    assert "limit_reached" in properties


def test_the_generated_frontend_type_was_regenerated(env):
    """
    The TS type must actually carry the field, not just the Python DTO.

    Without regeneration `scan.limit_reached` would be a type error at build time — or worse,
    silently `undefined` and therefore falsy, which renders the green caption on a truncated scan:
    exactly the defect this issue fixes.
    """
    types_gen = (FRONTEND / "api" / "types.gen.ts").read_text(encoding="utf-8")
    block = types_gen[types_gen.index("export interface ScanSummaryRes"):]
    block = block[:block.index("}")]

    assert "limit_reached" in block


# --- AC intent over the polling path (DEC-04) --------------------------------------------


def test_the_scan_page_handles_multi_status_and_not_only_failure():
    """
    The defect: `handleRunScan` checked `'failed'` alone, so a truncated scan reached the success
    toast and the user was told 완료 over an incomplete index.
    """
    code = _code(FILES_PAGE)

    assert "SCAN_LIMIT_REACHED" in code, "the 10K guard code must be handled by name"
    assert "scanTruncated" in code
    assert "'multi_status'" in code


def test_the_truncation_notice_says_what_happened_and_what_to_do():
    """
    AC intent: "파일이 너무 많습니다" plus a way out.

    A bare code like `SCAN_LIMIT_REACHED` is not a user-facing message, and a warning with no
    remedy leaves the user stuck.
    """
    code = _code(FILES_PAGE)

    assert "10,000개까지만 탐색했습니다" in code
    assert "좁혀" in code, "the notice must tell the user how to resolve it"


def test_the_closing_toast_does_not_claim_plain_completion_after_a_truncated_scan():
    """
    Even with the warning added, the *final* toast still said "스캔 및 중요도 분석 완료".

    Two toasts where the last one says 완료 reads as "there was a note, but it worked out" — so the
    closing message is downgraded to a warning that restates the truncation.
    """
    code = _code(FILES_PAGE)
    tail = code[code.index("if (analysisDone.status === 'multi_status')"):]
    tail = tail[:tail.index("} catch")]

    assert "scanTruncated" in tail, "the closing branch must know the scan was truncated"
    assert "10,000개 제한" in tail


def test_the_notice_is_a_toast_and_not_a_blocking_dialog():
    """
    CLAUDE.md §6 over the AC's "에러 다이얼로그" — the indexed files are usable, so blocking the
    whole screen over a partial success is disproportionate. Recorded as the deliberate deviation.
    """
    code = _code(FILES_PAGE)

    assert "addToast(" in code
    for blocking in ("window.alert", "window.confirm", "<Modal"):
        assert blocking not in code, f"{blocking} would block on a non-blocking outcome"


# --- The dashboard tile ------------------------------------------------------------------


def test_the_dashboard_no_longer_hardcodes_the_guard_verdict():
    """
    The exact defect string. It claimed "정상 탐색" unconditionally — green on a truncated
    workspace, on the one tile a user checks to find out whether everything was indexed.
    """
    code = _code(DASHBOARD)

    assert "10K Limit Guard 정상 (정상 탐색)" not in code
    assert "scan.limit_reached" in code, "the caption must read the real guard state"


def test_the_dashboard_binds_the_scan_summary_endpoint():
    """
    AC Task Breakdown: 수치 영역 데이터 바인딩 (Query 연동).

    `files.length` alone was the file count, which is the list the explorer happens to hold —
    filtered or not yet loaded — rather than what the server scanned.
    """
    code = _code(DASHBOARD)

    # Matched without the `api.` prefix: the call is chained across lines
    # (`api\n  .getScanSummary(...)`) like the neighbouring `getAnalyticsSummary`, so a
    # single-line `api.getScanSummary` substring fails on formatting rather than on behaviour.
    assert ".getScanSummary(workspaceId)" in code
    assert "scan.file_count" in code
    assert "scan.total_size_mb" in code


def test_the_dashboard_distinguishes_loading_from_not_truncated():
    """
    Three states, not two: loading, truncated, clean.

    Collapsing loading into "clean" would flash the green "정상" caption on every dashboard open,
    including on workspaces that are in fact truncated — a wrong claim shown by default.
    """
    code = _code(DASHBOARD)

    assert "scan === null" in code
    assert "불러오는 중" in code


def test_the_truncation_caption_is_visually_distinct():
    """
    The warning must not be styled like the success caption.

    `text-emerald-400` on a truncation notice would make the problem state look like the healthy
    one at a glance, which is how the original hardcoded label went unnoticed.
    """
    code = _code(DASHBOARD)
    tile = code[code.index("총 스캔 문서"):code.index("핵심 중요 문서")]

    assert "text-amber-400" in tile, "the truncated state needs its own colour"
    assert "AlertTriangle" in tile
