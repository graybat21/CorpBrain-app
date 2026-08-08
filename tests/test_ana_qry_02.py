"""
ANA-QRY-02 / DEC-04: async task skeleton — 202 + task_id, SQLite-backed progress, polling.

The assertions here are deliberately about *where the state lives*, not just about the shape
of a response. An in-memory dict would pass a naive "does progress increase" test and still
violate DEC-04 and REQ-NF-011, which is exactly how CORE #2 in docs/loop/DECISION_LOG.md got
past review the first time. `test_progress_is_readable_from_a_second_db_manager` is the one
that cannot be satisfied by a dict.
"""

import os
import shutil
import tempfile
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from src.backend.api.app import create_app
from src.backend.db import DatabaseManager
from src.backend.repositories.task_repository import TaskRepository
from src.backend.services.task_service import TaskQueryService, TaskRunner
from tests.task_polling import poll_until_done

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")


@pytest.fixture
def temp_env():
    """A DatabaseManager on a temp DB, plus the task trio wired the way create_app wires it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "task_test.db")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
        task_repo = TaskRepository(db_mgr)
        runner = TaskRunner(db_mgr, task_repo=task_repo)
        query = TaskQueryService(db_mgr, task_repo=task_repo)
        try:
            yield db_mgr, db_path, task_repo, runner, query
        finally:
            for task_id in runner.active_task_ids():
                runner.wait(task_id, timeout=10)
            db_mgr.close()


@pytest.fixture
def api():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "task_api_test.db")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
        token = "test_task_token"
        app = create_app(db_mgr, session_token=token)
        with TestClient(app) as client:
            yield client, {"Authorization": f"Bearer {token}"}, tmpdir, app
        for task_id in app.state.task_runner.active_task_ids():
            app.state.task_runner.wait(task_id, timeout=10)
        db_mgr.close()


# --- Scenario 1: progress DTO ------------------------------------------------------------


def test_progress_dto_reports_processed_total_and_percent(temp_env):
    """AC S1: a task mid-flight reports processed/total/percent/status."""
    _, _, task_repo, _, query = temp_env
    task = task_repo.create("analyze_deep", total_count=200)
    task_repo.mark_running(task["task_id"])
    task_repo.increment_processed(task["task_id"], 45)

    progress = query.get_progress(task["task_id"])
    assert progress["processed"] == 45
    assert progress["total"] == 200
    assert progress["percent"] == 22.5
    assert progress["status"] == "running"
    assert progress["task_type"] == "analyze_deep"


def test_percent_is_zero_not_a_division_error_when_total_unknown(temp_env):
    """A scan's total is unknown until the walk finishes, so total==0 is a normal state."""
    _, _, task_repo, _, query = temp_env
    task = task_repo.create("scan")
    progress = query.get_progress(task["task_id"])
    assert progress["total"] == 0
    assert progress["percent"] == 0.0


def test_eta_is_none_rather_than_a_fabricated_zero(temp_env):
    """
    ETA is omitted whenever there is nothing to extrapolate from.

    A queued task with 0 processed items has no measured rate. Reporting `0` there would
    render as a full progress bar over work that has not started — worse than an empty field.
    """
    _, _, task_repo, _, query = temp_env

    queued = task_repo.create("scan", total_count=100)
    assert query.get_progress(queued["task_id"])["eta_sec"] is None

    unknown_total = task_repo.create("scan")
    task_repo.increment_processed(unknown_total["task_id"], 5)
    assert query.get_progress(unknown_total["task_id"])["eta_sec"] is None

    done = task_repo.create("scan", total_count=3)
    task_repo.increment_processed(done["task_id"], 3)
    task_repo.finish(done["task_id"], "completed")
    assert query.get_progress(done["task_id"])["eta_sec"] is None


def test_eta_is_derived_from_measured_throughput(temp_env):
    """
    A running task with real elapsed time yields a non-negative integer ETA.

    Deliberately asserts only that the number exists and is sane rather than a specific value:
    the rate is measured wall-clock, so pinning an exact second would make this flaky.
    """
    _, _, task_repo, _, query = temp_env
    task = task_repo.create("analyze_deep", total_count=10)
    task_repo.mark_running(task["task_id"])
    time.sleep(0.15)
    task_repo.increment_processed(task["task_id"], 2)

    eta = query.get_progress(task["task_id"])["eta_sec"]
    assert isinstance(eta, int)
    assert eta >= 0


