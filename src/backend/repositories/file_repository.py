import os
from typing import Any, Dict, List, Optional
from src.backend.db import DatabaseManager


class FileRepository:
    def __init__(self, db_mgr: DatabaseManager):
        self.db_mgr = db_mgr

    def bulk_upsert(self, file_records: List[Dict[str, Any]]):
        if not file_records:
            return

        query = """
            INSERT INTO File_Meta (
                file_id, workspace_id, current_path, original_path,
                file_name, extension, size_bytes, last_modified, parse_status, importance_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id, current_path) DO UPDATE SET
                file_name = excluded.file_name,
                extension = excluded.extension,
                size_bytes = excluded.size_bytes,
                last_modified = excluded.last_modified,
                parse_status = excluded.parse_status,
                importance_score = excluded.importance_score,
                updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        """

        with self.db_mgr.transaction() as conn:
            conn.executemany(
                query,
                [
                    (
                        r["file_id"],
                        r["workspace_id"],
                        r["current_path"],
                        r["original_path"],
                        r["file_name"],
                        r["extension"],
                        r["size_bytes"],
                        r["last_modified"],
                        r.get("parse_status", "pending"),
                        r.get("importance_score", 0),
                    )
                    for r in file_records
                ],
            )

    def list_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM File_Meta WHERE workspace_id = ? ORDER BY file_name ASC;", (workspace_id,))
        return [dict(row) for row in cursor.fetchall()]

    def update_path(self, workspace_id: str, file_id: str, new_path: str, new_filename: Optional[str] = None):
        """Update current_path (and optionally file_name) for an existing file_id (DEC-08)."""
        if new_filename is None:
            new_filename = os.path.basename(new_path)

        query = """
            UPDATE File_Meta
            SET current_path = ?,
                file_name = ?,
                updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            WHERE workspace_id = ? AND file_id = ?;
        """
        with self.db_mgr.transaction() as conn:
            conn.execute(query, (new_path, new_filename, workspace_id, file_id))
