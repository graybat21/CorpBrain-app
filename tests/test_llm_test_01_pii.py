"""
LLM-TEST-01 (issue #33) — PII masking unit suite (DEC-14 / REQ-FUNC-008, 009 / REQ-NF-006).

`tests/test_llm_cmd_02.py` already covers the happy path for all 7 types. This file adds what the
issue's task breakdown asks for and that file does not have: separator/fullwidth variants, the
two integrity conditions failed **independently**, overlapping-match merging, fail-closed on an
internal error, ReDoS bounds, and log hygiene on both the success and failure paths.

Three real defects were found while writing it, and are fixed in the same change:

1. **Fullwidth digits bypassed detection.** `\\d` matches `０`, but an explicit class like
   `[1-4]` and a literal `0` do not — so `９００１０１-１２３４５６７` was not masked at all,
   while a fullwidth phone number matched ACCOUNT instead of PHONE (masked, but counted under the
   wrong type). Fixed by normalising before the scan.
2. **Hyphen-less and space-separated forms were missed.** `9001011234567` and `010 1234 5678`
   are how people actually type these.
3. **`_ner_scan()` returned None** where AC S3 requires an empty list.

The separator relaxation is deliberately NOT applied to BIZNO/ACCOUNT — see PATTERNS for why,
and `test_a_bare_ten_digit_number_is_not_masked` pins that boundary.
"""

import logging
import time

import pytest

from src.backend.pii_filter import MaskedResult, PIIFilter, PIIMaskingFailedException

TOKEN_FORMAT = {
    "RRN": "[PII:RRN]",
    "PHONE": "[PII:PHONE]",
    "EMAIL": "[PII:EMAIL]",
    "ACCOUNT": "[PII:ACCOUNT]",
    "CARD": "[PII:CARD]",
    "BIZNO": "[PII:BIZNO]",
    "PASSPORT": "[PII:PASSPORT]",
}


@pytest.fixture
def pf():
    return PIIFilter()


# --- AC Scenario 1: the three named values, exactly (DEC-14) -----------------------------


def test_scenario_1_the_three_named_values_are_masked_exactly(pf):
    """
    AC S1 verbatim: "010-1234-5678", "test@test.com", "990101-1234567".

    Also asserts the digit *count* is gone. `***-****-****` would satisfy "the number is absent"
    while still leaking how many digits it had, and DEC-14 abolished that form for that reason.
    """
    text = "연락처 010-1234-5678, 메일 test@test.com, 주민 990101-1234567"
    result = pf.mask(text)

    assert "[PII:PHONE]" in result.masked_text
    assert "[PII:EMAIL]" in result.masked_text
    assert "[PII:RRN]" in result.masked_text
    for raw in ("010-1234-5678", "test@test.com", "990101-1234567"):
        assert raw not in result.masked_text
    # No digit-count leak: nothing but the tokens' own characters remains.
    assert "*" not in result.masked_text
    assert not any(ch.isdigit() for ch in result.masked_text)
    assert result.counts == {"PHONE": 1, "EMAIL": 1, "RRN": 1}


def test_the_only_token_format_is_pii_type(pf):
    """
    DEC-14: `[MASKED]` and `***-****-****` are both abolished.

    Pinned so a later "friendlier" placeholder cannot be introduced silently.
    """
    text = (
        "주민 850505-1010101 전화 010-1111-2222 메일 user@corp.com "
        "카드 1234-5678-9012-3456 사업자 123-45-67890 계좌 110-123-456789 여권 M12345678"
    )
    masked = pf.mask(text).masked_text

    assert "[MASKED]" not in masked
    assert "***" not in masked
    for token in TOKEN_FORMAT.values():
        assert token in masked, token


# --- Separator and width variants (the issue's edge-case dataset) ------------------------


