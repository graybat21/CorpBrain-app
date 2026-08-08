import os
import sys
import tempfile

import pytest

from src.backend.config_manager import DEV_API_KEY_ENV, ConfigManager
from src.backend.utils.security import SecretStorageUnavailableError

# API key storage is Windows DPAPI (DEC-12) and has no cross-platform equivalent. The
# round-trip assertions therefore only mean something on Windows, which is what CI runs. Off
# Windows the requirement is the *refusal*, tested separately below — a base64 fallback that
# let these pass everywhere is exactly what used to write a recoverable key to disk.
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only (DEC-12)")


def test_config_export_import_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path1 = os.path.join(tmpdir, "config1.json")
        cfg_path2 = os.path.join(tmpdir, "config2.json")

        cm1 = ConfigManager(config_path=cfg_path1)
        cm1.set("llm_mode", "Option B")
        cm1.set("watcher_mode", "realtime")

        exported_json = cm1.export_config()

        cm2 = ConfigManager(config_path=cfg_path2)
        cm2.import_config(exported_json)

        assert cm2.get("llm_mode") == "Option B"
        assert cm2.get("watcher_mode") == "realtime"

        cm1.close()
        cm2.close()


def test_config_export_never_carries_the_key_material():
    """
    DEC-12: exported config exposes `api_key_configured` only — never the key or its blob.

    Asserted on every host because it is a property of the export format, not of DPAPI.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))
        exported = cm.export_config()

        assert "api_key_encrypted" not in exported
        assert "api_key_configured" in exported

        cm.close()


@windows_only
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


@windows_only
def test_dpapi_api_key_survives_export_import_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        cm1 = ConfigManager(config_path=os.path.join(tmpdir, "config1.json"))
        cm1.set_api_key("sk-ant-testkey12345")
        exported_json = cm1.export_config()

        cm2 = ConfigManager(config_path=os.path.join(tmpdir, "config2.json"))
        cm2.import_config(exported_json)

        # The blob is not in the export (see test above), so the imported config must NOT
        # claim a key is configured. Import carrying a key across accounts would also break
        # DPAPI's user binding.
        assert cm2.is_api_key_configured() is False

        cm1.close()
        cm2.close()


@pytest.mark.skipif(sys.platform == "win32", reason="asserts the no-DPAPI host behaviour")
def test_storing_a_key_is_refused_without_dpapi(monkeypatch):
    """
    A host without DPAPI must refuse to persist, not silently store something reversible.

    This is the regression guard for the removed `MOCK_ENC:<base64>` fallback: it satisfied
    the round-trip assertion above while leaving the key recoverable from the DB file.
    """
    monkeypatch.delenv(DEV_API_KEY_ENV, raising=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))

        with pytest.raises(SecretStorageUnavailableError):
            cm.set_api_key("sk-ant-should-never-be-written")

        assert cm.get("api_key_encrypted") == ""
        assert cm.is_api_key_configured() is False

        cm.close()


@pytest.mark.skipif(sys.platform == "win32", reason="asserts the no-DPAPI host behaviour")
def test_clearing_a_key_is_allowed_without_dpapi():
    """Clearing writes no secret, so it must work everywhere."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))
        cm.set_api_key("")  # must not raise
        assert cm.get("api_key_encrypted") == ""
        cm.close()


@pytest.mark.skipif(sys.platform == "win32", reason="dev-host env fallback only")
def test_dev_env_key_is_read_but_never_persisted(monkeypatch):
    monkeypatch.setenv(DEV_API_KEY_ENV, "sk-ant-from-env")
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))

        assert cm.get_api_key() == "sk-ant-from-env"
        assert cm.is_api_key_configured() is True
        # The env key must leave no trace in the database.
        assert cm.get("api_key_encrypted") == ""

        cm.close()


def test_auto_creation_missing_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "nested", "config.json")

        cm = ConfigManager(config_path=cfg_path)
        assert cm.get("llm_mode") == "Option A"
        cm.close()
