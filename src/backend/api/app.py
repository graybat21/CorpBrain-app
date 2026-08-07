import secrets
from typing import Any, Dict, Optional
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

    @app.post("/api/v1/workspace/{workspace_id}/rename/apply")
    def apply_rename_endpoint(workspace_id: str, payload: Optional[Dict[str, Any]] = None):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.rename_service import RenameService
        rs = RenameService(db_mgr)
        items = payload.get("items") if payload else None
        history_id = payload.get("history_id") if payload else None
        res = rs.apply_rename(workspace_id, items=items, history_id=history_id)
        
        if res.get("status") == "multi_status":
            return JSONResponse(
                status_code=status.HTTP_207_MULTI_STATUS,
                content=ApiResponse.success(res).model_dump()
            )
        return ApiResponse.success(res)

    @app.post("/api/v1/workspace/{workspace_id}/rename/undo")
    def undo_rename_endpoint(workspace_id: str, payload: Optional[Dict[str, Any]] = None):
        ws = app.state.ws_service.get_workspace(workspace_id)
        if not ws:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=ApiResponse[None].fail("NOT_FOUND", f"Workspace {workspace_id} not found").model_dump(),
            )
        from src.backend.services.rename_service import RenameService
        rs = RenameService(db_mgr)
        history_id = payload.get("history_id") if payload else None
        res = rs.undo_rename(workspace_id, history_id=history_id)
        
        if res.get("status") == "multi_status":
            return JSONResponse(
                status_code=status.HTTP_207_MULTI_STATUS,
                content=ApiResponse.success(res).model_dump()
            )
        return ApiResponse.success(res)

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
