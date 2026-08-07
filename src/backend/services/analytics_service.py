import logging
import uuid
from typing import Any, Dict, List, Optional

from src.backend.config_manager import ConfigManager
from src.backend.db import DatabaseManager

logger = logging.getLogger("CorpBrain.AnalyticsService")


class AnalyticsService:
    # Default Claude token price ($3.00 / 1,000,000 tokens = 0.000003 USD per token)
    DEFAULT_TOKEN_PRICE_USD = 0.000003

    def __init__(self, db_mgr: DatabaseManager, config_mgr: Optional[ConfigManager] = None):
        self.db_mgr = db_mgr
        self.config_mgr = config_mgr or ConfigManager(db_mgr)

    def log_event(
        self,
        workspace_id: str,
        event_type: str,
        file_id: Optional[str] = None,
        wiki_id: Optional[str] = None,
        tokens_used: int = 0,
        cost_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Logs user action/analytics event into Analytics_Log (STAT-CMD-01 / DEC-07 / DEC-16).
        - Lowercase event_type (e.g. 'deeplink_click', 'watcher_update')
        - DEC-16: Option B sets cost_usd=0.0, Option A calculates cost via App_Config price.
          Unmeasured/failed calls set cost_usd=NULL (None).
        """
        clean_event_type = event_type.lower()
        log_id = str(uuid.uuid4())

        llm_mode = self.config_mgr.get("llm_mode", "Option A")

        # DEC-16 cost rules
        if cost_usd is None:
            if llm_mode == "Option B":
                calc_cost: Optional[float] = 0.0
            elif llm_mode == "Option A" and tokens_used > 0:
                price = float(self.config_mgr.get("claude_token_price_usd", self.DEFAULT_TOKEN_PRICE_USD))
                calc_cost = float(tokens_used) * price
            else:
                calc_cost = None
        else:
            calc_cost = cost_usd

        with self.db_mgr.transaction() as conn:
            conn.execute(
                """INSERT INTO Analytics_Log (log_id, workspace_id, file_id, wiki_id, event_type, tokens_used, cost_usd)
                   VALUES (?, ?, ?, ?, ?, ?, ?);""",
                (log_id, workspace_id, file_id, wiki_id, clean_event_type, tokens_used, calc_cost),
            )

        logger.info(f"[AnalyticsService] Logged event {clean_event_type} for workspace {workspace_id} (cost={calc_cost})")
        return {
            "log_id": log_id,
            "workspace_id": workspace_id,
            "event_type": clean_event_type,
            "file_id": file_id,
            "wiki_id": wiki_id,
            "tokens_used": tokens_used,
            "cost_usd": calc_cost
        }

    def get_analytics_summary(
        self,
        workspace_id: str,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Computes dashboard analytics summary (STAT-QRY-01 / DEC-07 / DEC-11).
        - Saved time calculation: SUM(tokens_used) / (250 WPM * 1.3 tokens/word) -> minutes
        - Compression ratio: COUNT(parsed files) : COUNT(wiki content) (Snapshot metric, no period filter DEC-07)
        - Preserves historical counts when files/wikis deleted (DEC-07)
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()

        # Build period filter query for log events
        where_clauses = ["workspace_id = ?"]
        params: List[Any] = [workspace_id]

        if from_time:
            where_clauses.append("created_at >= ?")
            params.append(from_time)
        if to_time:
            where_clauses.append("created_at <= ?")
            params.append(to_time)

        where_sql = " AND ".join(where_clauses)

        # 1. Total tokens & saved minutes (250 WPM * 1.3 tokens/word = 325 tokens/min)
        q_tokens = f"SELECT COALESCE(SUM(tokens_used), 0) AS total_tokens, COALESCE(SUM(cost_usd), 0.0) AS total_cost FROM Analytics_Log WHERE {where_sql};"
        t_row = cursor.execute(q_tokens, params).fetchone()
        total_tokens = t_row["total_tokens"] if t_row else 0
        total_cost = t_row["total_cost"] if t_row else 0.0

        saved_minutes = round(total_tokens / 325.0, 1)

        # 2. Event type counts (deeplink_click, watcher_update)
        q_deeplink = f"SELECT COUNT(*) FROM Analytics_Log WHERE {where_sql} AND event_type = 'deeplink_click';"
        deeplink_count = cursor.execute(q_deeplink, params).fetchone()[0]

        q_watcher = f"SELECT COUNT(*) FROM Analytics_Log WHERE {where_sql} AND event_type = 'watcher_update';"
        watcher_count = cursor.execute(q_watcher, params).fetchone()[0]

        # 3. Snapshot compression ratio (DEC-07: parsed files : wiki documents, current state snapshot)
        parsed_files = cursor.execute(
            "SELECT COUNT(*) FROM File_Meta WHERE workspace_id = ? AND parse_status = 'parsed';",
            (workspace_id,)
        ).fetchone()[0]

        wiki_docs = cursor.execute(
            "SELECT COUNT(*) FROM Wiki_Content WHERE workspace_id = ?;",
            (workspace_id,)
        ).fetchone()[0]

        compression_ratio_str = f"{parsed_files}:{wiki_docs}"

        return {
            "workspace_id": workspace_id,
            "period": {
                "from_time": from_time,
                "to_time": to_time
            },
            "saved_time_minutes": saved_minutes,
            "total_tokens_used": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "deeplink_clicks_count": deeplink_count,
            "watcher_updates_count": watcher_count,
            "compression_ratio": compression_ratio_str,
            "knowledge_ratio_scope": "current"
        }
