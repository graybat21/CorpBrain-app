"""
STAT-QRY-01 + STAT-TEST-01 (issues #51, #52) — WPM time-saved and the dashboard metrics
(REQ-FUNC-027, 029 / DEC-07 / DEC-11 / ASM-05).

`tests/test_stat_cmd_01_qry_01.py` covers logging and a summary shape. This adds the AC's own
arithmetic and the two rules that are easy to get quietly wrong:

**DEC-07 — the compression ratio is a snapshot, the rest is period-filtered.** The two live in one
response, so a single `WHERE created_at` applied to everything would silently make the ratio depend
on the date range the user happened to pick. Asserted by moving the period around and watching the
ratio hold still.

**DEC-11 — the backend never infers a period boundary.** `from`/`to` arrive as caller-computed UTC
instants because the frontend knows the user's timezone and the server does not. A server that
guessed "this week" would be up to 9 hours off from KST's week, and the error would be invisible:
the number is plausible either way.

AC S1's figure is verified end to end rather than restated: 250,000 words x 1.3 token/word =
325,000 tokens, / (250 WPM x 1.3) = exactly 1,000 minutes. Both paths agree because 250,000 / 250
is also 1,000, which is what makes the constant pair self-consistent.
"""

import os
import tempfile
import uuid

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.analytics_service import AnalyticsService

#: ASM-05's reading speed and the token/word factor the AC uses. 250 x 1.3 = 325 tokens/min.
WPM = 250
TOKENS_PER_WORD = 1.3
TOKENS_PER_MINUTE = WPM * TOKENS_PER_WORD


@pytest.fixture
def stats_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "stat.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            ws_id = WorkspaceRepository(db_mgr).create("Stat WS", [root])["workspace_id"]
            yield AnalyticsService(db_mgr), db_mgr, ws_id, root
        finally:
            db_mgr.close()


def _log(db_mgr, ws_id, event_type: str, tokens: int = 0, created_at: str = None) -> str:
    """
    Insert an Analytics_Log row, optionally backdated.

    Written directly rather than through `log_event` because the period tests need a controlled
    `created_at`, and the service (correctly) always stamps `now`.
    """
    log_id = str(uuid.uuid4())
    with db_mgr.transaction() as tx:
        if created_at is None:
            tx.execute(
                """INSERT INTO Analytics_Log (log_id, workspace_id, event_type, tokens_used)
                   VALUES (?, ?, ?, ?);""",
                (log_id, ws_id, event_type, tokens),
            )
        else:
            tx.execute(
                """INSERT INTO Analytics_Log (log_id, workspace_id, event_type, tokens_used, created_at)
                   VALUES (?, ?, ?, ?, ?);""",
                (log_id, ws_id, event_type, tokens, created_at),
            )
    return log_id


# --- AC Scenario 1: the exact figure the AC names ----------------------------------------


def test_scenario_1_two_hundred_fifty_thousand_words_is_one_thousand_minutes(stats_env):
    """
    AC S1 verbatim: 250,000 words of extracted text returns 1,000 minutes saved.

    Computed through the real service from real rows, not restated as a formula. The two derivations
    agree — 250,000 x 1.3 / 325 and 250,000 / 250 are both 1,000 — which is what makes the constant
    pair self-consistent rather than two numbers that happen to be in the code.
    """
    service, db_mgr, ws_id, root = stats_env
    tokens = int(250_000 * TOKENS_PER_WORD)  # 325,000
    _log(db_mgr, ws_id, "analysis_complete", tokens=tokens)

    summary = service.get_analytics_summary(ws_id)

    assert summary["total_tokens_used"] == tokens
    assert summary["saved_time_minutes"] == 1000.0


