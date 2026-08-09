"""
RN-CMD-01 (issue #37) — real LLM suggestion behind the DEC-17 masking gate.

What was wrong: `process_rename_suggestions` called `self.pii_filter.mask(raw_prompt)` and
**threw the result away**, then produced `f"2026-08_{name}"` from a hardcoded rule. So the gate
ran but guarded nothing — no prompt was ever transmitted — and the "recommendation" was string
concatenation. The audit called this FAKE.

The load-bearing tests here are the ones that inspect the *transmitted prompt*, because DEC-17's
whole claim is about what leaves the machine: masked text, and no absolute path. A test that only
checked the returned filename would have passed against the hardcoded version too.

`RecordingLlmRouter` fakes the model's answer only. The masking, the prompt construction, the
token-leftover rejection, the Windows validation and the persistence are all real code.
"""

import os
import tempfile

import pytest

from src.backend.db import DatabaseManager
from src.backend.network_guard import EgressBlockedError, UpstreamStatusError, UpstreamUnavailableError
from src.backend.pii_filter import PIIMaskingFailedException
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.rename_service import RenameService
from tests.fakes import NoRetryResilience, RecordingLlmRouter

RRN = "900101-1234567"
PII_FILENAME = f"홍길동_주민등록증_{RRN}.pdf"


@pytest.fixture
def service_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "rn.db"))
        try:
            ws_id = WorkspaceRepository(db_mgr).create("RN37 WS", [tmpdir])["workspace_id"]
            router = RecordingLlmRouter()
            service = RenameService(
                db_mgr=db_mgr, llm_router=router, resilience=NoRetryResilience()
            )
            yield service, ws_id, tmpdir, router
        finally:
            db_mgr.close()


def _file(tmpdir: str, name: str, file_id: str = "f1", subdir: str = "계약") -> dict:
    return {
        "file_id": file_id,
        "file_name": name,
        "extension": os.path.splitext(name)[1],
        "current_path": os.path.join(tmpdir, subdir, name),
    }


# --- AC Scenario 1: a real suggestion, persisted -----------------------------------------


def test_scenario_1_three_files_get_suggestions_persisted_as_pending(service_env):
    """
    AC S1: three files in, a mapping list saved with `status='pending'`.

    The router returns a different name per file, so this also proves the suggestion is read
    back from the response rather than derived from the input.
    """
    service, ws_id, tmpdir, router = service_env
    router.reply = lambda prompt: "2026-08_계약서.pdf" if "계약서" in prompt else "2026-08_기타.pdf"

    files = [
        _file(tmpdir, "aB3x9.pdf", "f1"),
        _file(tmpdir, "계약서_초안.pdf", "f2"),
        _file(tmpdir, "zz_temp.pdf", "f3"),
    ]
    result = service.generate_rename_diff(ws_id, files)

    assert len(result["items"]) == 3
    assert all(i["status"] == "pending" for i in result["items"]), result["items"]
    # Read from the model's reply, not concatenated from the old name.
    by_id = {i["file_id"]: i["new_name"] for i in result["items"]}
    assert by_id["f2"] == "2026-08_계약서.pdf"
    assert by_id["f1"] == "2026-08_기타.pdf"

    # Persisted with a history row the client can hand back (DEC-08).
    assert result["history_id"]
    conn = service.db_mgr.get_connection()
    row = conn.execute(
        "SELECT status, old_paths FROM Rename_History WHERE history_id = ?;",
        (result["history_id"],),
    ).fetchone()
    assert row["status"] == "pending"


def test_the_suggestion_is_no_longer_a_hardcoded_prefix(service_env):
    """
    The regression guard for this issue: the service must not invent a name by itself.

    Before the fix every suggestion was `2026-08_<original>` regardless of what any model said.
    A router answering something else must win.
    """
    service, ws_id, tmpdir, router = service_env
    router.reply = "완전히_다른_이름.pdf"

    items = service.process_rename_suggestions(ws_id, [_file(tmpdir, "원본.pdf")])

    assert items[0]["new_name"] == "완전히_다른_이름.pdf"
    assert not items[0]["new_name"].startswith("2026-08_원본")


