from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: Optional[T] = None
    error: Optional[ApiError] = None

    @classmethod
    def success(cls, data: T) -> "ApiResponse[T]":
        return cls(ok=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str) -> "ApiResponse[T]":
        return cls(ok=False, data=None, error=ApiError(code=code, message=message))


class WorkspaceCreateReq(BaseModel):
    workspace_name: str = Field(..., min_length=1, description="Workspace name")
    root_paths: List[str] = Field(..., min_length=1, description="List of root folder paths")

    @field_validator("root_paths")
    @classmethod
    def validate_paths(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("root_paths cannot be empty")
        for path in v:
            if not path or not path.strip():
                raise ValueError("path elements cannot be empty string")
        return v


class WorkspaceItemRes(BaseModel):
    workspace_id: str
    workspace_name: str
    root_path: str
    created_at: str
    updated_at: str


class WorkspaceListRes(BaseModel):
    items: List[WorkspaceItemRes]
    total: int


# --- API-002: Analysis & Task DTOs ---

class TaskAcceptedRes(BaseModel):
    task_id: str
    status: str = "pending"


class TaskProgressRes(BaseModel):
    task_id: str
    status: str
    processed: int
    total: int
    percent: float
    eta_sec: Optional[int] = None
    error_code: Optional[str] = None


class ScanProgressRes(BaseModel):
    workspace_id: str
    scanned_count: int
    limit_reached: bool


class FastAnalysisRes(BaseModel):
    workspace_id: str
    items: List[Dict[str, Any]]


class WikiMarkdownRes(BaseModel):
    wiki_id: str
    workspace_id: str
    folder_1depth: str
    markdown_content: str


# --- API-003: LLM, Rename, Watcher, Analytics DTOs ---

class LlmOptionReq(BaseModel):
    llm_mode: str = Field(..., description="Option A (Cloud) or Option B (Local)")
    api_key: Optional[str] = None

    @field_validator("llm_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("Option A", "Option B"):
            raise ValueError("llm_mode must be 'Option A' or 'Option B'")
        return v


class LlmHealthCheckRes(BaseModel):
    status: str
    mode: str
    is_healthy: bool
    # DEC-13: daemon reachability and per-model presence are reported separately —
    # a live daemon with no models still cannot run analysis, so these are never merged.
    api_key_configured: bool = False
    daemon_online: bool = False
    embedding_model_ready: bool = False
    generation_model_ready: bool = False
    error_code: Optional[str] = None


class RenameDiffRes(BaseModel):
    workspace_id: str
    items: List[Dict[str, Any]]


class RenameApplyReq(BaseModel):
    workspace_id: str
    apply_all: bool = True


class WatcherStatusRes(BaseModel):
    workspace_id: str
    is_enabled: bool
    debounce_ms: int


class WatcherConfigReq(BaseModel):
    workspace_id: str
    is_enabled: bool
    debounce_ms: int = 500


class AnalyticsDashboardRes(BaseModel):
    workspace_id: str
    total_files: int
    total_wikis: int
    total_tokens: int
    total_cost_usd: float
