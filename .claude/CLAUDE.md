# Claude Code Agent Instructions (CLAUDE.md)

This file contains binding operating procedures and coding conventions for AI coding assistants (including Claude Code, Aider, and Antigravity) operating in the **CorpBrain-app** workspace. Always adhere to these rules without exception.

## 1. Project Overview & Core Architecture (SRS-001 Compliant)
- **Project Name**: CorpBrain MVP (Windows desktop application for corporate document analysis, wiki generation, real-time watcher, and intelligent batch renaming).
- **Architecture & Packaging**: Standalone offline-first Windows executable (`.exe` packaged via PyInstaller). External remote telemetry is strictly forbidden (Zero Telemetry & Closed Network security).
- **Desktop Shell — LOCKED (SRS §3.2 `DEC-01`)**: **pywebview** embedding the OS-native **WebView2 (Edge Chromium)** runtime, packaged by **PyInstaller `--onefile`** into a single `CorpBrain.exe`. Python is the host process; the React UI is a **prebuilt static SPA bundle** embedded via `--add-data` and loaded with a **HashRouter**.
  - **Do NOT introduce Electron, Tauri, Next.js, SSR, or any Node.js runtime dependency into the shipped artifact.** Node/npm may be used only as a build-time toolchain for the React bundle. A sidecar/multi-process shell architecture is out of scope.
  - If WebView2 Runtime is absent, show an Evergreen Bootstrapper guidance dialog and exit gracefully — never crash.
- **3-Tier Component Stack & Domains** (per SRS §3.6):
  - **Presentation Layer (UI)**: React-based Desktop UI (Workspace history panel, scan statistical dashboard, 1-Depth tabbed markdown wiki viewer). Communicates with Core Layer via IPC (REST API / JSON).
  - **Core Application Layer (Backend)**: **Python 3** modular services:
    - `DatabaseManager` + per-table Repositories: thread-local `sqlite3` access, `transaction()` context manager.
    - `WorkspaceManager`: Multi-folder merging & project CRUD.
    - `FileScanner` & `TextParser`: File tree traversing (with `.git`/`Windows`/`node_modules` blacklist & 10,000 file upper-limit pause guard) and text extraction for `.docx`, `.pdf`, `.txt`, `.md`.
    - `AnalysisEngine` & `LLMRouter`: Fast (filename-ranking) & Deep (chunking/wiki) semantic analysis with hybrid routing (Cloud Option A with in-memory **regex-only** PII masking to `[PII:TYPE]` tokens (`DEC-14`) vs. Local Ollama Option B with two-mode provisioning: `assisted` install/pull on a networked PC, `detect_only` on a closed network (`DEC-13`)).
    - `WatcherDaemon`: Real-time Windows OS filesystem event monitoring via Python `watchdog`.
    - `RenameManager` & `DeepLinkBridge`: AI batch renaming with 100% undo capabilities and `os.startfile` Trust-Anchor hyperlinking resolved from `file_id` → `File_Meta.current_path` (`DEC-08`).
    - `NetworkGuard`: The single outbound-egress gate — `purpose`-tagged calls against a code-constant destination whitelist (`DEC-15`). No other module performs network I/O.
    - `AnalyticsService`: In-app productivity statistics calculation (saved time based on 200~250 WPM, fact-check rates).
  - **Data Persistence Layer**: Local SQLite (`corpbrain_meta.db`) for relational structural metadata, local ChromaDB / FAISS for vector embeddings, and local rolling application log files.
- **Architectural Principle**: Maintain strict architectural layer separation: **[Data & IPC Contracts] ➔ [Python Core Engines / Business Logic] ➔ [React UI Rendering & IPC Binding]**. Never implement business logic or file/db mutations directly in React UI components.

## 2. Git Flow & Branching Policy (STRICT)
- **NO DIRECT MAIN COMMIT**: **Never** make commits or push directly to the `main` or `master` branch. The default target branch for any task development is always a dedicated feature branch.
- **Branch Naming Convention**: When assigned a GitHub Issue, immediately create and switch to a new branch following this pattern before modifying any file:
  `feature/issue-<number>-<short-kebab-name>` (e.g., `feature/issue-15-db-schema-init`, `feature/issue-11-workspace-dto`).
