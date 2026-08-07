from src.backend.pii_filter import MaskedResult, PIIFilter


def test_scenario_1_pii_masking_phone_and_rrn():
    pf = PIIFilter()
    sample_text = "제 번호는 010-1234-5678 이고 주민번호는 900101-1234567 입니다."
    res = pf.mask(sample_text)

    assert "010-1234-5678" not in res.masked_text
    assert "900101-1234567" not in res.masked_text
    assert "[PII:PHONE]" in res.masked_text
    assert "[PII:RRN]" in res.masked_text
    assert res.counts["PHONE"] == 1
    assert res.counts["RRN"] == 1


def test_scenario_2_integrity_2_condition_and_failure():
    pf = PIIFilter()

    # Integrity Condition A check: masked text rescan has 0 matches
    # Integrity Condition B check: raw match string not in masked text
    # Simulate a broken integrity case
    raw_str = "010-9999-8888"
    partially_masked_text = "전화번호: 010-9999-8888_masked"

    # Condition B should fail because raw_str is inside partially_masked_text
    is_valid = pf.validate_integrity(partially_masked_text, [raw_str])
    assert is_valid is False


def test_scenario_3_log_hygiene_and_counts_only():
    pf = PIIFilter()
    sample = "이메일: test@example.com, 사업자번호: 123-45-67890"
    res = pf.mask(sample)

    assert isinstance(res, MaskedResult)
    assert "test@example.com" not in res.masked_text
    assert "123-45-67890" not in res.masked_text
    assert res.counts == {"EMAIL": 1, "BIZNO": 1}
    # Verify no raw PII in counts dictionary
    for k, v in res.counts.items():
        assert isinstance(k, str)
        assert isinstance(v, int)


def test_all_7_pii_types_detection():
    pf = PIIFilter()
    text = (
        "주민번호 850505-1010101, 전화번호 010-1111-2222, "
        "이메일 user@corp.com, 카드 1234-5678-9012-3456, "
        "사업자 123-45-67890, 계좌 110-123-456789, 여권 M12345678"
    )
    res = pf.mask(text)

    assert "[PII:RRN]" in res.masked_text
    assert "[PII:PHONE]" in res.masked_text
    assert "[PII:EMAIL]" in res.masked_text
    assert "[PII:CARD]" in res.masked_text
    assert "[PII:BIZNO]" in res.masked_text
    assert "[PII:ACCOUNT]" in res.masked_text
    assert "[PII:PASSPORT]" in res.masked_text

    assert len(res.counts) == 7
