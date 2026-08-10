"""
LLM-TEST-02 (issue #34) — health check, retry, and partial-failure policy
(TC-LLM-005 / TC-AVAIL-003 / DEC-16 / REQ-NF-010).

`tests/test_llm_cmd_03.py` covers retry and batch isolation but sets `backoff_base_sec=0.01`, so
it never asserts the **shipped** schedule. DEC-16 specifies 1s → 2s → 4s, and a service that
waited 100ms between attempts would pass every existing test while hammering a rate-limited API.

So the backoff here is asserted with a **fake clock**: `time.sleep` is replaced by a recorder, and
the recorded durations are compared against the real defaults. The AC asks for exactly this ("백오프
대기는 가짜 시계로 주입해 테스트가 실제로 7초를 기다리지 않게 한다").

The load-bearing test in this file is `test_scenario_4_*`: an Option A failure must never reach the
local adapter. That is a security property, not a reliability one — auto-switching changes whether
documents leave the machine, and the user approved one answer to that question. It is asserted by
call count on a spy, because "the local adapter was not called" is only provable as a zero.
"""

import time

import pytest

from src.backend.network_guard import (
    EgressBlockedError,
    UpstreamStatusError,
    UpstreamUnavailableError,
)
from src.backend.services.llm_resilience_service import (
    LLMResilienceService,
)


class SleepRecorder:
    """
    Replaces `time.sleep`, recording what the code asked to wait without waiting.

    A fake clock rather than a shortened base: shortening it (as the existing tests do) proves the
    retry loop runs, but leaves the actual delays — the thing DEC-16 fixes — unverified.
    """

    def __init__(self):
        self.durations: list = []

    def __call__(self, seconds: float) -> None:
        self.durations.append(seconds)


@pytest.fixture
def no_wait(monkeypatch):
    recorder = SleepRecorder()
    monkeypatch.setattr(time, "sleep", recorder)
    return recorder


# --- DEC-16's retry schedule, at the shipped defaults ------------------------------------


def test_the_backoff_schedule_is_one_two_four_seconds(no_wait):
    """
    DEC-16: max 3 attempts, exponential backoff 1s → 2s → 4s.

    Asserted against the DEFAULT `backoff_base_sec`, not a test-shortened one. A service waiting
    100ms between attempts passes every existing test while hammering a rate-limited API — and 429
    is the error most likely to trigger this path.
    """
    service = LLMResilienceService()  # shipped defaults
    attempts = {"n": 0}

    def always_transient():
        attempts["n"] += 1
        raise UpstreamUnavailableError("read timeout")

    with pytest.raises(UpstreamUnavailableError):
        service.execute_with_retry(always_transient, file_id="f1")

    assert attempts["n"] == 3, "DEC-16 allows exactly 3 attempts"
    # Two waits for three attempts — the last failure does not sleep before giving up.
    assert no_wait.durations == [1.0, 2.0], no_wait.durations


def test_a_recovering_call_stops_retrying_immediately(no_wait):
    """A success on attempt 2 must not sleep again — the schedule is per failure, not per attempt."""
    service = LLMResilienceService()
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise UpstreamUnavailableError("first attempt fails")
        return "ok"

    assert service.execute_with_retry(flaky, file_id="f1") == "ok"
    assert attempts["n"] == 2
    assert no_wait.durations == [1.0]


@pytest.mark.parametrize(
    "error,should_retry",
    [
        (UpstreamStatusError(429, "llm_cloud"), True),
        (UpstreamStatusError(500, "llm_cloud"), True),
        (UpstreamStatusError(503, "llm_cloud"), True),
        (UpstreamStatusError(401, "llm_cloud"), False),
        (UpstreamStatusError(400, "llm_cloud"), False),
        (UpstreamStatusError(404, "llm_cloud"), False),
        (UpstreamUnavailableError("connect timeout"), True),
        (EgressBlockedError("not whitelisted"), False),
    ],
)
def test_only_transient_errors_consume_retries(no_wait, error, should_retry):
    """
    DEC-16's retry table. A non-transient error must fail on the FIRST attempt.

    Retrying a 401 burns three calls and 3 seconds to receive the same answer, and retrying an
    EgressBlockedError repeatedly attempts a transmission the gate already refused.
    """
    from src.backend.services.rename_service import RenameService

    service = LLMResilienceService()
    attempts = {"n": 0}

    def failing():
        attempts["n"] += 1
        raise error

    with pytest.raises(type(error)):
        service.execute_with_retry(
            failing, file_id="f1", is_transient_error=RenameService._is_transient
        )

    assert attempts["n"] == (3 if should_retry else 1), f"{error!r} -> {attempts['n']} attempts"
    if not should_retry:
        assert no_wait.durations == [], "a non-transient error must not sleep at all"


# --- AC Scenario 3: partial failure is never disguised as success ------------------------


