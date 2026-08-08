import json
import logging
import os
from typing import Any, Dict, FrozenSet, Optional
from urllib.parse import urlparse

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


def _silent_unlink(path: str) -> None:
    """
    Delete a partial download, tolerating its absence.

    A failed download must not leave a truncated installer on disk that a later step could
    execute. This is a cleanup path, so a missing file is the expected case, not an error —
    but the failure is logged rather than swallowed (CLAUDE.md: no bare except).
    """
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("[NetworkGuard] Could not remove partial download", exc_info=True)


class EgressBlockedError(Exception):
    """Raised when an egress network request targets a host outside the allowed whitelist for a given purpose."""
    pass


class UpstreamUnavailableError(Exception):
    """
    The whitelisted host could not be reached, or the connection/read timed out.

    DEC-16 classifies this as a *transient* failure: it is one of the conditions
    LLMResilienceService may retry with backoff.
    """
    pass


class UpstreamStatusError(Exception):
    """
    The whitelisted host answered with a non-2xx status.

    Carries ``status_code`` so the caller can apply DEC-16's retry rule without re-parsing a
    message string: 429 and 5xx are transient, everything else (401, 400, ...) is not and
    must never be retried. ``retry_after`` carries the header value when the server sent one.

    The response body is deliberately NOT attached — an upstream error body can echo back the
    prompt that produced it, and DEC-14/DEC-15 forbid that reaching a log or an error response.
    """

    def __init__(self, status_code: int, purpose: str, retry_after: Optional[str] = None):
        super().__init__(f"Upstream returned HTTP {status_code} for purpose '{purpose}'")
        self.status_code = status_code
        self.purpose = purpose
        self.retry_after = retry_after


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
        """
        Issue an HTTP request only after strict NetworkGuard validation.

        Requires httpx. The previous stdlib fallback here silently discarded **kwargs, so a
        caller passing `json=`/`headers=`/`timeout=` got a request that dropped its body and
        blocked forever — a lie that would surface as a mysterious upstream error rather than
        a bug here. It has no callers, so it now fails loudly instead. Use `get_json` /
        `post_json` for the small-JSON cases; those work without httpx.
        """
        cls.validate_egress(purpose, url)
        if not HAS_HTTPX:
            raise NotImplementedError(
                "NetworkGuard.request requires httpx (see requirements.txt). "
                "For small JSON payloads use get_json/post_json, which use the stdlib."
            )
        return httpx.request(method, url, **kwargs)

    @classmethod
    def is_reachable(cls, purpose: str, url: str, timeout: float = 5.0) -> bool:
        """
        Whitelist-validated HEAD probe — "can I reach this host right now?" (DEC-13).

        This is the pre-check that decides `assisted` vs `detect_only`. It returns a bool
        rather than raising for an unreachable host because unreachability is the *expected*
        answer on a closed network (A1's default environment), not an error condition.

        An `EgressBlockedError` from validation still propagates: a whitelist violation is a
        programming error and must not be reported as "the network is down", which would
        silently downgrade a blocked request into `detect_only`.

        Some hosts reject HEAD with 405 while serving GET fine. A status response of any kind
        still proves reachability, which is the only question being asked, so any HTTP answer
        counts as True — including an error status.
        """
        cls.validate_egress(purpose, url)

        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "CorpBrain"})
            with urllib.request.urlopen(req, timeout=timeout):
                return True
        except urllib.error.HTTPError:
            # The host answered, just not with 2xx. Reachable.
            return True
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.info(
                f"[NetworkGuard] Host not reachable for purpose '{purpose}': {type(e).__name__}"
            )
            return False

    @classmethod
    def download_to_file(
        cls,
        purpose: str,
        url: str,
        dest_path: str,
        timeout: float = 30.0,
        progress_cb: Optional[Any] = None,
    ) -> int:
        """
        Whitelist-validated streaming download to a local file (DEC-15).

        Used for the Ollama installer (`purpose='provisioning'`). Streams in chunks rather than
        reading into memory: the installer is hundreds of MB and a `resp.read()` would hold all
        of it resident on a 16GB office PC (CON-05).

        **Redirects are re-validated.** urllib follows them transparently, so a whitelisted
        host redirecting to an arbitrary one would smuggle egress past the gate — the exact
        hole DEC-15 exists to close. The final URL is checked against the same whitelist after
        the fact, and a mismatch deletes the partial file and raises `EgressBlockedError`.

        `progress_cb(downloaded_bytes, total_bytes_or_None)` is invoked per chunk so the caller
        can persist DEC-04 progress. Exceptions from it are not caught — a broken callback
        should surface, not corrupt a download silently.

        Returns the number of bytes written.

        Raises:
            EgressBlockedError: initial or post-redirect host not whitelisted.
            UpstreamStatusError: non-2xx response.
            UpstreamUnavailableError: unreachable or timed out.
        """
        cls.validate_egress(purpose, url)

        chunk_size = 1024 * 256
        downloaded = 0
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CorpBrain"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                if not (200 <= status < 300):
                    raise UpstreamStatusError(status, purpose)

                # geturl() is the URL after every redirect hop. Validating it is what makes
                # the whitelist hold for a redirect chain.
                cls.validate_egress(purpose, resp.geturl())

                total_header = resp.headers.get("Content-Length") if resp.headers else None
                total = int(total_header) if total_header and total_header.isdigit() else None

                with open(dest_path, "wb") as out:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        out.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb is not None:
                            progress_cb(downloaded, total)
        except EgressBlockedError:
            # A redirect left the whitelist. The partial file is deleted so a later step
            # cannot execute a binary that came from an unvetted host.
            _silent_unlink(dest_path)
            raise
        except urllib.error.HTTPError as e:
            _silent_unlink(dest_path)
            logger.warning(f"[NetworkGuard] Upstream HTTP {e.code} for purpose '{purpose}'")
            raise UpstreamStatusError(e.code, purpose) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _silent_unlink(dest_path)
            logger.info(f"[NetworkGuard] Unreachable host for purpose '{purpose}': {type(e).__name__}")
            raise UpstreamUnavailableError(
                f"Upstream unavailable for purpose '{purpose}': {type(e).__name__}"
            ) from None

        return downloaded

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

    @classmethod
    def post_json(cls, purpose: str, url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        """
        Validated JSON POST helper (DEC-15).

        Unlike `get_json`, this RAISES instead of returning None. The difference is
        deliberate: `get_json` covers health probes where "no answer" is a legitimate answer
        ("Ollama isn't running"), whereas a POST is a real operation whose failure the caller
        must be able to classify. DEC-16 requires distinguishing retryable from
        non-retryable, and a bare None cannot carry a status code.

        `timeout` is required — no default. Timeout values live in App_Config
        (`llm_timeout_*`) and DEC-16 forbids hardcoding them, so a default here would just be
        a hardcoded value hiding one call away from the rule.

        Raises:
            EgressBlockedError: host/purpose pair not whitelisted; NO request is issued.
            UpstreamUnavailableError: unreachable or timed out (transient, DEC-16).
            UpstreamStatusError: non-2xx response; inspect `.status_code` to classify.
            ValueError: 2xx response whose body is not valid JSON.
        """
        cls.validate_egress(purpose, url)

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "CorpBrain"},
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            # HTTPError is a subclass of URLError, so it must be caught first. `from None`
            # on every re-raise below: the chained original carries the full URL (query
            # string included) into the traceback, and DEC-15 permits logging host+purpose
            # only. Never read e.read() — an error body can echo the prompt (DEC-14).
            retry_after = None
            try:
                retry_after = e.headers.get("Retry-After") if e.headers else None
            except AttributeError:
                retry_after = None
            logger.warning(f"[NetworkGuard] Upstream HTTP {e.code} for purpose '{purpose}'")
            raise UpstreamStatusError(e.code, purpose, retry_after) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.info(f"[NetworkGuard] Unreachable host for purpose '{purpose}': {type(e).__name__}")
            raise UpstreamUnavailableError(
                f"Upstream unavailable for purpose '{purpose}': {type(e).__name__}"
            ) from None

        if not (200 <= status < 300):
            logger.warning(f"[NetworkGuard] Unexpected status {status} for purpose '{purpose}'")
            raise UpstreamStatusError(status, purpose)

        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"[NetworkGuard] Malformed JSON response for purpose '{purpose}': {type(e).__name__}")
            raise ValueError(f"Malformed JSON response for purpose '{purpose}'") from None