- **Atomic Commits**: Write clear, imperative commit messages prefixing the issue number or component name (e.g., `feat(db): implement corpbrain_meta.db SQLite schema [Closes #15]`). Do not bundle unrelated architectural changes in a single commit.

## 3. GitHub Issues & Projects Orchestration
- **Issue Specification Retrieval**: Before writing any code, always use the GitHub CLI to view and analyze the complete issue specification:
  ```bash
  gh issue view <issue-number>
  ```
- **Requirements Parsing**: Carefully parse the Markdown body of the issue, paying critical attention to **References (SRS/API)**, **Task Breakdown**, and **Acceptance Criteria (GWT Scenarios)**.
- **Pull Request Creation**: Upon satisfying all issue requirements and passing validation, push your feature branch and open a Pull Request using the GitHub CLI:
  ```bash
  gh pr create --title "[Phase X] Closes #<number>: <issue-title>" --body "$(cat <<'EOF'
  ## Summary of Changes
  - Implemented core functionality according to issue specifications.

  ## Verification & DoD
  - [x] Validated BDD/GWT Acceptance Criteria.
  - [x] Checked test coverage and zero regression.

  Closes #<number>
  EOF
  )"
  ```
  *(Note: Replace `X` and `<number>` with the actual phase and issue ID. Including `Closes #ID` in the PR body is strictly mandatory to trigger automatic GitHub Projects Kanban transitions).*

## 4. Coding Standards & Implementation Boundaries
- **Python Backend**: Follow PEP 8 conventions, type hints (Python 3.10+), modular package structure, and clean async/await patterns (`asyncio`). Use `pathlib.Path` for all filesystem paths.
- **Data Access — LOCKED (SRS §6.2 `DEC-05`)**: Standard-library **`sqlite3` only**. **Do not introduce SQLAlchemy, SQLModel, Alembic, or Prisma** (Prisma additionally violates `DEC-01` via its Node runtime).
  - SQL lives **only inside per-table Repository classes**; never let SQL strings leak into service or API layers. Repositories convert `sqlite3.Row` → Pydantic DTO explicitly, keeping DTOs separate from DB entities.
  - Migrations are **`PRAGMA user_version`-based**: numbered `migrations/vNNN_*.sql` applied in order, each wrapped in a single transaction; bump `user_version` only on success.
  - Connections are **thread-local** (`threading.local`) — `sqlite3` connections cannot cross threads. No connection-pool library.
  - Apply on **every new connection**: `journal_mode=WAL`, **`foreign_keys=ON` (per-connection, mandatory every time)**, `busy_timeout=5000`, `synchronous=NORMAL`. Use `isolation_level=None` plus explicit `BEGIN` via `DatabaseManager.transaction()`.
  - **Storage types & timezone — LOCKED (SRS §6.2 `DEC-11`)**: `UUID` → **TEXT** (36-char hyphenated lowercase, `str(uuid.uuid4())`); `DATETIME` → **TEXT ISO-8601 UTC** (`YYYY-MM-DDTHH:MM:SS.ffffffZ`). Do not store UUIDs as BLOB or timestamps as INTEGER epoch (exception: `File_Meta.last_modified` stays REAL — it is compared against `Path.stat().st_mtime`).
    - Always `datetime.now(timezone.utc)`; **never naive `datetime.now()`**. Backend stores and returns UTC only; KST conversion happens in the frontend. Period boundaries arrive as caller-computed `from`/`to` UTC instants — **the backend never infers a week/month boundary itself.**
    - **`ON UPDATE CURRENT_TIMESTAMP` is MySQL syntax that SQLite does not support — never write it in a schema.** Set `updated_at` explicitly in each Repository's `UPDATE` statement; **do not add `AFTER UPDATE` triggers**.
    - Timestamp defaults use `DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))`, not `DEFAULT CURRENT_TIMESTAMP` (which yields a different, non-`Z` format).
  - The global settings table is **`App_Config`** (single KV table, `DEC-10`). **`Settings_Meta` does not exist** — do not create it or split settings into per-domain tables; namespace by key prefix (`llm_*`, `embedding_*`) instead.
  - SQLite allows only **one writer**. Keep write transactions short: **never perform LLM inference or file I/O inside a write transaction.**
