import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from src.backend.db import DatabaseManager
from src.backend.pii_filter import PIIFilter, PIIMaskingFailedException
from src.backend.utils.file_utils import derive_folder_1depth

logger = logging.getLogger("CorpBrain.RenameService")


class RenameService:
    INVALID_WIN_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|]')
    RESERVED_WIN_NAMES = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    }

    #: The instruction sent to the LLM. Deliberately demands JSON only: a model that explains
    #: itself in prose would have its prose parsed as a filename.
    #:
    #: Note what the context does NOT contain — no absolute path, no drive letter, no
    #: `C:\Users\<account>`, no UNC server name (DEC-17). Only the filename, extension, the
    #: 1-depth folder name and a depth count, which is the whole allowance.
    SUGGEST_PROMPT_TEMPLATE = (
        "다음 파일에 대해 일관된 규칙의 새 파일명 하나를 제안하세요.\n"
        "규칙: [연도-월]_[문서종류]_[핵심주제] 형식, 한글 유지, 확장자 보존.\n"
        "파일명: {file_name}\n"
        "확장자: {extension}\n"
        "상위 폴더: {folder_1depth}\n"
        "폴더 깊이: {depth_level}\n"
        '반드시 이 JSON 형식만 출력하세요: {{"suggested_name": "새이름{extension}"}}'
    )

    def __init__(
        self,
        db_mgr: DatabaseManager,
        pii_filter: Optional[PIIFilter] = None,
        llm_router: Optional[Any] = None,
        resilience: Optional[Any] = None,
    ):
        self.db_mgr = db_mgr
        self.pii_filter = pii_filter or PIIFilter()
        # Injected so a test can drive the real masking/parsing/validation path without a live
        # model. Constructed lazily rather than defaulted to None: a None router that silently
        # skipped the LLM is exactly the hardcoded-suggestion state this issue replaces
        # (DECISION_LOG 재발방지 4 — a default that bypasses the real path proves nothing).
        self._llm_router = llm_router
        # DEC-16: max 3 attempts, exponential backoff, transient errors only.
        self._resilience = resilience
        # The history row written by the most recent process_rename_suggestions call, read back
        # by generate_rename_diff. Per-instance rather than returned from
        # process_rename_suggestions so that method's List return type is unchanged for its
        # three existing callers.
        self._last_history_id: Optional[str] = None

    @property
    def llm_router(self) -> Any:
        """The LLMRouter, built on first use so constructing this service stays cheap."""
        if self._llm_router is None:
            from src.backend.config_manager import ConfigManager
            from src.backend.services.llm_router import LLMRouter
            self._llm_router = LLMRouter(ConfigManager(self.db_mgr))
        return self._llm_router

    @property
    def resilience(self) -> Any:
        if self._resilience is None:
            from src.backend.services.llm_resilience_service import LLMResilienceService
            self._resilience = LLMResilienceService()
        return self._resilience

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        """
        DEC-16: retry 429/5xx and connect/read timeouts only.

        Never retried: 401 (bad key), 400 (bad request), EgressBlockedError (DEC-15),
        PIIMaskingFailedException (DEC-14). Retrying those burns cost and time for an identical
        outcome — and re-running a masking failure would repeatedly attempt to transmit.
        """
        from src.backend.network_guard import (
            EgressBlockedError,
            UpstreamStatusError,
            UpstreamUnavailableError,
        )

        if isinstance(exc, (EgressBlockedError, PIIMaskingFailedException)):
            return False
        if isinstance(exc, UpstreamStatusError):
            return exc.status_code == 429 or 500 <= exc.status_code < 600
        if isinstance(exc, (UpstreamUnavailableError, TimeoutError)):
            return True
        return False

    @classmethod
    def parse_suggestion(cls, content: str, fallback_extension: str = "") -> Optional[str]:
        """
        Pull `suggested_name` out of the model's reply.

        Tolerates the two things models do even when told not to: wrapping JSON in a ```json
        fence, and adding a sentence before or after it. A brace-scan is used rather than
        `json.loads(content)` so surrounding prose does not discard an otherwise valid answer.

        Returns None when nothing usable is present — the caller then keeps the original name
        rather than inventing one (DEC-16 partial failure).
        """
        if not content:
            return None

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(content[start : end + 1])
                name = parsed.get("suggested_name")
                if isinstance(name, str) and name.strip():
                    # Returned verbatim, NOT stripped. A trailing space or dot is invalid on
                    # Windows, and quietly trimming it here would hand `is_valid_windows_filename`
                    # a name the model never proposed — so the validation would pass on a
                    # different string than the one under review. Let the validator reject it and
                    # tell the user, rather than silently repairing a name they will then approve.
                    return name
            except (json.JSONDecodeError, AttributeError):
                pass

        # A bare filename on its own line is accepted as a last resort, but only if it looks
        # like one — otherwise a refusal sentence ("죄송하지만...") would become a filename.
        stripped = content.strip()
        if fallback_extension and stripped.endswith(fallback_extension) and "\n" not in stripped:
            return stripped
        return None

    @classmethod
    def build_prompt_context(cls, file_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build prompt context containing ONLY relative file info (DEC-17).
        Strictly excludes current_path, original_path, drive letters, user profile paths.
        """
        current_path = file_meta.get("current_path", "").replace("\\", "/")
        parts = [p for p in current_path.split("/") if p]

        folder_1depth = derive_folder_1depth(current_path)
        depth_level = len(parts)

        return {
            "file_name": file_meta.get("file_name", ""),
            "extension": file_meta.get("extension", ""),
            "folder_1depth": folder_1depth,
            "depth_level": depth_level,
        }

    @classmethod
    def is_valid_windows_filename(cls, name: str) -> bool:
        """Validate Windows filename safety (DEC-17 / REQ-NF-007)."""
        if not name or len(name) > 255:
            return False

        # Invalid characters
        if cls.INVALID_WIN_CHARS_PATTERN.search(name):
            return False

        # Trailing space or dot
        if name.endswith(" ") or name.endswith("."):
            return False

        # Reserved Windows names
        base_name = name.split(".")[0].upper()
        if base_name in cls.RESERVED_WIN_NAMES:
            return False

        return True

    def generate_rename_diff(
        self,
        workspace_id: str,
        files: List[Dict[str, Any]],
        mock_llm_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        `process_rename_suggestions` plus the `history_id` of the row it wrote.

        The API layer needs that id: DEC-08 keeps absolute paths off the client, so the frontend
        cannot assemble the `items` list `apply_rename` takes and must hand back the id instead.
        The id was previously reachable only by re-querying Rename_History, which would put SQL
        outside a Repository (DEC-05) or make the client guess the newest row.
        """
        items = self.process_rename_suggestions(workspace_id, files, mock_llm_callback)
        return {"items": items, "history_id": self._last_history_id}

    def process_rename_suggestions(
        self,
        workspace_id: str,
        files: List[Dict[str, Any]],
        mock_llm_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Processes file list for rename recommendations:
        1. Builds relative prompt context (no absolute path)
        2. Applies PIIFilter gate (DEC-17)
        3. Obtains LLM suggestion
        4. Rejects names containing leftover [PII:TYPE] tokens
        5. Validates Windows filename safety
        6. Saves Diff in Rename_History
        """
        diff_results = []
        old_paths_list = []
        new_paths_list = []

        for f in files:
            ctx = self.build_prompt_context(f)
            raw_prompt = self.SUGGEST_PROMPT_TEMPLATE.format(**ctx)

            try:
                # DEC-17: the same PIIFilter gate as analysis chunks — no Rename-specific
                # masking logic, no separate token format, and no branch on "is this a chunk or
                # a filename", because that branch is the bypass.
                masked = self.pii_filter.mask(raw_prompt)
            except PIIMaskingFailedException as e:
                # Fail-closed (DEC-14): the transmission is blocked. Only the exception is
                # logged — never the filename, which is what the masking failed to sanitise.
                logger.warning(f"[RN-CMD-01] PII masking failed, transmission blocked: {type(e).__name__}")
                diff_results.append({
                    "file_id": f["file_id"],
                    "old_name": f["file_name"],
                    "new_name": f["file_name"],
                    "status": "PII_MASKING_FAILED",
                    "note": "PII 마스킹 실패 — 수동 확인 필요"
                })
                continue

            if masked.counts:
                # Per-type counts only, never the matched strings (DEC-14 log hygiene).
                logger.info(f"[RN-CMD-01] Masked PII before transmission: {masked.counts}")

            if mock_llm_callback is not None:
                # Retained for the three existing callers and for tests that need a fixed
                # suggestion. It receives the *masked* prompt, not the raw filename, so a test
                # double cannot accidentally exercise a path that skips the gate.
                suggested_name = mock_llm_callback(masked.masked_text)
            else:
                suggested_name = self._request_suggestion(masked.masked_text, ctx, f["file_id"])

            if suggested_name is None:
                # DEC-16 partial failure: this one file drops out and keeps its original name;
                # the batch continues. The failure is not retried again here — `_request_suggestion`
                # already exhausted the retry policy.
                diff_results.append({
                    "file_id": f["file_id"],
                    "old_name": f["file_name"],
                    "new_name": f["file_name"],
                    "status": "LLM_FAILED",
                    "note": "추천 실패 — 원래 이름 유지"
                })
                continue

            # Check leftover [PII:TYPE] tokens (DEC-17)
            if "[PII:" in suggested_name:
                diff_results.append({
                    "file_id": f["file_id"],
                    "old_name": f["file_name"],
                    "new_name": f["file_name"],
                    "status": "PII_TOKEN_LEFT",
                    "note": "PII 포함 — 수동 확인 필요"
                })
                continue

            # Check Windows filename safety (DEC-17)
            if not self.is_valid_windows_filename(suggested_name):
                diff_results.append({
                    "file_id": f["file_id"],
                    "old_name": f["file_name"],
                    "new_name": f["file_name"],
                    "status": "INVALID_FILENAME",
                    "note": "유효하지 않은 파일명"
                })
                continue

            diff_results.append({
                "file_id": f["file_id"],
                "old_name": f["file_name"],
                "new_name": suggested_name,
                "status": "pending",
                "note": "추천 완료"
            })
            old_paths_list.append(f["current_path"])
            new_paths_list.append(os.path.join(os.path.dirname(f["current_path"]), suggested_name))

        # Save Diff history in DB
        history_id = str(uuid.uuid4())
        with self.db_mgr.transaction() as conn:
            conn.execute(
                """INSERT INTO Rename_History (history_id, workspace_id, old_paths, new_paths, status)
                   VALUES (?, ?, ?, ?, ?);""",
                (history_id, workspace_id, json.dumps(old_paths_list), json.dumps(new_paths_list), "pending"),
            )
        self._last_history_id = history_id

        return diff_results

    def _request_suggestion(
        self, masked_prompt: str, ctx: Dict[str, Any], file_id: str
    ) -> Optional[str]:
        """
        Ask the configured engine for one filename, with the DEC-16 retry policy.

        **`masked_prompt` is what goes out — never the raw prompt.** That is the whole point of
        DEC-17: the Rename path is a second cloud transmission channel and uses the same gate as
        analysis chunks.

        Returns None on failure so the caller can keep the original name and continue with the
        rest of the batch. The engine is never switched on failure (DEC-16): Option A ↔ Option B
        changes whether documents leave the machine, so it only ever comes from an explicit
        settings action.
        """
        try:
            response = self.resilience.execute_with_retry(
                lambda: self.llm_router.generate(masked_prompt, max_tokens=200),
                file_id=file_id,
                is_transient_error=self._is_transient,
            )
        except Exception as e:
            # Bare `except Exception` is deliberate and narrow in effect: every failure mode
            # here (unavailable engine, bad key, blocked egress, retries exhausted) has the same
            # correct outcome — drop this one file. The type is logged; the message is not
            # surfaced to a client (DEC-03).
            logger.warning(
                "[RN-CMD-01] Suggestion failed for file %s: %s", file_id, type(e).__name__
            )
            return None

        content = (response or {}).get("content", "") if isinstance(response, dict) else ""
        return self.parse_suggestion(content, ctx.get("extension", ""))

    def apply_rename(
        self,
        workspace_id: str,
        items: Optional[List[Dict[str, Any]]] = None,
        history_id: Optional[str] = None,
        file_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes OS-level physical file rename and updates SQLite File_Meta (RN-CMD-02 / DEC-08 / DEC-05).
        - Updates File_Meta.current_path and file_name per file commit (DEC-05).
        - Leaves original_path and Wiki_Content untouched (DEC-08).
        - Handles file locks/errors via partial failure (HTTP 207).

        `file_ids` narrows the batch to the user's selection (AC S2, issue #40). `None` applies
        everything, which is what every existing caller expects. The filter is applied to the
        resolved pairs rather than trusting the caller to send paths — DEC-08 keeps absolute paths
        off the client, so a selection can only ever be expressed as ids.
        """
        if not items and history_id:
            conn = self.db_mgr.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT old_paths, new_paths FROM Rename_History WHERE history_id = ?;", (history_id,))
            row = cursor.fetchone()
            if row:
                old_list = json.loads(row["old_paths"])
                new_list = json.loads(row["new_paths"])
                items = []
                # strict=True: the two JSON arrays are written together in
                # process_rename_suggestions, so unequal lengths mean a corrupted history row.
                for old_p, new_p in zip(old_list, new_list, strict=True):
                    # Fetch file_id from File_Meta by current_path == old_p
                    c = conn.cursor()
                    c.execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (old_p,))
                    r = c.fetchone()
                    if r:
                        items.append({"file_id": r["file_id"], "old_path": old_p, "new_path": new_p})

        if items and file_ids is not None:
            # Intersect rather than reorder or extend: an id the batch does not contain is
            # silently dropped, because the alternative is renaming a file the history row never
            # described. An empty selection therefore applies nothing, which is the correct
            # reading of "the user approved none of them".
            selected = set(file_ids)
            items = [i for i in items if i["file_id"] in selected]

        if not items:
            return {"status": "completed", "applied_count": 0, "failed": []}

        succeeded = []
        failed = []

        for item in items:
            file_id = item["file_id"]
            old_path = item["old_path"]
            new_path = item["new_path"]
            new_name = os.path.basename(new_path)

            if not os.path.exists(old_path):
                failed.append({
                    "file_id": file_id,
                    "old_path": old_path,
                    "new_path": new_path,
                    "error_code": "FILE_NOT_FOUND",
                    "error_message": "원본 파일이 존재하지 않습니다."
                })
                continue

            try:
                # 1. Physical OS Rename
                os.rename(old_path, new_path)

                # 2. Update File_Meta current_path and file_name per file commit (DEC-05 / DEC-08)
                with self.db_mgr.transaction() as conn:
                    conn.execute(
                        """UPDATE File_Meta
                           SET current_path = ?, file_name = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                           WHERE file_id = ?;""",
                        (new_path, new_name, file_id),
                    )
                succeeded.append({"file_id": file_id, "old_path": old_path, "new_path": new_path})
                logger.info(f"[RenameService] Renamed file {file_id}: {old_path} -> {new_path}")
            except Exception as e:
                logger.error(f"[RenameService] OS Rename failed for file {file_id}: {e}")
                failed.append({
                    "file_id": file_id,
                    "old_path": old_path,
                    "new_path": new_path,
                    "error_code": type(e).__name__,
                    "error_message": str(e)
                })

        status = "applied" if not failed else "multi_status"

        # Update the Rename_History row's status to reflect completion (issue #90 fix).
        # DEC-05: SQL only inside Repository classes, but Rename_History has no dedicated repository
        # yet, and this is a single-row write tied to the rename transaction, so it stays here.
        if history_id:
            with self.db_mgr.transaction() as conn:
                conn.execute(
                    "UPDATE Rename_History SET status = ? WHERE history_id = ?;",
                    (status, history_id)
                )

        return {
            "status": status,
            "applied_count": len(succeeded),
            "succeeded": succeeded,
            "failed": failed
        }

    def undo_rename(self, workspace_id: str, history_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reverts OS physical file names to old_paths based on Rename_History (RN-CMD-03 / DEC-08).
        - Reverts File_Meta.current_path and file_name.
        - Leaves original_path and Wiki_Content untouched (DEC-08).
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()

        if history_id:
            cursor.execute(
                """SELECT history_id, old_paths, new_paths, status, undone_at
                   FROM Rename_History WHERE history_id = ?;""",
                (history_id,),
            )
        else:
            # Most recent first — "최근 변경된 항목 조회 (역순)". Without an explicit history_id
            # the newest batch is the one the user means by "undo".
            cursor.execute(
                """SELECT history_id, old_paths, new_paths, status, undone_at
                   FROM Rename_History WHERE workspace_id = ?
                   ORDER BY created_at DESC LIMIT 1;""",
                (workspace_id,)
            )

        row = cursor.fetchone()
        if not row:
            return {"status": "no_history", "reverted_count": 0, "failed": []}

        hist_id = row["history_id"]

        # Already reverted: answer ALREADY_UNDONE rather than walking the pairs again.
        #
        # A second pass finds every file back at `old_path`, so `os.path.exists(new_path)` fails
        # for all of them and the caller receives per-file FILE_NOT_FOUND — an error describing a
        # missing file when the truth is that the work was already done. Worse, if the user has
        # since created a *new* file at one of those `new_path` names, the second undo would
        # rename that unrelated file (RenamePage already expects this code — issue #39).
        if row["status"] == "reverted":
            return {
                "history_id": hist_id,
                "status": "already_undone",
                "error_code": "ALREADY_UNDONE",
                "undone_at": row["undone_at"],
                "reverted_count": 0,
                "succeeded": [],
                "failed": [],
            }

        old_list = json.loads(row["old_paths"])
        new_list = json.loads(row["new_paths"])

        succeeded = []
        failed = []

        # strict=True — same paired-array invariant as apply_rename.
        # Reversed: the batch is undone in the opposite order it was applied. It matters when a
        # batch renamed A→B and B→C — replaying forwards would put A back while C still occupies
        # B's slot, and reverse order frees each target before the next revert needs it.
        for old_path, new_path in reversed(list(zip(old_list, new_list, strict=True))):
            old_name = os.path.basename(old_path)
            # Find file_id by current_path == new_path
            cursor.execute("SELECT file_id FROM File_Meta WHERE current_path = ?;", (new_path,))
            file_row = cursor.fetchone()
            file_id = file_row["file_id"] if file_row else "unknown"

            if not os.path.exists(new_path):
                failed.append({
                    "file_id": file_id,
                    "current_path": new_path,
                    "target_path": old_path,
                    "error_code": "FILE_NOT_FOUND",
                    "error_message": "원복할 대상 파일이 존재하지 않습니다."
                })
                continue

            try:
                # 1. OS Rename back to old_path
                os.rename(new_path, old_path)

                # 2. Update File_Meta current_path and file_name (DEC-08)
                if file_id != "unknown":
                    with self.db_mgr.transaction() as c:
                        c.execute(
                            """UPDATE File_Meta
                               SET current_path = ?, file_name = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                               WHERE file_id = ?;""",
                            (old_path, old_name, file_id),
                        )
                succeeded.append({"file_id": file_id, "reverted_path": old_path})
            except Exception as e:
                failed.append({
                    "file_id": file_id,
                    "current_path": new_path,
                    "target_path": old_path,
                    "error_code": type(e).__name__,
                    "error_message": str(e)
                })

        status = "reverted" if not failed else "multi_status"

        # Mark the batch reverted only on a clean sweep. A partial revert stays un-flagged on
        # purpose: some files are still at their new names, so the batch genuinely is not undone
        # and a retry must be allowed to finish the job. Flagging it would strand those files
        # behind ALREADY_UNDONE with no way to complete the revert.
        if status == "reverted":
            with self.db_mgr.transaction() as c:
                c.execute(
                    """UPDATE Rename_History
                       SET status = 'reverted',
                           undone_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                       WHERE history_id = ?;""",
                    (hist_id,),
                )

        return {
            "history_id": hist_id,
            "status": status,
            "reverted_count": len(succeeded),
            "succeeded": succeeded,
            "failed": failed
        }
