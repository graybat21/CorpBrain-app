import uuid
from typing import Any, Dict, List, Optional

from src.backend.db import DatabaseManager


class WorkspaceRepository:
    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr

    def create(self, name: str, root_path: str) -> Dict[str, Any]:
        ws_id = str(uuid.uuid4())
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path)
                   VALUES (?, ?, ?);""",
                (ws_id, name, root_path),
            )
            conn.execute(
                """INSERT INTO Watcher_Config (workspace_id, is_enabled, debounce_ms)
                   VALUES (?, 1, 500);""",
                (ws_id,),
            )
        return self.get_by_id(ws_id)

    def get_by_id(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Workspace_Meta WHERE workspace_id = ?;", (workspace_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def list_all(self) -> List[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Workspace_Meta ORDER BY created_at DESC;")
        return [dict(row) for row in cursor.fetchall()]

    def delete(self, workspace_id: str) -> bool:
        """Deletes workspace from SQLite. Foreign keys ON DELETE CASCADE handles child tables."""
        with self.db_mgr.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Workspace_Meta WHERE workspace_id = ?;", (workspace_id,))
            return cursor.rowcount > 0
