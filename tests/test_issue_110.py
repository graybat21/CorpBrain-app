"""
Issue #110 — the Chroma temp-dir teardown flake on Windows CI.

`backend (windows-latest)` failed intermittently (2 of 3 runs at its worst) with
`PermissionError [WinError 32]` on `chroma.sqlite3`, then `NotADirectoryError [WinError 267]`
from `shutil.rmtree`'s own error handler. The test bodies passed — only teardown failed.

Two distinct defects were behind it, and they need separate tests:

1. `TemporaryDirectory` deletes with no retry, while Chroma's Rust/SQLite layer can drop the OS
   handle a moment after `client.close()` returns. That is a race → bounded retry.
2. The `store` fixture called `manager.close()` as a trailing statement after `yield`, so a
   failing assertion skipped it — and the resulting teardown error buried the real failure.

The race cannot be reproduced on macOS/Linux (unlinking an open file is legal there), so the
retry is tested against a *simulated* failing rmtree rather than a real handle. That is
deliberate: asserting the retry logic is possible everywhere, asserting the Windows kernel's
behaviour is not.
"""

import os
import shutil
import sys

import pytest

from tests.fakes import chroma_temp_dir


def test_the_directory_is_removed_on_the_happy_path():
    with chroma_temp_dir() as tmpdir:
        assert os.path.isdir(tmpdir)
        with open(os.path.join(tmpdir, "f.txt"), "w") as f:
            f.write("x")
    assert not os.path.exists(tmpdir)


def test_a_transient_permission_error_is_retried(monkeypatch):
    """
    The first rmtree attempts fail, a later one succeeds — exactly the Windows handle race.

    Without the retry this raised out of teardown and failed a run whose tests all passed.
    """
    real_rmtree = shutil.rmtree
    attempts = {"n": 0}

    def flaky_rmtree(path, *args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise PermissionError(32, "The process cannot access the file")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", flaky_rmtree)

    with chroma_temp_dir() as tmpdir:
        captured = tmpdir

    assert attempts["n"] == 3, "should have retried until it succeeded"
    assert not os.path.exists(captured)


def test_a_permanent_failure_does_not_raise_out_of_teardown(monkeypatch):
    """
    After the retry budget, cleanup gives up quietly.

    A leaked temp directory is the OS's problem at reboot; a teardown exception fails an
    otherwise-green run, which is strictly worse.
    """
    def always_fails(path, *args, **kwargs):
        if kwargs.get("ignore_errors"):
            return None
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(shutil, "rmtree", always_fails)

    # No exception despite cleanup never succeeding.
    with chroma_temp_dir():
        pass


def test_an_exception_from_the_body_is_never_swallowed(monkeypatch):
    """
    The regression that made the flake expensive to diagnose.

    A `return` inside the `finally` would discard an in-flight exception, so a real assertion
    failure would vanish and be replaced by a confusing teardown error. `break` preserves it.
    """
    def always_fails(path, *args, **kwargs):
        if kwargs.get("ignore_errors"):
            return None
        raise PermissionError(32, "held open")

    monkeypatch.setattr(shutil, "rmtree", always_fails)

    with pytest.raises(AssertionError, match="the real failure"):
        with chroma_temp_dir():
            raise AssertionError("the real failure")


def test_the_store_fixture_closes_its_manager_even_when_a_test_fails():
    """
    The `store` fixture's close must be in a `finally` (HANDOFF.md 함정 5).

    Asserted by reading the source: the failure mode is "an assertion error gets buried", which
    cannot be observed from inside a passing test. Comments are stripped first so this file's
    own prose about `finally` cannot satisfy the check.
    """
    path = os.path.join(os.path.dirname(__file__), "test_db_002.py")
    source = open(path, encoding="utf-8").read()
    body = source[source.index("def store():"):source.index("# --- AC S1")]
    code = "\n".join(
        line.split("#")[0] for line in body.splitlines() if not line.strip().startswith("#")
    )

    assert "finally:" in code, "store must close its manager in a finally block"
    assert "chroma_temp_dir()" in code, "store must use the retrying temp dir (issue #110)"
    # A trailing `manager.close()` at the with-body's indent level is the bug being prevented.
    assert "\n        manager.close()" not in code, "close must not be a trailing statement"


@pytest.mark.skipif(sys.platform != "win32", reason="the handle race only exists on Windows")
def test_a_real_open_handle_is_tolerated_on_windows(tmp_path):
    """
    The end-to-end claim, runnable only on the platform that has the defect.

    An open handle inside the directory makes an unretried rmtree raise WinError 32. This must
    still leave teardown quiet.

    The handle is closed from a timer thread partway through the retry budget, which is what
    Chroma effectively does — releases the handle shortly after close() returns. Closing it
    before the `with` exits would prove nothing, since there would be no lock to tolerate.
    """
    import threading

    with chroma_temp_dir() as tmpdir:
        handle = open(os.path.join(tmpdir, "locked.db"), "w")
        handle.write("x")
        handle.flush()
        # Released after ~150ms: long enough that the first rmtree attempts fail, short enough
        # to land inside the retry budget. Teardown must absorb this without raising.
        threading.Timer(0.15, handle.close).start()