# --- Scenario 2: unknown task_id --------------------------------------------------------


def test_unknown_task_id_returns_404_envelope(api):
    """AC S2: 404 + the DEC-03 failure envelope with the standard NOT_FOUND code."""
    client, headers, _, _ = api
    res = client.get(f"/api/v1/analyze/{uuid.uuid4()}/progress", headers=headers)
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_progress_endpoint_requires_bearer_token(api):
    """DEC-02: no /api/v1/* route bypasses the token middleware, new ones included."""
    client, _, _, _ = api
    res = client.get(f"/api/v1/analyze/{uuid.uuid4()}/progress")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# --- DEC-04: state lives in SQLite ------------------------------------------------------


def test_progress_is_readable_from_a_second_db_manager(temp_env):
    """
    The load-bearing test for DEC-04.

    A second DatabaseManager on the same file is a stand-in for the next process: if progress
    were held in an in-memory dict this read would return nothing. It also pins that
    `increment_processed` really commits per call rather than buffering.
    """
    _, db_path, task_repo, _, _ = temp_env
    task = task_repo.create("analyze_deep", total_count=4)
    task_repo.mark_running(task["task_id"])
    task_repo.increment_processed(task["task_id"], 3)

    other = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
    try:
        # `other`'s boot recovery relabels live tasks, so read the counters — those are the
        # crash-visibility guarantee (REQ-NF-011) and recovery must not touch them.
        progress = TaskQueryService(other).get_progress(task["task_id"])
        assert progress is not None
        assert progress["processed"] == 3
        assert progress["total"] == 4
    finally:
        other.close()


def test_progress_is_committed_per_item_while_the_task_runs(temp_env):
    """
    Progress must be visible mid-task, not written once at the end.

    The body blocks on an event after its first item; the assertion happens while it is still
    parked there. A task that only committed on completion would report 0 here.
    """
    db_mgr, db_path, task_repo, runner, _ = temp_env
    first_item_done = threading.Event()
    release = threading.Event()

    def body(ctx):
        ctx.set_total(2)
        ctx.advance()
        first_item_done.set()
        release.wait(timeout=10)
        ctx.advance()
        return {"status": "completed"}

    task = runner.submit("analyze_deep", body)
    assert first_item_done.wait(timeout=10)

    observer = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
    try:
        mid = TaskQueryService(observer).get_progress(task["task_id"])
        assert mid["processed"] == 1
        assert mid["total"] == 2
    finally:
        observer.close()

    release.set()
    assert runner.wait(task["task_id"], timeout=10)
    assert task_repo.get(task["task_id"])["status"] == "completed"


# --- Boot recovery ----------------------------------------------------------------------


@pytest.mark.parametrize("stranded_status", ["running", "queued"])
def test_boot_recovery_marks_stranded_tasks_interrupted(temp_env, stranded_status):
    """
    DEC-04: both live states are stranded by a crash, not just 'running'.

    A 'queued' row is committed before the 202 is returned. If a crash happens in that window
    the worker never starts, so leaving it 'queued' means the frontend polls a task that will
    never advance and `list_interrupted()` never offers it for resume.
    """
    db_mgr, db_path, task_repo, _, _ = temp_env
    task_id = str(uuid.uuid4())
    with db_mgr.transaction() as tx:
        tx.execute(
            "INSERT INTO Async_Task (task_id, task_type, status, processed_count, total_count) VALUES (?, ?, ?, ?, ?);",
            (task_id, "analyze_deep", stranded_status, 7, 20),
        )

    reopened = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
    try:
        row = TaskRepository(reopened).get(task_id)
        assert row["status"] == "interrupted"
        # Recovery relabels state only. Losing the counters would destroy the very information
        # the user needs to decide whether resuming is worth it.
        assert row["processed_count"] == 7
        assert row["total_count"] == 20
    finally:
        reopened.close()