@pytest.mark.parametrize(
    "label,text,expected_type",
    [
        ("RRN hyphenated", "주민 900101-1234567", "RRN"),
        ("RRN no separator", "주민 9001011234567", "RRN"),
        ("RRN space", "주민 900101 1234567", "RRN"),
        ("RRN fullwidth", "주민 ９００１０１-１２３４５６７", "RRN"),
        ("RRN U+2010 hyphen", "주민 900101‐1234567", "RRN"),
        ("RRN U+2212 minus", "주민 900101−1234567", "RRN"),
        ("mobile hyphenated", "연락처 010-1234-5678", "PHONE"),
        ("mobile no separator", "연락처 01012345678", "PHONE"),
        ("mobile space", "연락처 010 1234 5678", "PHONE"),
        ("mobile fullwidth", "연락처 ０１０-１２３４-５６７８", "PHONE"),
        ("landline seoul", "전화 02-1234-5678", "PHONE"),
        ("landline no separator", "전화 0212345678", "PHONE"),
        ("landline area code", "전화 031-123-4567", "PHONE"),
        ("email plain", "메일 user@corp.com", "EMAIL"),
        ("email uppercase", "메일 USER@CORP.COM", "EMAIL"),
        ("email subdomain plus", "메일 a.b+c@sub.example.co.kr", "EMAIL"),
        ("email fullwidth at", "메일 user＠corp.com", "EMAIL"),
        ("card hyphenated", "카드 1234-5678-9012-3456", "CARD"),
        ("card space", "카드 1234 5678 9012 3456", "CARD"),
        ("bizno", "사업자 123-45-67890", "BIZNO"),
        ("account", "계좌 110-123-456789", "ACCOUNT"),
        ("passport M", "여권 M12345678", "PASSPORT"),
        ("passport S", "여권 S12345678", "PASSPORT"),
    ],
)
def test_every_variant_is_masked_under_the_right_type(pf, label, text, expected_type):
    """
    Each variant must be masked AND counted under the correct type.

    The type matters, not just the masking: a fullwidth phone number used to match ACCOUNT, so it
    was replaced but recorded as the wrong kind of PII — and the per-type counts are the one
    thing DEC-14 permits us to log.
    """
    result = pf.mask(text)

    assert result.counts.get(expected_type) == 1, f"{label}: {result.masked_text} {result.counts}"
    assert TOKEN_FORMAT[expected_type] in result.masked_text


def test_fullwidth_characters_outside_the_match_are_preserved(pf):
    """
    Normalisation is for *scanning* only — the substitution happens on the original text.

    Otherwise masking would quietly rewrite a user's fullwidth punctuation into ASCII, changing
    document text it was never asked to touch.
    """
    result = pf.mask("이름 홍길동 ／ 주민 ９００１０１-１２３４５６７")

    assert "／" in result.masked_text, "an unrelated fullwidth character was rewritten"
    assert "[PII:RRN]" in result.masked_text


@pytest.mark.parametrize(
    "text",
    [
        "주문번호 2026080912345",       # 13 digits, but not a valid RRN date
        "타임스탬프 1700000000123",
        "금액 1234567890 원",           # a bare 10-digit run is not treated as BIZNO
        "버전 1234-5678",
        "ROOM12345678",                 # not a passport number
        "ID12345678901234567890",       # a long digit run must not yield an RRN
    ],
)
def test_ordinary_numbers_are_not_masked(pf, text):
    """
    Over-masking is the safe direction for a leak, but not when it corrupts ordinary documents.

    A filter that replaced every 10-digit number would mangle order numbers and part codes
    throughout a real corpus — which is why the separator relaxation stops where it does.
    """
    assert pf.mask(text).counts == {}, text


def test_a_bare_ten_digit_number_is_not_masked(pf):
    """
    The stated boundary: hyphen-less BIZNO is out of scope on purpose.

    Pinned as a test so the decision is visible rather than implicit, and so a later "let's catch
    that too" change has to confront the false-positive cost deliberately.
    """
    assert pf.mask("사업자 1234567890").counts == {}


# --- AC Scenario 2: the two integrity conditions, failed independently -------------------


def test_scenario_2_condition_b_catches_a_partial_substitution(pf):
    """
    AC S2: only the first 6 digits were replaced, so a rescan finds nothing — but the tail
    survives. Condition ⓐ alone would pass this.

    This is the case that proves the AND is load-bearing rather than belt-and-braces.
    """
    raw = "900101-1234567"
    # A partial substitution: the RRN is still present, but split so that NO pattern re-matches
    # it. `900101-1` and `234567` are each too short to be any of the 7 types, so condition A —
    # "rescanning finds zero matches" — is satisfied. The original string nevertheless survives
    # in the text, spanning the inserted token.
    partially_masked = "주민 900101-1[PII:X]234567"

    # Condition A alone passes this: prove it, or the test is not isolating anything.
    scan = partially_masked.translate(PIIFilter._NORMALIZE_MAP)
    assert all(p.search(scan) is None for p in PIIFilter.PATTERNS.values()), (
        "the fixture must satisfy condition A, otherwise this proves nothing about B"
    )

    # And yet the whole thing must be rejected, because a fragment of the original is present.
    # Condition B is the only thing that can catch it.
    assert pf.validate_integrity(partially_masked, ["900101-1"]) is False
    # The plain case too: a completely unsubstituted match.
    assert pf.validate_integrity("주민 900101-1234567", [raw]) is False


