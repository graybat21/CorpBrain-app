"""
Development-host compatibility shims (Windows is the only *shipped* target).

CorpBrain ships as a single Windows ``CorpBrain.exe`` (DEC-01) and every design decision
assumes Windows APIs: DPAPI for the API key (DEC-12), ``os.startfile`` for deeplinks
(DEC-08), ``%LocalAppData%`` for the data directory (DEC-05/06). None of those exist on
macOS or Linux, so a developer on a non-Windows host cannot run the test suite or
``scripts/dev_serve.py`` at all.

This module is the single place where "which host am I developing on" is answered. It
exists so the branch is written **once** here instead of being re-derived in every module
that touches an OS API — the same reasoning that puts every SQL string in a Repository and
every outbound request in ``NetworkGuard``.

Boundary this module does NOT cross
-----------------------------------
A shim makes a *development* host runnable. It never changes what the shipped Windows
artifact does, and it never weakens a security control to achieve that:

- ``open_with_default_app`` really opens the file on macOS/Linux, because a deeplink that
  silently no-ops would let DL-CMD-02 regressions through on a dev host.
- Secret storage has **no** shim. DPAPI has no cross-platform equivalent that satisfies
  DEC-12, and a base64 "mock encryption" fallback is plaintext-at-rest wearing a costume.
  On a non-Windows host, persisting a key raises and the key is read from the environment
  in memory only. See ``src/backend/utils/security.py``.
"""

import os
import subprocess
import sys
from pathlib import Path

#: True only on the shipped target platform. Read this instead of re-testing
#: ``sys.platform`` so every caller agrees on the definition.
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


def open_with_default_app(path: str) -> None:
    """
    Launch ``path`` in the OS default application.

    Windows uses ``os.startfile`` — the DEC-08 / REQ-FUNC-021 requirement, and the only
    behaviour that ships. macOS and Linux delegate to ``open`` / ``xdg-open`` so a
    developer can verify the deeplink round trip for real rather than against a stub.

    Raises:
        OSError: launch failed. Callers already map this to ``PATH_NOT_ACCESSIBLE``
            (DEC-03), so the shim deliberately normalizes every platform's failure into
            the same exception type the Windows path raises. ``os.startfile`` is absent
            (not merely failing) off Windows, and an ``AttributeError`` leaking out would
            bypass that mapping and surface as a 500.
    """
    if IS_WINDOWS:
        os.startfile(path)  # noqa: S606 - Windows-only, path resolved server-side from file_id
        return

    launcher = "open" if IS_MACOS else "xdg-open"
    try:
        # check=True so a non-zero exit becomes an exception rather than a silent success —
        # the caller reports "opened" purely on the absence of a raise.
        subprocess.run([launcher, path], check=True, capture_output=True)
    except FileNotFoundError as exc:
        # The launcher binary itself is missing (a bare Linux container has no xdg-open).
        raise OSError(f"{launcher} is not available on this host") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise OSError(f"{launcher} exited {exc.returncode}: {stderr}") from exc


def get_local_app_data_dir() -> Path:
    """
    Return the per-user application-data base directory.

    Windows resolves ``%LocalAppData%``, which is what SRS §6.2 specifies and what the
    shipped exe uses. Off Windows the env var is absent, and the previous fallback
    ``os.path.expanduser("~\\\\AppData\\\\Local")`` did not fail loudly — POSIX
    ``expanduser`` leaves a backslash string untouched, so it returned the literal
    ``~\\AppData\\Local`` and the app created a **relative** directory of that name in
    whatever the current working directory happened to be.

    The macOS/Linux equivalent is used instead, so a dev-host run writes to one predictable
    place outside the repo.
    """
    if IS_WINDOWS:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data)
        # Windows without LOCALAPPDATA is anomalous but expanduser works correctly here.
        return Path(os.path.expanduser("~")) / "AppData" / "Local"

    # An explicit override still wins off Windows: tests/test_db_002.py redirects
    # LOCALAPPDATA with monkeypatch.setenv, and that has to keep working on every host.
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data)

    if IS_MACOS:
        return Path.home() / "Library" / "Application Support"
    # Linux: XDG Base Directory spec.
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