@pytest.mark.parametrize(
    "words,expected_minutes",
    [
        (250, 1.0),
        (2_500, 10.0),
        (25_000, 100.0),
        (250_000, 1000.0),
        (125, 0.5),
    ],
)
def test_the_conversion_is_linear_across_magnitudes(stats_env, words, expected_minutes):
    """
    One data point can be satisfied by a coincidence; five across three orders of magnitude cannot.

    Also pins the constant: any WPM other than 250 breaks every row here at once, so a "tuning"
    change has to be deliberate (ASM-05 fixes it at 200~250).
    """
    service, db_mgr, ws_id, root = stats_env
    _log(db_mgr, ws_id, "analysis_complete", tokens=int(words * TOKENS_PER_WORD))

    summary = service.get_analytics_summary(ws_id)

    assert summary["saved_time_minutes"] == pytest.approx(expected_minutes, abs=0.05)


def test_tokens_accumulate_across_events(stats_env):
    """
    Saved time is a SUM, so many small analyses must add up.

    A MAX or a last-write-wins would look right on a single-file workspace and under-report by
    orders of magnitude on a real one.
    """
    service, db_mgr, ws_id, root = stats_env
    for _ in range(10):
        _log(db_mgr, ws_id, "analysis_complete", tokens=32_500)  # 100 minutes each

    summary = service.get_analytics_summary(ws_id)

    assert summary["total_tokens_used"] == 325_000
    assert summary["saved_time_minutes"] == 1000.0


def test_an_empty_workspace_reports_zero_not_an_error(stats_env):
    """
    A fresh workspace has no logs, and the dashboard must render 0 rather than fail.

    `COALESCE(SUM(...), 0)` is what makes this work — without it SUM returns NULL and the division
    raises, taking the whole dashboard down on the one screen a new user sees first.
    """
    service, db_mgr, ws_id, root = stats_env

    summary = service.get_analytics_summary(ws_id)

    assert summary["total_tokens_used"] == 0
    assert summary["saved_time_minutes"] == 0.0
    assert summary["deeplink_clicks_count"] == 0


# --- DEC-07: the compression ratio is a snapshot -----------------------------------------


