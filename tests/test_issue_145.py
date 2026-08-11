"""
Repo-wide guard for issue #145 — text-mode subprocess calls must pin their encoding.

`subprocess.run(..., text=True)` decodes the child's output with the host's ANSI codepage
(`locale.getpreferredencoding`), not UTF-8. On a Korean Windows install that is cp949, so a child
that writes any non-ASCII byte — an em-dash, a progress bar, a Korean path — raises
`UnicodeDecodeError` *inside subprocess's reader thread*. The call itself does not raise: the
thread dies, `result.stdout` comes back `None`, and the caller fails much later with a
`TypeError` that names nothing about encodings. P7 hit exactly this in `tests/test_issue_25.py`.

The CI blind spot this closes (the actual subject of #145): GitHub's `windows-latest` runner is an
English (UTF-8 / cp1252) host, so it can never reproduce the failure. Pinning `encoding=` at every
call site is enforceable statically, which is what makes it checkable on every host — including
the ones where the bug cannot be triggered.

This is an AST check, not a grep: a regex over source would be satisfied by the word "encoding"
appearing in a comment near the call, which is the failure mode the P7 report warned about.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNED_DIRS = ("src", "scripts", "tests")

#: Keywords that put a call into text mode, where a decode happens and an encoding is therefore
#: required. `errors=` alone does not imply text mode, so it is not listed.
TEXT_MODE_KEYWORDS = ("text", "universal_newlines")

#: The subprocess entry points that decode child output.
SUBPROCESS_FUNCS = ("run", "Popen", "check_output", "call", "check_call")


def _python_files():
    for directory in SCANNED_DIRS:
        yield from sorted((REPO_ROOT / directory).rglob("*.py"))


def _is_subprocess_call(node: ast.Call) -> bool:
    """True for `subprocess.<func>(...)` — attribute form only, which is how this repo calls it."""
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in SUBPROCESS_FUNCS
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
    )


def _keyword(node: ast.Call, name: str):
    for kw in node.keywords:
        if kw.arg == name:
            return kw
    return None


def _is_text_mode(node: ast.Call) -> bool:
    """
    True when the call decodes output.

    Only a literal `True` counts. A variable or expression cannot be resolved statically, and
    treating it as text mode would fail the guard on calls this rule cannot actually judge.
    """
    for name in TEXT_MODE_KEYWORDS:
        kw = _keyword(node, name)
        if kw is not None and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _violations():
    found = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # a broken file is compileall's problem, not this guard's
            raise AssertionError(f"{path} does not parse: {exc}") from exc

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_subprocess_call(node):
                continue
            if not _is_text_mode(node):
                continue
            if _keyword(node, "encoding") is None:
                found.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}")
    return found


def test_every_text_mode_subprocess_call_pins_an_encoding():
    """
    The guard itself: no text-mode subprocess call anywhere in the repo may omit `encoding=`.

    Listing the offending file:line rather than asserting a bare count, so a failure says where to
    look instead of only that the number moved.
    """
    violations = _violations()
    assert violations == [], (
        "text-mode subprocess calls without encoding= (issue #145) — these decode with the host "
        "ANSI codepage and break on a non-UTF-8 (e.g. cp949) Windows host:\n  "
        + "\n  ".join(violations)
    )


def test_the_guard_detects_a_violation_it_is_meant_to_catch():
    """
    Proves the guard is load-bearing rather than vacuously green.

    Without this, deleting the detection logic would leave `test_every_text_mode...` passing on an
    empty list forever — a guard that guards nothing. The sample is parsed in memory; nothing is
    written to the repo.
    """
    offending = ast.parse(
        "import subprocess\n"
        "subprocess.run(['x'], capture_output=True, text=True)\n"
    )
    calls = [n for n in ast.walk(offending) if isinstance(n, ast.Call) and _is_subprocess_call(n)]
    assert len(calls) == 1
    assert _is_text_mode(calls[0]) is True
    assert _keyword(calls[0], "encoding") is None, "the sample must look like a real violation"

    compliant = ast.parse(
        "import subprocess\n"
        "subprocess.run(['x'], capture_output=True, text=True, encoding='utf-8')\n"
    )
    ok_calls = [n for n in ast.walk(compliant) if isinstance(n, ast.Call) and _is_subprocess_call(n)]
    assert _keyword(ok_calls[0], "encoding") is not None

    # universal_newlines is the older spelling of the same switch and must be treated alike.
    legacy = ast.parse(
        "import subprocess\n"
        "subprocess.run(['x'], universal_newlines=True)\n"
    )
    legacy_calls = [n for n in ast.walk(legacy) if isinstance(n, ast.Call) and _is_subprocess_call(n)]
    assert _is_text_mode(legacy_calls[0]) is True

    # A binary-mode call is out of scope: nothing is decoded, so there is nothing to pin.
    binary = ast.parse(
        "import subprocess\n"
        "subprocess.run(['x'], capture_output=True)\n"
    )
    binary_calls = [n for n in ast.walk(binary) if isinstance(n, ast.Call) and _is_subprocess_call(n)]
    assert _is_text_mode(binary_calls[0]) is False


def test_the_guard_actually_scans_the_repo():
    """
    A scan that reaches no files would also report zero violations.

    Pins that the walk finds real modules and, specifically, the two call sites P7 and this issue
    fixed — if the scanned directories are ever renamed, this fails instead of silently passing.
    """
    files = {p.relative_to(REPO_ROOT).as_posix() for p in _python_files()}

    assert len(files) > 50, f"only {len(files)} files scanned — the walk is not reaching the repo"
    assert "src/backend/services/provisioning_service.py" in files
    assert "tests/test_issue_25.py" in files
