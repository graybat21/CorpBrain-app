import pytest

from src.backend.network_guard import EgressBlockedError, NetworkGuard


def test_scenario_1_allowed_destination_passes():
    host = NetworkGuard.validate_egress("llm_local", "http://127.0.0.1:11434/api/embeddings")
    assert host == "127.0.0.1"

    host_cloud = NetworkGuard.validate_egress("llm_cloud", "https://api.anthropic.com/v1/messages")
    assert host_cloud == "api.anthropic.com"


def test_scenario_2_subdomain_attacker_blocked():
    with pytest.raises(EgressBlockedError) as exc_info:
        NetworkGuard.validate_egress("llm_cloud", "https://api.anthropic.com.attacker.net/v1/messages")
    assert "Egress blocked" in str(exc_info.value)


def test_scenario_3_purpose_mismatch_blocked():
    # Calling Anthropic API with provisioning purpose should be blocked
    with pytest.raises(EgressBlockedError) as exc_info:
        NetworkGuard.validate_egress("provisioning", "https://api.anthropic.com/v1/messages")
    assert "Egress blocked" in str(exc_info.value)


def test_invalid_purpose_string_blocked():
    with pytest.raises(EgressBlockedError) as exc_info:
        NetworkGuard.validate_egress("unauthorized_purpose", "http://127.0.0.1:11434")
    assert "Invalid purpose" in str(exc_info.value)