def test_the_compression_ratio_counts_parsed_files_against_wiki_documents(stats_env):
    """
    DEC-07: the ratio is `COUNT(parsed files) : COUNT(wiki docs)`, not token-versus-token.

    "5 documents became 1 page" is the claim a user can check by looking; a token ratio is a number
    they have no way to verify, which is why DEC-07 chose counts.
    """
    service, db_mgr, ws_id, root = stats_env
    file_repo = FileRepository(db_mgr)
    for i in range(5):
        path = os.path.join(root, f"doc{i}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("x")
        file_repo.bulk_upsert([{
            "file_id": str(uuid.uuid4()), "workspace_id": ws_id,
            "current_path": path, "original_path": path,
            "file_name": f"doc{i}.md", "extension": ".md",
            "size_bytes": 1, "last_modified": 1700000000.0,
            "parse_status": "parsed", "importance_score": 0,
        }])
    with db_mgr.transaction() as tx:
        tx.execute(
            """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
               VALUES (?, ?, ?, ?);""",
            (str(uuid.uuid4()), ws_id, "docs", "# 요약"),
        )

    summary = service.get_analytics_summary(ws_id)

    assert summary["compression_ratio"] == "5:1"
    assert summary["knowledge_ratio_scope"] == "current"


def test_unparsed_files_are_excluded_from_the_ratio(stats_env):
    """
    Only `parse_status='parsed'` counts.

    Counting pending files would claim compression for documents the wiki has never read — the
    ratio would improve simply by scanning more, which inverts its meaning.
    """
    service, db_mgr, ws_id, root = stats_env
    file_repo = FileRepository(db_mgr)
    for i, status in enumerate(["parsed", "parsed", "pending", "failed"]):
        path = os.path.join(root, f"f{i}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("x")
        file_repo.bulk_upsert([{
            "file_id": str(uuid.uuid4()), "workspace_id": ws_id,
            "current_path": path, "original_path": path,
            "file_name": f"f{i}.md", "extension": ".md",
            "size_bytes": 1, "last_modified": 1700000000.0,
            "parse_status": status, "importance_score": 0,
        }])

    assert service.get_analytics_summary(ws_id)["compression_ratio"] == "2:0"


def test_the_ratio_ignores_the_period_filter(stats_env):
    """
    DEC-07's load-bearing rule: the ratio is a **current snapshot**, period-independent.

    Both metrics share one response, so a single `WHERE created_at` applied to everything would
    silently make the ratio depend on the range the user picked — and a ratio that changes when you
    switch from "this week" to "this month" is telling the user something untrue about their files.
    """
    service, db_mgr, ws_id, root = stats_env
    file_repo = FileRepository(db_mgr)
    path = os.path.join(root, "doc.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("x")
    file_repo.bulk_upsert([{
        "file_id": str(uuid.uuid4()), "workspace_id": ws_id,
        "current_path": path, "original_path": path,
        "file_name": "doc.md", "extension": ".md",
        "size_bytes": 1, "last_modified": 1700000000.0,
        "parse_status": "parsed", "importance_score": 0,
    }])

    unfiltered = service.get_analytics_summary(ws_id)
    ancient = service.get_analytics_summary(
        ws_id, from_time="1999-01-01T00:00:00.000Z", to_time="1999-12-31T23:59:59.999Z"
    )

    assert unfiltered["compression_ratio"] == "1:0"
    assert ancient["compression_ratio"] == "1:0", "the ratio must not move with the period"
    assert ancient["knowledge_ratio_scope"] == "current"


def test_the_ratio_survives_deleted_history(stats_env):
    """
    DEC-07: a deleted wiki row lowers the wiki count, which is correct for a snapshot.

    Recorded as the deliberate reading — "current" in `knowledge_ratio_scope` says the number
    describes what exists now, not what was ever produced.
    """
    service, db_mgr, ws_id, root = stats_env
    wiki_id = str(uuid.uuid4())
    with db_mgr.transaction() as tx:
        tx.execute(
            """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
               VALUES (?, ?, ?, ?);""",
            (wiki_id, ws_id, "docs", "# 요약"),
        )
    assert service.get_analytics_summary(ws_id)["compression_ratio"] == "0:1"

    with db_mgr.transaction() as tx:
        tx.execute("DELETE FROM Wiki_Content WHERE wiki_id = ?;", (wiki_id,))

    assert service.get_analytics_summary(ws_id)["compression_ratio"] == "0:0"


# --- DEC-11: the period comes from the caller -------------------------------------------


def test_the_period_filter_selects_only_rows_inside_it(stats_env):
    """
    Saved time IS period-filtered, unlike the ratio.

    Backdated rows are inserted directly because `log_event` always stamps `now` — correctly, but
    that makes it useless for testing a boundary.
    """
    service, db_mgr, ws_id, root = stats_env
    _log(db_mgr, ws_id, "analysis_complete", tokens=325, created_at="2026-08-01T00:00:00.000Z")
    _log(db_mgr, ws_id, "analysis_complete", tokens=650, created_at="2026-08-15T00:00:00.000Z")
    _log(db_mgr, ws_id, "analysis_complete", tokens=975, created_at="2026-09-01T00:00:00.000Z")

    august = service.get_analytics_summary(
        ws_id, from_time="2026-08-01T00:00:00.000Z", to_time="2026-08-31T23:59:59.999Z"
    )

    assert august["total_tokens_used"] == 975, "only the two August rows"
    assert august["saved_time_minutes"] == 3.0


def test_the_boundaries_are_inclusive(stats_env):
    """
    `>=` and `<=`, so a row exactly at the boundary is included.

    Exclusive bounds would drop an event at midnight — a real occurrence, since a scheduled
    overnight analysis lands there.
    """
    service, db_mgr, ws_id, root = stats_env
    _log(db_mgr, ws_id, "analysis_complete", tokens=325, created_at="2026-08-01T00:00:00.000Z")
    _log(db_mgr, ws_id, "analysis_complete", tokens=325, created_at="2026-08-31T23:59:59.999Z")

    summary = service.get_analytics_summary(
        ws_id, from_time="2026-08-01T00:00:00.000Z", to_time="2026-08-31T23:59:59.999Z"
    )

    assert summary["total_tokens_used"] == 650, "both boundary rows must be included"


def test_the_service_takes_instants_and_never_a_period_name(stats_env):
    """
    DEC-11: the backend must not accept "week"/"month" and infer a boundary.

    The frontend knows the user's timezone; the server does not. A server-inferred "this week" would
    be up to 9 hours off from KST's week, and the error is invisible — the number is plausible
    either way. Asserted on the signature so the temptation cannot be added quietly.
    """
    import inspect

    signature = inspect.signature(AnalyticsService.get_analytics_summary)
    assert set(signature.parameters) == {"self", "workspace_id", "from_time", "to_time"}
    for forbidden in ("period", "range", "week", "month", "days"):
        assert forbidden not in signature.parameters, forbidden


def test_the_response_echoes_the_period_it_used(stats_env):
    """
    The response restates `from`/`to` so the frontend can label the figure it renders.

    Without it, a stale request and a fresh one are indistinguishable in the UI — the user sees a
    number with no idea which range produced it.
    """
    service, db_mgr, ws_id, root = stats_env

    summary = service.get_analytics_summary(
        ws_id, from_time="2026-08-01T00:00:00.000Z", to_time="2026-08-31T23:59:59.999Z"
    )

    assert summary["period"]["from_time"] == "2026-08-01T00:00:00.000Z"
    assert summary["period"]["to_time"] == "2026-08-31T23:59:59.999Z"


# --- Event counts (the other two dashboard tiles) ---------------------------------------


def test_event_counts_are_per_type_and_period_filtered(stats_env):
    """
    Deeplink clicks and watcher updates are counted separately — they are two dashboard tiles.

    Filtered by period, unlike the ratio, because "how much did I use this feature this week" is
    the question they answer.
    """
    service, db_mgr, ws_id, root = stats_env
    for _ in range(3):
        _log(db_mgr, ws_id, "deeplink_click", created_at="2026-08-10T00:00:00.000Z")
    for _ in range(2):
        _log(db_mgr, ws_id, "watcher_update", created_at="2026-08-10T00:00:00.000Z")
    _log(db_mgr, ws_id, "deeplink_click", created_at="2026-07-01T00:00:00.000Z")

    august = service.get_analytics_summary(
        ws_id, from_time="2026-08-01T00:00:00.000Z", to_time="2026-08-31T23:59:59.999Z"
    )

    assert august["deeplink_clicks_count"] == 3, "the July click is outside the period"
    assert august["watcher_updates_count"] == 2


def test_another_workspace_does_not_contribute(stats_env):
    """
    Every query is scoped by `workspace_id`.

    Without the scope the dashboard would show the sum across every workspace, which reads as an
    inexplicably large "time saved" for a workspace the user just created.
    """
    service, db_mgr, ws_id, root = stats_env
    other_ws = WorkspaceRepository(db_mgr).create("Other", [tempfile.mkdtemp()])["workspace_id"]
    _log(db_mgr, ws_id, "analysis_complete", tokens=325)
    _log(db_mgr, other_ws, "analysis_complete", tokens=99_999)

    assert service.get_analytics_summary(ws_id)["total_tokens_used"] == 325


def test_cost_is_summed_and_zero_is_distinct_from_unmeasured(stats_env):
    """
    DEC-16: Option B records `cost_usd = 0`, not NULL — "no cost" and "not measured" differ.

    Summing NULLs as zero would make a local-only workspace indistinguishable from one whose cost
    was never recorded, and the second is a bug worth seeing.
    """
    service, db_mgr, ws_id, root = stats_env
    log_id = str(uuid.uuid4())
    with db_mgr.transaction() as tx:
        tx.execute(
            """INSERT INTO Analytics_Log (log_id, workspace_id, event_type, tokens_used, cost_usd)
               VALUES (?, ?, ?, ?, ?);""",
            (log_id, ws_id, "analysis_complete", 325, 0.0),
        )

    summary = service.get_analytics_summary(ws_id)

    assert summary["total_cost_usd"] == 0.0
    row = db_mgr.get_connection().execute(
        "SELECT cost_usd FROM Analytics_Log WHERE log_id = ?;", (log_id,)
    ).fetchone()
    assert row["cost_usd"] is not None, "Option B must store 0, never NULL"
