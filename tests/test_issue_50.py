"""
STAT-FE-01 (issue #50) — My Analytics dashboard (REQ-FUNC-028~030 / REQ-NF-005).

The React half is asserted statically, per tests/test_ws_fe_01.py — there is no frontend test
runner by decision. What that proves: the four metrics are bound to real DTO fields, no chart
library was added, the Empty State exists and is reachable, DEC-07's snapshot scope is respected in
the labelling, and DEC-11's period boundary is computed client-side. What it cannot prove: the
rendered layout or the animation.

**No Recharts.** The issue's task breakdown suggests it, but it is not in CLAUDE.md §4's
pre-approved list and a new runtime package also enters the PyInstaller bundle (DEC-01). The AC's
one visual is a compression ratio — two counts and a bar — which is a div with a width. Recorded as
CORE 2 in docs/loop/CHECKPOINT.md so the deviation from the issue text is visible.

The backend half is exercised for real: the endpoint the page calls must return every field the
page binds, so a DTO rename breaks a test here rather than blanking a tile at runtime.
"""

import os
import re
import tempfile
from pathlib import Path

from src.backend.db import DatabaseManager
from src.backend.repositories.workspace_repository import WorkspaceRepository

FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"
PAGE = FRONTEND / "pages" / "AnalyticsPage.tsx"
APP = FRONTEND / "App.tsx"
SIDEBAR = FRONTEND / "components" / "Sidebar.tsx"
STORE = FRONTEND / "store" / "appStore.ts"

#: Every DTO field the page renders. A rename on the backend must fail a test here rather than
#: silently blanking a tile.
BOUND_FIELDS = [
    "saved_time_minutes",
    "deeplink_clicks_count",
    "watcher_updates_count",
    "compression_ratio",
    "knowledge_ratio_scope",
    "total_tokens_used",
    "total_cost_usd",
]


def _code(path: Path) -> str:
    """Source with comments stripped — same rationale as tests/test_ws_fe_01.py::_code."""
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


# --- The contract between page and endpoint ----------------------------------------------


def test_every_field_the_page_binds_exists_in_the_response():
    """
    The page reads seven DTO fields; the endpoint must return all seven.

    Asserted against the live OpenAPI schema rather than the DTO class, since DEC-02 makes the
    schema the contract SSOT — and a field present on the model but absent from the response is
    exactly the drift that blanks a tile at runtime.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "fe.db"))
        try:
            app = create_app(db_mgr, session_token="fe-token")
            TestClient(app)  # triggers schema generation
            schema = app.openapi()
            properties = schema["components"]["schemas"]["AnalyticsSummaryRes"]["properties"]

            for field in BOUND_FIELDS:
                assert field in properties, f"the page binds {field}, the response does not carry it"
        finally:
            db_mgr.close()


def test_the_page_binds_only_real_fields():
    """
    The mirror direction: every `summary.X` the page reads must be a real DTO field.

    A typo would render `undefined` — which React displays as an empty tile, not an error, so it
    would ship looking merely "empty" rather than broken.
    """
    from src.backend.api.dtos import AnalyticsSummaryRes

    code = _code(PAGE)
    referenced = set(re.findall(r"summary\.(\w+)", code))
    known = set(AnalyticsSummaryRes.model_fields)

    unknown = referenced - known
    assert unknown == set(), f"the page reads fields that do not exist: {sorted(unknown)}"


def test_the_endpoint_returns_a_usable_response_for_a_new_workspace():
    """
    A workspace with no history must return zeros, not an error.

    This is the state the Empty State branch depends on, and the first screen a new user reaches —
    a 500 here would make the feature look broken on first contact.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "fe2.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            ws_id = WorkspaceRepository(db_mgr).create("New WS", [root])["workspace_id"]

            app = create_app(db_mgr, session_token="fe-token")
            client = TestClient(app)
            res = client.get(
                f"/api/v1/workspace/{ws_id}/analytics/summary",
                headers={"Authorization": "Bearer fe-token"},
            )

            assert res.status_code == 200, res.text
            data = res.json()["data"]
            assert data["saved_time_minutes"] == 0.0
            assert data["compression_ratio"] == "0:0"
            assert data["knowledge_ratio_scope"] == "current"
        finally:
            db_mgr.close()


