import os
import tempfile

import pytest

from src.backend.config_manager import ConfigManager
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.analytics_service import AnalyticsService


@pytest.fixture
def stat_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "stat_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)

        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)
        config_mgr = ConfigManager(db_mgr)

        ws_res = ws_repo.create("Analytics Test WS", tmpdir)
        ws_id = ws_res["workspace_id"]

        f1_id = "stat_file_001"
        file_repo.bulk_upsert([
            {
                "workspace_id": ws_id,
                "file_id": f1_id,
                "current_path": os.path.join(tmpdir, "doc1.txt"),
                "original_path": os.path.join(tmpdir, "doc1.txt"),
                "file_name": "doc1.txt",
                "extension": ".txt",
                "size_bytes": 1024,
                "last_modified": 1700000000.0,
                "importance_score": 50,
                "parse_status": "parsed",
            }
        ])

        conn = db_mgr.get_connection()
        conn.execute(
            """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
               VALUES ('wiki_stat_001', ?, 'Tech', 'Wiki content');""",
            (ws_id,)
        )

        svc = AnalyticsService(db_mgr, config_mgr=config_mgr)
        yield svc, db_mgr, config_mgr, ws_id, f1_id, tmpdir
        db_mgr.close()


def test_scenario_1_log_event_and_cost_calculation_rules(stat_setup):
    svc, db_mgr, config_mgr, ws_id, f1_id, tmpdir = stat_setup

    # 1. Option A (Claude Cloud) -> cost_usd calculated from price
    config_mgr.set("llm_mode", "Option A")
    res_a = svc.log_event(ws_id, event_type="deeplink_click", file_id=f1_id, wiki_id="wiki_stat_001", tokens_used=1000)

    assert res_a["event_type"] == "deeplink_click"  # Lowercase snake_case
    assert res_a["cost_usd"] == pytest.approx(0.003, rel=1e-3)

    # 2. Option B (Local Ollama) -> cost_usd MUST be 0.0 (DEC-16)
    config_mgr.set("llm_mode", "Option B")
    res_b = svc.log_event(ws_id, event_type="watcher_update", file_id=f1_id, tokens_used=5000)
    assert res_b["cost_usd"] == 0.0

    # 3. Unmeasured / Failed call -> cost_usd MUST be None (NULL in DB, DEC-16)
    config_mgr.set("llm_mode", "Option A")
    res_null = svc.log_event(ws_id, event_type="deep_analysis", file_id=f1_id, tokens_used=0, cost_usd=None)
    assert res_null["cost_usd"] is None


def test_scenario_2_wpm_time_saved_calculation(stat_setup):
    svc, db_mgr, config_mgr, ws_id, f1_id, tmpdir = stat_setup

    # Log 32,500 tokens -> 32,500 / 325 = 100.0 minutes
    svc.log_event(ws_id, event_type="deeplink_click", file_id=f1_id, tokens_used=16250)
    svc.log_event(ws_id, event_type="watcher_update", file_id=f1_id, tokens_used=16250)

    summary = svc.get_analytics_summary(ws_id)

    assert summary["saved_time_minutes"] == 100.0
    assert summary["total_tokens_used"] == 32500
    assert summary["deeplink_clicks_count"] == 1
    assert summary["watcher_updates_count"] == 1


def test_scenario_3_snapshot_compression_ratio_and_historical_preservation(stat_setup):
    svc, db_mgr, config_mgr, ws_id, f1_id, tmpdir = stat_setup

    svc.log_event(ws_id, event_type="deeplink_click", file_id=f1_id, wiki_id="wiki_stat_001", tokens_used=1000)

    # Delete file from File_Meta
    conn = db_mgr.get_connection()
    conn.execute("DELETE FROM File_Meta WHERE file_id = ?;", (f1_id,))

    # DEC-07: Analytics_Log file_id becomes NULL, but historical record & count remain intact
    summary = svc.get_analytics_summary(ws_id)
    assert summary["deeplink_clicks_count"] == 1
    assert summary["compression_ratio"] == "0:1"  # 0 parsed files : 1 wiki document
    assert summary["knowledge_ratio_scope"] == "current"


def test_scenario_4_period_filter_utc_iso8601(stat_setup):
    svc, db_mgr, config_mgr, ws_id, f1_id, tmpdir = stat_setup

    # Insert events with explicit timestamp
    conn = db_mgr.get_connection()
    conn.execute(
        """INSERT INTO Analytics_Log (log_id, workspace_id, event_type, tokens_used, cost_usd, created_at)
           VALUES ('log_past', ?, 'deeplink_click', 10000, 0.03, '2026-01-01T00:00:00.000Z');""",
        (ws_id,)
    )
    conn.execute(
        """INSERT INTO Analytics_Log (log_id, workspace_id, event_type, tokens_used, cost_usd, created_at)
           VALUES ('log_recent', ?, 'deeplink_click', 5000, 0.015, '2026-08-01T00:00:00.000Z');""",
        (ws_id,)
    )

    # Query with period filter from 2026-07-01 to 2026-08-31
    summary = svc.get_analytics_summary(ws_id, from_time="2026-07-01T00:00:00.000Z", to_time="2026-08-31T23:59:59.000Z")

    assert summary["total_tokens_used"] == 5000
    assert summary["deeplink_clicks_count"] == 1
