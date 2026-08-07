import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("CorpBrain.LLMResilience")


class LLMUnavailableException(Exception):
    """Raised when 10 consecutive files fail (DEC-16)."""
    pass


class LLMResilienceService:
    def __init__(
        self,
        max_retries: int = 3,
        backoff_base_sec: float = 1.0,
        consecutive_fail_limit: int = 10,
    ):
        self.max_retries = max_retries
        self.backoff_base_sec = backoff_base_sec
        self.consecutive_fail_limit = consecutive_fail_limit
        self._consecutive_failures = 0

    def reset_failure_counter(self):
        self._consecutive_failures = 0

    def execute_with_retry(
        self,
        func: Callable[[], Any],
        file_id: str,
        is_transient_error: Optional[Callable[[Exception], bool]] = None,
    ) -> Any:
        """
        Executes an LLM or embedding call with up to max_retries exponential backoff (DEC-16).
        Raises Exception if all retries fail.
        """
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = func()
                # On success, reset consecutive failure counter
                self._consecutive_failures = 0
                return result
            except Exception as e:
                last_exception = e
                # Check if transient error (e.g. rate limit, timeout)
                if is_transient_error and not is_transient_error(e):
                    logger.warning(f"[LLMResilience] Non-transient error for file {file_id}: {e}")
                    break
                if attempt < self.max_retries:
                    sleep_time = self.backoff_base_sec * (2 ** (attempt - 1))
                    logger.info(
                        f"[LLMResilience] Attempt {attempt}/{self.max_retries} failed for file {file_id}. Retrying in {sleep_time}s..."
                    )
                    time.sleep(sleep_time)

        # All retries failed
        self._consecutive_failures += 1
        logger.error(
            f"[LLMResilience] File {file_id} failed after {self.max_retries} attempts (Consecutive failures: {self._consecutive_failures}/{self.consecutive_fail_limit}). Error: {last_exception}"
        )

        if self._consecutive_failures >= self.consecutive_fail_limit:
            raise LLMUnavailableException(
                f"Consecutive failure limit reached ({self.consecutive_fail_limit} files). LLM engine unavailable."
            )

        raise last_exception

    def process_file_batch(
        self,
        files: List[Dict[str, Any]],
        process_file_func: Callable[[Dict[str, Any]], Any],
    ) -> Dict[str, Any]:
        """
        Process a batch of files with file isolation (DEC-16).
        Single file failures do not stop the batch; failed files are accumulated into failed_files list.
        Aborts early with LLM_UNAVAILABLE if 10 consecutive files fail.
        """
        succeeded: List[str] = []
        failed: List[Dict[str, Any]] = []

        self.reset_failure_counter()

        for f in files:
            file_id = f.get("file_id", "unknown")
            try:
                # Bind the loop variable explicitly. The lambda is invoked inside this same
                # iteration so late binding is harmless today, but a future change that defers
                # the call would silently process the last file N times.
                self.execute_with_retry(lambda f=f: process_file_func(f), file_id=file_id)
                succeeded.append(file_id)
            except LLMUnavailableException as ue:
                logger.error(f"[LLMResilience] Aborting batch due to circuit breaker: {ue}")
                failed.append({
                    "file_id": file_id,
                    "error_code": "LLM_UNAVAILABLE",
                    "error_message": str(ue)
                })
                return {
                    "status": "failed",
                    "error_code": "LLM_UNAVAILABLE",
                    "succeeded_count": len(succeeded),
                    "failed": failed,
                    "aborted_early": True
                }
            except Exception as e:
                failed.append({
                    "file_id": file_id,
                    "error_code": type(e).__name__,
                    "error_message": str(e)
                })

        status = "completed" if not failed else "multi_status"
        return {
            "status": status,
            "succeeded_count": len(succeeded),
            "failed": failed,
            "aborted_early": False
        }
