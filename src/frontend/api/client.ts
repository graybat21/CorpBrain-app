/**
 * The single IPC entry point. Every backend call in the app goes through here.
 *
 * DEC-02: the base URL and the Bearer session token are injected by the pywebview host into
 * `window.__CORPBRAIN__` after the server picks an OS-assigned random port. The token is read
 * from that object on every request and is never hardcoded, never written to localStorage /
 * sessionStorage / a cookie, and never logged — it grants full access to the local API for the
 * lifetime of the process.
 *
 * DEC-03: responses arrive in the `{ok, data, error}` envelope. It is unwrapped exactly once,
 * here, so page code sees either a value or a thrown `ApiClientError`. Field names stay
 * `snake_case` all the way into the components — there is no camelCase conversion layer.
 *
 * DEC-04: long-running commands answer 202 with a `task_id`; `pollTask` polls progress at 1s
 * intervals. There is no WebSocket or SSE channel and none may be added.
 */

import { API_PATHS } from './types.gen';
import { resolveApiUrl } from './urlBuilder';
import type {
  AnalyticsEventReq,
  AnalyticsEventRes,
  AnalyticsSummaryRes,
  ApiError,
  DeepLinkOpenReq,
  DeepLinkOpenRes,
  DeepLinkStatusRes,
  FileListRes,
  HealthRes,
  InterruptedTaskListRes,
  LlmConfigUpdatedRes,
  LlmHealthCheckRes,
  LlmOnboardReq,
  LlmOptionReq,
  LlmPriceUpdateReq,
  LlmPriceUpdatedRes,
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
  WorkspaceCreateReq,
  WorkspaceDeletedRes,
  WorkspaceItemRes,
  WorkspaceListRes,
  WorkspaceWikiRes,
} from './types.gen';

/** What the pywebview host injects before the SPA loads (DEC-02). */
interface CorpBrainBridge {
  baseUrl: string;
  token: string;
}

declare global {
  interface Window {
    __CORPBRAIN__?: CorpBrainBridge;
  }
}

/**
 * A failed call, carrying the DEC-03 `error` object.
 *
 * `code` is one of the standard identifiers from the DEC-03 table, so callers branch on it
 * rather than on message text, which is Korean prose meant for a Toast.
 */
export class ApiClientError extends Error {
  readonly code: string;
  readonly field?: string | null;
  readonly details?: Record<string, unknown> | null;
  readonly status: number;

  constructor(error: ApiError, status: number) {
    super(error.message);
    this.name = 'ApiClientError';
    this.code = error.code;
    this.field = error.field;
    this.details = error.details;
    this.status = status;
  }
}

/** A batch where some items failed: HTTP 207 + `ok:true` + `data.failed[]` (DEC-03 / DEC-16). */
export interface PartialResult<T> {
  data: T;
  is_partial: boolean;
}

function bridge(): CorpBrainBridge {
  const injected = window.__CORPBRAIN__;
  if (!injected?.baseUrl || !injected?.token) {
    // Reached when the SPA is opened directly in a browser rather than by the host. Failing
    // loudly beats sending unauthenticated requests that all come back UNAUTHORIZED.
    throw new ApiClientError(
      {
        code: 'UNAUTHORIZED',
        message: '데스크톱 셸이 세션 정보를 주입하지 않았습니다. CorpBrain.exe 로 실행해 주세요.',
      },
      0,
    );
  }
  return injected;
}

/**
 * Substitute `{name}` placeholders in an API_PATHS entry and build the request URL.
 *
 * Delegates to the pure `resolveApiUrl`, supplying the browser's real `window.location.href` as
 * the base to resolve the injected `baseUrl` against. The injected value is "/" (DEC-02 keeps the
 * OS-assigned port out of the markup), and `new URL(path, "/")` throws "Invalid base URL" — see
 * urlBuilder.ts (issue #162).
 */
function buildUrl(
  baseUrl: string,
  template: string,
  params?: Record<string, string>,
  query?: Record<string, string | number | undefined>,
): string {
  return resolveApiUrl(baseUrl, window.location.href, template, params, query);
}

