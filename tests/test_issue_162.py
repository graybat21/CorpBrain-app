"""
Regression for issue #162 — the SPA could make no API call because client.ts built request URLs
with `new URL(path, baseUrl)` where the shell injects baseUrl="/".

The WHATWG URL constructor requires an ABSOLUTE base; "/" is relative, so it threw
`TypeError: Failed to construct 'URL': Invalid base URL`, surfacing as a Toast on workspace
creation (and on every other call). The fix resolves the injected base against the page's own
`window.location.href` first, in the pure `src/frontend/api/urlBuilder.ts` module.

There is no JS test runner in this project (Vitest/jsdom were rejected — smoke checklist §1), so
this verifies through `node`, whose WHATWG URL is byte-for-byte the browser's:

  * `test_whatwg_url_semantics_*` run on ANY node (plain JS) and pin the behaviour the fix relies
    on — the buggy base throws, resolving against the location does not. These run in CI's backend
    job, which has a system node but no npm packages.
  * `test_the_real_urlBuilder_module_*` execute the ACTUAL `resolveApiUrl` from urlBuilder.ts via
    node's `--experimental-strip-types` (node >= 22.6). On an older node they skip rather than
    fail, so CI on a pre-22.6 runner still goes green while a 22.6+ host runs the real code.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
URL_BUILDER = REPO_ROOT / "src" / "frontend" / "api" / "urlBuilder.ts"
CLIENT_TS = REPO_ROOT / "src" / "frontend" / "api" / "client.ts"

NODE = shutil.which("node")

# The route the screenshot failed on, plus a param/query case so the whole builder is exercised.
LOCATION_HREF = "http://127.0.0.1:52341/#/dashboard"
EXPECTED_ORIGIN = "http://127.0.0.1:52341"


def _run_node(script: str, *args: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        entry = Path(tmp) / "probe.mjs"
        entry.write_text(script, encoding="utf-8")
        return subprocess.run(
            [NODE, str(entry), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",  # issue #145: never let the host codepage decode child output
            errors="replace",
            timeout=60,
        )


def _node_supports_strip_types() -> bool:
    if not NODE:
        return False
    out = subprocess.run(
        [NODE, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    if not m:
        return False
    major, minor = int(m.group(1)), int(m.group(2))
    return (major, minor) >= (22, 6)


pytestmark = pytest.mark.skipif(NODE is None, reason="node is required to exercise WHATWG URL")


# --- WHATWG semantics the fix depends on (portable, any node) ---------------------------------


def test_whatwg_url_semantics_the_buggy_base_throws():
    """`new URL(path, "/")` — exactly what client.ts used to do — throws in the WHATWG runtime."""
    result = _run_node(
        "try { new URL('api/v1/workspace', '/'); console.log('NO_THROW'); }\n"
        "catch (e) { console.log('THROW:' + e.constructor.name); }\n"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "THROW:TypeError", result.stdout


def test_whatwg_url_semantics_resolving_against_location_works():
    """Resolving "/" against the page href first — what the fix does — yields a valid absolute URL."""
    result = _run_node(
        "const href = process.argv[2];\n"
        "const base = new URL('/', href);\n"
        "console.log(new URL('api/v1/workspace', base).toString());\n",
        LOCATION_HREF,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{EXPECTED_ORIGIN}/api/v1/workspace"


# --- The actual urlBuilder.ts module, executed as real code (node >= 22.6) ---------------------


def _resolve_via_real_module(base_url: str, href: str, template: str, params=None, query=None):
    """Import the REAL resolveApiUrl from urlBuilder.ts under node and call it."""
    # A file:// URL, not a bare path — Windows ESM rejects `import ... from "C:/..."`.
    script = (
        f"import {{ resolveApiUrl }} from {json.dumps(URL_BUILDER.as_uri())};\n"
        "const [b, h, t, p, q] = process.argv.slice(2);\n"
        "try {\n"
        "  const out = resolveApiUrl(b, h, t, p ? JSON.parse(p) : undefined, q ? JSON.parse(q) : undefined);\n"
        "  console.log('OK:' + out);\n"
        "} catch (e) { console.log('THROW:' + e.constructor.name + ':' + e.message); }\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        entry = Path(tmp) / "probe.mts"  # .mts => ESM + type stripping
        entry.write_text(script, encoding="utf-8")
        args = [base_url, href, template, params or "", query or ""]
        return subprocess.run(
            [NODE, "--experimental-strip-types", str(entry), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )


@pytest.mark.skipif(not _node_supports_strip_types(), reason="needs node >= 22.6 for --experimental-strip-types")
def test_the_real_urlBuilder_module_handles_the_injected_slash_base():
    """The shipped `resolveApiUrl` turns baseUrl="/" into a valid absolute URL (the #162 fix)."""
    result = _resolve_via_real_module("/", LOCATION_HREF, "/api/v1/workspace")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"OK:{EXPECTED_ORIGIN}/api/v1/workspace", result.stdout


@pytest.mark.skipif(not _node_supports_strip_types(), reason="needs node >= 22.6 for --experimental-strip-types")
def test_the_real_urlBuilder_module_handles_an_absolute_base_and_params_and_query():
    """An absolute injected base, a path param, and a query all survive the real builder."""
    result = _resolve_via_real_module(
        "http://127.0.0.1:8000/",
        LOCATION_HREF,
        "/api/v1/workspace/{workspace_id}/file",
        json.dumps({"workspace_id": "ws 1/a"}),
        json.dumps({"limit": 10, "skip": ""}),
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip()
    assert out.startswith("OK:http://127.0.0.1:8000/api/v1/workspace/")
    assert "ws%201%2Fa/file" in out, out          # the param is percent-encoded
    assert "limit=10" in out and "skip=" not in out  # empty query values are dropped


# --- Tie the executable proof to the real source (comment-stripped, not a prose match) ---------


def _strip_ts_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)  # block comments
    src = re.sub(r"//[^\n]*", "", src)                     # line comments
    return src


def test_client_ts_resolves_the_base_against_the_window_location():
    """
    The real client must feed the page location into the builder — not the bare injected baseUrl.

    Checked on comment-stripped code so the prose explaining the bug cannot satisfy the assertion.
    This is what fails if a future edit reverts buildUrl to `new URL(path, baseUrl)`.
    """
    client = _strip_ts_comments(CLIENT_TS.read_text(encoding="utf-8"))
    assert "resolveApiUrl(baseUrl, window.location.href" in client, (
        "buildUrl no longer resolves the base against window.location (issue #162 regression)"
    )
    # And the builder itself must resolve the base before using it as a URL base.
    builder = _strip_ts_comments(URL_BUILDER.read_text(encoding="utf-8"))
    assert "new URL(withSlash, locationHref)" in builder, (
        "urlBuilder no longer absolutises the base against locationHref"
    )
