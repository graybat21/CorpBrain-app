import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.backend.network_guard import (
    EgressBlockedError,
    NetworkGuard,
    UpstreamStatusError,
    UpstreamUnavailableError,
)


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


# --------------------------------------------------------------------------------------
# post_json (DEC-15 / DEC-16)
#
# 127.0.0.1 is a whitelisted host for purpose 'llm_local', so a throwaway stdlib HTTP
# server on an OS-assigned port lets these exercise the real urllib transport, real
# status handling and real JSON decoding. No transport is mocked; the only thing standing
# in for Ollama is the response body.
# --------------------------------------------------------------------------------------

class _StubHandler(BaseHTTPRequestHandler):
    """Echoes back a scripted status/body. `script` is set on the server instance."""

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler's required name
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        self.server.received.append({
            "path": self.path,
            "content_type": self.headers.get("Content-Type"),
            "body": raw.decode("utf-8"),
        })

        status, body, extra_headers = self.server.script
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for key, value in extra_headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # keep pytest output clean


@pytest.fixture
def stub_server():
    """Yields (base_url, server). Set `server.script = (status, body, headers)` per test."""
    server = HTTPServer(("127.0.0.1", 0), _StubHandler)
    server.script = (200, "{}", {})
    server.received = []

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_post_json_sends_json_body_and_returns_decoded_response(stub_server):
    base_url, server = stub_server
    server.script = (200, json.dumps({"embedding": [0.1, 0.2, 0.3]}), {})

    result = NetworkGuard.post_json(
        "llm_local", f"{base_url}/api/embeddings", {"model": "nomic-embed-text", "prompt": "hi"}, timeout=5.0
    )

    assert result == {"embedding": [0.1, 0.2, 0.3]}
    assert len(server.received) == 1
    assert server.received[0]["content_type"] == "application/json"
    assert json.loads(server.received[0]["body"]) == {"model": "nomic-embed-text", "prompt": "hi"}


def test_post_json_blocks_wrong_purpose_destination_pair_without_issuing_a_request(stub_server):
    """
    DEC-15: a mismatched (purpose, destination) pair must block BEFORE any bytes leave.

    The stub server is pointed at with a purpose it is not whitelisted for; the assertion
    that matters is `server.received == []` — that no request was issued, not merely that
    an exception was raised after one was.
    """
    base_url, server = stub_server

    with pytest.raises(EgressBlockedError):
        NetworkGuard.post_json("llm_cloud", f"{base_url}/v1/messages", {"prompt": "secret"}, timeout=5.0)
    with pytest.raises(EgressBlockedError):
        NetworkGuard.post_json("provisioning", f"{base_url}/install", {"prompt": "secret"}, timeout=5.0)

    assert server.received == []

    # Exact host matching: a suffix that merely *contains* a whitelisted host is blocked.
    with pytest.raises(EgressBlockedError):
        NetworkGuard.post_json("llm_cloud", "https://api.anthropic.com.attacker.net/v1/messages", {}, timeout=5.0)


def test_post_json_non_transient_status_carries_code_for_dec16_classification(stub_server):
    """DEC-16: 401 must never be retried, so the caller needs the code, not a message string."""
    base_url, server = stub_server
    server.script = (401, json.dumps({"error": "invalid api key"}), {})

    with pytest.raises(UpstreamStatusError) as exc_info:
        NetworkGuard.post_json("llm_local", f"{base_url}/api/embeddings", {"prompt": "hi"}, timeout=5.0)

    assert exc_info.value.status_code == 401
    assert exc_info.value.purpose == "llm_local"


def test_post_json_transient_status_exposes_retry_after(stub_server):
    """DEC-16: 429 is retryable and `retry-after` must be honoured when present."""
    base_url, server = stub_server
    server.script = (429, json.dumps({"error": "slow down"}), {"Retry-After": "7"})

    with pytest.raises(UpstreamStatusError) as exc_info:
        NetworkGuard.post_json("llm_local", f"{base_url}/api/embeddings", {"prompt": "hi"}, timeout=5.0)

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == "7"


def test_post_json_error_never_leaks_the_response_body(stub_server):
    """
    DEC-14/DEC-15: an upstream error body can echo the prompt that produced it.

    post_json deliberately never calls e.read(), so the prompt must not appear anywhere in
    the raised exception — neither in its message nor in a chained cause's traceback.
    """
    base_url, server = stub_server
    secret = "hong-gildong-010-1234-5678"
    server.script = (400, json.dumps({"error": f"bad prompt: {secret}"}), {})

    with pytest.raises(UpstreamStatusError) as exc_info:
        NetworkGuard.post_json("llm_local", f"{base_url}/api/embeddings", {"prompt": secret}, timeout=5.0)

    assert secret not in str(exc_info.value)
    # `from None` must have broken the chain — a chained HTTPError would carry the URL and
    # the readable error body along with it.
    assert exc_info.value.__cause__ is None


def test_post_json_malformed_json_raises_value_error(stub_server):
    base_url, server = stub_server
    server.script = (200, "not json at all", {})

    with pytest.raises(ValueError):
        NetworkGuard.post_json("llm_local", f"{base_url}/api/embeddings", {"prompt": "hi"}, timeout=5.0)


def test_post_json_unreachable_port_raises_transient():
    # Port 1 on loopback: whitelisted host, nothing listening.
    with pytest.raises(UpstreamUnavailableError):
        NetworkGuard.post_json("llm_local", "http://127.0.0.1:1/api/embeddings", {"a": 1}, timeout=1.0)


def test_request_fallback_fails_loudly_without_httpx(monkeypatch):
    """It used to silently drop **kwargs, sending a request that was not the one requested."""
    import src.backend.network_guard as guard_mod

    monkeypatch.setattr(guard_mod, "HAS_HTTPX", False)
    with pytest.raises(NotImplementedError):
        guard_mod.NetworkGuard.request("llm_local", "POST", "http://127.0.0.1:11434/api/embeddings", json={"a": 1})
