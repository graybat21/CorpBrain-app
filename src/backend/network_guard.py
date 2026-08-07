import logging
from urllib.parse import urlparse
from typing import Any, Dict, FrozenSet, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
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
