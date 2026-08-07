import json
import logging
from urllib.parse import urlparse
from typing import Any, Dict, FrozenSet, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# urllib is imported unconditionally as the stdlib fallback transport.
# DEC-15: this module is the ONLY place allowed to import a network library.
import urllib.error
import urllib.request

logger = logging.getLogger("CorpBrain.NetworkGuard")


class EgressBlockedError(Exception):
    """Raised when an egress network request targets a host outside the allowed whitelist for a given purpose."""
    pass


class NetworkGuard:
    # Code constants - NEVER load from config/env (DEC-15)
    _ALLOWED: Dict[str, FrozenSet[str]] = {
        "llm_local": frozenset({"127.0.0.1", "localhost"}),
        "llm_cloud": frozenset({"api.anthropic.com"}),
        "provisioning": frozenset({"github.com", "objects.githubusercontent.com", "ollama.com"}),
    }

    @classmethod
    def validate_egress(cls, purpose: str, url: str) -> str:
        """Validate URL hostname against code-constant whitelist for purpose. Exact match only."""
        if purpose not in cls._ALLOWED:
            logger.warning(f"[NetworkGuard] Invalid egress purpose requested: '{purpose}'")
            raise EgressBlockedError(f"Invalid purpose: '{purpose}'")

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        allowed_hosts = cls._ALLOWED[purpose]
        if host not in allowed_hosts:
            logger.warning(f"[NetworkGuard] Blocked unauthorized egress attempt to host '{host}' with purpose '{purpose}'")
            raise EgressBlockedError(f"Egress blocked: host '{host}' not allowed for purpose '{purpose}'")

        return host

    @classmethod
    def request(cls, purpose: str, method: str, url: str, **kwargs) -> Any:
        """Issue HTTP request only after strict NetworkGuard validation."""
        cls.validate_egress(purpose, url)
        if HAS_HTTPX:
            return httpx.request(method, url, **kwargs)
        else:
            req = urllib.request.Request(url, method=method.upper())
            return urllib.request.urlopen(req)

    @classmethod
    def get_json(cls, purpose: str, url: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Validated JSON GET helper (DEC-15).

        Callers must never import a network library themselves, so this method exists to
        cover the common "read a small JSON document" case (e.g. Ollama's GET /api/tags).

        Returns the decoded object on HTTP 200, or None when the host is unreachable,
        answers with a non-200 status, or returns a body that is not valid JSON.
        An EgressBlockedError from validation is NOT swallowed — a whitelist violation is a
        programming error, not a transient network condition (DEC-16: never retry it either).
        """
        cls.validate_egress(purpose, url)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CorpBrain"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if getattr(resp, "status", None) != 200:
                    return None
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            # Never log the URL's query string or any body — host+purpose only (DEC-15).
            logger.info(f"[NetworkGuard] Unreachable host for purpose '{purpose}': {type(e).__name__}")
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"[NetworkGuard] Malformed JSON response for purpose '{purpose}': {type(e).__name__}")
            return None
