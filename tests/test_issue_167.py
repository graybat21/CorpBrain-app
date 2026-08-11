"""
Regression for issue #167 — the workspace-create modal defaults the workspace name to the
selected folder's name via the pure `deriveWorkspaceName` in src/frontend/utils/pathName.ts.

The shell side (native folder dialog via pywebview js_api) is covered in test_app_ui_01_shell.py.
Here we pin the name-derivation, which has no test runner of its own (Vitest/jsdom rejected —
smoke §1). As with issue #162, the real module is executed under node's --experimental-strip-types
(node >= 22.6, else skipped) so a copy cannot drift from what ships; plain-JS assertions are not
needed because the logic is pure string handling with no WHATWG-specific behaviour.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PATH_NAME_TS = REPO_ROOT / "src" / "frontend" / "utils" / "pathName.ts"

NODE = shutil.which("node")


def _node_supports_strip_types() -> bool:
    if not NODE:
        return False
    out = subprocess.run(
        [NODE, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)


def _derive(path: str) -> str:
    """Run the REAL deriveWorkspaceName from pathName.ts under node and return its output."""
    script = (
        f"import {{ deriveWorkspaceName }} from {json.dumps(PATH_NAME_TS.as_uri())};\n"
        "console.log(JSON.stringify(deriveWorkspaceName(process.argv[2])));\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        entry = Path(tmp) / "probe.mts"
        entry.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [NODE, "--experimental-strip-types", str(entry), path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip())


pytestmark = pytest.mark.skipif(
    not _node_supports_strip_types(), reason="needs node >= 22.6 for --experimental-strip-types"
)


@pytest.mark.parametrize(
    "path, expected",
    [
        (r"C:\Users\docto\문서\2026기술수요조사", "2026기술수요조사"),  # the screenshot's folder
        (r"C:\Users\docto\문서\2026기술수요조사\\", "2026기술수요조사"),  # trailing separator
        ("/home/user/projects/corpbrain", "corpbrain"),                # forward slashes
        ("D:/data/문서 모음/", "문서 모음"),                            # spaces + trailing slash
        ("", ""),                                                      # empty -> empty
        ("\\\\", ""),                                                  # separators only -> empty
    ],
)
def test_derive_workspace_name_takes_the_last_folder_segment(path, expected):
    assert _derive(path) == expected