def test_the_period_query_is_accepted_as_utc_instants():
    """
    DEC-11: the page computes the week boundary locally and sends instants.

    The endpoint must accept `from_time`/`to_time` — if it only took a period name, the frontend
    could not express a KST week at all.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "fe3.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            ws_id = WorkspaceRepository(db_mgr).create("Period WS", [root])["workspace_id"]

            app = create_app(db_mgr, session_token="fe-token")
            client = TestClient(app)
            res = client.get(
                f"/api/v1/workspace/{ws_id}/analytics/summary",
                params={
                    "from_time": "2026-08-03T00:00:00.000Z",
                    "to_time": "2026-08-10T00:00:00.000Z",
                },
                headers={"Authorization": "Bearer fe-token"},
            )

            assert res.status_code == 200, res.text
            assert res.json()["data"]["period"]["from_time"] == "2026-08-03T00:00:00.000Z"
        finally:
            db_mgr.close()


# --- No chart library (CLAUDE.md §4 / DEC-01) --------------------------------------------


def test_no_chart_library_was_added():
    """
    CORE 2: the issue suggests Recharts, CLAUDE.md §4 does not approve it.

    A new runtime package also enters the PyInstaller-embedded bundle (DEC-01), and the AC's one
    visual is two counts and a bar. Checked against package.json AND the page's imports, because
    either alone could be satisfied while the other slipped.
    """
    package_json = (Path(__file__).resolve().parent.parent / "package.json").read_text(encoding="utf-8")
    for library in ("recharts", "chart.js", "victory", "nivo", "apexcharts", "d3"):
        assert library not in package_json, f"{library} is not an approved dependency (CLAUDE.md §4)"

    code = _code(PAGE)
    assert "recharts" not in code.lower()
    # The compression visual is plain CSS width.
    assert "style={{ width:" in code


# --- AC S1: four metric cards ------------------------------------------------------------


def test_scenario_1_four_metric_cards_are_rendered():
    """
    AC S1: 절약시간 / 팩트체크 / 압축률 / 자동화, as four cards.

    The AC names the metrics, not the DTO fields, so the mapping is recorded as MINOR 2 —
    팩트체크 ← deeplink_clicks_count (opening the source IS the fact-check), 자동화 ←
    watcher_updates_count.
    """
    code = _code(PAGE)

    # `<MetricCard` alone also matches the component's own definition, so count the JSX usages by
    # their required prop instead — each rendered card carries exactly one `delayMs`.
    assert code.count("delayMs={") == 4, "AC S1 requires exactly four rendered cards"
    for label in ("절약한 시간", "팩트체크", "지식 압축률", "자동화"):
        assert label in code, label
    for field in ("saved_time_minutes", "deeplink_clicks_count", "compression_ratio", "watcher_updates_count"):
        assert field in code, field


def test_the_cards_animate_in_with_a_stagger():
    """
    AC S1 says "애니메이션과 함께". Staggered, so the four arrive in sequence.

    A timeout rather than CSS `animation-delay`: with a delay the card is visible for the first
    frame before the animation starts, which flashes on a slow render.
    """
    code = _code(PAGE)

    assert "delayMs" in code
    assert "transition-all" in code
    assert "setTimeout" in code
    # Four distinct delays, not one shared value.
    delays = sorted(set(re.findall(r"delayMs=\{(\d+)\}", code)))
    assert len(delays) == 4, f"expected four distinct stagger delays, got {delays}"


# --- AC S2: Empty State ------------------------------------------------------------------


def test_scenario_2_the_empty_state_uses_the_wording_the_ac_names():
    """AC S2: "분석을 시작하면 통계가 표시됩니다"."""
    code = _code(PAGE)
    assert "분석을 시작하면 통계가 표시됩니다" in code


def test_the_empty_state_requires_all_four_metrics_to_be_zero():
    """
    A workspace with only deeplink clicks must show its real numbers, not the Empty State.

    Checking a single metric would hide genuine activity behind "you have not started yet" — the
    most annoying possible false negative, since the user just did the thing.
    """
    code = _code(PAGE)
    start = code.index("const isEmpty")
    # Slice to the end of the assignment, not to the next `return (` — an earlier `return (`
    # exists in this file, so indexing from 0 produced an empty slice and the assertions below
    # passed vacuously. Caught by the first run.
    empty_expr = code[start:code.index(";", start)]

    for field in ("saved_time_minutes", "deeplink_clicks_count", "watcher_updates_count", "compression_ratio"):
        assert field in empty_expr, f"{field} must participate in the empty check"
    assert "&&" in empty_expr, "the metrics must be ANDed, not ORed"


def test_the_empty_state_and_the_cards_are_mutually_exclusive():
    """
    Showing four zeros next to "you have not started" would contradict itself.

    Asserted structurally: the cards render under `!isEmpty`.
    """
    code = _code(PAGE)
    assert "!isEmpty" in code
    assert "{isEmpty &&" in code


# --- DEC-07 / DEC-16 labelling -----------------------------------------------------------


def test_the_ratio_is_not_labelled_with_the_period():
    """
    DEC-07: the ratio is period-independent, so it must not be captioned "이번 주".

    Attributing a period to a snapshot tells the user something untrue — and the summary DOES carry
    a period for the other metrics, which is exactly what makes the mistake easy.
    """
    code = _code(PAGE)
    assert "knowledge_ratio_scope" in code
    assert "현재 시점 기준" in code

    bar = code[code.index("const CompressionBar"):code.index("function formatSavedTime")]
    assert "이번 주" not in bar, "a snapshot metric must not be labelled with a period"


def test_the_cost_is_presented_as_an_estimate():
    """
    DEC-16: displayed cost is an estimate from a user-editable price, never a bill.

    Without the caveat the app states a wrong figure confidently whenever the seeded price is
    stale — which DEC-16 calls the worst failure form.
    """
    code = _code(PAGE)
    assert "추정" in code
    assert "실제 청구액과 다를 수 있습니다" in code


def test_the_saved_time_states_its_basis():
    """
    ASM-05 makes 250 WPM an assumption, so the figure must say so.

    "You saved 3 hours" presented as fact invites a dispute the app cannot win; "estimated at 250
    WPM" is checkable.
    """
    code = _code(PAGE)
    assert "WPM" in code
    assert "추정치" in code


# --- REQ-NF-005: local API only ----------------------------------------------------------


def test_the_page_talks_only_to_the_local_api():
    """
    REQ-NF-005 / CON-03: no external telemetry, and analytics is the feature most likely to grow
    one — every product instinct says to ship usage numbers somewhere.
    """
    code = _code(PAGE)

    assert "api.getAnalyticsSummary" in code
    for forbidden in ("fetch('http", 'fetch("http', "https://", "gtag", "analytics.track", "posthog"):
        assert forbidden not in code, f"{forbidden} would be an external transmission"


# --- Navigation wiring -------------------------------------------------------------------


def test_the_page_is_reachable_from_the_sidebar():
    """
    A page not in the switch is dead code, and a page not in the sidebar is unreachable.

    Both halves, plus the store's union type — TypeScript would reject the tab id otherwise, and
    the whole thing would fail to build rather than fail visibly.
    """
    assert "'analytics'" in _code(STORE), "the ActiveTab union must include the new tab"

    app = _code(APP)
    assert "AnalyticsPage" in app
    assert "case 'analytics':" in app

    sidebar = _code(SIDEBAR)
    assert "id: 'analytics'" in sidebar
    assert "My Analytics" in sidebar


def test_the_page_handles_no_selected_workspace():
    """
    Analytics is per workspace, so the page must say so rather than calling the API with null.

    Without the guard the first render fires a request with `undefined` in the path, which returns
    404 and surfaces as an error toast on a screen the user did nothing wrong on.
    """
    code = _code(PAGE)
    assert "if (!currentWorkspace)" in code
    assert "워크스페이스를 선택하면" in code
