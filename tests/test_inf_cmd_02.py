import os
import sys
import tempfile
from contextlib import contextmanager

import pytest

from src.backend.config_manager import DEV_API_KEY_ENV, ConfigManager
from src.backend.utils.security import SecretStorageUnavailableError

# API key storage is Windows DPAPI (DEC-12) and has no cross-platform equivalent. The
# round-trip assertions therefore only mean something on Windows, which is what CI runs. Off
# Windows the requirement is the *refusal*, tested separately below — a base64 fallback that
# let these pass everywhere is exactly what used to write a recoverable key to disk.
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only (DEC-12)")


@contextmanager
def config_in_temp_dir():
    """
    A ConfigManager on its own database, closed even if the test body fails.

    `close()` in a trailing statement is skipped when an assertion raises, and on Windows the
    still-open sqlite handle then makes TemporaryDirectory teardown fail with
    `PermissionError: [WinError 32]`. That buries the real assertion error under a cleanup
    traceback — which is exactly how the first CI run reported this file.

    Each manager gets a distinct directory on purpose: `ConfigManager(config_path=...)` uses
    only the *directory* of that path and always names the DB `corpbrain_meta.db`, so two
    filenames in one tmpdir are one shared database.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "config.json"))
        try:
            yield cm
        finally:
            cm.close()


@contextmanager
def two_separate_configs():
    """Two ConfigManagers backed by genuinely different databases. See config_in_temp_dir."""
    with config_in_temp_dir() as cm1, config_in_temp_dir() as cm2:
        assert cm1.db_mgr.db_path != cm2.db_mgr.db_path
        yield cm1, cm2


def test_config_export_import_roundtrip():
    with two_separate_configs() as (cm1, cm2):
        cm1.set("llm_mode", "Option B")
        cm1.set("watcher_mode", "realtime")

        # Asserted because the previous version of this test shared one database between the
        # two managers and passed without export/import doing anything — cm2 was simply reading
        # cm1's writes. Pinning the pre-import value is what tells an import from a coincidence.
        assert cm2.get("llm_mode") == "Option A"

        cm2.import_config(cm1.export_config())

        assert cm2.get("llm_mode") == "Option B"
        assert cm2.get("watcher_mode") == "realtime"


def test_config_export_never_carries_the_key_material():
    """
    DEC-12: exported config exposes `api_key_configured` only — never the key or its blob.

    Asserted on every host because it is a property of the export format, not of DPAPI.
    """
    with config_in_temp_dir() as cm:
        exported = cm.export_config()

        assert "api_key_encrypted" not in exported
        assert "api_key_configured" in exported


@windows_only
def test_dpapi_secret_encryption():
    with config_in_temp_dir() as cm:
        assert cm.is_api_key_configured() is False
        assert cm.get_api_key() == ""

        raw_key = "secret_api_key_value_999"
        cm.set_api_key(raw_key)

        assert cm.is_api_key_configured() is True
        assert cm.get_api_key() == raw_key


@windows_only
def test_exported_config_does_not_carry_the_key_to_another_install():
    """
    The key must not ride along in an exported config (DEC-12).

    `export_config` omits `api_key_encrypted` and `import_config` skips the derived
    `api_key_configured` flag, so a fresh install importing the config still has no key —
    which is also the only correct outcome, since a DPAPI blob is bound to the account that
    created it and would not decrypt elsewhere anyway.
    """
    with two_separate_configs() as (cm1, cm2):
        cm1.set_api_key("sk-ant-testkey12345")
        assert cm1.is_api_key_configured() is True

        cm2.import_config(cm1.export_config())

        assert cm2.is_api_key_configured() is False
        assert cm2.get("api_key_encrypted") == ""
        assert cm2.get_api_key() == ""


def test_exported_config_omits_the_key_column_across_installs():
    """
    Host-independent half of the test above: whatever is in `api_key_encrypted`, an export does
    not carry it to a second install. Asserted on every host because it is a property of the
    export format, and writing the column directly avoids needing DPAPI to produce a value.
    """
    with two_separate_configs() as (cm1, cm2):
        # Bypasses set_api_key deliberately: this is about the export format, not about
        # storage, so it must not depend on DPAPI being available.
        cm1.set("api_key_encrypted", "AQAAANCMnd8BFdERjHoAwE_Cl-sBAAAA-fake-blob")

        cm2.import_config(cm1.export_config())

        assert cm2.get("api_key_encrypted") == ""
        assert "fake-blob" not in cm1.export_config()


@pytest.mark.skipif(sys.platform == "win32", reason="asserts the no-DPAPI host behaviour")
def test_storing_a_key_is_refused_without_dpapi(monkeypatch):
    """
    A host without DPAPI must refuse to persist, not silently store something reversible.

    This is the regression guard for the removed `MOCK_ENC:<base64>` fallback: it satisfied
    the round-trip assertion above while leaving the key recoverable from the DB file.
    """
    monkeypatch.delenv(DEV_API_KEY_ENV, raising=False)
    with config_in_temp_dir() as cm:
        with pytest.raises(SecretStorageUnavailableError):
            cm.set_api_key("sk-ant-should-never-be-written")

        assert cm.get("api_key_encrypted") == ""
        assert cm.is_api_key_configured() is False


@pytest.mark.skipif(sys.platform == "win32", reason="asserts the no-DPAPI host behaviour")
def test_clearing_a_key_is_allowed_without_dpapi():
    """Clearing writes no secret, so it must work everywhere."""
    with config_in_temp_dir() as cm:
        cm.set_api_key("")  # must not raise
        assert cm.get("api_key_encrypted") == ""


@pytest.mark.skipif(sys.platform == "win32", reason="dev-host env fallback only")
def test_dev_env_key_is_read_but_never_persisted(monkeypatch):
    monkeypatch.setenv(DEV_API_KEY_ENV, "sk-ant-from-env")
    with config_in_temp_dir() as cm:
        assert cm.get_api_key() == "sk-ant-from-env"
        assert cm.is_api_key_configured() is True
        # The env key must leave no trace in the database.
        assert cm.get("api_key_encrypted") == ""


def test_auto_creation_missing_config():
    """The config directory is created on demand, including a missing intermediate level."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = ConfigManager(config_path=os.path.join(tmpdir, "nested", "config.json"))
        try:
            assert cm.get("llm_mode") == "Option A"
        finally:
            cm.close()