# --- AC Scenario 2: masked payload, no absolute path (DEC-17 / TC-SEC-005) ---------------


def test_scenario_2_the_transmitted_prompt_is_masked_and_pathless(service_env):
    """
    AC S2, and the assertion this whole issue exists for.

    Inspects what was handed to the router — the payload — not the returned name. Two separate
    claims, both required by DEC-17: the RRN is replaced by `[PII:RRN]`, and no absolute path
    string appears anywhere in it.
    """
    service, ws_id, tmpdir, router = service_env
    service.process_rename_suggestions(ws_id, [_file(tmpdir, PII_FILENAME)])

    assert len(router.prompts) == 1
    payload = router.prompts[0]

    # ⓐ the PII is gone and the token is present
    assert RRN not in payload, "the raw RRN reached the transmission payload"
    assert "[PII:RRN]" in payload

    # ⓑ no absolute path, drive letter, or account directory (DEC-17 / DEC-08)
    assert tmpdir not in payload
    assert "C:\\" not in payload
    assert "/Users/" not in payload
    assert os.path.join(tmpdir, "계약") not in payload
    # The 1-depth folder name alone IS allowed — that is the documented allowance.
    assert "계약" in payload


def test_a_masking_failure_blocks_transmission_fail_closed(service_env):
    """
    DEC-14 fail-closed: if masking raises, nothing is sent.

    Asserted by the router receiving zero prompts — the only way to prove a transmission did not
    happen. The file is reported for manual review rather than silently skipped.
    """
    service, ws_id, tmpdir, router = service_env

    class ExplodingFilter:
        def mask(self, text):
            raise PIIMaskingFailedException("integrity check failed")

    service.pii_filter = ExplodingFilter()
    items = service.process_rename_suggestions(ws_id, [_file(tmpdir, PII_FILENAME)])

    assert router.prompts == [], "a masking failure must block transmission entirely"
    assert items[0]["status"] == "PII_MASKING_FAILED"
    assert items[0]["new_name"] == items[0]["old_name"]


def test_the_log_never_records_the_matched_pii(service_env, caplog):
    """
    DEC-14 log hygiene: per-type counts only, never the matched string or the raw filename.

    A masking log that stores PII is the failure mode the feature exists to prevent.
    """
    import logging

    service, ws_id, tmpdir, router = service_env
    with caplog.at_level(logging.INFO):
        service.process_rename_suggestions(ws_id, [_file(tmpdir, PII_FILENAME)])

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert RRN not in logged
    assert "홍길동_주민등록증" not in logged
    # The count form is what may be logged.
    assert "RRN" in logged


# --- AC Scenario 3: leftover token is never used as a filename ---------------------------


def test_scenario_3_a_leftover_token_is_excluded_not_unmasked(service_env):
    """
    AC S3: `[PII:RRN]_신분증.pdf` must not become a filename, and must not be un-masked.

    Un-masking (substituting the original RRN back) is explicitly forbidden — it would write
    the PII onto the filesystem, which is worse than the name being unhelpful.
    """
    service, ws_id, tmpdir, router = service_env
    router.reply = "[PII:RRN]_신분증.pdf"

    items = service.process_rename_suggestions(ws_id, [_file(tmpdir, PII_FILENAME)])

    assert items[0]["status"] == "PII_TOKEN_LEFT"
    assert items[0]["note"] == "PII 포함 — 수동 확인 필요"
    # The masked token must never become a filename.
    assert "[PII:" not in items[0]["new_name"]
    # The file keeps the name it already has on disk — which does contain the RRN, because the
    # user named it that way. That is NOT un-masking: nothing was substituted back, and no new
    # name was written. Un-masking would mean building `홍길동_주민등록증_900101-1234567.pdf`
    # *from the model's `[PII:RRN]_신분증.pdf` reply*, which is what this asserts did not happen.
    assert items[0]["new_name"] == items[0]["old_name"] == PII_FILENAME
    assert "신분증" not in items[0]["new_name"], "the model's reply must not be un-masked into a name"