interface RequestOptions {
  params?: Record<string, string>;
  query?: Record<string, string | number | undefined>;
  body?: unknown;
  /** Set by pollTask so a cancelled poll loop does not leave a request in flight. */
  signal?: AbortSignal;
}

/**
 * Issue one request and unwrap the DEC-03 envelope.
 *
 * A 207 resolves like a 200 — `data.failed[]` describes which items failed and the caller
 * surfaces that. Only `ok:false` throws.
 */
async function request<T>(
  method: string,
  template: string,
  options: RequestOptions = {},
): Promise<PartialResult<T>> {
  const { baseUrl, token } = bridge();
  const url = buildUrl(baseUrl, template, options.params, options.query);

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw cause;
    }
    // The loopback server is in the same process as this window, so this means it died.
    throw new ApiClientError(
      { code: 'INTERNAL_ERROR', message: '로컬 서버에 연결할 수 없습니다.' },
      0,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    // Every /api/v1 route returns the envelope; a non-JSON body means something upstream of
    // the exception handlers answered, e.g. the token middleware rejecting the request.
    throw new ApiClientError(
      { code: response.status === 401 ? 'UNAUTHORIZED' : 'INTERNAL_ERROR', message: '서버 응답을 해석할 수 없습니다.' },
      response.status,
    );
  }

  const envelope = payload as { ok?: boolean; data?: T; error?: ApiError };

  if (envelope.ok === false || !response.ok) {
    throw new ApiClientError(
      envelope.error ?? { code: 'INTERNAL_ERROR', message: '알 수 없는 오류가 발생했습니다.' },
      response.status,
    );
  }

  return { data: envelope.data as T, is_partial: response.status === 207 };
}

/** Unwrap to the payload for the common case where a partial result is not meaningful. */
async function data<T>(method: string, template: string, options: RequestOptions = {}): Promise<T> {
  return (await request<T>(method, template, options)).data;
}

// --- Health ---

export function getHealth(): Promise<HealthRes> {
  return data<HealthRes>('GET', API_PATHS.GET_health);
}

// --- Workspace ---

export function listWorkspaces(): Promise<WorkspaceListRes> {
  return data<WorkspaceListRes>('GET', API_PATHS.GET_workspace);
}

export function createWorkspace(payload: WorkspaceCreateReq): Promise<WorkspaceItemRes> {
  return data<WorkspaceItemRes>('POST', API_PATHS.POST_workspace, { body: payload });
}

export function getWorkspace(workspaceId: string): Promise<WorkspaceItemRes> {
  return data<WorkspaceItemRes>('GET', API_PATHS.GET_workspace_item, {
    params: { workspace_id: workspaceId },
  });
}

export function deleteWorkspace(workspaceId: string): Promise<WorkspaceDeletedRes> {
  return data<WorkspaceDeletedRes>('DELETE', API_PATHS.DELETE_workspace_item, {
    params: { workspace_id: workspaceId },
  });
}

// --- Files & scan ---

export function listFiles(workspaceId: string): Promise<FileListRes> {
  return data<FileListRes>('GET', API_PATHS.GET_workspace_file, {
    params: { workspace_id: workspaceId },
  });
}

export function getScanSummary(workspaceId: string): Promise<ScanSummaryRes> {
  return data<ScanSummaryRes>('GET', API_PATHS.GET_workspace_scan_summary, {
    params: { workspace_id: workspaceId },
  });
}

export function startScan(workspaceId: string): Promise<TaskAcceptedRes> {
  return data<TaskAcceptedRes>('POST', API_PATHS.POST_workspace_scan, {
    params: { workspace_id: workspaceId },
  });
}

export function startFastAnalysis(workspaceId: string): Promise<TaskAcceptedRes> {
  return data<TaskAcceptedRes>('POST', API_PATHS.POST_workspace_analysis_fast, {
    params: { workspace_id: workspaceId },
  });
}

// --- Tasks (DEC-04) ---

export function getTaskProgress(taskId: string, signal?: AbortSignal): Promise<TaskProgressRes> {
  return data<TaskProgressRes>('GET', API_PATHS.GET_analyze_progress, {
    params: { task_id: taskId },
    signal,
  });
}

export function getTaskResult(taskId: string): Promise<TaskResultRes> {
  return data<TaskResultRes>('GET', API_PATHS.GET_task_result, { params: { task_id: taskId } });
}