- **Vector Store — LOCKED (SRS §6.2 `DEC-06`)**: **ChromaDB `PersistentClient`** at `%LocalAppData%\CorpBrain\vectors\`. FAISS is not used. **One collection per workspace**, named `ws_<workspace_id_hex>`, `hnsw:space=cosine`.
  - Embeddings are computed by **Ollama `nomic-embed-text` (768-dim)** via an explicitly injected embedding function. **Never rely on Chroma's default embedding function** — it downloads an ONNX model at runtime, violating REQ-NF-005. All embedding calls target `127.0.0.1` only.
  - **Do not add `sentence-transformers`, `torch`, or any in-process ML stack** — it would blow up the PyInstaller bundle and break CON-02.
  - **Cross-store consistency — LOCKED (SRS §6.2 `DEC-09`)**: SQLite and Chroma cannot share a transaction, so vectors are treated as **regenerable derived data** and Chroma is their **sole SSOT**.
    - **`File_Meta.vector_ids` does not exist — never reintroduce it.** Chunk IDs are computed deterministically as **`f"{file_id}:{chunk_index}"`**, never stored in SQLite. Deletion goes through the metadata filter `where={"file_id": ...}`.
    - Re-analysis is always **`delete_file(file_id)` → `upsert`**, never upsert alone (a shrunk document would leave stale trailing chunks).
    - Fixed write order: **Chroma delete → Chroma upsert → SQLite `parse_status='parsed'` commit.** Fixed delete order: **vectors first, SQLite row second** (reversing it leaks orphan vectors into search results).
    - **Never call Chroma inside a SQLite write transaction** (`DEC-05`) — embedding inference takes seconds.
    - Orphan vectors are reclaimed by **lazy delete during search post-processing** (drop chunks whose `file_id` is absent from `File_Meta`). Do not build a reconcile sweep or a GC scheduler; the fix for a mismatch is re-embedding, not reconciliation.
    - Every `workspace_id` FK is `ON DELETE CASCADE`; workspace deletion is one `delete_collection("ws_<id>")` plus one row delete.
  - Chunk metadata must include `{workspace_id, file_id, chunk_index, folder_1depth}`. Changing the embedding model/dimension invalidates all vectors: guard with `App_Config.embedding_model` / `embedding_dim` and require user consent before re-embedding. Never mix dimensions in one collection.
- **Cloud LLM (Option A) & Secrets — LOCKED (SRS §6.3 `DEC-12`)**: Provider is **Anthropic only**, model **`claude-sonnet-5`** via the official `anthropic` SDK. **Do not add OpenAI or any second provider** — define the adapter interface (`generate` / `health_check` / `estimate_cost`) and implement exactly two backends (Anthropic, Ollama).
  - The API key is encrypted with **Windows DPAPI** (`CryptProtectData` / `CryptUnprotectData` via `ctypes` — no new dependency) and stored base64-encoded in `App_Config['api_key_encrypted']`. Decrypt **only in memory immediately before a call**, then discard.
  - **Never hardcode a master key, derive one from a machine-fixed string, or store the key in plaintext.** Never put the key in env vars, logs, error responses, or crash reports. Settings responses expose only `api_key_configured: bool` — not even a partially masked key.
  - A DPAPI decrypt failure (DB moved to another account/PC) must surface as a **re-entry prompt**, never a silent skip or an empty-key call.
  - Model ID and price-per-MTok live in `App_Config` (`llm_cloud_model`, `cloud_price_input_per_mtok`, `cloud_price_output_per_mtok`). **Never hardcode prices** — cost is computed from the response's actual `usage.input_tokens` / `usage.output_tokens` (REQ-NF-016).
- **Local LLM (Option B) & Provisioning — LOCKED (SRS §6.3.2 `DEC-13`)**: Two Ollama models with **distinct roles** — embedding `nomic-embed-text` (~274MB, required by **every** user including Option A, per `DEC-06`) and generation `qwen2.5:7b-instruct` (~4.7GB, **Option B only**). IDs live in `App_Config` (`local_embedding_model`, `local_generation_model`) — **never hardcode a model name**. Do not present the two as one bundled download in onboarding UI or progress text.
  - **"Offline" is a property of the steady state, not of installation.** Provisioning has exactly two modes, auto-detected by an installer reachability pre-check (HEAD, 5s timeout) and recorded in `Async_Task.result_json.provision_mode`:
    - `assisted` — silent install + `ollama pull`.
    - `detect_only` — **closed network: detect a pre-provisioned Ollama only. Never attempt an install or a model download.**
  - A failed download terminates the task as `status='failed'` + `error_code='LLM_PROVISION_REQUIRED'` with the required-model list surfaced to the user. **Never retry the installer in a loop, never leave the task parked in "downloading", and never silently fall back to Option A** — that last one exfiltrates document content without consent.
  - `POST /api/v1/llm/onboard` takes `{purpose: 'embedding'|'generation'}` and returns **`202` + `task_id`** (`DEC-04`); progress comes from polling, not from the POST response.
  - Model presence is checked via Ollama's `GET /api/tags`. **Do not bundle model weights in the exe or re-distribute them in a custom format** (CON-02) — the offline path is the documented `%USERPROFILE%\.ollama\models` copy.
  - REQ-NF-005 forbids sending **document content, file paths, and usage logs** outward. Exactly two user-initiated exceptions exist: masked chunks to Anthropic (Option A) and provisioning binaries. **Adding any third outbound destination is forbidden.**
- **PII Masking — LOCKED (SRS §6.3.3 `DEC-14`)**: Detection is **regex-only**, covering exactly seven types: RRN, phone, email, bank account, credit card, business registration number, passport number.
  - **NER is out of MVP scope.** `PIIFilter._ner_scan()` stays an interface-only **no-op**. **Do not add spaCy, transformers, or any in-process NER model** — that is a `DEC-06`/CON-02 reversal, not a dependency addition. Probabilistic detection cannot produce the pass/fail criterion REQ-FUNC-009's Fail-Safe requires.
  - The only mask token format is **`[PII:TYPE]`** (`[PII:RRN]`, `[PII:PHONE]`, `[PII:EMAIL]`, `[PII:ACCOUNT]`, `[PII:CARD]`, `[PII:BIZNO]`, `[PII:PASSPORT]`). **`[MASKED]` and `***-****-****` are both abolished** — the latter leaks digit count.
  - Integrity verification requires **both** conditions: ⓐ re-scanning the masked text with the same regex set yields **zero matches**, **AND** ⓑ every original matched string is **absent as a substring** of the result. One condition alone is a self-fulfilling check.
  - **Fail-closed**: every exception on the mask/verify path blocks transmission (`PII_MASKING_FAILED`, 500). "Verification did not run, so allow it" is forbidden.
  - **Never write matched PII strings or raw chunks to logs, error responses, or `Analytics_Log`** — only per-type match counts (`{"PHONE": 2}`). A masking log that stores PII is the failure mode this feature exists to prevent.
  - Replace overlapping matches back-to-front (widest match wins, merged) so offsets don't shift. Avoid nested quantifiers in every pattern (ReDoS); never assemble a pattern from user input.
  - Person and organization names are **not** masked. Surface that limit in the UI and require explicit consent on the first Option A transmission; do not paper over it.
- **Rename Prompts & Path Exposure — LOCKED (SRS §6.3.3 `DEC-17`)**: The `RenameManager → LLMRouter` path is a **second cloud transmission channel**, and it uses the **same `PIIFilter` gate** as analysis chunks. **Do not write Rename-specific masking logic, a different token format, or a separate exception path.** Masking applies to **every prompt leaving for Option A** — never branch on "is this a chunk or a filename", because the branch is the bypass.
  - **Never put an absolute path in a prompt.** Only `file_name` + extension + **1-depth folder name** + depth count may be sent. Full `current_path`/`original_path` strings, drive letters, `C:\Users\<name>`, and UNC server names are forbidden — same principle as `DEC-08` keeping paths out of wiki markdown.
  - If the LLM response still contains a `[PII:TYPE]` token, **do not use it as a filename** — exclude that file from the diff and mark it "PII present — manual review". **Un-masking (substituting the original PII back) is forbidden.**
  - Validate suggested names against Windows forbidden characters (`\ / : * ? " < > |`), reserved device names (`CON`, `PRN`, `NUL`, `COM1`…), trailing spaces/dots, and `MAX_PATH` before offering them.
  - The call goes through `NetworkGuard` with `purpose='llm_cloud'` like every other egress (`DEC-15`). **Do not build a Rename-specific HTTP client.**
  - Option B (loopback Ollama) is not an external transmission, so masking does not gate it — but the path-exposure rule still holds for prompt hygiene.
  - "A filename is too short to hold PII" is wrong: `홍길동_연봉계약서_2026.docx` carries a name, a document type, and a date in one line.
