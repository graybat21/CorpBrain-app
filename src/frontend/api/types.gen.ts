/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by `python scripts/gen_api_types.py` from the FastAPI OpenAPI 3.1 schema, which
 * DEC-02 designates as the IPC contract SSOT. Editing this file by hand recreates the
 * hand-maintained parallel type definition that issue #91 removed.
 *
 * Property names are `snake_case` exactly as they appear on the wire (DEC-03) — there is no
 * camelCase conversion layer anywhere, this file included.
 *
 * To change a type: change the Pydantic DTO in src/backend/api/dtos.py, then regenerate.
 * tests/test_ws_fe_01.py fails if this file and the live schema disagree.
 */

export interface AnalyticsEventReq {
  event_type?: string;
  file_id?: string | null;
  wiki_id?: string | null;
  tokens_used?: number;
  cost_usd?: number | null;
}

export interface AnalyticsEventRes {
  log_id: string;
  workspace_id: string;
  event_type: string;
  file_id?: string | null;
  wiki_id?: string | null;
  tokens_used: number;
  cost_usd?: number | null;
}

/**
 * DEC-11: caller-supplied UTC instants, echoed back. The backend never infers a boundary.
 */
export interface AnalyticsPeriodRes {
  from_time?: string | null;
  to_time?: string | null;
}

export interface AnalyticsSummaryRes {
  workspace_id: string;
  period: AnalyticsPeriodRes;
  saved_time_minutes: number;
  total_tokens_used: number;
  total_cost_usd: number;
  deeplink_clicks_count: number;
  watcher_updates_count: number;
  compression_ratio: string;
  knowledge_ratio_scope: string;
}

export interface ApiError {
  code: string;
  message: string;
  field?: string | null;
  details?: Record<string, unknown> | null;
}

