import json
import logging
import os
from typing import Any, Dict, Optional

from src.backend.db import DatabaseManager
from src.backend.utils.security import decrypt_secret, encrypt_secret

logger = logging.getLogger("CorpBrain.ConfigManager")


class ConfigManager:
    DEFAULT_CONFIG = {
        "llm_mode": "Option A",
        "llm_cloud_model": "claude-sonnet-5",
        "cloud_price_input_per_mtok": "3.00",
        "cloud_price_output_per_mtok": "15.00",
        "cloud_price_updated_at": "2026-08-01T00:00:00Z",
        "llm_timeout_connect": "10",
        "llm_timeout_read": "120",
        "llm_timeout_embedding": "30",
        "llm_health_timeout": "5",
        "local_embedding_model": "nomic-embed-text",
        "local_generation_model": "qwen2.5:7b-instruct",
        "api_key_encrypted": "",
        # DEC-06: embedding identity of the vectors currently in ChromaDB. This is
        # deliberately NOT merged with `local_embedding_model` above even though the values
        # coincide today — the two keys answer different questions and can legitimately
        # diverge. `local_embedding_model` (DEC-13) is "which model should provisioning
        # pull?"; `embedding_model` is "which model produced the vectors already on disk?".
        # Changing the former must not silently reinterpret the latter, because mixing
        # dimensions in one collection is exactly what DEC-06 forbids.
        "embedding_model": "nomic-embed-text",
        "embedding_dim": "768",
        # "" | "pending" | "granted:<model>:<dim>" — consent state for re-embedding after an
        # embedding-identity change (DEC-06). Empty means no change has been detected.
        "embedding_reembed_consent": "",
    }

    def __init__(self, db_mgr: Optional[DatabaseManager] = None, config_path: Optional[str] = None):
        if db_mgr is None:
            if config_path:
                db_dir = os.path.dirname(config_path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                db_file = os.path.join(db_dir, "corpbrain_meta.db") if db_dir else "corpbrain_meta.db"
            else:
                db_file = None
            migrations_dir = os.path.join(os.path.dirname(__file__), "..", "..", "migrations")
            self.db_mgr = DatabaseManager(db_path=db_file, migrations_dir=migrations_dir)
            self._own_db = True
        else:
            self.db_mgr = db_mgr
            self._own_db = False
        self._init_defaults()

    def _init_defaults(self):
        """Initialize missing default keys in App_Config table (DEC-10 / DEC-16)."""
        with self.db_mgr.transaction() as conn:
            cursor = conn.cursor()
            for key, val in self.DEFAULT_CONFIG.items():
                cursor.execute("SELECT config_value FROM App_Config WHERE config_key = ?;", (key,))
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO App_Config (config_key, config_value) VALUES (?, ?);",
                        (key, str(val)),
                    )

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get config value from App_Config table."""
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT config_value FROM App_Config WHERE config_key = ?;", (key,))
        row = cursor.fetchone()
        if not row:
            return default
        return row["config_value"]

    def set(self, key: str, value: Any):
        """Set config value in App_Config table."""
        val_str = str(value)
        query = """
            INSERT INTO App_Config (config_key, config_value, updated_at)
            VALUES (?, ?, (strftime('%Y-%m-%dT%H:%M:%fZ','now')))
            ON CONFLICT(config_key) DO UPDATE SET
                config_value = excluded.config_value,
                updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'));
        """
        with self.db_mgr.transaction() as conn:
            conn.execute(query, (key, val_str))

    def set_api_key(self, api_key: str):
        """Encrypt API key using Windows DPAPI and store base64 blob (DEC-12)."""
        if not api_key:
            self.set("api_key_encrypted", "")
            return
        encrypted_blob = encrypt_secret(api_key)
        self.set("api_key_encrypted", encrypted_blob)

    def get_api_key(self) -> str:
        """
        Decrypt API key in-memory using Windows DPAPI (DEC-12).
        Returns empty string if decryption fails (e.g. transferred to another PC/account).
        """
        encrypted_blob = self.get("api_key_encrypted", "")
        if not encrypted_blob:
            return ""
        try:
            return decrypt_secret(encrypted_blob)
        except Exception as e:
            logger.warning(f"[ConfigManager] DPAPI decryption failed: {e}. Key re-entry required.")
            return ""

    def is_api_key_configured(self) -> bool:
        """Returns True if encrypted API key is present in DB (DEC-12)."""
        blob = self.get("api_key_encrypted", "")
        return bool(blob and blob.strip())

    def get_all(self) -> Dict[str, str]:
        """Get all config values excluding decrypted sensitive API key."""
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT config_key, config_value FROM App_Config;")
        rows = cursor.fetchall()
        result = {}
        for r in rows:
            if r["config_key"] == "api_key_encrypted":
                continue
            result[r["config_key"]] = r["config_value"]
        result["api_key_configured"] = str(self.is_api_key_configured())
        return result

    def close(self):
        if getattr(self, "_own_db", False) and self.db_mgr:
            self.db_mgr.close()

    def export_config(self) -> str:
        """Export all config keys as JSON string excluding sensitive decrypted key."""
        all_data = self.get_all()
        return json.dumps(all_data, ensure_ascii=False, indent=2)

    def import_config(self, json_str: str):
        """Import config key-values from JSON string (INF-CMD-02)."""
        data = json.loads(json_str)
        for k, v in data.items():
            if k == "api_key_configured":
                continue
            self.set(k, v)