def test_interrupted_endpoint_lists_stranded_tasks_without_resuming(api):
    """
    DEC-04 forbids auto-resume, so the endpoint is a query.

    Asserting the status is still 'interrupted' after the call is what pins that: a listing
    that quietly restarted the task would have flipped it to 'running'.
    """
    client, headers, _, app = api
    db_mgr = app.state.db_mgr
    task_id = str(uuid.uuid4())
    with db_mgr.transaction() as tx:
        tx.execute(
            "INSERT INTO Async_Task (task_id, task_type, status, processed_count, total_count) VALUES (?, ?, ?, ?, ?);",
            (task_id, "scan", "interrupted", 12, 50),
        )

    res = client.get("/api/v1/task/interrupted", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 1
    item = data["items"][0]
    assert item["task_id"] == task_id
    assert item["processed"] == 12
    assert item["total"] == 50

    assert app.state.task_repo.get(task_id)["status"] == "interrupted"
    assert app.state.task_runner.active_task_ids() == []


# --- Duplicate-run prevention -----------------------------------------------------------


def test_a_second_submit_reuses_the_live_task(api):
    """
    SRS §6.2.8: the (workspace_id, task_type) index exists for 중복 실행 방지.

    A double-clicked scan button would otherwise start two concurrent walks writing the same
    File_Meta rows. The second POST hands back the same task_id, so the frontend polls one
    task and cannot tell it was deduplicated.
    """
    client, headers, tmpdir, app = api
    res_ws = client.post(
        "/api/v1/workspace", json={"workspace_name": "Dup WS", "root_paths": [tmpdir]}, headers=headers
    )
    ws_id = res_ws.json()["data"]["workspace_id"]

    release = threading.Event()
    started = threading.Event()
    original_scan = app.state.scanner_service.scan_workspace

    def slow_scan(*args, **kwargs):
        started.set()
        release.wait(timeout=10)
        return original_scan(*args, **kwargs)

    app.state.scanner_service.scan_workspace = slow_scan
    try:
        first = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
        assert first.status_code == 202
        assert started.wait(timeout=10)

        second = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
        assert second.status_code == 202
        assert second.json()["data"]["task_id"] == first.json()["data"]["task_id"]
        assert len(app.state.task_runner.active_task_ids()) == 1
    finally:
        release.set()
        app.state.scanner_service.scan_workspace = original_scan

    poll_until_done(client, headers, first.json()["data"]["task_id"])

    # Once the first finished, a new submit is a genuinely new task.
    third = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
    assert third.json()["data"]["task_id"] != first.json()["data"]["task_id"]
    poll_until_done(client, headers, third.json()["data"]["task_id"])


def test_find_active_is_scoped_per_workspace_and_type(temp_env):
    """Dedup must not make one workspace's scan block another's."""
    db_mgr, _, task_repo, _, _ = temp_env
    ws_a, ws_b = str(uuid.uuid4()), str(uuid.uuid4())
    with db_mgr.transaction() as tx:
        # root_path carries a UNIQUE constraint, so the two workspaces need distinct roots.
        for ws_id in (ws_a, ws_b):
            tx.execute(
                "INSERT INTO Workspace_Meta (workspace_id, workspace_name, root_path) VALUES (?, ?, ?);",
                (ws_id, f"WS {ws_id[:4]}", f"C:\\Nowhere\\{ws_id}"),
            )

    task = task_repo.create("scan", workspace_id=ws_a)
    assert task_repo.find_active(ws_a, "scan")["task_id"] == task["task_id"]
    assert task_repo.find_active(ws_b, "scan") is None
    assert task_repo.find_active(ws_a, "analyze_fast") is None

    # A terminal task is not active, so the next run is not blocked by history.
    task_repo.finish(task["task_id"], "completed")
    assert task_repo.find_active(ws_a, "scan") is None


# --- Failure & partial-failure semantics ------------------------------------------------


def test_failing_body_records_failed_status_and_hides_the_message(temp_env):
    """
    DEC-03: the response carries error_code; the exception text stays in the DB and the log.

    The raised message contains a path-shaped string on purpose — the assertion is that it
    does not reach what the progress endpoint returns.
    """
    _, _, task_repo, runner, query = temp_env

    def body(ctx):
        raise RuntimeError(r"failed reading C:\Users\someone\secret.docx")

    task = runner.submit("analyze_deep", body)
    assert runner.wait(task["task_id"], timeout=10)

    progress = query.get_progress(task["task_id"])
    assert progress["status"] == "failed"
    assert progress["error_code"] == "INTERNAL_ERROR"
    assert "error_message" not in progress
    assert "secret.docx" not in str(progress)

    # Stored for local diagnosis, which is the only place it is allowed to exist.
    assert "secret.docx" in task_repo.get(task["task_id"])["error_message"]


def test_body_can_finish_multi_status_for_partial_failure(temp_env):
    """
    DEC-16: a partially failed task must not report success.

    'multi_status' is the terminal status that maps to HTTP 207 elsewhere in the API; a task
    that silently reported 'completed' would let the user trust a wiki with files missing.
    """
    _, _, task_repo, runner, query = temp_env

    def body(ctx):
        ctx.set_total(3)
        ctx.advance(2)
        return {"status": "multi_status", "error_code": "LLM_UNAVAILABLE"}

    task = runner.submit("analyze_deep", body)
    assert runner.wait(task["task_id"], timeout=10)

    progress = query.get_progress(task["task_id"])
    assert progress["status"] == "multi_status"
    assert progress["error_code"] == "LLM_UNAVAILABLE"
    assert progress["processed"] == 2
    assert progress["total"] == 3


def test_body_returning_an_unusable_status_fails_loudly(temp_env):
    """A body that invents a status must not park the task in a state nothing polls for."""
    _, _, task_repo, runner, query = temp_env

    def body(ctx):
        return {"status": "almost_done"}

    task = runner.submit("analyze_deep", body)
    assert runner.wait(task["task_id"], timeout=10)
    assert query.get_progress(task["task_id"])["status"] == "failed"


def test_unknown_task_type_is_rejected_before_a_row_exists(temp_env):
    """A typo'd task_type would otherwise create a task nothing polls for."""
    _, _, task_repo, runner, _ = temp_env
    with pytest.raises(ValueError):
        task_repo.create("analyse_fast")  # British spelling — not in DEC-04's list
    with pytest.raises(ValueError):
        runner.submit("not_a_task_type", lambda ctx: None)


def test_finish_rejects_a_non_terminal_status(temp_env):
    _, _, task_repo, _, _ = temp_env
    task = task_repo.create("scan")
    with pytest.raises(ValueError):
        task_repo.finish(task["task_id"], "running")
    with pytest.raises(ValueError):
        # 'interrupted' is set by boot recovery alone: a process able to write it here would
        # by definition not have been interrupted.
        task_repo.finish(task["task_id"], "interrupted")


# --- Result retrieval (DEC-16: failed[] must survive the 202) ----------------------------


def test_partial_failure_result_is_retrievable_as_207(temp_env):
    """
    The point of result_json: a 202 cannot carry `failed[]`, so it has to be persisted.

    Without this the user would be told the task finished and never learn which files were
    skipped — exactly the silent skip DEC-16 forbids.
    """
    _, _, task_repo, runner, query = temp_env

    def body(ctx):
        ctx.set_total(2)
        ctx.advance(2)
        return {
            "status": "multi_status",
            "result": {
                "status": "multi_status",
                "applied_count": 1,
                "failed": [{"file_id": "abc", "error_code": "PermissionError"}],
            },
        }

    task = runner.submit("rename_apply", body)
    assert runner.wait(task["task_id"], timeout=10)

    outcome = query.get_result(task["task_id"])
    assert outcome["status"] == "multi_status"
    assert outcome["result"]["applied_count"] == 1
    assert outcome["result"]["failed"][0]["file_id"] == "abc"


def test_result_is_none_while_the_task_is_unfinished(temp_env):
    _, _, task_repo, _, query = temp_env
    task = task_repo.create("rename_apply")
    outcome = query.get_result(task["task_id"])
    assert outcome["status"] == "queued"
    assert outcome["result"] is None


def test_result_endpoint_maps_multi_status_to_207(api):
    """A partially failed batch must not read as a plain success (DEC-03)."""
    client, headers, _, app = api
    task = app.state.task_repo.create("rename_apply")
    app.state.task_repo.finish(
        task["task_id"], "multi_status", result={"failed": [{"file_id": "x", "error_code": "OSError"}]}
    )

    res = client.get(f"/api/v1/task/{task['task_id']}/result", headers=headers)
    assert res.status_code == 207
    body = res.json()
    # DEC-03: partial failure is still ok:true with the detail in data.
    assert body["ok"] is True
    assert body["data"]["result"]["failed"][0]["file_id"] == "x"


def test_completed_result_is_200_and_unknown_task_is_404(api):
    client, headers, _, app = api
    task = app.state.task_repo.create("scan")
    app.state.task_repo.finish(task["task_id"], "completed", result={"scanned": 4})

    res = client.get(f"/api/v1/task/{task['task_id']}/result", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["result"]["scanned"] == 4

    missing = client.get(f"/api/v1/task/{uuid.uuid4()}/result", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


def test_corrupt_result_json_does_not_break_the_endpoint(temp_env):
    """A bad blob must degrade to None, not take the result route down with it."""
    db_mgr, _, task_repo, _, query = temp_env
    task = task_repo.create("scan")
    with db_mgr.transaction() as tx:
        tx.execute("UPDATE Async_Task SET result_json = ? WHERE task_id = ?;", ("{not json", task["task_id"]))
    assert query.get_result(task["task_id"])["result"] is None


def test_rename_apply_returns_202_and_persists_the_outcome(api):
    """
    DEC-04 lists rename_apply as a 202 task type; the renamed detail lives in the result.

    A real file is renamed here rather than mocked, because the thing being verified is that
    the async wrapper did not lose the service's output.
    """
    client, headers, tmpdir, app = api
    workdir = os.path.join(tmpdir, "renameables")
    os.makedirs(workdir)
    old_path = os.path.join(workdir, "old_name.txt")
    with open(old_path, "w", encoding="utf-8") as f:
        f.write("x")
    new_path = os.path.join(workdir, "new_name.txt")

    res_ws = client.post(
        "/api/v1/workspace", json={"workspace_name": "RN WS", "root_paths": [workdir]}, headers=headers
    )
    ws_id = res_ws.json()["data"]["workspace_id"]

    scan = client.post(f"/api/v1/workspace/{ws_id}/scan", headers=headers)
    poll_until_done(client, headers, scan.json()["data"]["task_id"])
    files = app.state.scanner_service.file_repo.list_by_workspace(ws_id)
    assert len(files) == 1

    res = client.post(
        f"/api/v1/workspace/{ws_id}/rename/apply",
        json={"items": [{"file_id": files[0]["file_id"], "old_path": files[0]["current_path"], "new_path": new_path}]},
        headers=headers,
    )
    assert res.status_code == 202
    task_id = res.json()["data"]["task_id"]
    assert res.json()["data"]["task_type"] == "rename_apply"

    done = poll_until_done(client, headers, task_id)
    assert done["status"] == "completed"

    outcome = client.get(f"/api/v1/task/{task_id}/result", headers=headers)
    assert outcome.status_code == 200
    result = outcome.json()["data"]["result"]
    assert result["status"] == "applied"
    assert result["applied_count"] == 1
    assert result["failed"] == []
    assert os.path.exists(new_path)


def test_rename_apply_partial_failure_surfaces_as_207(api):
    """A file that vanished before the rename must be reported, not silently dropped."""
    client, headers, tmpdir, app = api
    workdir = os.path.join(tmpdir, "partial")
    os.makedirs(workdir)

    res_ws = client.post(
        "/api/v1/workspace", json={"workspace_name": "RN Partial", "root_paths": [workdir]}, headers=headers
    )
    ws_id = res_ws.json()["data"]["workspace_id"]

    ghost = os.path.join(workdir, "never_existed.txt")
    res = client.post(
        f"/api/v1/workspace/{ws_id}/rename/apply",
        json={"items": [{"file_id": str(uuid.uuid4()), "old_path": ghost, "new_path": ghost + ".renamed"}]},
        headers=headers,
    )
    assert res.status_code == 202
    task_id = res.json()["data"]["task_id"]

    done = poll_until_done(client, headers, task_id)
    assert done["status"] == "multi_status"

    outcome = client.get(f"/api/v1/task/{task_id}/result", headers=headers)
    assert outcome.status_code == 207
    assert outcome.json()["data"]["result"]["failed"][0]["error_code"] == "FILE_NOT_FOUND"


# --- Migration ---------------------------------------------------------------------------


def test_v002_upgrades_an_existing_v001_database_without_data_loss():
    """
    An installed app's DB is already at user_version=1, so v002 must be an upgrade, not a
    fresh-create-only path.

    Building the v001-only state from the real migration file rather than a hand-written
    schema: a copy would drift from what shipped, and then this test would prove nothing about
    the database a user actually has.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "upgrade.db")
        v001_only = os.path.join(tmpdir, "migrations_v001_only")
        os.makedirs(v001_only)
        shutil.copy(os.path.join(MIGRATIONS_DIR, "v001_initial_schema.sql"), v001_only)

        old = DatabaseManager(db_path=db_path, migrations_dir=v001_only)
        try:
            conn = old.get_connection()
            assert conn.execute("PRAGMA user_version;").fetchone()[0] == 1
            assert "result_json" not in [r[1] for r in conn.execute("PRAGMA table_info(Async_Task);")]
            with old.transaction() as tx:
                tx.execute(
                    "INSERT INTO Async_Task (task_id, task_type, status, processed_count) VALUES (?, ?, ?, ?);",
                    ("legacy-task", "scan", "completed", 9),
                )
        finally:
            old.close()

        upgraded = DatabaseManager(db_path=db_path, migrations_dir=MIGRATIONS_DIR)
        try:
            conn = upgraded.get_connection()
            # v003 adds Rename_History.status (issue #90), so the upgraded DB is now at version 3.
            assert conn.execute("PRAGMA user_version;").fetchone()[0] == 3
            assert "result_json" in [r[1] for r in conn.execute("PRAGMA table_info(Async_Task);")]
            row = TaskRepository(upgraded).get("legacy-task")
            assert row["processed_count"] == 9
            assert row["status"] == "completed"
            assert row["result_json"] is None
        finally:
            upgraded.close()


# --- Concurrency ------------------------------------------------------------------------


def test_concurrent_increments_do_not_lose_counts(temp_env):
    """
    `increment_processed` is an in-SQL increment, not read-modify-write.

    Two workers on separate thread-local connections advancing the same task would drop counts
    under read-modify-write. 40 increments must yield exactly 40.
    """
    _, _, task_repo, runner, query = temp_env
    task = task_repo.create("analyze_deep", total_count=40)
    task_repo.mark_running(task["task_id"])
    barrier = threading.Barrier(4)

    def worker():
        repo = TaskRepository(task_repo.db_mgr)
        barrier.wait(timeout=10)
        for _ in range(10):
            repo.increment_processed(task["task_id"])

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert query.get_progress(task["task_id"])["processed"] == 40


def test_two_managers_on_different_paths_do_not_share_a_connection(temp_env):
    """
    Regression guard for a latent DatabaseManager bug.

    `_local` used to be a class attribute, so two managers with different db_path values in
    one thread handed out the same connection and the second silently read and wrote the
    first's database. DEC-04 workers run concurrently, which turns that from latent to active.
    """
    db_mgr, _, _, _, _ = temp_env
    with tempfile.TemporaryDirectory() as other_dir:
        other_path = os.path.join(other_dir, "other.db")
        other = DatabaseManager(db_path=other_path, migrations_dir=MIGRATIONS_DIR)
        try:
            assert db_mgr.get_connection() is not other.get_connection()
            task_in_other = TaskRepository(other).create("scan")
            assert TaskRepository(db_mgr).get(task_in_other["task_id"]) is None
        finally:
            other.close()


def test_release_thread_connection_is_safe_to_call_twice(temp_env):
    """
    Worker threads call this in a `finally`; a double call must not raise.

    Without the release, a worker's sqlite3 connection lives until process exit holding the
    WAL file, which on Windows blocks deleting the database directory (WinError 32).
    """
    db_mgr, _, _, _, _ = temp_env
    db_mgr.get_connection()
    db_mgr.release_thread_connection()
    db_mgr.release_thread_connection()
    # A fresh connection is handed out on demand afterwards.
    assert db_mgr.get_connection() is not None