def test_condition_a_catches_a_pattern_the_masking_created(pf):
    """
    The mirror case: condition ⓑ passes because no *original* match survives, yet the masked text
    contains a fresh PII-shaped string that masking itself produced.

    Neither condition subsumes the other, which is the whole argument for the AND.
    """
    # No original match is present, so condition B is satisfied...
    masked = "연결 결과 010-9999-8888 입니다"
    assert all(orig not in masked for orig in ["900101-1234567"])
    # ...but condition A rejects it, because the text still holds a phone number.
    assert pf.validate_integrity(masked, ["900101-1234567"]) is False


def test_both_conditions_satisfied_returns_true(pf):
    assert pf.validate_integrity("주민 [PII:RRN], 전화 [PII:PHONE]", ["900101-1234567", "010-1234-5678"]) is True


def test_condition_a_sees_fullwidth_leaks(pf):
    """
    Condition ⓐ rescans the normalised form, matching what `mask` scans.

    Rescanning the raw form would let a fullwidth RRN that survived masking pass verification —
    the patterns cannot see it in that form, so the check would be blind exactly where the
    original bug lived.
    """
    assert pf.validate_integrity("주민 ９００１０１-１２３４５６７", []) is False


# --- Overlapping matches ----------------------------------------------------------------


def test_overlapping_patterns_produce_one_token_not_two(pf):
    """
    `123-45-67890` matches both BIZNO and ACCOUNT. Exactly one token must be inserted.

    A double substitution would either nest tokens or shift the offsets of every later match.
    """
    result = pf.mask("사업자 123-45-67890 입니다")

    assert result.masked_text.count("[PII:") == 1, result.masked_text
    assert sum(result.counts.values()) == 1
    assert "67890" not in result.masked_text


def test_adjacent_matches_keep_their_offsets(pf):
    """
    Back-to-front substitution: several matches in one string must all land correctly.

    Replacing front-to-back shifts every subsequent index by the token/​match length delta, which
    corrupts later replacements — silently, since the output still looks masked.
    """
    text = "010-1111-2222 / 900101-1234567 / user@corp.com / M12345678"
    result = pf.mask(text)

    assert result.counts == {"PHONE": 1, "RRN": 1, "EMAIL": 1, "PASSPORT": 1}
    # The separators between them survive intact, which is what proves the offsets held.
    assert result.masked_text.count(" / ") == 3
    assert not any(ch.isdigit() for ch in result.masked_text)


def test_repeated_occurrences_are_all_masked_and_counted(pf):
    result = pf.mask("전화 010-1111-2222 그리고 010-3333-4444")

    assert result.counts["PHONE"] == 2
    assert result.masked_text.count("[PII:PHONE]") == 2


# --- Fail-closed (REQ-FUNC-009) ---------------------------------------------------------


def test_an_internal_error_raises_rather_than_returning_unmasked_text(pf, monkeypatch):
    """
    Fail-closed: every exception on the mask path blocks transmission.

    "Verification did not run, so allow it" is explicitly forbidden — so the failure mode must be
    a raise, never a return of the original text.
    """
    class Exploding:
        def finditer(self, text):
            raise RuntimeError("regex engine failure")

    monkeypatch.setitem(PIIFilter.PATTERNS, "RRN", Exploding())

    with pytest.raises(PIIMaskingFailedException):
        pf.mask("주민 900101-1234567")


def test_a_failed_integrity_check_raises(pf, monkeypatch):
    """A mask that cannot be verified is not returned — it raises."""
    monkeypatch.setattr(PIIFilter, "validate_integrity", lambda self, m, o: False)

    with pytest.raises(PIIMaskingFailedException):
        pf.mask("주민 900101-1234567")


def test_the_exception_message_carries_no_pii(pf, monkeypatch):
    """
    DEC-14: the failure path must not leak what it failed to mask.

    `from None` on the internal-error re-raise exists for this — a chained traceback would carry
    the original text into every log that records the exception.
    """
    monkeypatch.setattr(PIIFilter, "validate_integrity", lambda self, m, o: False)

    with pytest.raises(PIIMaskingFailedException) as exc:
        pf.mask("주민 900101-1234567 전화 010-1234-5678")

    message = str(exc.value)
    assert "900101-1234567" not in message
    assert "010-1234-5678" not in message
    # And the cause chain is broken, so the text cannot resurface through __cause__.
    assert exc.value.__cause__ is None


