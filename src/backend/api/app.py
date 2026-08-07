import secrets
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from src.backend.api.dtos import (
    ApiResponse,
    FastAnalysisRes,
    LlmHealthCheckRes,
    LlmOptionReq,
    RenameDiffRes,
    ScanProgressRes,
    WorkspaceCreateReq,
    WorkspaceItemRes,
    WorkspaceListRes,
)
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.scanner_service import ScannerService
from src.backend.services.workspace_service import WorkspaceService


def create_app(db_mgr: Optional[DatabaseManager] = None, session_token: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="CorpBrain IPC API", version="1.1.0", docs_url="/docs", redoc_url=None)

    if db_mgr is None:
        db_mgr = DatabaseManager()
    if session_token is None:
        session_token = secrets.token_urlsafe(32)

    app.state.db_mgr = db_mgr
    app.state.session_token = session_token

    ws_repo = WorkspaceRepository(db_mgr)
    file_repo = FileRepository(db_mgr)
    app.state.ws_service = WorkspaceService(ws_repo)
    app.state.scanner_service = ScannerService(file_repo)

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

    # --- API-002: Scan & Analysis Endpoints ---

    @app.post("/api/v1/workspace/{workspace_id}/scan")
    def scan_workspace_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        records, limit_reached = app.state.scanner_service.scan_workspace(workspace_id, ws["root_path"])
        res = ScanProgressRes(workspace_id=workspace_id, scanned_count=len(records), limit_reached=limit_reached)
        return ApiResponse.success(res)

    @app.post("/api/v1/workspace/{workspace_id}/analysis/fast")
    def fast_analysis_endpoint(workspace_id: str):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.analysis_service import FastAnalysisService
        fast_service = FastAnalysisService(app.state.scanner_service.file_repo)
        items = fast_service.run_fast_analysis(workspace_id)
        return ApiResponse.success(FastAnalysisRes(workspace_id=workspace_id, items=items))

    # --- API-003: LLM Config, Rename, Watcher, Analytics Endpoints ---

    @app.get("/api/v1/config/llm")
    def get_llm_config():
        from src.backend.config_manager import ConfigManager
        cm = ConfigManager(db_mgr)
        return ApiResponse.success(LlmHealthCheckRes(
            status="ok",
            mode=cm.get("llm_mode", "Option A"),
            is_healthy=True
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

    return app