export function listInterruptedTasks(): Promise<InterruptedTaskListRes> {
  return data<InterruptedTaskListRes>('GET', API_PATHS.GET_task_interrupted);
}

/** Terminal states, as written by the task runner. */
const TERMINAL_STATUSES = ['completed', 'failed', 'multi_status', 'interrupted'];

export interface PollTaskOptions {
  onProgress?: (progress: TaskProgressRes) => void;
  signal?: AbortSignal;
  /** Guards against a task whose row stops advancing; ~10 min at the 1s interval. */
  maxPolls?: number;
}

/**
 * Poll a task to a terminal state and return its last progress row (DEC-04).
 *
 * The 1s interval is the specified one. `onProgress` fires on every tick including the last,
 * so a progress bar reaches its terminal value without the caller re-reading.
 */
export async function pollTask(
  taskId: string,
  options: PollTaskOptions = {},
): Promise<TaskProgressRes> {
  const { onProgress, signal, maxPolls = 600 } = options;

  for (let attempt = 0; attempt < maxPolls; attempt += 1) {
    if (signal?.aborted) {
      throw new DOMException('poll aborted', 'AbortError');
    }
    const progress = await getTaskProgress(taskId, signal);
    onProgress?.(progress);
    if (TERMINAL_STATUSES.includes(progress.status)) {
      return progress;
    }
    await sleep(1000, signal);
  }

  throw new ApiClientError(
    { code: 'INTERNAL_ERROR', message: '작업이 응답하지 않아 진행 상황 확인을 중단했습니다.' },
    0,
  );
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new DOMException('poll aborted', 'AbortError'));
    }
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

// --- LLM config ---

export function getLlmConfig(): Promise<LlmHealthCheckRes> {
  return data<LlmHealthCheckRes>('GET', API_PATHS.GET_config_llm);
}

/**
 * DEC-12: `api_key` travels to the loopback server in this body and is not retained here.
 * Do not store it in the Zustand store, localStorage, or a component ref — the backend
 * encrypts it with DPAPI and thereafter reports only `api_key_configured: bool`.
 */
export function setLlmConfig(payload: LlmOptionReq): Promise<LlmConfigUpdatedRes> {
  return data<LlmConfigUpdatedRes>('POST', API_PATHS.POST_config_llm, { body: payload });
}

/**
 * DEC-16: the cloud price table is user-editable and is never fetched over the network —
 * a price lookup would be a fourth egress destination (DEC-15).
 *
 * `cloud_price_updated_at` is the date the prices are *current as of*, supplied by the user, not
 * the time of the edit. It answers "which price list is this?", so stamping it with `now()` would
 * relabel a rate copied from last quarter's page as today's.
 */
export function setLlmPrice(payload: LlmPriceUpdateReq): Promise<LlmPriceUpdatedRes> {
  return data<LlmPriceUpdatedRes>('POST', API_PATHS.POST_config_llm_price, { body: payload });
}

/**
 * LLM-CMD-03 / DEC-13: start Ollama provisioning.
 *
 * Returns a task_id, not a result (DEC-04) — a 4.7GB model pull cannot be a synchronous
 * request. Poll `getTaskProgress` at 1s intervals and read `progress_message` to show which
 * model is downloading: DEC-13 forbids presenting the ~274MB embedder and the ~4.7GB
 * generation model as one combined download.
 *
 * `purpose: 'embedding'` is needed by every user including Option A (DEC-06);
 * `'generation'` is Option B only and additionally pulls the generation model.
 *
 * On failure the task ends with `error_code: 'LLM_PROVISION_REQUIRED'`. On a closed network
 * that is the expected outcome and the required-model list is in the task result — surface it
 * rather than retrying, since the app never installs anything in `detect_only` mode.
 */
export function onboardLlm(payload: LlmOnboardReq): Promise<TaskAcceptedRes> {
  return data<TaskAcceptedRes>('POST', API_PATHS.POST_llm_onboard, { body: payload });
}

// --- Rename ---

export function generateRenameDiff(workspaceId: string): Promise<RenameDiffRes> {
  return data<RenameDiffRes>('POST', API_PATHS.POST_workspace_rename_diff, {
    params: { workspace_id: workspaceId },
  });
}

