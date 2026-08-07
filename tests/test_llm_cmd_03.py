from src.backend.services.llm_resilience_service import (
    LLMResilienceService,
)


def test_scenario_1_transient_error_retry_and_recovery():
    service = LLMResilienceService(max_retries=3, backoff_base_sec=0.01)
    attempts = 0

    def mock_flaky_llm_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("Temporary connection timeout (HTTP 504)")
        return "Success response"

    res = service.execute_with_retry(mock_flaky_llm_call, file_id="file_001")
    assert res == "Success response"
    assert attempts == 3


def test_scenario_2_single_file_isolation_in_batch():
    service = LLMResilienceService(max_retries=2, backoff_base_sec=0.01)

    files = [{"file_id": f"file_{i:02d}"} for i in range(1, 11)]

    def process_func(f):
        # File 3 raises persistent error
        if f["file_id"] == "file_03":
            raise ValueError("Corrupt file content")
        return True

    batch_res = service.process_file_batch(files, process_func)

    assert batch_res["status"] == "multi_status"
    assert batch_res["succeeded_count"] == 9
    assert len(batch_res["failed"]) == 1
    assert batch_res["failed"][0]["file_id"] == "file_03"
    assert batch_res["failed"][0]["error_code"] == "ValueError"
    assert batch_res["aborted_early"] is False


def test_scenario_3_consecutive_failures_circuit_breaker():
    service = LLMResilienceService(max_retries=1, backoff_base_sec=0.01, consecutive_fail_limit=10)

    # 15 failing files
    files = [{"file_id": f"bad_file_{i:02d}"} for i in range(1, 16)]

    def always_fail(f):
        raise TimeoutError("Ollama daemon down")

    batch_res = service.process_file_batch(files, always_fail)

    assert batch_res["status"] == "failed"
    assert batch_res["error_code"] == "LLM_UNAVAILABLE"
    assert batch_res["aborted_early"] is True
    # Should stop after 10 consecutive failures
    assert len(batch_res["failed"]) == 10
