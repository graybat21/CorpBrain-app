from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    # DEC-03 lists `field?` and `details?` as part of the error object. `field` names the
    # offending request field on a validation failure; `details` carries per-field messages.
    # Neither ever holds a stack trace or an absolute internal path — those go to the local log.
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: Optional[T] = None
    error: Optional[ApiError] = None

    @classmethod
    def success(cls, data: T) -> "ApiResponse[T]":
        return cls(ok=True, data=data, error=None)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> "ApiResponse[T]":
        return cls(
            ok=False,
            data=None,
            error=ApiError(code=code, message=message, field=field, details=details),
        )


class HealthRes(BaseModel):
    status: str
    app: str


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
    # Every merged root, in selection order (issue #105). The v001 single `root_path` field is
    # gone rather than retained alongside this list: two representations of the same fact drift,
    # and a consumer reading only the scalar is how multi-folder merging silently stopped working.
    root_paths: List[str]
    created_at: str
    updated_at: str


class WorkspaceListRes(BaseModel):
    items: List[WorkspaceItemRes]
    total: int


class WorkspaceDeletedRes(BaseModel):
    deleted: bool
    workspace_id: str


class FileItemRes(BaseModel):
    """
    One File_Meta row as the UI consumes it.

    `original_path` is deliberately absent. DEC-08 makes it immutable audit data and requires
    every open/existence check to go through `current_path`; not shipping it to the frontend
    removes the possibility of a component picking the stale one.
    """
    file_id: str
    workspace_id: str
    file_name: str
    extension: str
    current_path: str
    size_bytes: int
    last_modified: float
    parse_status: str
    importance_score: int
    created_at: str
    updated_at: str


class FileListRes(BaseModel):
    workspace_id: str
    items: List[FileItemRes]
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
    # Human-readable current step (issue #29). Provisioning's steps are not interchangeable
    # units, so a counter alone cannot say which model is downloading (DEC-13). None for the
    # per-file tasks. Never carries a document path or content (REQ-NF-005).
    progress_message: Optional[str] = None
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


class ScanSummaryRes(BaseModel):
    """SCAN-QRY-01. `estimated_analysis_seconds` is an estimate from measured throughput."""
    workspace_id: str
    file_count: int
    total_size_mb: float
    estimated_analysis_seconds: float


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


class LlmOnboardReq(BaseModel):
    """
    LLM-CMD-03 / DEC-13: which role is being provisioned.

    `embedding` needs only `nomic-embed-text` (~274MB) — required by **every** user including
    Option A (DEC-06). `generation` additionally needs `qwen2.5:7b-instruct` (~4.7GB), Option B
    only. The two are never presented as one bundled download, so the caller must say which.
    """
    purpose: str = Field(..., description="'embedding' or 'generation'")

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        if v not in ("embedding", "generation"):
            raise ValueError("purpose must be 'embedding' or 'generation'")
        return v


class LlmConfigUpdatedRes(BaseModel):
    """
    DEC-12: only the mode is echoed back. The API key — even partially masked — is never in a
    response body; `GET /api/v1/config/llm` reports `api_key_configured: bool` instead.
    """
    updated: bool
    llm_mode: str


class RenameDiffItemRes(BaseModel):
    """
    One row of the rename diff.

    Names only, never paths: DEC-17 keeps absolute paths out of anything that reaches the LLM,
    and DEC-08 keeps them out of anything cached client-side. `status` is one of
    `pending` / `PII_TOKEN_LEFT` / `PII_MASKING_FAILED` / `INVALID_FILENAME` / `LLM_FAILED`;
    anything other than `pending` means the file is excluded from the batch and needs manual
    review.

    `LLM_FAILED` (issue #37) is the DEC-16 partial-failure case: the suggestion call was retried
    and gave up, so this one file keeps its original name while the rest of the batch proceeds.
    It is a per-item status, not an error envelope — the request itself succeeded.
    """
    file_id: str
    old_name: str
    new_name: str
    status: str
    note: str


class RenameDiffRes(BaseModel):
    workspace_id: str
    items: List[RenameDiffItemRes]
    # The Rename_History row this diff was persisted as. The client applies the diff by
    # returning this id: DEC-08 keeps absolute paths off the client, so it cannot build the
    # path pairs `apply_rename` needs. None when no file produced a `pending` suggestion.
    history_id: Optional[str] = None


