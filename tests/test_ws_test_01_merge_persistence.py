"""
WS-TEST-01 (issue #66) — folder-merge business logic and restart persistence.

`tests/test_issue_105.py` covers the multi-root scan and one restart case. This adds the merge
logic's own edge cases and the persistence claim as its own subject: **every** workspace field and
its child rows survive a connection cycle, in the order they were selected.

"Simulate App Restart" is a second `DatabaseManager` over the same file, with the first closed
first. That is the strongest available stand-in — WAL contents, `PRAGMA` settings applied per
connection, and anything cached in the manager are all discarded, so a value that only lived in
memory cannot survive. What it does not simulate is a process crash mid-write; `Async_Task`
recovery covers that separately.

Merge de-duplication matters more than it looks: `Workspace_Root` carries
`UNIQUE(workspace_id, root_path)`, so a duplicate that reached the INSERT would abort the whole
creation. The user's two ways of producing one — picking the same folder twice in the OS dialog,
or a trailing separator — must both collapse before the write.
"""

import os
import tempfile

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.workspace_service import WorkspaceService


@pytest.fixture
def env():
    """A temp dir plus a helper that makes real folders, since the service validates existence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ws.db")
        db_mgr = DatabaseManager(db_path=db_path)

        def folder(name: str) -> str:
            path = os.path.join(tmpdir, name)
            os.makedirs(path, exist_ok=True)
            return path

        try:
            yield db_mgr, db_path, folder, tmpdir
        finally:
            db_mgr.close()


def _service(db_mgr) -> WorkspaceService:
    return WorkspaceService(WorkspaceRepository(db_mgr))


# --- Merge logic: de-duplication ---------------------------------------------------------


def test_the_same_folder_picked_twice_collapses_to_one_root(env):
    """
    The OS folder dialog lets a user add the same directory twice.

    `Workspace_Root` has `UNIQUE(workspace_id, root_path)`, so a duplicate reaching the INSERT
    aborts the entire creation — the user loses the whole workspace over a double click.
    """
    db_mgr, db_path, folder, tmpdir = env
    alpha = folder("알파")

    workspace = _service(db_mgr).create_workspace("중복", [alpha, alpha])

    assert workspace["root_paths"] == [alpha]


def test_a_trailing_separator_is_the_same_folder(env):
    """
    `/docs` and `/docs/` name one directory.

    Path text arrives from a file picker, a paste, or a config import, and only one of those
    reliably normalises — so the service must.
    """
    db_mgr, db_path, folder, tmpdir = env
    alpha = folder("알파")

    workspace = _service(db_mgr).create_workspace("구분자", [alpha, alpha + os.sep])

    assert len(workspace["root_paths"]) == 1


def test_de_duplication_preserves_the_first_occurrence_order(env):
    """
    Order is the user's selection order, and de-duplication must not reshuffle it.

    The sidebar lists roots back in this order, so a set-based de-dup would make the display
    non-deterministic between runs — which reads as data changing on its own.
    """
    db_mgr, db_path, folder, tmpdir = env
    a, b, c = folder("A"), folder("B"), folder("C")

    workspace = _service(db_mgr).create_workspace("순서", [c, a, c, b, a])

    assert workspace["root_paths"] == [c, a, b]


def test_distinct_folders_are_all_kept(env):
    """The control case: de-duplication must not be over-eager."""
    db_mgr, db_path, folder, tmpdir = env
    roots = [folder("알파"), folder("베타"), folder("감마")]

    workspace = _service(db_mgr).create_workspace("셋", roots)

    assert workspace["root_paths"] == roots


# --- Merge logic: validation ------------------------------------------------------------


def test_a_nonexistent_folder_aborts_the_whole_creation(env):
    """
    Validation is all-or-nothing: no workspace row is written if any root is missing.

    A partial workspace would scan a subset and report success — the exact #105 failure mode, just
    arrived at from a different direction.
    """
    db_mgr, db_path, folder, tmpdir = env
    alpha = folder("알파")
    missing = os.path.join(tmpdir, "없는폴더")

    with pytest.raises(FileNotFoundError):
        _service(db_mgr).create_workspace("실패", [alpha, missing])

    assert WorkspaceRepository(db_mgr).list_all() == [], "no partial workspace may survive"


def test_an_empty_root_list_is_rejected(env):
    """A workspace with no folder has nothing to scan, so it is a validation failure, not an empty
    workspace."""
    db_mgr, db_path, folder, tmpdir = env

    with pytest.raises(ValueError):
        _service(db_mgr).create_workspace("빈목록", [])


def test_a_bare_string_is_rejected_rather_than_silently_split(env):
    """
    `create("name", "/tmp/a")` must raise, not enumerate the string character by character.

    Without the guard, `enumerate("/tmp/a")` inserts one row per character and every row after the
    first collides on the UNIQUE constraint — an IntegrityError far from the actual mistake.
    """
    db_mgr, db_path, folder, tmpdir = env
    alpha = folder("알파")

    with pytest.raises(TypeError):
        WorkspaceRepository(db_mgr).create("문자열", alpha)


# --- AC Scenario 1: restart persistence ---------------------------------------------------


def test_scenario_1_a_workspace_survives_a_connection_cycle(env):
    """
    AC S1: create, close the manager, reopen, and the data is intact.

    A second `DatabaseManager` over the same file is the strongest available stand-in for a restart
    — WAL contents, per-connection PRAGMAs and anything the manager cached are all discarded, so a
    value that only lived in memory cannot survive.
    """
    db_mgr, db_path, folder, tmpdir = env
    roots = [folder("알파"), folder("베타")]
    created = _service(db_mgr).create_workspace("영속", roots)
    workspace_id = created["workspace_id"]
    db_mgr.close()

    reopened = DatabaseManager(db_path=db_path)
    try:
        found = WorkspaceRepository(reopened).get_by_id(workspace_id)

        assert found is not None
        assert found["workspace_name"] == "영속"
        assert found["root_paths"] == roots, "root order must survive the restart"
        assert found["created_at"] == created["created_at"]
    finally:
        reopened.close()


def test_the_listing_survives_a_restart_with_its_ordering(env):
    """
    `list_all` orders by `created_at DESC, rowid DESC`, which the sidebar depends on.

    Ordering is a persistence property too: if it came from insertion order in memory, the list
    would come back arbitrary after a restart.

    The `rowid DESC` tiebreaker was added for this test (issue #66, MINOR 1). `created_at` uses
    `strftime('%f')` — millisecond resolution — and three inserts land inside one millisecond, so
    `created_at` alone left the order undefined and the sidebar could reshuffle between two
    identical requests. Found because this test creates three workspaces back to back, which is
    also exactly what a user does.
    """
    db_mgr, db_path, folder, tmpdir = env
    service = _service(db_mgr)
    first = service.create_workspace("첫번째", [folder("A")])
    second = service.create_workspace("두번째", [folder("B")])
    third = service.create_workspace("세번째", [folder("C")])
    db_mgr.close()

    reopened = DatabaseManager(db_path=db_path)
    try:
        listed = WorkspaceRepository(reopened).list_all()

        assert [w["workspace_id"] for w in listed] == [
            third["workspace_id"], second["workspace_id"], first["workspace_id"]
        ]
        # Roots come back attached, not as a separate lookup the caller has to remember.
        assert all(w["root_paths"] for w in listed)
    finally:
        reopened.close()


def test_child_rows_survive_the_restart_too(env):
    """
    `Watcher_Config` is created alongside the workspace, so it must survive with it.

    A workspace whose watcher row vanished would silently fall back to default settings — the
    user's chosen mode replaced without any message.
    """
    db_mgr, db_path, folder, tmpdir = env
    created = _service(db_mgr).create_workspace("자식행", [folder("알파")])
    workspace_id = created["workspace_id"]
    db_mgr.close()

    reopened = DatabaseManager(db_path=db_path)
    try:
        row = reopened.get_connection().execute(
            "SELECT is_enabled, debounce_ms FROM Watcher_Config WHERE workspace_id = ?;",
            (workspace_id,),
        ).fetchone()
        assert row is not None, "the Watcher_Config row created with the workspace must persist"
        assert row["debounce_ms"] == 500
    finally:
        reopened.close()


def test_scanned_files_survive_the_restart(env):
    """
    The point of persistence: a scan done before a restart is not repeated after it.

    Without this, reopening the app would rescan every workspace — minutes of I/O the user already
    paid for, and REQ-NF-011's whole premise.
    """
    db_mgr, db_path, folder, tmpdir = env
    root = folder("문서")
    created = _service(db_mgr).create_workspace("스캔영속", [root])
    workspace_id = created["workspace_id"]

    path = os.path.join(root, "보고서.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 내용")
    FileRepository(db_mgr).bulk_upsert([{
        "file_id": "f-persist", "workspace_id": workspace_id,
        "current_path": path, "original_path": path,
        "file_name": "보고서.md", "extension": ".md",
        "size_bytes": 6, "last_modified": 1700000000.0,
        "parse_status": "parsed", "importance_score": 77,
    }])
    db_mgr.close()

    reopened = DatabaseManager(db_path=db_path)
    try:
        rows = FileRepository(reopened).list_by_workspace(workspace_id)

        assert len(rows) == 1
        assert rows[0]["file_name"] == "보고서.md"
        # The analysis result survives too, not just the row.
        assert rows[0]["importance_score"] == 77
        assert rows[0]["parse_status"] == "parsed"
    finally:
        reopened.close()


def test_two_restarts_in_a_row_are_stable(env):
    """
    Reading twice must not mutate anything.

    `DatabaseManager.__init__` runs migrations and `recover_interrupted_tasks` on every
    construction, so "open" is not a read-only act — an idempotency bug there would corrupt data on
    the second launch rather than the first, which is far harder to attribute.
    """
    db_mgr, db_path, folder, tmpdir = env
    roots = [folder("알파"), folder("베타")]
    created = _service(db_mgr).create_workspace("두번재시작", roots)
    db_mgr.close()

    snapshots = []
    for _ in range(2):
        manager = DatabaseManager(db_path=db_path)
        try:
            snapshots.append(WorkspaceRepository(manager).get_by_id(created["workspace_id"]))
        finally:
            manager.close()

    assert snapshots[0] == snapshots[1]
    assert snapshots[0]["root_paths"] == roots


# --- Deletion cascade (the other half of WS-CMD-01) --------------------------------------


def test_deleting_a_workspace_removes_its_roots_and_files(env):
    """
    `ON DELETE CASCADE` on every `workspace_id` FK (DEC-05).

    Orphan rows would block re-registering the same folders — `Workspace_Root`'s UNIQUE constraint
    is per workspace, but a leaked row keeps its `workspace_id` pointing at nothing.
    """
    db_mgr, db_path, folder, tmpdir = env
    root = folder("알파")
    service = _service(db_mgr)
    created = service.create_workspace("삭제대상", [root])
    workspace_id = created["workspace_id"]

    FileRepository(db_mgr).bulk_upsert([{
        "file_id": "f-del", "workspace_id": workspace_id,
        "current_path": os.path.join(root, "a.md"), "original_path": os.path.join(root, "a.md"),
        "file_name": "a.md", "extension": ".md",
        "size_bytes": 1, "last_modified": 1700000000.0,
        "parse_status": "pending", "importance_score": 0,
    }])

    assert service.delete_workspace(workspace_id) is True

    conn = db_mgr.get_connection()
    assert conn.execute("SELECT COUNT(*) FROM Workspace_Root;").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM File_Meta;").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM Watcher_Config;").fetchone()[0] == 0
    # And the folders can be registered again.
    service.create_workspace("재등록", [root])


def test_the_deletion_persists_across_a_restart(env):
    """A delete that only cleared an in-memory cache would reappear on the next launch."""
    db_mgr, db_path, folder, tmpdir = env
    service = _service(db_mgr)
    created = service.create_workspace("삭제영속", [folder("알파")])
    service.delete_workspace(created["workspace_id"])
    db_mgr.close()

    reopened = DatabaseManager(db_path=db_path)
    try:
        assert WorkspaceRepository(reopened).get_by_id(created["workspace_id"]) is None
        assert WorkspaceRepository(reopened).list_all() == []
    finally:
        reopened.close()