- **LLM Failure & Cost — LOCKED (SRS §6.3 `DEC-16`)**: **Never auto-switch engines.** An Option A failure must not silently fall back to Option B (or the reverse) — the A/B choice is a security decision, and switching changes whether documents leave the machine, plus quality, cost, and runtime, without consent. Engine changes come only from an explicit settings action.
  - Retry **transient errors only**: HTTP `429`, `5xx`, connect/read timeouts. **Never retry** `401`, `400`, `EgressBlockedError` (`DEC-15`), or `PII_MASKING_FAILED` (`DEC-14`) — the outcome is identical and only burns cost and time.
  - Retry policy is **max 3 attempts, exponential backoff (1s → 2s → 4s + jitter)**, honoring `retry-after` when present. **No unbounded retry loops.**
  - Timeouts come from `App_Config` (`llm_timeout_connect` 10s, `llm_timeout_read` 120s, embedding 30s, health check 5s). **Do not hardcode timeout values.**
  - After retries are exhausted, **fail that one file and continue the task**. Accumulate failures in `Async_Task` per-file commits and return **HTTP 207 + `ok:true` + `data.failed[]`** (`DEC-03`). Failure entries carry `file_id` + `error.code` — **never the source chunk or prompt**.
  - **Never return 200/`ok:true` for a partially failed task.** A silent skip means the user trusts a wiki with documents missing from it.
  - Abort the whole task only when the pre-flight health check fails or **10 consecutive failures** occur → `status='failed'` + `LLM_UNAVAILABLE`.
  - Failed files keep `File_Meta.parse_status != 'parsed'`, so re-analysis reprocesses exactly them. **Do not build a separate retry queue.**
  - Prices are **migration-seeded** into `App_Config` with `cloud_price_updated_at`, user-editable in settings. **Never fetch a price table over the network** — that would be a fourth egress destination (`DEC-15`). Displayed cost is an **estimate**; always show the price reference date, never label it as the actual bill.
  - Option B failures use the same rules and record `Analytics_Log.cost_usd = 0` (not `NULL`) — `0` means "no cost", `NULL` means "not measured".