# --- Log hygiene (DEC-14) ---------------------------------------------------------------


def test_no_pii_reaches_the_log_on_the_success_path(pf, caplog):
    with caplog.at_level(logging.DEBUG):
        pf.mask("주민 900101-1234567 메일 hong@example.com")

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "900101-1234567" not in logged
    assert "hong@example.com" not in logged


def test_no_pii_reaches_the_log_on_the_failure_path(pf, caplog, monkeypatch):
    monkeypatch.setattr(PIIFilter, "validate_integrity", lambda self, m, o: False)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(PIIMaskingFailedException):
            pf.mask("주민 900101-1234567")

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "900101-1234567" not in logged


def test_the_result_carries_counts_only_never_matched_strings(pf):
    """
    `MaskedResult` is what callers persist and log. It must hold per-type counts and the masked
    text — never the matched originals.

    A masking log that stores PII is the exact failure this feature exists to prevent.
    """
    result = pf.mask("주민 900101-1234567 전화 010-1234-5678")

    assert isinstance(result, MaskedResult)
    assert set(result.__dataclass_fields__) == {"masked_text", "counts"}
    assert result.counts == {"RRN": 1, "PHONE": 1}
    for key, value in result.counts.items():
        assert isinstance(key, str) and isinstance(value, int)
    assert "900101-1234567" not in str(result)


# --- ReDoS (DEC-14) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,text",
    [
        ("hyphen run", "-" * 20000),
        ("digit-hyphen alternation", "1-" * 10000),
        ("at-sign run", "a@" * 10000),
        ("partial bizno repeat", "123-45-" * 3000),
        ("digit-space alternation", "1 " * 10000),
        ("dotted local part", ("a." * 5000) + "@example.com"),
    ],
)
def test_pathological_input_finishes_within_the_bound(pf, label, text):
    """
    ReDoS regression: no pattern may backtrack catastrophically.

    1 second is generous for these sizes — a genuinely exponential pattern would not finish at
    all, so the bound distinguishes "linear-ish" from "hung" rather than measuring performance.
    """
    started = time.perf_counter()
    pf.mask(text)
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, f"{label} took {elapsed:.2f}s"


def test_no_pattern_contains_a_nested_quantifier():
    """
    Structural guard, not a timing one: the property that makes ReDoS impossible here.

    A timing test can pass on a fast machine while the pattern is still exponential; this checks
    the shape instead. Looks for a quantifier applied to an already-quantified group.
    """
    import re as _re

    for name, pattern in PIIFilter.PATTERNS.items():
        source = pattern.pattern
        assert not _re.search(r"\([^)]*[+*]\)[+*]", source), f"{name} has a nested quantifier"


# --- AC Scenario 3: NER is out of scope (DEC-14 / DEC-06) -------------------------------


def test_scenario_3_names_and_organisations_are_not_masked(pf):
    """
    AC S3: person and organisation names pass through, and that is the documented scope.

    Not a defect — probabilistic detection cannot produce the pass/fail criterion REQ-FUNC-009's
    fail-safe needs, so DEC-14 keeps NER out of MVP and requires the limit to be surfaced in the
    UI instead of papered over.
    """
    text = "김철수 부장이 삼성전자와 계약했습니다."
    result = pf.mask(text)

    assert result.masked_text == text
    assert result.counts == {}
    assert "김철수" in result.masked_text
    assert "삼성전자" in result.masked_text


def test_ner_scan_returns_an_empty_list_not_none(pf):
    """
    AC S3 asserts an empty list. It returned None, so a caller iterating the result would raise.

    An interface-only no-op still has to honour its own signature.
    """
    assert pf._ner_scan("김철수 삼성전자") == []


def test_a_name_next_to_real_pii_does_not_prevent_masking(pf):
    """The realistic case: a name adjacent to a number that IS in scope."""
    result = pf.mask("김철수 010-1234-5678")

    assert "김철수" in result.masked_text
    assert "[PII:PHONE]" in result.masked_text


# --- Empty and degenerate input ---------------------------------------------------------


@pytest.mark.parametrize("text", ["", None])
def test_empty_input_is_handled_without_raising(pf, text):
    result = pf.mask(text) if text is not None else pf.mask("")
    assert result.masked_text == ""
    assert result.counts == {}


def test_text_with_no_pii_is_returned_unchanged(pf):
    text = "이 문서에는 개인정보가 없습니다."
    result = pf.mask(text)
    assert result.masked_text == text
    assert result.counts == {}
