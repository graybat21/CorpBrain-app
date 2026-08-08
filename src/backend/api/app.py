import logging
import secrets
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.backend.api.dtos import (
    AnalyticsEventReq,
    AnalyticsEventRes,
    AnalyticsSummaryRes,
    ApiResponse,
    DeepLinkOpenReq,
    DeepLinkOpenRes,
    DeepLinkStatusRes,
    FileItemRes,
    FileListRes,
    HealthRes,
    InterruptedTaskItemRes,
    InterruptedTaskListRes,
    LlmConfigUpdatedRes,
    LlmHealthCheckRes,
    LlmOptionReq,
    PendingRenameDiffItemRes,
    RenameApplyReq,
    RenameDiffRes,
    RenameUndoReq,
    ScanSummaryRes,
    TaskAcceptedRes,
    TaskProgressRes,
    TaskResultRes,
    WatcherConfigReq,
    WatcherConfigRes,
    WatcherStatusRes,
    WikiTabRes,
    WorkspaceCreateReq,
    WorkspaceDeletedRes,
    WorkspaceItemRes,
    WorkspaceListRes,
    WorkspaceWikiRes,
)
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.task_repository import TaskRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService
from src.backend.services.task_service import TaskQueryService, TaskRunner
from src.backend.services.workspace_service import WorkspaceService
from src.backend.utils.logging_setup import configure_logging

logger = logging.getLogger(__name__)

# DEC-03: FastAPI's own HTTPException carries a status code but no error code, so the ones
# raised inside Starlette (404 for an unrouted path, 405 for a wrong method) need mapping onto
# the standard table. Anything unlisted becomes INTERNAL_ERROR rather than a code invented here
# — adding a code requires updating the DEC-03 table in the same change.
_HTTP_STATUS_TO_ERROR_CODE = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_FAILED",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "UNAUTHORIZED",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "NOT_FOUND",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_FAILED",
}


