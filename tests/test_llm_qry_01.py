import os
import sys
import tempfile
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src.backend.config_manager import DEV_API_KEY_ENV, ConfigManager
from src.backend.db import DatabaseManager
from src.backend.network_guard import EgressBlockedError, NetworkGuard
from src.backend.services.query_services import LlmQueryService


@pytest.fixture
def llm_qry_setup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "llm_qry_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        config_mgr = ConfigManager(db_mgr)

        service = LlmQueryService(db_mgr)
        yield service, config_mgr, db_mgr
        db_mgr.close()


def _configure_api_key(config_mgr, monkeypatch, key: str = "sk-ant-test-key-12345") -> None:
    """
    Put the config into "a key is available" state on whichever host is running.

    These tests are about health-check *logic* (which flags and error codes come back), not
    about how the key is stored — DEC-12 storage itself is covered in test_inf_cmd_02.py and
    test_llm_cmd_01.py. On Windows the real DPAPI path runs; elsewhere the dev environment
    variable supplies it, since `set_api_key` correctly refuses to persist without DPAPI.
    """
    if sys.platform == "win32":
        config_mgr.set_api_key(key)
    else:
        monkeypatch.setenv(DEV_API_KEY_ENV, key)


def _mock_tags_response(body: bytes):
    """Build a urlopen context-manager mock returning the given /api/tags body."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


# Ollama reporting both required models present (DEC-13).
BOTH_MODELS = b'{"models": [{"name": "nomic-embed-text:latest"}, {"name": "qwen2.5:7b-instruct"}]}'
# Daemon alive but holding an unrelated model only.
NO_REQUIRED_MODELS = b'{"models": [{"name": "llama3:latest"}]}'

# Connection refused, as urllib actually reports it when the daemon is down.
DAEMON_DOWN = urllib.error.URLError("Connection refused")


def test_service_defaults_to_real_network_guard(llm_qry_setup):
    """DEC-15: the validated egress path must be what runs in production, not an opt-in."""
    service, _, _ = llm_qry_setup
    assert service.network_guard is NetworkGuard


def test_scenario_1_option_a_health_check(llm_qry_setup, monkeypatch):
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option A")
    # The dev-host fallback reads this env var, so a real key in the developer's shell would
    # otherwise make the "not configured" half of this test pass for the wrong reason.
    monkeypatch.delenv(DEV_API_KEY_ENV, raising=False)

    with patch("urllib.request.urlopen", return_value=_mock_tags_response(BOTH_MODELS)):
        # API key not set
        res1 = service.check_health()
        assert res1["mode"] == "Option A"
        assert res1["api_key_configured"] is False
        assert res1["status_ok"] is False
        assert res1["error_code"] == "API_KEY_NOT_CONFIGURED"

        # API key set
        _configure_api_key(config_mgr, monkeypatch)
        res2 = service.check_health()
        assert res2["api_key_configured"] is True
        assert res2["status_ok"] is True
        assert res2["error_code"] is None


def test_scenario_2_option_b_daemon_offline(llm_qry_setup):
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option B")

    with patch("urllib.request.urlopen", side_effect=DAEMON_DOWN):
        res = service.check_health()
        assert res["mode"] == "Option B"
        assert res["daemon_online"] is False
        assert res["status_ok"] is False
        assert res["error_code"] == "LLM_UNAVAILABLE"


def test_scenario_3_option_b_daemon_online_models_missing(llm_qry_setup):
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option B")

    with patch("urllib.request.urlopen", return_value=_mock_tags_response(NO_REQUIRED_MODELS)):
        res = service.check_health()
        assert res["mode"] == "Option B"
        assert res["daemon_online"] is True
        assert res["embedding_model_ready"] is False
        assert res["generation_model_ready"] is False
        assert res["status_ok"] is False
        assert res["error_code"] == "LLM_PROVISION_REQUIRED"


def test_scenario_4_option_b_all_ready(llm_qry_setup):
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option B")

    with patch("urllib.request.urlopen", return_value=_mock_tags_response(BOTH_MODELS)):
        res = service.check_health()
        assert res["mode"] == "Option B"
        assert res["daemon_online"] is True
        assert res["embedding_model_ready"] is True
        assert res["generation_model_ready"] is True
        assert res["status_ok"] is True
        assert res["error_code"] is None


def test_scenario_5_option_a_needs_embedding_model(llm_qry_setup, monkeypatch):
    """
    AC Scenario 3 (DEC-06 파급): Option A with a valid key but no local embedding model.

    Cloud generation is fine, but deep analysis is impossible because DEC-06 routes every
    embedding through local Ollama. The two facts must be reported separately so the user
    learns this before starting an analysis, not during it.
    """
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option A")
    _configure_api_key(config_mgr, monkeypatch)

    with patch("urllib.request.urlopen", side_effect=DAEMON_DOWN):
        res = service.check_health()
        assert res["mode"] == "Option A"
        assert res["api_key_configured"] is True
        assert res["daemon_online"] is False
        assert res["embedding_model_ready"] is False
        # The cloud engine itself is usable...
        assert res["status_ok"] is True
        # ...but provisioning is still required for deep analysis.
        assert res["error_code"] == "LLM_PROVISION_REQUIRED"


def test_health_check_uses_loopback_purpose_only(llm_qry_setup):
    """
    DEC-15: the tag probe must be tagged purpose='llm_local' against 127.0.0.1.
    Recording the guard calls proves the request is actually routed through validation
    rather than issued directly by the service.
    """
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option B")

    calls = []

    class RecordingGuard:
        @staticmethod
        def get_json(purpose, url, timeout=5.0):
            calls.append((purpose, url))
            return {"models": []}

        @staticmethod
        def validate_egress(purpose, url):
            calls.append((purpose, url))
            return url

    service.network_guard = RecordingGuard
    service.check_health()

    assert calls == [("llm_local", LlmQueryService.OLLAMA_TAGS_URL)]


def test_option_a_validates_cloud_purpose(llm_qry_setup):
    """DEC-15: Option A must additionally validate purpose='llm_cloud' -> api.anthropic.com."""
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option A")

    calls = []

    class RecordingGuard:
        @staticmethod
        def get_json(purpose, url, timeout=5.0):
            calls.append((purpose, url))
            return {"models": []}

        @staticmethod
        def validate_egress(purpose, url):
            calls.append((purpose, url))
            return url

    service.network_guard = RecordingGuard
    service.check_health()

    assert ("llm_cloud", "https://api.anthropic.com") in calls
    # Real NetworkGuard must accept that exact pair.
    assert NetworkGuard.validate_egress("llm_cloud", "https://api.anthropic.com") == "api.anthropic.com"


def test_egress_violation_is_not_swallowed(llm_qry_setup):
    """
    DEC-16: EgressBlockedError must never be retried or absorbed into a "daemon offline"
    result — a whitelist violation is a programming error, not a transient condition.
    """
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option B")

    class BlockingGuard:
        @staticmethod
        def get_json(purpose, url, timeout=5.0):
            raise EgressBlockedError("Egress blocked: host 'evil.example' not allowed")

        @staticmethod
        def validate_egress(purpose, url):
            return url

    service.network_guard = BlockingGuard

    with pytest.raises(EgressBlockedError):
        service.check_health()


def test_health_timeout_comes_from_app_config(llm_qry_setup):
    """DEC-16: timeouts are read from App_Config, never hardcoded."""
    service, config_mgr, db_mgr = llm_qry_setup
    config_mgr.set("llm_mode", "Option B")
    config_mgr.set("llm_health_timeout", "12")

    seen = {}

    class TimeoutRecordingGuard:
        @staticmethod
        def get_json(purpose, url, timeout=5.0):
            seen["timeout"] = timeout
            return {"models": []}

        @staticmethod
        def validate_egress(purpose, url):
            return url

    service.network_guard = TimeoutRecordingGuard
    service.check_health()

    assert seen["timeout"] == 12.0