- **Network Egress & Zero-Telemetry — LOCKED (SRS §4.2 `DEC-15`)**: Every outbound network request goes through the **single `NetworkGuard` module**. `NetworkGuard` is **outbound-only** — the `DEC-02` FastAPI loopback server is inbound and out of its scope.
  - Each call requires a **`purpose` tag**, and only three `(purpose, destination)` pairs exist: `llm_local` → `127.0.0.1:11434`, `llm_cloud` → `api.anthropic.com`, `provisioning` → the Ollama distribution host. A mismatched pair (e.g. `provisioning` aimed at Anthropic) is blocked too.
  - The whitelist is a **code constant inside `NetworkGuard`**. **Never read it from `App_Config`, a settings file, or an env var** — a runtime-mutable whitelist is not a whitelist.
  - Host matching is **exact**. Never use substring or suffix matching (`evil-api.anthropic.com.attacker.net` must not pass).
  - A violation raises `EgressBlockedError` and **no request is issued**. Log the blocked host and `purpose` only — never the request body.
  - **Do not import `httpx`, `requests`, `socket`, or `urllib.request` in any module other than `NetworkGuard`** — a CI lint rule enforces this and failing it blocks the merge. Route the call through `NetworkGuard` instead.
  - `purpose='provisioning'` requests carry **no document data** — not in the body, query string, or User-Agent.
  - **Never add a remote telemetry or crash-reporting SDK** (GA, Sentry, PostHog, …). Crash details go to the local rolling log only.
  - **Adding a fourth destination is a design-decision change, not a code change**: the `DEC-15` whitelist table and `REQ-NF-005` must be updated in the same change, otherwise reject it.
  - Do not monkey-patch `socket.socket` at runtime to enforce this — it intercepts ChromaDB/`anthropic` SDK internals and breaks unpredictably under PyInstaller. The import lint achieves the same goal statically.