export function applyRename(
  workspaceId: string,
  payload: RenameApplyReq,
): Promise<TaskAcceptedRes> {
  return data<TaskAcceptedRes>('POST', API_PATHS.POST_workspace_rename_apply, {
    params: { workspace_id: workspaceId },
    body: payload,
  });
}

export function undoRename(workspaceId: string, payload: RenameUndoReq): Promise<TaskAcceptedRes> {
  return data<TaskAcceptedRes>('POST', API_PATHS.POST_workspace_rename_undo, {
    params: { workspace_id: workspaceId },
    body: payload,
  });
}

// --- Watcher ---

export function getWatcherConfig(workspaceId: string): Promise<WatcherConfigRes> {
  return data<WatcherConfigRes>('GET', API_PATHS.GET_workspace_watcher_config, {
    params: { workspace_id: workspaceId },
  });
}

export function setWatcherConfig(
  workspaceId: string,
  payload: WatcherConfigReq,
): Promise<WatcherConfigRes> {
  return data<WatcherConfigRes>('POST', API_PATHS.POST_workspace_watcher_config, {
    params: { workspace_id: workspaceId },
    body: payload,
  });
}

export function getWatcherStatus(workspaceId: string): Promise<WatcherStatusRes> {
  return data<WatcherStatusRes>('GET', API_PATHS.GET_workspace_watcher_status, {
    params: { workspace_id: workspaceId },
  });
}

// --- Analytics ---

export function logAnalyticsEvent(
  workspaceId: string,
  payload: AnalyticsEventReq,
): Promise<AnalyticsEventRes> {
  return data<AnalyticsEventRes>('POST', API_PATHS.POST_workspace_analytics_event, {
    params: { workspace_id: workspaceId },
    body: payload,
  });
}

/**
 * DEC-11: `from_time`/`to_time` are caller-computed UTC instants. The backend never infers a
 * week or month boundary, so the frontend converts from KST and sends explicit bounds.
 */
export function getAnalyticsSummary(
  workspaceId: string,
  range?: { from_time?: string; to_time?: string },
): Promise<AnalyticsSummaryRes> {
  return data<AnalyticsSummaryRes>('GET', API_PATHS.GET_workspace_analytics_summary, {
    params: { workspace_id: workspaceId },
    query: { from_time: range?.from_time, to_time: range?.to_time },
  });
}

// --- Deeplink (DEC-08) ---

/** `file_id` only. The server resolves the path; a caller-supplied path is never accepted. */
export function openDeepLink(
  workspaceId: string,
  payload: DeepLinkOpenReq,
): Promise<DeepLinkOpenRes> {
  return data<DeepLinkOpenRes>('POST', API_PATHS.POST_workspace_deeplink_open, {
    params: { workspace_id: workspaceId },
    body: payload,
  });
}

export function getDeepLinkStatus(
  workspaceId: string,
  fileId: string,
): Promise<DeepLinkStatusRes> {
  return data<DeepLinkStatusRes>('GET', API_PATHS.GET_workspace_deeplink_status, {
    params: { workspace_id: workspaceId },
    query: { file_id: fileId },
  });
}

// --- Wiki (ANA-QRY-01) ---

/**
 * Fetch all wiki tabs for a workspace (issue #7 / ANA-QRY-01).
 *
 * Each tab corresponds to one folder_1depth row in Wiki_Content. The frontend renders
 * these as separate tabs in the wiki viewer (ANA-FE-02). Markdown content includes
 * [[file_id:<UUID>]] anchors (DEC-08), which the frontend replaces with clickable badges.
 *
 * Depends on: ANA-CMD-03 (wiki generation) must have run first, otherwise tabs=[].
 */
export function getWorkspaceWiki(workspaceId: string): Promise<WorkspaceWikiRes> {
  return data<WorkspaceWikiRes>('GET', API_PATHS.GET_workspace_wiki, {
    params: { workspace_id: workspaceId },
  });
}

/** Turn any thrown value into Toast-ready text without leaking an object into the UI. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiClientError) {
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return '알 수 없는 오류가 발생했습니다.';
}
