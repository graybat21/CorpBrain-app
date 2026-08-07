import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from src.backend.utils.security import decrypt_secret, encrypt_secret


class ConfigManager:
    DEFAULT_CONFIG = {
        "llm_mode": "Option B",  # Option A (Cloud) / Option B (Local)
        "watcher_mode": "realtime",
        "llm_timeout_connect": 10,
        "llm_timeout_read": 120,
        "embedding_timeout": 30,
        "health_timeout": 5,
        "encrypted_api_key": "",
        "cloud_price_per_file": 0.005,
        "cloud_price_updated_at": "2026-08-01T00:00:00Z",
    }

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
            base_dir = Path(local_app_data) / "CorpBrain"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = str(base_dir / "config.json")
        else:
            self.config_path = config_path
            Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)

        self._config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            self._config_data = dict(self.DEFAULT_CONFIG)
            self.save_config()
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with default to handle new keys
                    self._config_data = dict(self.DEFAULT_CONFIG)
                    self._config_data.update(loaded)
            except Exception:
                self._config_data = dict(self.DEFAULT_CONFIG)
                self.save_config()
        return self._config_data

    def save_config(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config_data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config_data.get(key, default)

    def set(self, key: str, value: Any):
        self._config_data[key] = value
        self.save_config()

    def set_api_key(self, api_key: str):
        if api_key:
            encrypted = encrypt_secret(api_key)
            self.set("encrypted_api_key", encrypted)
        else:
            self.set("encrypted_api_key", "")

    def get_api_key(self) -> str:
        encrypted = self.get("encrypted_api_key", "")
        if not encrypted:
            return ""
        return decrypt_secret(encrypted)

    def is_api_key_configured(self) -> bool:
        return bool(self.get("encrypted_api_key", ""))

    def export_config(self) -> str:
        """Export config as JSON string excluding sensitive decrypted data."""
        export_data = dict(self._config_data)
        # Exclude actual raw keys
        return json.dumps(export_data, indent=2, ensure_ascii=False)

    def import_config(self, json_str: str):
        """Import config JSON string (REQ-NF-015)."""
        imported = json.loads(json_str)
        self._config_data.update(imported)
        self.save_config()