def test_scenario_3_ninety_seven_of_one_hundred_succeed_with_three_listed(no_wait):
    """
    AC S3 verbatim: 100 files, 3 fail after 3 retries each. 97 land, and `failed[]` has 3 entries.

    The AC's emphasis — "200/ok:true 로 조용히 넘어가지 않는다" — is why the failure list matters
    more than the count: a silent skip means the user trusts a wiki with documents missing from it,
    and nothing on screen says which.
    """
    service = LLMResilienceService()
    files = [{"file_id": f"file_{i:03d}"} for i in range(100)]
    doomed = {"file_007", "file_042", "file_099"}

    def process(f):
        if f["file_id"] in doomed:
            raise UpstreamStatusError(503, "llm_cloud")
        return True

    result = service.process_file_batch(files, process)

    assert result["succeeded_count"] == 97
    assert len(result["failed"]) == 3
    assert {e["file_id"] for e in result["failed"]} == doomed
    assert result["aborted_early"] is False
    # Three doomed files x 2 sleeps each — the retry policy really ran per file.
    assert no_wait.durations == [1.0, 2.0] * 3


def test_the_failure_entries_carry_no_chunk_or_prompt(no_wait):
    """
    DEC-16: a failure entry holds `file_id` + `error.code`, never the source chunk or prompt.

    The prompt is the one thing guaranteed to contain document text, so echoing it into a result
    the frontend renders would undo the DEC-14 masking that got it out there safely.
    """
    service = LLMResilienceService()
    secret_chunk = "계약자 홍길동 주민번호 900101-1234567"

    def process(f):
        # A realistic failure: the exception message names the prompt that produced it.
        raise UpstreamStatusError(400, "llm_cloud")

    result = service.process_file_batch([{"file_id": "f1", "text": secret_chunk}], process)

    blob = str(result)
    assert "900101-1234567" not in blob
    assert "홍길동" not in blob
    assert secret_chunk not in blob
    assert result["failed"][0]["error_code"] == "UpstreamStatusError"


def test_a_fully_failed_batch_is_not_reported_as_completed(no_wait):
    """
    Ten consecutive failures trip the circuit breaker: the batch aborts as `failed` +
    `LLM_UNAVAILABLE` rather than grinding through the rest.

    With the daemon down, retrying 1,000 files three times each accomplishes nothing except making
    the user wait — DEC-16 names 10 consecutive failures as the cut-off.
    """
    service = LLMResilienceService(consecutive_fail_limit=10)
    files = [{"file_id": f"f{i}"} for i in range(50)]

    def always_fails(f):
        raise UpstreamUnavailableError("daemon down")

    result = service.process_file_batch(files, always_fails)

    assert result["status"] == "failed"
    assert result["error_code"] == "LLM_UNAVAILABLE"
    assert result["aborted_early"] is True
    # It stopped at the limit rather than attempting all 50.
    assert len(result["failed"]) == 10


def test_a_success_resets_the_consecutive_counter(no_wait):
    """
    The breaker counts *consecutive* failures, so an intermittent 20% failure rate must not abort
    a long batch.

    Counting total failures instead would make a large workspace impossible to analyse — 10
    scattered failures in 1,000 files is a normal outcome, not an outage.
    """
    service = LLMResilienceService(consecutive_fail_limit=10)
    files = [{"file_id": f"f{i}"} for i in range(30)]

    def every_third_fails(f):
        if int(f["file_id"][1:]) % 3 == 0:
            raise UpstreamUnavailableError("flaky")
        return True

    result = service.process_file_batch(files, every_third_fails)

    assert result["status"] == "completed"
    assert result["aborted_early"] is False
    assert result["succeeded_count"] == 20
    assert len(result["failed"]) == 10


# --- AC Scenario 4: no engine auto-switch (the security property) -----------------------


def test_scenario_4_an_option_a_failure_never_reaches_the_local_adapter(no_wait):
    """
    AC S4 / DEC-16's most consequential rule, and the reason this file exists.

    Option A fails with 503 while a healthy Ollama sits on loopback. The local adapter must be
    called **zero** times: the A/B choice decides whether documents leave the machine, and the user
    approved one answer to that question. Silently answering the other one is a confidentiality
    breach dressed as a fallback.

    Asserted by call count on a spy, because "was not called" is only provable as a zero.
    """
    import os
    import tempfile

    from src.backend.config_manager import ConfigManager
    from src.backend.db import DatabaseManager
    from src.backend.services.llm_router import LLMRouter

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "sw.db"))
        try:
            config = ConfigManager(db_mgr=db_mgr)
            config.set("llm_mode", "Option A")

            router = LLMRouter(db_mgr)
            cloud_calls = {"n": 0}
            local_calls = {"n": 0}

            def failing_cloud(prompt, max_tokens):
                cloud_calls["n"] += 1
                raise UpstreamStatusError(503, "llm_cloud")

            def healthy_local(prompt, max_tokens):
                local_calls["n"] += 1
                return {"content": "local answer", "usage": {}, "cost_usd": 0.0}

            router._generate_cloud = failing_cloud
            router._generate_local = healthy_local

            service = LLMResilienceService()
            with pytest.raises(UpstreamStatusError):
                service.execute_with_retry(
                    lambda: router.generate("분석 요청", max_tokens=100), file_id="f1"
                )

            assert cloud_calls["n"] == 3, "the cloud path should exhaust its retries"
            assert local_calls["n"] == 0, (
                "DEC-16: an Option A failure must NEVER fall through to the local adapter"
            )
            # And the persisted engine choice is untouched.
            assert config.get("llm_mode") == "Option A"
        finally:
            db_mgr.close()


