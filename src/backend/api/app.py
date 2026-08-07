import secrets
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.backend.api.dtos import (
    ApiResponse,
    InterruptedTaskItemRes,
    InterruptedTaskListRes,
    LlmHealthCheckRes,
    LlmOptionReq,
    RenameDiffRes,
    TaskAcceptedRes,
    TaskProgressRes,
    TaskResultRes,
    WorkspaceCreateReq,
    WorkspaceItemRes,
    WorkspaceListRes,
)
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.task_repository import TaskRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService
from src.backend.services.task_service import TaskQueryService, TaskRunner
from src.backend.services.workspace_service import WorkspaceService


class _LazyVectorStore:
    """
    Defers VectorDBManager construction until a vector operation actually happens.

    Building a Chroma PersistentClient eagerly in create_app would mean every request — and
    every API test that only lists workspaces — pays for opening chroma.sqlite3. Admin mode
    (workspace_id=None) is enough here: workspace deletion only ever calls delete_collection.
    """

    def __init__(self, persist_dir: str):
        self._persist_dir = persist_dir
        self._manager: Optional[Any] = None

    def _ensure(self) -> Any:
        if self._manager is None:
            from src.backend.services.vector_service import VectorDBManager
            self._manager = VectorDBManager(workspace_id=None, persist_dir=self._persist_dir)
        return self._manager

    def delete_collection(self, name: str) -> None:
        self._ensure().delete_collection(name)

    def close(self) -> None:
        if self._manager is not None:
            self._manager.close()
            self._manager = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Release the Chroma client on shutdown so chroma.sqlite3 is not left open."""
    yield
    vector_store = getattr(app.state, "vector_store", None)
    if vector_store is not None:
        vector_store.close()


def create_app(db_mgr: Optional[DatabaseManager] = None, session_token: Optional[str] = None) -> FastAPI:
    app = FastAPI(
        title="CorpBrain IPC API",
        version="1.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    if db_mgr is None:
        db_mgr = DatabaseManager()
    if session_token is None:
        session_token = secrets.token_urlsafe(32)

    app.state.db_mgr = db_mgr
    app.state.session_token = session_token

    ws_repo = WorkspaceRepository(db_mgr)
    file_repo = FileRepository(db_mgr)
    # DEC-09: workspace deletion must drop the Chroma collection before the SQLite row.
    # Without this injection the vector cleanup step was skipped entirely in production, so
    # every deleted workspace left its whole collection behind. Lazy so that merely creating
    # the app (or listing workspaces) does not spin up a Chroma client.
    app.state.vector_store = _LazyVectorStore(db_mgr.vectors_dir)
    app.state.ws_service = WorkspaceService(ws_repo, vector_store=app.state.vector_store)
    app.state.scanner_service = ScannerService(file_repo)
    # DEC-04: long-running commands return 202 + task_id and the frontend polls. State lives
    # in the Async_Task table, never in an in-memory dict — TaskRunner holds threads only.
    app.state.task_repo = TaskRepository(db_mgr)
    app.state.task_runner = TaskRunner(db_mgr, task_repo=app.state.task_repo)
    app.state.task_query_service = TaskQueryService(db_mgr, task_repo=app.state.task_repo)

    # Middleware: Bearer token auth check for all /api/v1/* routes (DEC-02)
    @app.middleware("http")
    async def verify_bearer_token(request: Request, call_next):
        if request.url.path.startswith("/api/v1/") and request.url.path != "/api/v1/health":
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=ApiResponse[None].fail("UNAUTHORIZED", "Missing Bearer token").model_dump(),
                )
            token = auth_header.split(" ", 1)[1]
            if token != app.state.session_token:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=ApiResponse[None].fail("UNAUTHORIZED", "Invalid session token").model_dump(),
                )
        response = await call_next(request)
        return response

    @app.get("/api/v1/health")
    def health():
        return ApiResponse.success({"status": "ok", "app": "CorpBrain"})

    @app.post("/api/v1/workspace", status_code=status.HTTP_201_CREATED)
    def create_workspace(req: WorkspaceCreateReq):
        try:
            ws = app.state.ws_service.create_workspace(req.workspace_name, req.root_paths)
            item = WorkspaceItemRes(**ws)
            return ApiResponse.success(item)
        except FileNotFoundError as e:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", str(e)).model_dump(),
            )
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ApiResponse[None].fail("BAD_REQUEST", str(e)).model_dump(),
            )

    @app.get("/api/v1/workspace")
    def list_workspaces():
        workspaces = app.state.ws_service.list_workspaces()
        items = [WorkspaceItemRes(**ws) for ws in workspaces]
        res = WorkspaceListRes(items=items, total=len(items))
        return ApiResponse.success(res)

    @app.get("/api/v1/workspace/{workspace_id}")
    def get_workspace(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        return ApiResponse.success(WorkspaceItemRes(**ws))

    @app.delete("/api/v1/workspace/{workspace_id}")
    def delete_workspace(workspace_id: str):
        deleted = app.state.ws_service.delete_workspace(workspace_id)
        if not deleted:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        return ApiResponse.success({"deleted": True, "workspace_id": workspace_id})

    # --- API-002: Scan & Analysis Endpoints (DEC-04: 202 + task_id, then poll) ---

    def _accepted(task: Dict[str, Any]) -> JSONResponse:
        """202 + task_id. Progress comes from polling, never from this response (DEC-04)."""
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=ApiResponse.success(TaskAcceptedRes(
                task_id=task["task_id"],
                task_type=task["task_type"],
                status=task["status"],
                workspace_id=task["workspace_id"],
            )).model_dump(),
        )

    def _submit_once(task_type: str, workspace_id: str, body) -> JSONResponse:
        """
        Submit unless an identical task is already live for this workspace.

        SRS §6.2.8 gives the `(workspace_id, task_type)` index the job of "중복 실행 방지": a
        double-clicked button would otherwise run two concurrent scans writing the same
        File_Meta rows. Re-accepting the *existing* task_id keeps this idempotent without
        inventing an error code outside the DEC-03 table — the frontend polls the same task
        either way and cannot tell the difference, which is the correct outcome.

        This is a check-then-act, so two requests arriving in the same instant can both pass.
        The target is a double-clicked button in a single-user desktop app, not concurrent
        clients; closing the window properly needs a uniqueness constraint on the live rows,
        which is a schema migration and out of this task's scope.
        """
        existing = app.state.task_repo.find_active(workspace_id, task_type)
        if existing is not None:
            return _accepted(existing)
        return _accepted(app.state.task_runner.submit(task_type, body, workspace_id=workspace_id))

    @app.post("/api/v1/workspace/{workspace_id}/scan", status_code=status.HTTP_202_ACCEPTED)
    def scan_workspace_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )

        root_path = ws["root_path"]

        def body(ctx):
            records, limit_reached = app.state.scanner_service.scan_workspace(workspace_id, root_path)
            ctx.set_total(len(records))
            ctx.advance(len(records))
            if limit_reached:
                # SCAN-CMD-02: the walk stopped at 10,000 files. The scan itself succeeded, so
                # this is a partial result (DEC-03 207), not a failure — the user needs to
                # know their workspace is larger than what was indexed.
                return {"status": "multi_status", "error_code": "SCAN_LIMIT_REACHED"}
            return {"status": "completed"}

        return _submit_once("scan", workspace_id, body)

    @app.post("/api/v1/workspace/{workspace_id}/analysis/fast", status_code=status.HTTP_202_ACCEPTED)
    def fast_analysis_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )

        def body(ctx):
            from src.backend.services.analysis_service import FastAnalysisService
            fast_service = FastAnalysisService(app.state.scanner_service.file_repo)
            items = fast_service.run_fast_analysis(workspace_id)
            ctx.set_total(len(items))
            ctx.advance(len(items))
            # Scores are persisted to File_Meta.importance_score by the service, so the result
            # is read back from there — DEC-04 forbids returning payloads in a progress
            # response, and the same rule applies to what a task body hands back.
            return {"status": "completed"}

        return _submit_once("analyze_fast", workspace_id, body)

    # --- ANA-QRY-02: Task Progress Polling (DEC-04, 1s intervals) ---

    @app.get("/api/v1/analyze/{task_id}/progress")
    def task_progress_endpoint(task_id: str):
        progress = app.state.task_query_service.get_progress(task_id)
        if progress is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Task {task_id} not found").model_dump(),
            )
        return ApiResponse.success(TaskProgressRes(**progress))

    @app.get("/api/v1/task/{task_id}/result")
    def task_result_endpoint(task_id: str):
        """
        A finished task's outcome, fetched once after polling reports a terminal status.

        Separate from the progress route because that one is polled every second and DEC-04
        forbids putting payloads there. HTTP 207 when the task ended `multi_status`, so a
        partially failed batch never reads as a plain success (DEC-03/DEC-16).
        """
        result = app.state.task_query_service.get_result(task_id)
        if result is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Task {task_id} not found").model_dump(),
            )
        res = ApiResponse.success(TaskResultRes(**result))
        if result["status"] == "multi_status":
            return JSONResponse(status_code=status.HTTP_207_MULTI_STATUS, content=res.model_dump())
        return res

    @app.get("/api/v1/task/interrupted")
    def interrupted_tasks_endpoint(workspace_id: Optional[str] = None):
        """
        Tasks stranded by a crash, so the UI can ask whether to resume.

        DEC-04 forbids auto-resume, which is why this is a query: the answer is a prompt, not
        a restart.
        """
        items = app.state.task_query_service.list_interrupted(workspace_id)
        res = InterruptedTaskListRes(
            items=[InterruptedTaskItemRes(**item) for item in items],
            total=len(items),
        )
        return ApiResponse.success(res)

    # --- API-003: LLM Config, Rename, Watcher, Analytics Endpoints ---

    @app.get("/api/v1/config/llm")
    def get_llm_config():
        # LLM-QRY-01: report the real probe result, never a hardcoded is_healthy (DEC-13).
        from src.backend.services.query_services import LlmQueryService
        health = LlmQueryService(db_mgr).check_health()
        return ApiResponse.success(LlmHealthCheckRes(
            status="ok",
            mode=health["mode"],
            is_healthy=health["status_ok"],
            api_key_configured=health["api_key_configured"],
            daemon_online=health["daemon_online"],
            embedding_model_ready=health["embedding_model_ready"],
            generation_model_ready=health["generation_model_ready"],
            error_code=health["error_code"],
        ))

    @app.post("/api/v1/config/llm")
    def update_llm_config(req: LlmOptionReq):
        from src.backend.config_manager import ConfigManager
        cm = ConfigManager(db_mgr)
        cm.set("llm_mode", req.llm_mode)
        if req.api_key is not None:
            cm.set_api_key(req.api_key)
        return ApiResponse.success({"updated": True, "llm_mode": req.llm_mode})

    @app.post("/api/v1/workspace/{workspace_id}/rename/diff")
    def generate_rename_diff_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.rename_service import RenameService
        files = app.state.scanner_service.file_repo.list_by_workspace(workspace_id)
        rs = RenameService(db_mgr)
        diff_items = rs.process_rename_suggestions(workspace_id, files)
        return ApiResponse.success(RenameDiffRes(workspace_id=workspace_id, items=diff_items))

    def _rename_task_result(res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a RenameService result onto a task outcome.

        RenameService reports 'applied'/'reverted'/'no_history' on success and 'multi_status'
        on partial failure. Only the last of those is a terminal Async_Task status, so the
        successful labels collapse to 'completed' while the service's own status is preserved
        inside `result` — the frontend still sees which operation it was.

        `failed[]` is carried through untouched. It is the reason result_json exists: DEC-16
        requires the per-file failures to reach the user, and a 202 response cannot carry them.
        """
        service_status = res.get("status")
        return {
            "status": "multi_status" if service_status == "multi_status" else "completed",
            "result": res,
        }

    @app.post("/api/v1/workspace/{workspace_id}/rename/apply", status_code=status.HTTP_202_ACCEPTED)
    def apply_rename_endpoint(workspace_id: str, payload: Optional[Dict[str, Any]] = None):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        items = payload.get("items") if payload else None
        history_id = payload.get("history_id") if payload else None

        def body(ctx):
            from src.backend.services.rename_service import RenameService
            res = RenameService(db_mgr).apply_rename(workspace_id, items=items, history_id=history_id)
            total = len(res.get("succeeded", [])) + len(res.get("failed", []))
            ctx.set_total(total)
            ctx.advance(total)
            return _rename_task_result(res)

        # DEC-04 lists rename_apply as a 202 task type. The renamed/failed detail is not lost:
        # it is persisted to result_json and read back from GET /api/v1/task/{id}/result.
        return _submit_once("rename_apply", workspace_id, body)

    @app.post("/api/v1/workspace/{workspace_id}/rename/undo", status_code=status.HTTP_202_ACCEPTED)
    def undo_rename_endpoint(workspace_id: str, payload: Optional[Dict[str, Any]] = None):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        history_id = payload.get("history_id") if payload else None

        def body(ctx):
            from src.backend.services.rename_service import RenameService
            res = RenameService(db_mgr).undo_rename(workspace_id, history_id=history_id)
            total = len(res.get("succeeded", [])) + len(res.get("failed", []))
            ctx.set_total(total)
            ctx.advance(total)
            return _rename_task_result(res)

        return _submit_once("rename_undo", workspace_id, body)

    @app.get("/api/v1/workspace/{workspace_id}/watcher/config")
    def get_watcher_config_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.watcher_service import WatcherService
        if not hasattr(app.state, "watcher_service"):
            app.state.watcher_service = WatcherService(db_mgr, app.state.scanner_service.file_repo)
        cfg = app.state.watcher_service.get_config(workspace_id)
        return ApiResponse.success(cfg)

    @app.post("/api/v1/workspace/{workspace_id}/watcher/config")
    def update_watcher_config_endpoint(workspace_id: str, payload: Dict[str, Any]):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.watcher_service import WatcherService
        if not hasattr(app.state, "watcher_service"):
            app.state.watcher_service = WatcherService(db_mgr, app.state.scanner_service.file_repo)

        mode = payload.get("mode", "manual")
        debounce_ms = payload.get("debounce_ms", 500)
        try:
            cfg = app.state.watcher_service.update_config(workspace_id, mode, debounce_ms=debounce_ms)
            return ApiResponse.success(cfg)
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ApiResponse[None].fail("BAD_REQUEST", str(e)).model_dump(),
            )

    @app.get("/api/v1/workspace/{workspace_id}/watcher/status")
    def get_watcher_status_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.watcher_service import WatcherService
        if not hasattr(app.state, "watcher_service"):
            app.state.watcher_service = WatcherService(db_mgr, app.state.scanner_service.file_repo)

        cfg = app.state.watcher_service.get_config(workspace_id)
        q_size = app.state.watcher_service.queue.qsize()
        return ApiResponse.success({
            "workspace_id": workspace_id,
            "mode": cfg["mode"],
            "is_enabled": bool(cfg["is_enabled"]),
            "queued_items_count": q_size
        })

    # --- Analytics & Statistics Endpoints (STAT-CMD-01 & STAT-QRY-01) ---

    @app.post("/api/v1/workspace/{workspace_id}/analytics/event")
    def log_analytics_event_endpoint(workspace_id: str, payload: Dict[str, Any]):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.analytics_service import AnalyticsService
        svc = AnalyticsService(db_mgr)
        event_type = payload.get("event_type", "deeplink_click")
        file_id = payload.get("file_id")
        wiki_id = payload.get("wiki_id")
        tokens_used = payload.get("tokens_used", 0)
        cost_usd = payload.get("cost_usd")

        res = svc.log_event(
            workspace_id,
            event_type=event_type,
            file_id=file_id,
            wiki_id=wiki_id,
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )
        return ApiResponse.success(res)

    @app.get("/api/v1/workspace/{workspace_id}/analytics/summary")
    def get_analytics_summary_endpoint(
        workspace_id: str,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None
    ):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.analytics_service import AnalyticsService
        svc = AnalyticsService(db_mgr)
        summary = svc.get_analytics_summary(workspace_id, from_time=from_time, to_time=to_time)
        return ApiResponse.success(summary)

    # --- DeepLink Open Endpoint (DL-CMD-02) ---

    @app.post("/api/v1/workspace/{workspace_id}/deeplink/open")
    def deeplink_open_file_endpoint(workspace_id: str, payload: Dict[str, Any]):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        file_id = payload.get("file_id")
        if not file_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ApiResponse[None].fail("INVALID_INPUT", "file_id is required").model_dump(),
            )
        from src.backend.services.deeplink_service import DeepLinkService
        svc = DeepLinkService(db_mgr)
        result = svc.open_file(workspace_id, file_id)
        if result.get("status") == "error":
            code = result.get("error_code", "UNKNOWN")
            http_status = status.HTTP_404_NOT_FOUND if code == "NOT_FOUND" else status.HTTP_422_UNPROCESSABLE_ENTITY
            return JSONResponse(
                status_code=http_status,
                content=ApiResponse[None].fail(code, result.get("message", "")).model_dump(),
            )
        return ApiResponse.success(result)

    # --- DeepLink Query Endpoint (DL-QRY-01) ---

    @app.get("/api/v1/workspace/{workspace_id}/deeplink/status")
    def deeplink_status_endpoint(workspace_id: str, file_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.query_services import DeepLinkQueryService
        svc = DeepLinkQueryService(db_mgr)
        result = svc.check_deeplink_status(workspace_id, file_id)
        return ApiResponse.success(result)

    # --- Scan Query Endpoint (SCAN-QRY-01) ---

    @app.get("/api/v1/workspace/{workspace_id}/scan/summary")
    def scan_summary_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.query_services import ScanQueryService
        svc = ScanQueryService(db_mgr)
        return ApiResponse.success(svc.get_scan_summary(workspace_id))

    # --- Rename Diff Query Endpoint (RN-QRY-01) ---

    @app.get("/api/v1/workspace/{workspace_id}/rename/diff")
    def rename_diff_query_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.query_services import RenameQueryService
        svc = RenameQueryService(db_mgr)
        return ApiResponse.success(svc.get_pending_rename_diff(workspace_id))

    # --- Workspace List & Detail Query Endpoints (WS-QRY-01) ---

    @app.get("/api/v1/workspaces")
    def list_all_workspaces_endpoint():
        from src.backend.services.query_services import WorkspaceQueryService
        svc = WorkspaceQueryService(db_mgr)
        return ApiResponse.success(svc.list_workspaces())

    return app