- **React Frontend**: Follow modern ESNext conventions for UI components. Frontend communicates with Python Core exclusively via IPC (REST API / JSON).
- **Local API Server — LOCKED (SRS §3.3 `DEC-02`)**: **FastAPI + uvicorn** (daemon thread, started before the WebView loads), DTOs as **Pydantic v2** models.
  - Bind to **`127.0.0.1` only** with an **OS-assigned random port** (`port=0`). Never bind `0.0.0.0`; never hardcode a fixed port.
  - Every `/api/v1/*` route MUST pass the **`Authorization: Bearer <session-token>`** middleware (token from `secrets.token_urlsafe(32)` at boot). **Never add a route that bypasses token verification**, including debug routes. Never write the token to disk, env vars, or logs.
  - CORS `allow_origins` restricted to the injected local origin — wildcard `*` is forbidden.
  - The **FastAPI-generated OpenAPI 3.1 schema is the contract SSOT**. Generate frontend TypeScript types from it; do not hand-maintain a parallel type file.
- **IPC Contract — LOCKED (SRS §6.1 `DEC-03`)**:
  - **All JSON field names are `snake_case`** at every layer (Python model, wire payload, frontend consumption). Do **not** add a camelCase conversion layer (`alias_generator=to_camel`) — alias drift causes silent field loss. Component-internal local variables may follow JS convention.
  - Resource paths are **singular** (`/api/v1/workspace`, not `/workspaces`).
  - Every response uses the envelope: success `{"ok": true, "data": {...}}` / failure `{"ok": false, "error": {"code", "message", "field?", "details?"}}`. Normalize FastAPI's default `{"detail": ...}` via exception handlers; never leak it. Partial failure = **HTTP 207 + `ok: true` + `data.failed[]`**; only total failure uses `ok: false`.
  - Use the standard `error.code` identifiers from the `DEC-03` table (`VALIDATION_FAILED`, `UNAUTHORIZED`, `NOT_FOUND`, `PATH_NOT_ACCESSIBLE`, `SCAN_LIMIT_REACHED`, `LLM_UNAVAILABLE`, `LLM_PROVISION_REQUIRED`, `PII_MASKING_FAILED`, `ALREADY_UNDONE`, `INTERNAL_ERROR`). Adding a new code requires updating that table in the same change.
  - **Never include stack traces or absolute internal paths in an error response body** — log them locally instead.
- **Long-Running Tasks — LOCKED (SRS §6.1 `DEC-04`)**: `scan`, `analyze_fast`, `analyze_deep`, `llm_onboard`, `rename_apply`, `rename_undo` return **`202` + `task_id` immediately**; the frontend polls `GET /api/v1/analyze/{task_id}/progress` at **1s intervals**. **Do not introduce WebSocket or SSE** — no push channel exists by design.
  - Task state lives in the **SQLite `Async_Task` table, never in an in-memory dict** — this is what satisfies REQ-NF-011 (RPO/RTO). Commit progress after each processed file.
  - On boot, transition `queued`/`running` rows to **`interrupted`** and ask the user before resuming. **Never auto-resume** a stranded task. Resume must be idempotent (skip `File_Meta.parse_status == 'parsed'`).
  - Do not return large payloads (wiki markdown) in a progress response — read persisted rows instead.
- **Deeplink Anchoring & Path Identity — LOCKED (SRS §6.2.3 `DEC-08`)**: A file's stable identity is its **`file_id` (UUID)**, never its path.
  - The only deeplink anchor format in wiki markdown is **`[[file_id:<UUID>]]`**. `Wiki_Content.deeplink_mappings` maps sentence index → `file_id`. **Never persist an absolute path inside `markdown_content`, `deeplink_mappings`, or vector metadata** — a cached path is exactly what our own rename feature invalidates.
  - `File_Meta` has two path columns: **`current_path`** (live location, mutable) and **`original_path`** (first-scan location, immutable, audit only). **All file opening and existence checks use `current_path`.** Never open `original_path`.
  - Rename, Undo, and Watcher move events resolve to a **single-row `UPDATE` of `current_path` + `file_name`**. They must not touch `Wiki_Content`, `deeplink_mappings`, or re-embed vectors. On `FileMovedEvent`, look the row up by `src_path` and update it — **never re-register the file under a new `file_id`** (that silently orphans every deeplink and analytics row).
  - `os.startfile` targets are resolved server-side from `file_id`. **Never accept a caller-supplied path** in a request body or query param.
  - Broken link (REQ-FUNC-022) means "`current_path` exists in the DB but not on disk", or the `file_id` row is gone. Internal renames are, by definition, never broken links.
