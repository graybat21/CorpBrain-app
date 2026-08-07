import os
import tempfile

from src.backend.config_manager import ConfigManager


def test_config_export_import_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path1 = os.path.join(tmpdir, "config1.json")
        cfg_path2 = os.path.join(tmpdir, "config2.json")

        cm1 = ConfigManager(config_path=cfg_path1)
        cm1.set("llm_mode", "Option B")
        cm1.set("watcher_mode", "realtime")
        cm1.set_api_key("sk-ant-testkey12345")

        exported_json = cm1.export_config()

        cm2 = ConfigManager(config_path=cfg_path2)
        cm2.import_config(exported_json)

        assert cm2.get("llm_mode") == "Option B"
        assert cm2.get("watcher_mode") == "realtime"
        assert cm2.is_api_key_configured() is True
        assert cm2.get_api_key() == "sk-ant-testkey12345"

        cm1.close()
        cm2.close()


def test_dpapi_secret_encryption():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config_dpapi.json")
        cm = ConfigManager(config_path=cfg_path)

        assert cm.is_api_key_configured() is False
        assert cm.get_api_key() == ""

        raw_key = "secret_api_key_value_999"
        cm.set_api_key(raw_key)

        assert cm.is_api_key_configured() is True
        assert cm.get_api_key() == raw_key

        cm.close()


def test_auto_creation_missing_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "nested", "config.json")

        cm = ConfigManager(config_path=cfg_path)
        assert cm.get("llm_mode") == "Option A"
        cm.close()
