"""
RN-FE-01 (issue #40) — selective rename approval.

The audit left two items open: AC S2 (per-row approve/reject) and the WCAG contrast DoD. AC S2
needed a DTO change, which is the substance here — `RenameApplyReq.file_ids` lets the client name
a subset, and `apply_rename` intersects it with the history row it already holds.

`file_ids`, never paths. DEC-08 keeps absolute paths off the client, so a selection can only be
expressed as ids — and accepting a caller-supplied path would be the exact hole DEC-08 closes.
The backend half is tested for real; the React half is static source assertions, following
tests/test_ws_fe_01.py, since there is no frontend runner by decision.
"""

import json
import os
import re
import tempfile
import uuid
from pathlib import Path

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.rename_service import RenameService

RENAME_PAGE = Path(__file__).resolve().parent.parent / "src" / "frontend" / "pages" / "RenamePage.tsx"


def _code(path: Path) -> str:
    """Source with comments stripped — same rationale as tests/test_ws_fe_01.py::_code."""
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


@pytest.fixture
def batch():
    """Three scanned files plus a Rename_History row naming all three."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "sel.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            file_repo = FileRepository(db_mgr)
            ws_id = WorkspaceRepository(db_mgr).create("Select WS", [root])["workspace_id"]

            olds, news, ids = [], [], []
            for name in ("a.txt", "b.txt", "c.txt"):
                path = os.path.join(root, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(name)
                file_id = str(uuid.uuid4())
                olds.append(path)
                news.append(os.path.join(root, f"2026-08_{name}"))
                ids.append(file_id)
                file_repo.bulk_upsert([{
                    "file_id": file_id,
                    "workspace_id": ws_id,
                    "current_path": path,
                    "original_path": path,
                    "file_name": name,
                    "extension": ".txt",
                    "size_bytes": 1,
                    "last_modified": 1700000000.0,
                    "parse_status": "pending",
                    "importance_score": 0,
                }])

            history_id = str(uuid.uuid4())
            with db_mgr.transaction() as c:
                c.execute(
                    """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
                       VALUES (?, ?, ?, ?, 'pending');""",
                    (history_id, ws_id, json.dumps(olds), json.dumps(news)),
                )

            yield RenameService(db_mgr=db_mgr), db_mgr, ws_id, history_id, olds, news, ids
        finally:
            db_mgr.close()


# --- AC Scenario 2: only the approved files are applied ----------------------------------


def test_scenario_2_only_the_selected_files_are_renamed(batch):
    """
    AC S2 verbatim: 3 files, 1 rejected, [선택 적용] applies the other 2.

    Asserted on disk, not just on the return value — the claim is that the rejected file was not
    touched, and a count can be right while the wrong file moved.
    """
    service, db_mgr, ws_id, history_id, olds, news, ids = batch

    result = service.apply_rename(ws_id, history_id=history_id, file_ids=[ids[0], ids[2]])

    assert result["applied_count"] == 2, result
    assert result["failed"] == []
    # The two approved files moved.
    assert os.path.exists(news[0]) and not os.path.exists(olds[0])
    assert os.path.exists(news[2]) and not os.path.exists(olds[2])
    # The rejected one did not.
    assert os.path.exists(olds[1]), "the rejected file was renamed anyway"
    assert not os.path.exists(news[1])


def test_the_db_reflects_only_the_applied_subset(batch):
    """
    `File_Meta.current_path` must match disk for all three — including the untouched one.

    A DB that disagrees with disk is what produces broken deeplinks (DEC-08).
    """
    service, db_mgr, ws_id, history_id, olds, news, ids = batch
    service.apply_rename(ws_id, history_id=history_id, file_ids=[ids[1]])

    rows = {r["file_id"]: r["current_path"] for r in FileRepository(db_mgr).list_by_workspace(ws_id)}
    assert rows[ids[0]] == olds[0]
    assert rows[ids[1]] == news[1]
    assert rows[ids[2]] == olds[2]
    for file_id, path in rows.items():
        assert os.path.exists(path), f"{file_id} DB path does not exist on disk: {path}"


def test_an_omitted_file_ids_applies_the_whole_batch(batch):
    """
    `None` means "all of them" — every existing caller passes no selection at all.

    A change that made the parameter required would break the apply-all path silently in
    RenamePage's previous behaviour.
    """
    service, db_mgr, ws_id, history_id, olds, news, ids = batch

    result = service.apply_rename(ws_id, history_id=history_id)

    assert result["applied_count"] == 3
    assert all(os.path.exists(p) for p in news)


def test_an_empty_selection_applies_nothing(batch):
    """
    `[]` is not the same as `None`: it means the user approved none of them.

    Treating an empty list as "all" would rename the entire batch on a click the user made to
    apply nothing — the worst possible reading.
    """
    service, db_mgr, ws_id, history_id, olds, news, ids = batch

    result = service.apply_rename(ws_id, history_id=history_id, file_ids=[])

    assert result["applied_count"] == 0
    assert all(os.path.exists(p) for p in olds), "an empty selection renamed files"
    assert not any(os.path.exists(p) for p in news)


def test_an_unknown_file_id_is_ignored_not_applied(batch):
    """
    An id outside the batch is dropped rather than acted on.

    The alternative is renaming a file the history row never described — and since the server
    resolves paths from its own row, an unknown id has no path to act on anyway. Silently
    dropping it is right; inventing one would not be.
    """
    service, db_mgr, ws_id, history_id, olds, news, ids = batch

    result = service.apply_rename(
        ws_id, history_id=history_id, file_ids=[ids[0], str(uuid.uuid4())]
    )

    assert result["applied_count"] == 1
    assert os.path.exists(news[0])
    assert os.path.exists(olds[1]) and os.path.exists(olds[2])


def test_the_selection_cannot_smuggle_a_path(batch):
    """
    DEC-08: the request carries ids, and the server resolves paths from its own history row.

    Verified structurally — `RenameApplyReq.file_ids` is a list of plain strings, so there is no
    field a path could travel in, and `apply_rename` filters resolved items rather than trusting
    caller-supplied pairs.
    """
    from src.backend.api.dtos import RenameApplyReq

    req = RenameApplyReq(history_id="h", file_ids=[r"C:\Users\hong\문서\a.txt"])
    # The value is accepted as a *string* but is meaningless as a selector: it matches no file_id,
    # so nothing is applied.
    service, db_mgr, ws_id, history_id, olds, news, ids = batch
    result = service.apply_rename(ws_id, history_id=history_id, file_ids=req.file_ids)

    assert result["applied_count"] == 0
    assert all(os.path.exists(p) for p in olds)


# --- The endpoint -----------------------------------------------------------------------


def test_the_endpoint_forwards_the_selection(batch):
    """The route must pass `file_ids` through; a dropped parameter would apply everything."""
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    service, db_mgr, ws_id, history_id, olds, news, ids = batch
    app = create_app(db_mgr, session_token="sel-token")
    headers = {"Authorization": "Bearer sel-token"}
    client = TestClient(app)

    try:
        res = client.post(
            f"/api/v1/workspace/{ws_id}/rename/apply",
            json={"history_id": history_id, "file_ids": [ids[2]]},
            headers=headers,
        )
        assert res.status_code == 202, res.text
        assert app.state.task_runner.wait(res.json()["data"]["task_id"], timeout=20)

        assert os.path.exists(news[2]), "the selected file was not renamed"
        assert os.path.exists(olds[0]) and os.path.exists(olds[1]), "unselected files were renamed"
    finally:
        for tid in list(app.state.task_runner.active_task_ids()):
            app.state.task_runner.wait(tid, timeout=10)


def test_file_ids_is_part_of_the_generated_contract():
    """
    DEC-02: the OpenAPI schema is the SSOT, so the field must reach types.gen.ts.

    Without it the frontend could not type the request, and tsc would not catch a typo.
    """
    types = (Path(__file__).resolve().parent.parent / "src" / "frontend" / "api" / "types.gen.ts")
    content = types.read_text(encoding="utf-8")
    assert "file_ids?: string[] | null;" in content, "file_ids missing from the generated types"


# --- Frontend structure (static) --------------------------------------------------------


def test_the_page_sends_the_approved_ids(RENAME_PAGE=RENAME_PAGE):
    code = _code(RENAME_PAGE)
    assert "file_ids:" in code, "the apply call must carry the selection"
    assert "Array.from(approvedIds)" in code
    # And still no path: DEC-08 keeps them off the client entirely.
    assert "old_path" not in code
    assert "new_path" not in code


def test_an_excluded_row_cannot_be_approved():
    """
    AC S3: a PII-excluded row's checkbox is disabled, and bulk-select skips it.

    Two separate mechanisms, because either alone leaves a hole — a disabled input still
    round-trips if a bulk action writes its id, and a filtered bulk action still allows a click.
    """
    code = _code(RENAME_PAGE)

    assert "disabled={item.status !== APPLICABLE_STATUS}" in code, "row checkbox must be disabled"
    # Select-all builds its set from pendingItems, which is filtered by status.
    assert "pendingItems.map((i) => i.file_id)" in code
    assert "items.filter((item) => item.status === APPLICABLE_STATUS)" in code


def test_a_regenerated_diff_resets_the_selection():
    """
    A new diff must not inherit approvals from the previous run.

    Stale ids would either be ignored (harmless) or, if a file_id recurred, approve something the
    user never looked at.
    """
    code = _code(RENAME_PAGE)
    assert "setApprovedIds(" in code
    # The reset happens where the new diff is stored.
    generate_block = code[code.index("const handleGenerate"):code.index("const handleApplyAll")]
    assert "setApprovedIds(" in generate_block


def test_an_empty_selection_is_refused_before_the_request():
    """No task slot is consumed for a click that would apply nothing."""
    code = _code(RENAME_PAGE)
    assert "approvedIds.size === 0" in code


def test_the_before_after_colours_are_the_wcag_checked_pair():
    """
    DoD: WCAG AA contrast, and AC S1's red/green pairing.

    rose-300 (9.44:1) and emerald-300 (11.71:1) against the slate-900 panel — both measured, both
    well past the 4.5:1 body-text threshold. Pinned so a later palette tweak has to re-measure.
    """
    code = _code(RENAME_PAGE)
    assert "text-rose-300" in code, "before column must be red (AC S1)"
    assert "text-emerald-300" in code, "after column must be green (AC S1)"


def test_status_is_conveyed_as_text_not_only_colour():
    """
    A red/green pair alone fails for colour-blind users, so the status column must carry the
    same information as text.

    Not a WCAG contrast item — a separate criterion (use of colour), and the reason the status
    badge is not decorative.
    """
    code = _code(RENAME_PAGE)
    assert "Pending" in code
    assert "{item.status}" in code
    assert "{item.note}" in code