class PendingRenameDiffItemRes(BaseModel):
    """
    RN-QRY-01: a persisted `pending` diff row, as opposed to a freshly generated one.

    Known broken — `RenameQueryService.get_pending_rename_diff` queries a `Rename_History.status`
    column that does not exist (issue #90). Typed here anyway so the contract the fix must
    satisfy is in the OpenAPI schema rather than only in that issue's body.
    """
    file_id: Optional[str] = None
    old_name: str
    new_name: Optional[str] = None
    history_id: str
    status: str


class RenameApplyItemReq(BaseModel):
    """
    One rename to perform. Paths here are server-side state echoed back from the diff, not
    user input: `apply_rename` refuses anything whose `old_path` is absent from disk.
    """
    file_id: str
    old_path: str
    new_path: str


class RenameApplyReq(BaseModel):
    items: Optional[List[RenameApplyItemReq]] = None
    history_id: Optional[str] = None
    # AC S2 (issue #40): apply only these files out of the batch. `None` means "all of them",
    # which keeps every existing caller working.
    #
    # `file_id`s, never paths: DEC-08 keeps absolute paths off the client, so the frontend cannot
    # name a file any other way — and accepting a caller-supplied path here would be the exact
    # hole DEC-08 closes. The server intersects these ids with the history row it already holds.
    file_ids: Optional[List[str]] = None


class RenameUndoReq(BaseModel):
    history_id: Optional[str] = None


class WatcherConfigRes(BaseModel):
    workspace_id: str
    mode: str
    is_enabled: bool
    debounce_ms: int


class WatcherConfigReq(BaseModel):
    mode: str = "manual"
    debounce_ms: int = 500


class WatcherStatusRes(BaseModel):
    workspace_id: str
    mode: str
    is_enabled: bool
    queued_items_count: int


class AnalyticsEventReq(BaseModel):
    event_type: str = "deeplink_click"
    file_id: Optional[str] = None
    wiki_id: Optional[str] = None
    tokens_used: int = 0
    # DEC-16: 0 means "no cost" (Option B), null means "not measured". The service applies that
    # distinction, so this stays Optional rather than defaulting to 0.0.
    cost_usd: Optional[float] = None


class AnalyticsEventRes(BaseModel):
    log_id: str
    workspace_id: str
    event_type: str
    file_id: Optional[str] = None
    wiki_id: Optional[str] = None
    tokens_used: int
    cost_usd: Optional[float] = None


class AnalyticsPeriodRes(BaseModel):
    """DEC-11: caller-supplied UTC instants, echoed back. The backend never infers a boundary."""
    from_time: Optional[str] = None
    to_time: Optional[str] = None


class AnalyticsSummaryRes(BaseModel):
    workspace_id: str
    period: AnalyticsPeriodRes
    saved_time_minutes: float
    total_tokens_used: int
    total_cost_usd: float
    deeplink_clicks_count: int
    watcher_updates_count: int
    compression_ratio: str
    knowledge_ratio_scope: str


class DeepLinkOpenReq(BaseModel):
    """DEC-08: `file_id` only. A caller-supplied path is never accepted."""
    file_id: str = Field(..., min_length=1)


class DeepLinkOpenRes(BaseModel):
    """
    DL-CMD-02 success. Carries the file *name*, never its path (issue #19).

    `opened_path` used to be here and was a full absolute path — the one thing DEC-08 keeps off
    the client, returned on the happy path of the very feature DEC-08 exists for. No frontend
    consumer ever read it; a name is what a UI can legitimately display.
    """
    status: str
    file_id: str
    file_name: str


class DeepLinkStatusRes(BaseModel):
    """
    DL-QRY-01. `is_broken` is true when the row's `current_path` is missing from disk, or when
    the file_id has no row at all — in which case `file_name`/`current_path` are null.
    """
    file_id: str
    is_broken: bool
    reason: Optional[str] = None
    file_name: Optional[str] = None
    current_path: Optional[str] = None


class WikiTabRes(BaseModel):
    """A single wiki tab (one folder_1depth) returned by ANA-QRY-01."""
    wiki_id: str
    folder_1depth: str
    markdown_content: str
    created_at: str
    updated_at: str


class WorkspaceWikiRes(BaseModel):
    """All wiki tabs for a workspace, ordered by folder_1depth (issue #7)."""
    workspace_id: str
    tabs: List[WikiTabRes]
