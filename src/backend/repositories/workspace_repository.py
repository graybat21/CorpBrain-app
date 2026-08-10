import uuid
from typing import Any, Dict, List, Optional

from src.backend.db import DatabaseManager


class WorkspaceRepository:
    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr

    def create(self, name: str, root_paths: List[str]) -> Dict[str, Any]:
        """
        Insert one Workspace_Meta row plus one Workspace_Root row per folder (issue #105).

        Every root is written inside the same transaction as the parent row: a workspace that
        committed with only some of its folders would scan a subset and report success, which
        is the failure mode this issue exists to remove.
        """
        # A bare string is rejected rather than wrapped: `enumerate("/tmp/a")` yields one row
        # per character, and every row after the first collides on
        # UNIQUE(workspace_id, root_path) — a confusing IntegrityError far from the mistake.
        if isinstance(root_paths, str):
            raise TypeError("root_paths must be a list of paths, not a single string")
        if not root_paths:
            raise ValueError("At least one root path is required")

        ws_id = str(uuid.uuid4())
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """INSERT INTO Workspace_Meta (workspace_id, workspace_name)
                   VALUES (?, ?);""",
                (ws_id, name),
            )
            for order, path in enumerate(root_paths):
                conn.execute(
                    """INSERT INTO Workspace_Root (root_id, workspace_id, root_path, sort_order)
                       VALUES (?, ?, ?, ?);""",
                    (str(uuid.uuid4()), ws_id, path, order),
                )
            conn.execute(
                """INSERT INTO Watcher_Config (workspace_id, is_enabled, debounce_ms)
                   VALUES (?, 1, 500);""",
                (ws_id,),
            )
        return self.get_by_id(ws_id)

    def list_roots(self, workspace_id: str) -> List[str]:
        """Root folders of one workspace, in the order the user selected them."""
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT root_path FROM Workspace_Root
               WHERE workspace_id = ? ORDER BY sort_order ASC, created_at ASC;""",
            (workspace_id,),
        )
        return [row["root_path"] for row in cursor.fetchall()]

    def get_by_id(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Workspace_Meta WHERE workspace_id = ?;", (workspace_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._with_roots(dict(row))

    def list_all(self) -> List[Dict[str, Any]]:
        """
        Every workspace with its roots attached.

        One query per workspace for the roots would be N+1; a single JOIN keeps the sidebar
        listing at two statements regardless of how many workspaces exist.
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        # `rowid DESC` as the tiebreaker (issue #66): `created_at` uses `strftime('%f')`, which is
        # millisecond resolution, so two workspaces created in the same millisecond had no defined
        # order — the sidebar list could reshuffle between two identical requests, which reads as
        # data changing on its own. rowid is monotonic per insert, so it breaks the tie in true
        # creation order rather than arbitrarily.
        cursor.execute("SELECT * FROM Workspace_Meta ORDER BY created_at DESC, rowid DESC;")
        workspaces = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """SELECT workspace_id, root_path FROM Workspace_Root
               ORDER BY workspace_id, sort_order ASC, created_at ASC;"""
        )
        roots_by_ws: Dict[str, List[str]] = {}
        for row in cursor.fetchall():
            roots_by_ws.setdefault(row["workspace_id"], []).append(row["root_path"])

        for ws in workspaces:
            ws["root_paths"] = roots_by_ws.get(ws["workspace_id"], [])
        return workspaces

    def _with_roots(self, ws: Dict[str, Any]) -> Dict[str, Any]:
        ws["root_paths"] = self.list_roots(ws["workspace_id"])
        return ws

    def delete(self, workspace_id: str) -> bool:
        """Deletes workspace from SQLite. Foreign keys ON DELETE CASCADE handles child tables."""
        with self.db_mgr.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Workspace_Meta WHERE workspace_id = ?;", (workspace_id,))
            return cursor.rowcount > 0