# --- Windows filename safety (DEC-17 / REQ-NF-007) --------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "invalid:name.pdf",       # forbidden character
        'quote"name.pdf',
        "pipe|name.pdf",
        "CON",                     # reserved device name
        "NUL.txt",
        "trailing_space.pdf ",     # trailing space — Windows silently strips it
        "trailing_dot.pdf.",
        "a" * 300 + ".pdf",       # over the length limit
    ],
)
def test_an_unsafe_suggestion_is_rejected(service_env, bad_name):
    """
    A model can return anything; the filesystem cannot take anything.

    Every rejection keeps the original name rather than sanitising silently — a quietly altered
    name is one the user never approved.
    """
    service, ws_id, tmpdir, router = service_env
    router.reply = bad_name

    items = service.process_rename_suggestions(ws_id, [_file(tmpdir, "원본.pdf")])

    assert items[0]["status"] == "INVALID_FILENAME", bad_name
    assert items[0]["new_name"] == "원본.pdf"


# --- DEC-16 failure policy --------------------------------------------------------------


def test_a_failed_call_keeps_the_original_name_and_continues(service_env):
    """
    DEC-16 partial failure: one file's failure must not abort the batch.

    The failing file reports LLM_FAILED and keeps its name; the others still get suggestions.
    """
    service, ws_id, tmpdir, router = service_env

    def flaky(prompt):
        if "실패파일" in prompt:
            raise UpstreamUnavailableError("engine down")
        return "2026-08_성공.pdf"

    router.reply = flaky
    items = service.process_rename_suggestions(
        ws_id,
        [_file(tmpdir, "실패파일.pdf", "f1"), _file(tmpdir, "정상파일.pdf", "f2")],
    )

    by_id = {i["file_id"]: i for i in items}
    assert by_id["f1"]["status"] == "LLM_FAILED"
    assert by_id["f1"]["new_name"] == "실패파일.pdf"
    assert by_id["f2"]["status"] == "pending"
    assert by_id["f2"]["new_name"] == "2026-08_성공.pdf"


@pytest.mark.parametrize(
    "exc,expected",
    [
        (UpstreamStatusError(429, "llm_cloud"), True),
        (UpstreamStatusError(503, "llm_cloud"), True),
        (UpstreamStatusError(401, "llm_cloud"), False),
        (UpstreamStatusError(400, "llm_cloud"), False),
        (UpstreamUnavailableError("timeout"), True),
        (EgressBlockedError("not whitelisted"), False),
        (PIIMaskingFailedException("verify failed"), False),
    ],
)
def test_only_transient_errors_are_retried(exc, expected):
    """
    DEC-16's retry table, exactly.

    401/400 give the same answer every time, and retrying EgressBlockedError or a masking
    failure would repeatedly attempt a transmission the gate already refused.
    """
    assert RenameService._is_transient(exc) is expected


def test_the_engine_is_never_switched_on_failure(service_env):
    """
    DEC-16: an Option A failure must not fall back to Option B (or the reverse).

    The A/B choice decides whether documents leave the machine, so it changes only from an
    explicit settings action.
    """
    from src.backend.config_manager import ConfigManager

    service, ws_id, tmpdir, router = service_env
    config = ConfigManager(service.db_mgr)
    config.set("llm_mode", "Option A")
    router.raises = UpstreamStatusError(500, "llm_cloud")

    service.process_rename_suggestions(ws_id, [_file(tmpdir, "원본.pdf")])

    assert config.get("llm_mode") == "Option A"


# --- Response parsing -------------------------------------------------------------------