def _install_exception_handlers(app: FastAPI) -> None:
    """
    Normalize every error path onto the DEC-03 envelope.

    Without these, FastAPI answers a validation failure with its own `{"detail": [...]}` and an
    unhandled exception with the plain text `Internal Server Error`. Both bypass the envelope,
    and the second one leaks whatever the exception message holds — which for this app is
    routinely an absolute path (`sqlite3.OperationalError` on `%LocalAppData%\\CorpBrain\\...`)
    or a traceback under a debug server. That is CORE #6 in docs/loop/DECISION_LOG.md.

    The rule these enforce: the response body carries a code and a human-readable message and
    nothing else. Exception text and tracebacks go to the local rolling log via `logger`.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code = _HTTP_STATUS_TO_ERROR_CODE.get(exc.status_code, "INTERNAL_ERROR")
        # `exc.detail` is set by our own code or by Starlette's routing ("Not Found"), never by
        # an exception's str(), so it is safe to surface. A 5xx detail is not — it can carry
        # arbitrary text — so it is logged and replaced.
        if exc.status_code >= 500:
            logger.error("HTTPException %s on %s: %s", exc.status_code, request.url.path, exc.detail)
            message = "요청 처리 중 내부 오류가 발생했습니다."
        else:
            message = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse[None].fail(code, message).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Pydantic's error list, reduced to a field name and a message.

        `exc.errors()` entries can include an `input` value echoing the raw request body, which
        for this app may hold an API key (`POST /api/v1/config/llm`) — DEC-12 forbids putting
        that in a response. Only `loc` and `msg` are copied out.
        """
        errors = exc.errors()
        field = None
        details: Dict[str, Any] = {}
        for err in errors:
            # loc is ('body', 'llm_mode') — drop the source segment to name the field itself.
            parts = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
            name = ".".join(parts) if parts else "request"
            details[name] = err.get("msg", "invalid value")
            if field is None:
                field = name
        first = details.get(field, "요청 값이 유효하지 않습니다.") if field else "요청 값이 유효하지 않습니다."
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ApiResponse[None]
            .fail("VALIDATION_FAILED", first, field=field, details=details)
            .model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """
        Last resort. The exception is logged with its traceback and the client gets a code.

        `str(exc)` is never sent: an OSError stringifies to the absolute path it failed on, and
        DEC-03 forbids absolute internal paths in a response body.
        """
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[None]
            .fail("INTERNAL_ERROR", "요청 처리 중 내부 오류가 발생했습니다.")
            .model_dump(),
        )


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

    # REQ-NF-014 (issue #24): attach the rolling file handler before anything else can fail.
    # Until this call existed every `logger.*` in the codebase went to Python's last-resort
    # stderr handler and was discarded in a windowed exe (DEC-01) — including the
    # unhandled-exception traceback that `_install_exception_handlers` keeps out of the DEC-03
    # response body on the stated grounds that it is "logged locally".
    #
    # Only when this app owns its DatabaseManager: a caller passing one in is a test or an
    # embedding process, and writing into the real %LocalAppData%\CorpBrain\logs from a test
    # run would violate the path isolation REQ-NF-004 asks for.
    if db_mgr is None:
        configure_logging()
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

    # DEC-03: every error leaves through the envelope, including the ones FastAPI raises itself.
    _install_exception_handlers(app)

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

    # Exception handlers: map known exceptions to DEC-03 error codes
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        from src.backend.services.vector_service import EmbeddingModelChangedError

        if isinstance(exc, EmbeddingModelChangedError):
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=ApiResponse[None].fail("EMBEDDING_MODEL_CHANGED", str(exc)).model_dump(),
            )
        # Other unhandled exceptions fall to INTERNAL_ERROR
        import logging
        logger = logging.getLogger("CorpBrain.API")
        logger.exception(f"Unhandled exception: {type(exc).__name__}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ApiResponse[None].fail("INTERNAL_ERROR", "An internal error occurred").model_dump(),
        )

    # Every route carries an explicit response_model. DEC-02 makes the generated OpenAPI schema
    # the contract SSOT, and a route without one contributes an empty `{}` response schema —
    # there is then nothing for the frontend types to be generated from. tests/test_ws_fe_01.py
    # asserts this holds for every /api/v1 route so a new one cannot skip it.
    @app.get("/api/v1/health", response_model=ApiResponse[HealthRes])
    def health():
        return ApiResponse.success(HealthRes(status="ok", app="CorpBrain"))

    @app.post(
        "/api/v1/workspace",
        status_code=status.HTTP_201_CREATED,
        response_model=ApiResponse[WorkspaceItemRes],
    )
    def create_workspace(req: WorkspaceCreateReq):
        try:
            ws = app.state.ws_service.create_workspace(req.workspace_name, req.root_paths)
            item = WorkspaceItemRes(**ws)
            return ApiResponse.success(item)
        except FileNotFoundError as e:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("PATH_NOT_ACCESSIBLE", str(e)).model_dump(),
            )
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ApiResponse[None].fail("VALIDATION_FAILED", str(e)).model_dump(),
            )

    @app.get("/api/v1/workspace", response_model=ApiResponse[WorkspaceListRes])
    def list_workspaces():
        workspaces = app.state.ws_service.list_workspaces()
        items = [WorkspaceItemRes(**ws) for ws in workspaces]
        res = WorkspaceListRes(items=items, total=len(items))
        return ApiResponse.success(res)

    @app.get("/api/v1/workspace/{workspace_id}", response_model=ApiResponse[WorkspaceItemRes])
    def get_workspace(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        return ApiResponse.success(WorkspaceItemRes(**ws))

    @app.delete("/api/v1/workspace/{workspace_id}", response_model=ApiResponse[WorkspaceDeletedRes])
    def delete_workspace(workspace_id: str):
        deleted = app.state.ws_service.delete_workspace(workspace_id)
        if not deleted:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        return ApiResponse.success(WorkspaceDeletedRes(deleted=True, workspace_id=workspace_id))

    # --- File List Query (WS-FE-01 / ANA-FE-01) ---

    @app.get("/api/v1/workspace/{workspace_id}/file", response_model=ApiResponse[FileListRes])
    def list_workspace_files(workspace_id: str):
        """
        The scanned files of a workspace, with their fast-analysis importance scores.

        `FileRepository.list_by_workspace` already existed but was reachable only from inside
        the service layer, so the dashboard and the file explorer had no way to show anything
        (issue #91: "대시보드는 항상 0을 표시한다"). Path is singular per DEC-03.

        Unpaginated on purpose: SCAN-CMD-02 caps a workspace at 10,000 files, and the UI needs
        the full set to compute its own score histogram. If that cap ever rises, this needs a
        limit/offset before it needs anything else.
        """
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        rows = app.state.scanner_service.file_repo.list_by_workspace(workspace_id)
        # Field-by-field rather than **row: File_Meta rows carry original_path, which DEC-08
        # keeps as audit-only data. Constructing explicitly means a future column cannot leak
        # into the response just by being added to the table.
        items: List[FileItemRes] = [
            FileItemRes(
                file_id=r["file_id"],
                workspace_id=r["workspace_id"],
                file_name=r["file_name"],
                extension=r["extension"],
                current_path=r["current_path"],
                size_bytes=r["size_bytes"],
                last_modified=r["last_modified"],
                parse_status=r["parse_status"],
                importance_score=r["importance_score"] or 0,
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
        return ApiResponse.success(FileListRes(workspace_id=workspace_id, items=items, total=len(items)))

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

    @app.post(
        "/api/v1/workspace/{workspace_id}/scan",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ApiResponse[TaskAcceptedRes],
    )
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

    @app.post(
        "/api/v1/workspace/{workspace_id}/analysis/fast",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ApiResponse[TaskAcceptedRes],
    )
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

    @app.get("/api/v1/analyze/{task_id}/progress", response_model=ApiResponse[TaskProgressRes])
    def task_progress_endpoint(task_id: str):
        progress = app.state.task_query_service.get_progress(task_id)
        if progress is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Task {task_id} not found").model_dump(),
            )
        return ApiResponse.success(TaskProgressRes(**progress))

    @app.get("/api/v1/task/{task_id}/result", response_model=ApiResponse[TaskResultRes])
    def task_result_endpoint(task_id: str):
        """
        A finished task's outcome, fetched once after polling reports a terminal status.

        Separate from the progress route because that one is polled every second and DEC-04
        forbids putting payloads there. HTTP 207 when any files failed, so a partially failed
        batch never reads as a plain success (DEC-03/DEC-16).

        Issue #89: the 207 decision now comes from the presence of `failed[]` in result_json,
        not from a string label. Services may use different internal status labels
        ('completed', 'applied', 'reverted') and that's fine — what matters for the HTTP
        status is whether any file failed.
        """
        result = app.state.task_query_service.get_result(task_id)
        if result is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Task {task_id} not found").model_dump(),
            )
        res = ApiResponse.success(TaskResultRes(**result))
        # HTTP 207 if any files failed, regardless of the internal status label (issue #89).
        # result["result"] is the parsed result_json from TaskRepository.get_result().
        result_payload = result.get("result") or {}
        if isinstance(result_payload, dict) and result_payload.get("failed"):
            return JSONResponse(status_code=status.HTTP_207_MULTI_STATUS, content=res.model_dump())
        return res

    @app.get("/api/v1/task/interrupted", response_model=ApiResponse[InterruptedTaskListRes])
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

    @app.get("/api/v1/config/llm", response_model=ApiResponse[LlmHealthCheckRes])
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

    @app.post("/api/v1/config/llm", response_model=ApiResponse[LlmConfigUpdatedRes])
    def update_llm_config(req: LlmOptionReq):
        from src.backend.config_manager import ConfigManager
        from src.backend.utils.security import SecretStorageUnavailableError
        cm = ConfigManager(db_mgr)
        cm.set("llm_mode", req.llm_mode)
        if req.api_key is not None:
            try:
                cm.set_api_key(req.api_key)
            except SecretStorageUnavailableError as exc:
                # Only reachable on a non-Windows development host: DEC-12 storage is DPAPI and
                # there is no fallback (a reversible one would be plaintext at rest). Mapped
                # explicitly so the developer sees the actual reason instead of the generic
                # INTERNAL_ERROR the catch-all handler would return. `str(exc)` is safe here —
                # the message is a fixed string naming the platform, with no path or key in it.
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content=ApiResponse[None].fail("INTERNAL_ERROR", str(exc)).model_dump(),
                )
        # DEC-12: the key is never echoed back, not even masked.
        return ApiResponse.success(LlmConfigUpdatedRes(updated=True, llm_mode=req.llm_mode))

    @app.post("/api/v1/workspace/{workspace_id}/rename/diff", response_model=ApiResponse[RenameDiffRes])
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
        # history_id comes back with the items because DEC-08 keeps absolute paths off the
        # client: the frontend applies a diff by handing this id back, not by sending paths.
        diff = rs.generate_rename_diff(workspace_id, files)
        return ApiResponse.success(RenameDiffRes(
            workspace_id=workspace_id,
            items=diff["items"],
            history_id=diff["history_id"],
        ))

    def _rename_task_result(res: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a RenameService result onto a task outcome.

        RenameService reports 'applied'/'reverted'/'no_history'/'multi_status'. Issue #89:
        all of these map to Async_Task.status='completed' (the task finished), and the
        service's own status is preserved inside `result` so the frontend can distinguish them.

        HTTP 207 is decided by the presence of `failed[]` in get_task_result_endpoint, not by
        this status label. `failed[]` is carried through untouched — DEC-16 requires per-file
        failures to reach the user, and a 202 response cannot carry them.
        """
        return {
            "status": "completed",
            "result": res,
        }

    @app.post(
        "/api/v1/workspace/{workspace_id}/rename/apply",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ApiResponse[TaskAcceptedRes],
    )
    def apply_rename_endpoint(workspace_id: str, payload: Optional[RenameApplyReq] = None):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        # RenameService takes plain dicts; dumping the validated models keeps the DTO boundary
        # at the API layer instead of pushing Pydantic into the service (CLAUDE.md §4).
        items = [item.model_dump() for item in payload.items] if payload and payload.items else None
        history_id = payload.history_id if payload else None

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

    @app.post(
        "/api/v1/workspace/{workspace_id}/rename/undo",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ApiResponse[TaskAcceptedRes],
    )
    def undo_rename_endpoint(workspace_id: str, payload: Optional[RenameUndoReq] = None):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        history_id = payload.history_id if payload else None

        def body(ctx):
            from src.backend.services.rename_service import RenameService
            res = RenameService(db_mgr).undo_rename(workspace_id, history_id=history_id)
            total = len(res.get("succeeded", [])) + len(res.get("failed", []))
            ctx.set_total(total)
            ctx.advance(total)
            return _rename_task_result(res)

        return _submit_once("rename_undo", workspace_id, body)

    # --- Wiki Generation Endpoint (ANA-CMD-03) ---

    @app.post(
        "/api/v1/workspace/{workspace_id}/wiki/generate",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ApiResponse[TaskAcceptedRes],
    )
    def generate_wiki_endpoint(workspace_id: str):
        """
        Generate wiki markdown documents for all folders in a workspace (ANA-CMD-03).

        DEC-04: Returns 202 + task_id. Frontend polls for progress.
        """
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )

        def body(ctx):
            from src.backend.services.wiki_service import WikiGenerationService
            svc = WikiGenerationService(db_mgr)
            result = svc.generate_wiki_for_workspace(workspace_id)
            ctx.set_total(result["succeeded_count"] + len(result["failed"]))
            ctx.advance(result["succeeded_count"] + len(result["failed"]))
            return result

        return _submit_once("wiki_generate", workspace_id, body)

    def _watcher_config_res(cfg: Dict[str, Any]) -> WatcherConfigRes:
        # is_enabled is stored as SQLite INTEGER 0/1; the DTO exposes a real bool so the
        # frontend does not end up with a truthiness check on a number (DEC-03).
        return WatcherConfigRes(
            workspace_id=cfg["workspace_id"],
            mode=cfg["mode"],
            is_enabled=bool(cfg["is_enabled"]),
            debounce_ms=cfg["debounce_ms"],
        )

    @app.get("/api/v1/workspace/{workspace_id}/watcher/config", response_model=ApiResponse[WatcherConfigRes])
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
        return ApiResponse.success(_watcher_config_res(cfg))

    @app.post("/api/v1/workspace/{workspace_id}/watcher/config", response_model=ApiResponse[WatcherConfigRes])
    def update_watcher_config_endpoint(workspace_id: str, payload: WatcherConfigReq):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.watcher_service import WatcherService
        if not hasattr(app.state, "watcher_service"):
            app.state.watcher_service = WatcherService(db_mgr, app.state.scanner_service.file_repo)

        try:
            cfg = app.state.watcher_service.update_config(
                workspace_id, payload.mode, debounce_ms=payload.debounce_ms
            )
            return ApiResponse.success(_watcher_config_res(cfg))
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ApiResponse[None].fail("VALIDATION_FAILED", str(e), field="mode").model_dump(),
            )

    @app.get("/api/v1/workspace/{workspace_id}/watcher/status", response_model=ApiResponse[WatcherStatusRes])
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
        return ApiResponse.success(WatcherStatusRes(
            workspace_id=workspace_id,
            mode=cfg["mode"],
            is_enabled=bool(cfg["is_enabled"]),
            queued_items_count=q_size,
        ))

    # --- Analytics & Statistics Endpoints (STAT-CMD-01 & STAT-QRY-01) ---

    @app.post("/api/v1/workspace/{workspace_id}/analytics/event", response_model=ApiResponse[AnalyticsEventRes])
    def log_analytics_event_endpoint(workspace_id: str, payload: AnalyticsEventReq):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.analytics_service import AnalyticsService
        svc = AnalyticsService(db_mgr)
        res = svc.log_event(
            workspace_id,
            event_type=payload.event_type,
            file_id=payload.file_id,
            wiki_id=payload.wiki_id,
            tokens_used=payload.tokens_used,
            cost_usd=payload.cost_usd
        )
        return ApiResponse.success(AnalyticsEventRes(**res))

    @app.get("/api/v1/workspace/{workspace_id}/analytics/summary", response_model=ApiResponse[AnalyticsSummaryRes])
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
        return ApiResponse.success(AnalyticsSummaryRes(**summary))

    # --- DeepLink Open Endpoint (DL-CMD-02) ---

    @app.post("/api/v1/workspace/{workspace_id}/deeplink/open", response_model=ApiResponse[DeepLinkOpenRes])
    def deeplink_open_file_endpoint(workspace_id: str, payload: DeepLinkOpenReq):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.deeplink_service import DeepLinkService
        svc = DeepLinkService(db_mgr)
        # DEC-08: only file_id crosses the wire; the path is resolved server-side from File_Meta.
        result = svc.open_file(workspace_id, payload.file_id)
        if result.get("status") == "error":
            code = result.get("error_code", "INTERNAL_ERROR")
            http_status = status.HTTP_404_NOT_FOUND if code == "NOT_FOUND" else status.HTTP_422_UNPROCESSABLE_ENTITY
            return JSONResponse(
                status_code=http_status,
                content=ApiResponse[None].fail(code, result.get("message", "")).model_dump(),
            )
        return ApiResponse.success(DeepLinkOpenRes(**result))

    # --- DeepLink Query Endpoint (DL-QRY-01) ---

    @app.get("/api/v1/workspace/{workspace_id}/deeplink/status", response_model=ApiResponse[DeepLinkStatusRes])
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
        return ApiResponse.success(DeepLinkStatusRes(**result))

    # --- Scan Query Endpoint (SCAN-QRY-01) ---

    @app.get("/api/v1/workspace/{workspace_id}/scan/summary", response_model=ApiResponse[ScanSummaryRes])
    def scan_summary_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.query_services import ScanQueryService
        svc = ScanQueryService(db_mgr)
        return ApiResponse.success(ScanSummaryRes(**svc.get_scan_summary(workspace_id)))

    # --- Rename Diff Query Endpoint (RN-QRY-01) ---

    @app.get(
        "/api/v1/workspace/{workspace_id}/rename/diff",
        response_model=ApiResponse[List[PendingRenameDiffItemRes]],
    )
    def rename_diff_query_endpoint(workspace_id: str):
        """
        The persisted `pending` diff, as opposed to POST on the same path which generates one.

        Known 500 — issue #90: the query reads a `Rename_History.status` column that the schema
        does not have. The route is typed here so the contract is in the OpenAPI schema, but the
        frontend must not depend on it until #90 lands; RenamePage uses the POST form instead.
        """
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.query_services import RenameQueryService
        svc = RenameQueryService(db_mgr)
        items = svc.get_pending_rename_diff(workspace_id)
        return ApiResponse.success([PendingRenameDiffItemRes(**item) for item in items])

    # --- Workspace List & Detail Query Endpoints (WS-QRY-01) ---

    @app.get("/api/v1/workspaces", response_model=ApiResponse[WorkspaceListRes])
    def list_all_workspaces_endpoint():
        """
        Duplicate of GET /api/v1/workspace, kept because WS-QRY-01 registered this path.

        DEC-03 mandates singular resource paths, so the plural form is the deprecated one: it
        now returns the same WorkspaceListRes envelope rather than a bare array, so a client
        cannot come to depend on a second, differently-shaped response. New callers use the
        singular path.
        """
        from src.backend.services.query_services import WorkspaceQueryService
        svc = WorkspaceQueryService(db_mgr)
        items = [WorkspaceItemRes(**ws) for ws in svc.list_workspaces()]
        return ApiResponse.success(WorkspaceListRes(items=items, total=len(items)))

    # --- Embedding Model Change Consent & Re-embedding (DEC-06 AC S3) ---

    @app.post(
        "/api/v1/workspace/{workspace_id}/reembed",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ApiResponse[TaskAcceptedRes],
    )
    def reembed_workspace_endpoint(workspace_id: str, consent_model: str, consent_dim: int):
        """
        User consent to drop the workspace's vector collection and re-analyze all files with
        the current embedding model. DEC-04: returns 202 + task_id, client polls for progress.

        Args:
            workspace_id: target workspace
            consent_model: user-confirmed target model name (must match App_Config)
            consent_dim: user-confirmed target dimension (must match App_Config)

        Returns:
            202 + task_id if consent token is valid and task is submitted
            409 EMBEDDING_MODEL_CHANGED if token is stale/mismatched
            404 NOT_FOUND if workspace does not exist
        """
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )

        consent_token = f"granted:{consent_model}:{consent_dim}"

        def reembed_body(ctx):
            from src.backend.config_manager import ConfigManager
            from src.backend.services.vector_service import DeepAnalysisService, VectorDBManager

            # Reset collection (consent is checked inside this call)
            v_db = VectorDBManager(workspace_id=workspace_id, persist_dir=db_mgr.vectors_dir, config_mgr=ConfigManager(db_mgr))
            v_db.reset_workspace_for_reembedding(consent_token)
            v_db.close()

            # Reset all File_Meta rows to pending (DEC-16: no separate retry queue)
            conn = db_mgr.get_connection()
            conn.execute("UPDATE File_Meta SET parse_status = 'pending' WHERE workspace_id = ?;", (workspace_id,))
            conn.commit()

            # Run full deep analysis
            service = DeepAnalysisService(db_mgr)
            batch_result = service.run_deep_analysis_batch(workspace_id)
            return {"batch_result": batch_result}

        task = app.state.task_runner.submit("reembed", reembed_body, workspace_id=workspace_id, total_count=0)
        return _accepted(task)

    # --- Wiki Query Endpoint (ANA-QRY-01) ---

    @app.get("/api/v1/workspace/{workspace_id}/wiki", response_model=ApiResponse[WorkspaceWikiRes])
    def get_workspace_wiki_endpoint(workspace_id: str):
        """
        Return all wiki tabs for a workspace (issue #7 / ANA-QRY-01).

        Each tab corresponds to one folder_1depth row in Wiki_Content. The frontend renders
        these as separate tabs in the wiki viewer (ANA-FE-02). Markdown content includes
        [[file_id:<UUID>]] anchors (DEC-08), which the frontend replaces with clickable badges.

        Depends on: ANA-CMD-03 (wiki generation) must have run first, otherwise tabs=[].
        """
        from src.backend.services.query_services import WikiQueryService
        svc = WikiQueryService(db_mgr)
        tabs = [WikiTabRes(**t) for t in svc.get_workspace_wiki(workspace_id)]
        return ApiResponse.success(WorkspaceWikiRes(workspace_id=workspace_id, tabs=tabs))

    return app
