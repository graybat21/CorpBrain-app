"""
Invariants for scripts/github_task_tracker.py TASK_MAP.

DECISION_LOG rule 2 makes `github_task_tracker.py complete <TASK_ID>` the only path that
closes an issue, so a wrong entry in TASK_MAP closes somebody else's unimplemented task. The
table shipped with ~13 wrong entries and was missing ANA-QRY-02 entirely; that was found by
hand against `gh issue list`.

These tests fix the part of that check that can run offline. A `gh` call cannot go in the
suite — it needs network and an authenticated user — so what is pinned here is local
consistency with `tasks/*.md`, which is the same set the issues were generated from.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
TRACKER = REPO_ROOT / "scripts" / "github_task_tracker.py"


@pytest.fixture(scope="module")
def task_map():
    """
    Parse TASK_MAP out of the source instead of importing it.

    Importing the module would be fine today, but the script's top level is where argparse and
    a `gh` availability check live; parsing keeps this test from ever depending on that.
    """
    source = TRACKER.read_text(encoding="utf-8")
    block = re.search(r"TASK_MAP\s*[:=][^{]*\{(.*?)\n\}", source, re.DOTALL)
    assert block, "TASK_MAP dict literal not found in github_task_tracker.py"
    pairs = re.findall(r'"([A-Z0-9\-]+)"\s*:\s*(\d+)', block.group(1))
    assert pairs, "TASK_MAP parsed as empty"
    return {code: int(number) for code, number in pairs}


def test_task_map_matches_the_task_spec_files_exactly(task_map):
    """
    Every task spec has an entry and every entry has a task spec.

    A missing entry means the task cannot be closed through the sanctioned path (this is what
    happened to ANA-QRY-02). An extra entry means a task code that does not exist can be
    "completed", which closes whatever issue number it happens to point at.
    """
    spec_codes = {p.stem for p in TASKS_DIR.glob("*.md")}
    assert spec_codes, "no task spec files found under tasks/"

    missing = sorted(spec_codes - set(task_map))
    extra = sorted(set(task_map) - spec_codes)
    assert not missing, f"task specs with no TASK_MAP entry: {missing}"
    assert not extra, f"TASK_MAP entries with no task spec: {extra}"


def test_issue_numbers_are_unique(task_map):
    """
    Two task codes pointing at one issue number is how a wrong entry manifests.

    It always closes the wrong task: whichever code is not the real owner still resolves to a
    real, likely-unimplemented issue.
    """
    seen: dict[int, str] = {}
    collisions = []
    for code, number in sorted(task_map.items()):
        if number in seen:
            collisions.append(f"#{number}: {seen[number]} and {code}")
        seen[number] = code
    assert not collisions, f"duplicate issue numbers in TASK_MAP: {collisions}"


def test_issue_numbers_are_positive(task_map):
    assert all(number > 0 for number in task_map.values())