export interface ApiResponse_AnalyticsEventRes_ {
  ok: boolean;
  data?: AnalyticsEventRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_AnalyticsSummaryRes_ {
  ok: boolean;
  data?: AnalyticsSummaryRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_DeepLinkOpenRes_ {
  ok: boolean;
  data?: DeepLinkOpenRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_DeepLinkStatusRes_ {
  ok: boolean;
  data?: DeepLinkStatusRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_FileListRes_ {
  ok: boolean;
  data?: FileListRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_HealthRes_ {
  ok: boolean;
  data?: HealthRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_InterruptedTaskListRes_ {
  ok: boolean;
  data?: InterruptedTaskListRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_List_PendingRenameDiffItemRes__ {
  ok: boolean;
  data?: PendingRenameDiffItemRes[] | null;
  error?: ApiError | null;
}

export interface ApiResponse_LlmConfigUpdatedRes_ {
  ok: boolean;
  data?: LlmConfigUpdatedRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_LlmHealthCheckRes_ {
  ok: boolean;
  data?: LlmHealthCheckRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_RenameDiffRes_ {
  ok: boolean;
  data?: RenameDiffRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_ScanSummaryRes_ {
  ok: boolean;
  data?: ScanSummaryRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_TaskAcceptedRes_ {
  ok: boolean;
  data?: TaskAcceptedRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_TaskProgressRes_ {
  ok: boolean;
  data?: TaskProgressRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_TaskResultRes_ {
  ok: boolean;
  data?: TaskResultRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_WatcherConfigRes_ {
  ok: boolean;
  data?: WatcherConfigRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_WatcherStatusRes_ {
  ok: boolean;
  data?: WatcherStatusRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_WorkspaceDeletedRes_ {
  ok: boolean;
  data?: WorkspaceDeletedRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_WorkspaceItemRes_ {
  ok: boolean;
  data?: WorkspaceItemRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_WorkspaceListRes_ {
  ok: boolean;
  data?: WorkspaceListRes | null;
  error?: ApiError | null;
}

export interface ApiResponse_WorkspaceWikiRes_ {
  ok: boolean;
  data?: WorkspaceWikiRes | null;
  error?: ApiError | null;
}

/**
 * DEC-08: `file_id` only. A caller-supplied path is never accepted.
 */
export interface DeepLinkOpenReq {
  file_id: string;
}

export interface DeepLinkOpenRes {
  status: string;
  file_id: string;
  opened_path: string;
}

/**
 * DL-QRY-01. `is_broken` is true when the row's `current_path` is missing from disk, or when
 * the file_id has no row at all — in which case `file_name`/`current_path` are null.
 */
export interface DeepLinkStatusRes {
  file_id: string;
  is_broken: boolean;
  reason?: string | null;
  file_name?: string | null;
  current_path?: string | null;
}

/**
 * One File_Meta row as the UI consumes it.
 *
 * `original_path` is deliberately absent. DEC-08 makes it immutable audit data and requires
 * every open/existence check to go through `current_path`; not shipping it to the frontend
 * removes the possibility of a component picking the stale one.
 */
export interface FileItemRes {
  file_id: string;
  workspace_id: string;
  file_name: string;
  extension: string;
  current_path: string;
  size_bytes: number;
  last_modified: number;
  parse_status: string;
  importance_score: number;
  created_at: string;
  updated_at: string;
}

export interface FileListRes {
  workspace_id: string;
  items: FileItemRes[];
  total: number;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface HealthRes {
  status: string;
  app: string;
}

/**
 * A task stranded by a crash, offered to the user for resume (DEC-04 — never automatic).
 */
export interface InterruptedTaskItemRes {
  task_id: string;
  task_type: string;
  status: string;
  processed: number;
  total: number;
  created_at: string;
  workspace_id?: string | null;
}

export interface InterruptedTaskListRes {
  items: InterruptedTaskItemRes[];
  total: number;
}

/**
 * DEC-12: only the mode is echoed back. The API key — even partially masked — is never in a
 * response body; `GET /api/v1/config/llm` reports `api_key_configured: bool` instead.
 */
export interface LlmConfigUpdatedRes {
  updated: boolean;
  llm_mode: string;
}

export interface LlmHealthCheckRes {
  status: string;
  mode: string;
  is_healthy: boolean;
  api_key_configured?: boolean;
  daemon_online?: boolean;
  embedding_model_ready?: boolean;
  generation_model_ready?: boolean;
  error_code?: string | null;
}

export interface LlmOptionReq {
  /**
   * Option A (Cloud) or Option B (Local)
   */
  llm_mode: string;
  api_key?: string | null;
}

/**
 * RN-QRY-01: a persisted `pending` diff row, as opposed to a freshly generated one.
 *
 * Known broken — `RenameQueryService.get_pending_rename_diff` queries a `Rename_History.status`
 * column that does not exist (issue #90). Typed here anyway so the contract the fix must
 * satisfy is in the OpenAPI schema rather than only in that issue's body.
 */
export interface PendingRenameDiffItemRes {
  file_id?: string | null;
  old_name: string;
  new_name?: string | null;
  history_id: string;
  status: string;
}

/**
 * One rename to perform. Paths here are server-side state echoed back from the diff, not
 * user input: `apply_rename` refuses anything whose `old_path` is absent from disk.
 */
export interface RenameApplyItemReq {
  file_id: string;
  old_path: string;
  new_path: string;
}

export interface RenameApplyReq {
  items?: RenameApplyItemReq[] | null;
  history_id?: string | null;
}

/**
 * One row of the rename diff.
 *
 * Names only, never paths: DEC-17 keeps absolute paths out of anything that reaches the LLM,
 * and DEC-08 keeps them out of anything cached client-side. `status` is one of
 * `pending` / `PII_TOKEN_LEFT` / `PII_MASKING_FAILED` / `INVALID_FILENAME`; anything other
 * than `pending` means the file is excluded from the batch and needs manual review.
 */
export interface RenameDiffItemRes {
  file_id: string;
  old_name: string;
  new_name: string;
  status: string;
  note: string;
}

export interface RenameDiffRes {
  workspace_id: string;
  items: RenameDiffItemRes[];
  history_id?: string | null;
}

export interface RenameUndoReq {
  history_id?: string | null;
}

/**
 * SCAN-QRY-01. `estimated_analysis_seconds` is an estimate from measured throughput.
 */
export interface ScanSummaryRes {
  workspace_id: string;
  file_count: number;
  total_size_mb: number;
  estimated_analysis_seconds: number;
}

/**
 * Body of the 202 returned by every long-running command (DEC-04).
 *
 * Carries the task_id and nothing else useful — progress comes from polling
 * GET /api/v1/analyze/{task_id}/progress at 1s intervals, not from this response.
 */
export interface TaskAcceptedRes {
  task_id: string;
  task_type: string;
  status?: string;
  workspace_id?: string | null;
}

export interface TaskProgressRes {
  task_id: string;
  task_type: string;
  status: string;
  processed: number;
  total: number;
  percent: number;
  eta_sec?: number | null;
  error_code?: string | null;
  workspace_id?: string | null;
}

/**
 * A finished task's outcome, fetched once after polling sees a terminal status.
 *
 * Kept out of TaskProgressRes because DEC-04 forbids returning large payloads from a
 * response that is polled every second.
 */
export interface TaskResultRes {
  task_id: string;
  task_type: string;
  status: string;
  error_code?: string | null;
  result?: Record<string, unknown> | null;
  workspace_id?: string | null;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface WatcherConfigReq {
  mode?: string;
  debounce_ms?: number;
}

export interface WatcherConfigRes {
  workspace_id: string;
  mode: string;
  is_enabled: boolean;
  debounce_ms: number;
}

export interface WatcherStatusRes {
  workspace_id: string;
  mode: string;
  is_enabled: boolean;
  queued_items_count: number;
}

/**
 * A single wiki tab (one folder_1depth) returned by ANA-QRY-01.
 */
export interface WikiTabRes {
  wiki_id: string;
  folder_1depth: string;
  markdown_content: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceCreateReq {
  /**
   * Workspace name
   */
  workspace_name: string;
  /**
   * List of root folder paths
   */
  root_paths: string[];
}

export interface WorkspaceDeletedRes {
  deleted: boolean;
  workspace_id: string;
}

export interface WorkspaceItemRes {
  workspace_id: string;
  workspace_name: string;
  root_path: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceListRes {
  items: WorkspaceItemRes[];
  total: number;
}

/**
 * All wiki tabs for a workspace, ordered by folder_1depth (issue #7).
 */
export interface WorkspaceWikiRes {
  workspace_id: string;
  tabs: WikiTabRes[];
}

/**
 * Every registered route, keyed by METHOD_resource.
 *
 * Path parameters are left as `{workspace_id}` placeholders — the client substitutes
 * them, so the literal here stays identical to what OpenAPI declares.
 */
export const API_PATHS = {
  GET_analyze_progress: "/api/v1/analyze/{task_id}/progress",
  GET_config_llm: "/api/v1/config/llm",
  POST_config_llm: "/api/v1/config/llm",
  GET_health: "/api/v1/health",
  GET_task_interrupted: "/api/v1/task/interrupted",
  GET_task_result: "/api/v1/task/{task_id}/result",
  GET_workspace: "/api/v1/workspace",
  POST_workspace: "/api/v1/workspace",
  DELETE_workspace_item: "/api/v1/workspace/{workspace_id}",
  GET_workspace_item: "/api/v1/workspace/{workspace_id}",
  POST_workspace_analysis_fast: "/api/v1/workspace/{workspace_id}/analysis/fast",
  POST_workspace_analytics_event: "/api/v1/workspace/{workspace_id}/analytics/event",
  GET_workspace_analytics_summary: "/api/v1/workspace/{workspace_id}/analytics/summary",
  POST_workspace_deeplink_open: "/api/v1/workspace/{workspace_id}/deeplink/open",
  GET_workspace_deeplink_status: "/api/v1/workspace/{workspace_id}/deeplink/status",
  GET_workspace_file: "/api/v1/workspace/{workspace_id}/file",
  POST_workspace_reembed: "/api/v1/workspace/{workspace_id}/reembed",
  POST_workspace_rename_apply: "/api/v1/workspace/{workspace_id}/rename/apply",
  GET_workspace_rename_diff: "/api/v1/workspace/{workspace_id}/rename/diff",
  POST_workspace_rename_diff: "/api/v1/workspace/{workspace_id}/rename/diff",
  POST_workspace_rename_undo: "/api/v1/workspace/{workspace_id}/rename/undo",
  POST_workspace_scan: "/api/v1/workspace/{workspace_id}/scan",
  GET_workspace_scan_summary: "/api/v1/workspace/{workspace_id}/scan/summary",
  GET_workspace_watcher_config: "/api/v1/workspace/{workspace_id}/watcher/config",
  POST_workspace_watcher_config: "/api/v1/workspace/{workspace_id}/watcher/config",
  GET_workspace_watcher_status: "/api/v1/workspace/{workspace_id}/watcher/status",
  GET_workspace_wiki: "/api/v1/workspace/{workspace_id}/wiki",
  POST_workspace_wiki_generate: "/api/v1/workspace/{workspace_id}/wiki/generate",
  GET_workspaces: "/api/v1/workspaces",
} as const;