@pytest.mark.parametrize(
    "content,expected",
    [
        ('{"suggested_name": "2026-08_보고서.pdf"}', "2026-08_보고서.pdf"),
        ('```json\n{"suggested_name": "a.pdf"}\n```', "a.pdf"),
        ('설명입니다. {"suggested_name": "b.pdf"} 이상입니다.', "b.pdf"),
        ("2026-08_bare.pdf", "2026-08_bare.pdf"),
        ("", None),
        ("죄송하지만 요청을 처리할 수 없습니다.", None),
        ('{"other_key": "x.pdf"}', None),
        ("not json at all", None),
    ],
)
def test_parse_suggestion_tolerates_real_model_output(content, expected):
    """
    Models add fences and prose even when told not to; a refusal must not become a filename.

    A brace-scan rather than `json.loads(content)` so surrounding prose does not discard a valid
    answer — but a prose-only reply still yields None, which the caller turns into LLM_FAILED.
    """
    assert RenameService.parse_suggestion(content, ".pdf") == expected


def test_a_refusal_sentence_never_becomes_a_filename():
    """The bare-name fallback must not swallow a multi-line or extension-less reply."""
    assert RenameService.parse_suggestion("첫 줄\n둘째 줄.pdf", ".pdf") is None
    assert RenameService.parse_suggestion("이름 없음", ".pdf") is None


# --- The masking leak this issue uncovered (DEC-14 boundary fix) -------------------------
#
# Found while wiring the real transmission: `PIIFilter.PATTERNS` used `\b` boundaries, and `_`
# is a word character — so there is NO boundary between `_` and a digit. Every PII type embedded
# in a filename the way users actually write them went out **completely unmasked**.
#
# `홍길동_주민등록증_900101-1234567.pdf` → transmitted verbatim. That is the exact leak DEC-17
# exists to prevent, and it only surfaced because AC S2 inspects the payload instead of the
# returned name. These tests pin the boundary so it cannot regress to `\b`.


@pytest.mark.parametrize(
    "filename,expected_type",
    [
        ("홍길동_주민등록증_900101-1234567.pdf", "RRN"),
        ("김철수_010-1234-5678_연락처.txt", "PHONE"),
        ("카드_1234-5678-9012-3456.xlsx", "CARD"),
        ("사업자_123-45-67890_등록증.pdf", "BIZNO"),
        ("계좌_123456-12-123456.txt", "ACCOUNT"),
        ("여권_M12345678_사본.pdf", "PASSPORT"),
        ("email_hong@example.com_첨부.pdf", "EMAIL"),
    ],
)
def test_pii_adjacent_to_an_underscore_is_masked(filename, expected_type):
    """
    All seven types, each embedded in a filename with an underscore immediately before it.

    Under `\\b` boundaries every one of these produced `counts == {}` — a silent pass-through.
    """
    from src.backend.pii_filter import PIIFilter

    result = PIIFilter().mask(filename)

    assert result.counts.get(expected_type) == 1, f"{filename} was not masked: {result.masked_text}"
    assert f"[PII:{expected_type}]" in result.masked_text


@pytest.mark.parametrize(
    "text",
    [
        "ID12345678901234567890.txt",   # a long digit run is not an RRN
        "ROOM12345678.txt",             # not a passport number
        "버전_1234-5678.txt",            # too short for a card number
        "not_an_email@",                # no domain
    ],
)
def test_the_boundary_fix_does_not_create_false_positives(text):
    """
    A lookaround is used rather than `[^\\d]` so the fix cannot over-match.

    Masking a version string or a room number would corrupt filenames wholesale — the opposite
    failure, and just as bad.
    """
    from src.backend.pii_filter import PIIFilter

    assert PIIFilter().mask(text).counts == {}, text


def test_the_integrity_check_still_holds_for_filename_shaped_input():
    """
    DEC-14 requires BOTH conditions: a rescan finds nothing, AND no original match survives.

    The boundary change altered what matches, so the verification has to be re-proven against
    the new shape — a mask that passes only its own rescan is a self-fulfilling check.
    """
    from src.backend.pii_filter import PIIFilter

    f = PIIFilter()
    text = "홍길동_주민등록증_900101-1234567_010-1234-5678.pdf"
    result = f.mask(text)

    assert RRN not in result.masked_text
    assert "010-1234-5678" not in result.masked_text
    # Condition A: a rescan of the masked text finds nothing.
    assert f.mask(result.masked_text).counts == {}
    assert f.validate_integrity(result.masked_text, [RRN, "010-1234-5678"]) is True
