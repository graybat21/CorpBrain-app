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
    """
    Body of the 202 returned by every long-running command (DEC-04).

    Carries the task_id and nothing else useful — progress comes from polling
    GET /api/v1/analyze/{task_id}/progress at 1s intervals, not from this response.
    """
    task_id: str
    task_type: str
    status: str = "queued"
    workspace_id: Optional[str] = None


class TaskProgressRes(BaseModel):
    task_id: str
    task_type: str
    status: str
    processed: int
    total: int
    percent: float
    eta_sec: Optional[int] = None
    # DEC-03: the code only. error_message stays in the DB and the local log because it can
    # hold an exception string containing an absolute internal path.
    error_code: Optional[str] = None
    workspace_id: Optional[str] = None


class TaskResultRes(BaseModel):
    """
    A finished task's outcome, fetched once after polling sees a terminal status.

    Kept out of TaskProgressRes because DEC-04 forbids returning large payloads from a
    response that is polled every second.
    """
    task_id: str
    task_type: str
    status: str
    error_code: Optional[str] = None
    # None while the task is still running. For a partially failed batch this is where
    # `failed[]` lives (DEC-16) — the 202 response could not carry it.
    result: Optional[Dict[str, Any]] = None
    workspace_id: Optional[str] = None


class InterruptedTaskItemRes(BaseModel):
    """A task stranded by a crash, offered to the user for resume (DEC-04 — never automatic)."""
    task_id: str
    task_type: str
    status: str
    processed: int
    total: int
    created_at: str
    workspace_id: Optional[str] = None


class InterruptedTaskListRes(BaseModel):
    items: List[InterruptedTaskItemRes]
    total: int


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