- **Preserve Documentation**: Maintain documentation integrity. Do not delete or modify existing architectural docstrings, inline comments, or project documentation files unless explicitly requested by the task.
- **Error Handling & Resilience**: Never allow silent failures or bare `except:` clauses. Specifically for OS filesystem operations, handle Windows `MAX_PATH` limits (260 characters), file locking restrictions (`PermissionError`, `OSError`), and UNC path edge cases gracefully. All exceptions must be logged with context.
- **No Hallucinated Dependencies**: Do not install new external third-party libraries or pip packages without documented technical justification or explicit instructions in the task specification. Leverage existing workspace tools and Python standard library (`os`, `pathlib`, `json`, `sqlite3`, `re`, etc.) wherever feasible.
  - **Pre-approved by design decisions** (no further justification needed): `pywebview`, `pyinstaller` (`DEC-01`); `fastapi`, `uvicorn`, `pydantic` (`DEC-02`); `chromadb` (`DEC-06`); `anthropic` (`DEC-12`); `watchdog`, `python-docx`, `pdfminer.six` (SRS §8). Anything beyond this list still requires justification.
  - **Explicitly forbidden**: SQLAlchemy / SQLModel / Alembic / Prisma (`DEC-05`), Electron / Tauri / Next.js / any shipped Node runtime (`DEC-01`), `faiss` / `sentence-transformers` / `torch` (`DEC-06`), WebSocket / SSE libraries (`DEC-04`), `openai` or any second LLM provider SDK (`DEC-12`), third-party keyring/crypto wrappers for secret storage — use DPAPI via `ctypes` (`DEC-12`), `spacy` / `transformers` / any NER model for PII detection (`DEC-14`), `sentry-sdk` / `posthog` / any remote telemetry or crash-reporting SDK (`DEC-15`).

## 5. Definition of Done (DoD) & Verification
A task is considered **DONE** only when ALL of the following criteria are verified:
1. **Acceptance Criteria**: All BDD/GWT (Given/When/Then) scenarios described in the issue specification are logically implemented and verified.
2. **Automated & Unit Testing**: Associated test cases (e.g., `TC-ANA-001`, `*-TEST-*` specifications) pass without regressions. If tests do not yet exist for a new module, write minimal verification test suites or scripts.
3. **Clean Build & Zero Lint Errors**: The codebase must build and run cleanly without syntax errors, unhandled runtime exceptions, or resource leaks.

## 6. Project Environment & Build
- **Python Version**: 3.10+ (type hints, `match` statements allowed)
- **Package Manager**: `pip` with `requirements.txt` (or `pyproject.toml` if configured)
- **Test Framework**: `pytest` (default) — run with `pytest tests/` from project root
- **Linter**: `ruff` or `flake8` — zero lint errors required before PR
- **Database**: SQLite (`corpbrain_meta.db`) at `%LocalAppData%\CorpBrain\` — stdlib `sqlite3`, `PRAGMA user_version` migrations in `migrations/` (see §4 `DEC-05`)
- **Frontend**: React SPA built by Vite with `base: './'` (relative assets, HashRouter) → static bundle embedded in the exe; communicates via REST IPC
- **Desktop Shell**: `pywebview` (WebView2 backend) — see §1 `DEC-01`
- **Packaging**: PyInstaller `--onefile` → single `CorpBrain.exe` for Windows 10/11
- **Key Directories**:
  - `src/` — Python backend source (core modules per SRS §6.4 Class Diagram)
  - `tests/` — pytest test suites
  - `frontend/` — React UI source
  - `docs/` — PRD, SRS, and architectural documents
  - `scripts/` — Build, migration, and utility scripts

## 7. Communication & Autonomy Limits
- **Stop and Seek Escalation/Guidance** immediately if you encounter:
  - Underspecified, ambiguous, or contradictory requirements between the Issue Body and structural blueprints.
  - Breaking database schemas or DTO contract changes that would invalidate existing downstream modules.
  - API rate-limiting, system permission denials, or unreachable local daemons (e.g., Ollama offline during setup).
- **Concise Reporting**: Keep descriptive outputs and progress reports to the user clean, factual, and structured in GitHub-flavored Markdown. Focus on architectural decisions and verification results rather than redundant storytelling.