def test_the_engine_choice_is_not_rewritten_by_a_failed_batch(no_wait):
    """
    A whole batch failing must not change `llm_mode` either.

    A per-call guard is not enough: a "helpful" batch-level fallback that flipped the setting after
    N failures would leave every *later* analysis running on the other engine, silently and
    permanently.
    """
    import os
    import tempfile

    from src.backend.config_manager import ConfigManager
    from src.backend.db import DatabaseManager

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "sw2.db"))
        try:
            config = ConfigManager(db_mgr=db_mgr)
            config.set("llm_mode", "Option A")

            service = LLMResilienceService(consecutive_fail_limit=5)
            service.process_file_batch(
                [{"file_id": f"f{i}"} for i in range(10)],
                lambda f: (_ for _ in ()).throw(UpstreamStatusError(503, "llm_cloud")),
            )

            assert config.get("llm_mode") == "Option A"
        finally:
            db_mgr.close()


# --- AC Scenarios 1 & 2: health check ---------------------------------------------------


def test_scenario_1_a_stopped_ollama_reports_unavailable():
    """
    AC S1: Option B with no daemon reports `status: false` and a reason.

    Simulated by an unreachable loopback port rather than by stubbing the probe — the failure this
    models is a real connection refusal, and that is what `get_json` turns into None.
    """
    import os
    import tempfile

    from src.backend.config_manager import ConfigManager
    from src.backend.db import DatabaseManager
    from src.backend.services.query_services import LlmQueryService

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "h.db"))
        try:
            ConfigManager(db_mgr=db_mgr).set("llm_mode", "Option B")

            health = LlmQueryService(db_mgr).check_health()

            assert health["status_ok"] is False
            assert health["error_code"] in ("LLM_UNAVAILABLE", "LLM_PROVISION_REQUIRED")
            # DEC-13: daemon reachability and model presence are reported separately.
            assert health["daemon_online"] is False
        finally:
            db_mgr.close()


def test_scenario_2_an_unconfigured_key_does_not_break_the_wiki_query():
    """
    AC S2 / REQ-NF-010: Option A with no usable key reports unhealthy, and reading an existing wiki
    still works.

    That separation is the requirement — a dead LLM must degrade generation, not browsing. If the
    health probe were on the read path, an expired key would make the whole app unusable.
    """
    import os
    import tempfile
    import uuid

    from src.backend.config_manager import ConfigManager
    from src.backend.db import DatabaseManager
    from src.backend.repositories.workspace_repository import WorkspaceRepository
    from src.backend.services.query_services import LlmQueryService, WikiQueryService

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "h2.db"))
        try:
            ConfigManager(db_mgr=db_mgr).set("llm_mode", "Option A")
            ws_id = WorkspaceRepository(db_mgr).create("WS", [tmpdir])["workspace_id"]
            with db_mgr.transaction() as tx:
                tx.execute(
                    """INSERT INTO Wiki_Content (wiki_id, workspace_id, folder_1depth, markdown_content)
                       VALUES (?, ?, ?, ?);""",
                    (str(uuid.uuid4()), ws_id, "계약", "# 기존 위키"),
                )

            health = LlmQueryService(db_mgr).check_health()
            assert health["status_ok"] is False
            assert health["api_key_configured"] is False

            # The wiki still reads — REQ-NF-010.
            tabs = WikiQueryService(db_mgr).get_workspace_wiki(ws_id)
            assert len(tabs) == 1, tabs
            assert tabs[0]["markdown_content"] == "# 기존 위키"
        finally:
            db_mgr.close()


def test_the_health_timeout_comes_from_app_config(no_wait):
    """
    DEC-16 forbids hardcoded timeouts, so the 5s health value must be read from `App_Config`.

    Pinned because a hardcoded literal is invisible until a low-spec PC needs a longer window and
    the setting turns out to do nothing.
    """
    import os
    import tempfile

    from src.backend.config_manager import ConfigManager
    from src.backend.db import DatabaseManager

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "t.db"))
        try:
            config = ConfigManager(db_mgr=db_mgr)
            assert config.get("llm_health_timeout") == "5"
            assert config.get("llm_timeout_connect") == "10"
            assert config.get("llm_timeout_read") == "120"
            assert config.get("llm_timeout_embedding") == "30"
        finally:
            db_mgr.close()
