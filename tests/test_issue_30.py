"""
LLM-FE-01 (issue #30) — LLM settings screen: health status and the price reference date
(DEC-16 / DEC-15 / DEC-12 / DEC-11).

AC S1 (live health status) was already satisfied: `SettingsPage` calls the real
`GET /api/v1/config/llm` probe and reports `is_healthy` / `daemon_online` /
`embedding_model_ready` / `generation_model_ready` separately (DEC-13).

AC S2 was not, and not merely in the UI. DEC-16 requires the price figures to be shown **with the
date they are current as of**, and to be user-editable. The values were seeded in
`ConfigManager.DEFAULT_CONFIG` but had no path out of the backend at all — `cloud_price` appeared
in no DTO and no route — so this adds the read fields, a `POST /api/v1/config/llm/price` route,
and the settings form.

Two rules the implementation is built around, both easy to get backwards:

- **The reference date is the caller's, not `now()`.** The field answers "which published price
  list is this?". Stamping the edit time would relabel a rate copied from last quarter's page as
  today's, destroying the only thing that makes the number interpretable.
- **No price lookup.** DEC-15 allows exactly three egress destinations, and DEC-16 says a price
  table must never be fetched. A "현재 단가 자동 확인" button is therefore not a missing feature but
  a forbidden one, and its absence is asserted below.
"""

import os
import re
import tempfile
from pathlib import Path

import pytest

from src.backend.config_manager import ConfigManager
from src.backend.db import DatabaseManager

FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"
SETTINGS = FRONTEND / "pages" / "SettingsPage.tsx"
CLIENT = FRONTEND / "api" / "client.ts"


def _code(path: Path) -> str:
    """Source with comments stripped — the rationale comments quote the strings under test."""
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


@pytest.fixture
def api_client():
    """A TestClient over a temp DB, with the seeded defaults in place."""
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "llm30.db"))
        try:
            app = create_app(db_mgr, session_token="tok30")
            yield TestClient(app), db_mgr
        finally:
            db_mgr.close()


def _auth():
    return {"Authorization": "Bearer tok30"}


# --- The prices are readable at all (they previously were not) -----------------------------


def test_the_seeded_prices_and_reference_date_are_returned(api_client):
    """
    The migration-seeded values must reach the client.

    Before this change `cloud_price` existed only in `ConfigManager.DEFAULT_CONFIG` — no DTO
    field, no route — so the settings screen had nothing to render and AC S2 could not be
    satisfied in the UI alone.
    """
    client, db_mgr = api_client

    res = client.get("/api/v1/config/llm", headers=_auth())

    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["cloud_price_input_per_mtok"] == 3.00
    assert data["cloud_price_output_per_mtok"] == 15.00
    assert data["cloud_price_updated_at"] == "2026-08-01T00:00:00Z"


def test_the_prices_are_numbers_not_strings(api_client):
    """
    `App_Config` is a TEXT KV table, so the values are stored as strings and must be converted.

    A string would render as "3.00" and break arithmetic silently in any future client-side
    estimate — JS would happily produce "3.00" * tokens as NaN.
    """
    client, db_mgr = api_client

    data = client.get("/api/v1/config/llm", headers=_auth()).json()["data"]

    assert isinstance(data["cloud_price_input_per_mtok"], float)
    assert isinstance(data["cloud_price_output_per_mtok"], float)


def test_the_reference_date_is_in_the_openapi_contract(api_client):
    """DEC-02: the schema is the SSOT the frontend type is generated from."""
    from src.backend.api.app import create_app

    client, db_mgr = api_client
    app = create_app(db_mgr, session_token="tok30")

    properties = app.openapi()["components"]["schemas"]["LlmHealthCheckRes"]["properties"]
    for field in (
        "cloud_price_input_per_mtok",
        "cloud_price_output_per_mtok",
        "cloud_price_updated_at",
    ):
        assert field in properties, field


def test_the_generated_frontend_type_carries_the_price_fields():
    """
    Without regeneration `health.cloud_price_updated_at` would be a TS error — or worse, silently
    `undefined`, which renders the "저장된 단가 정보를 불러오는 중" placeholder forever.
    """
    types_gen = (FRONTEND / "api" / "types.gen.ts").read_text(encoding="utf-8")
    block = types_gen[types_gen.index("export interface LlmHealthCheckRes"):]
    block = block[:block.index("}")]

    assert "cloud_price_updated_at" in block
    assert "cloud_price_input_per_mtok" in block


# --- Editing (DEC-16: user-editable, never fetched) ---------------------------------------


def test_a_price_edit_persists(api_client):
    """DEC-16 requires the prices to be user-editable in settings."""
    client, db_mgr = api_client

    res = client.post(
        "/api/v1/config/llm/price",
        headers=_auth(),
        json={
            "cloud_price_input_per_mtok": 2.5,
            "cloud_price_output_per_mtok": 12.0,
            "cloud_price_updated_at": "2026-07-01T00:00:00Z",
        },
    )

    assert res.status_code == 200, res.text
    assert res.json()["data"]["updated"] is True

    data = client.get("/api/v1/config/llm", headers=_auth()).json()["data"]
    assert data["cloud_price_input_per_mtok"] == 2.5
    assert data["cloud_price_output_per_mtok"] == 12.0
    assert data["cloud_price_updated_at"] == "2026-07-01T00:00:00Z"


def test_the_reference_date_is_the_callers_and_not_the_edit_time(api_client):
    """
    The load-bearing rule: `cloud_price_updated_at` is not stamped with `now()`.

    A user entering the rate published on 2026-01-15 must have it labelled 2026-01-15. Overwriting
    it with the save time would assert the figure is current as of today — the exact false claim
    the field exists to prevent, and it would look correct in every test that only checks the
    prices.
    """
    client, db_mgr = api_client
    past = "2026-01-15T00:00:00Z"

    client.post(
        "/api/v1/config/llm/price",
        headers=_auth(),
        json={
            "cloud_price_input_per_mtok": 1.0,
            "cloud_price_output_per_mtok": 5.0,
            "cloud_price_updated_at": past,
        },
    )

    stored = ConfigManager(db_mgr).get("cloud_price_updated_at")
    assert stored == past, "the stored date must be the one supplied, not the time of the edit"


def test_a_zero_price_is_accepted(api_client):
    """
    0.00 is a legitimate value (a free tier or a self-hosted deployment), not an empty field.

    A truthiness guard would reject it and silently keep the previous price — under-reporting cost
    forever with no visible error.
    """
    client, db_mgr = api_client

    res = client.post(
        "/api/v1/config/llm/price",
        headers=_auth(),
        json={
            "cloud_price_input_per_mtok": 0,
            "cloud_price_output_per_mtok": 0,
            "cloud_price_updated_at": "2026-08-01T00:00:00Z",
        },
    )

    assert res.status_code == 200, res.text
    assert client.get("/api/v1/config/llm", headers=_auth()).json()["data"][
        "cloud_price_input_per_mtok"
    ] == 0.0


def test_a_negative_price_is_rejected(api_client):
    """A negative price would produce a negative cost estimate, which is not a coherent figure."""
    client, db_mgr = api_client

    res = client.post(
        "/api/v1/config/llm/price",
        headers=_auth(),
        json={
            "cloud_price_input_per_mtok": -1,
            "cloud_price_output_per_mtok": 5.0,
            "cloud_price_updated_at": "2026-08-01T00:00:00Z",
        },
    )

    assert res.status_code == 422
    assert res.json()["ok"] is False
    assert res.json()["error"]["code"] == "VALIDATION_FAILED"


def test_an_unparseable_reference_date_is_rejected(api_client):
    """
    DEC-11: TEXT ISO-8601. Parsed rather than pattern-matched, so an impossible date fails too.

    An unparseable date is worse than none — the UI would render it verbatim beside a real number
    and imply the pair had been checked.
    """
    client, db_mgr = api_client

    for bad in ("어제", "2026-02-31", "08/01/2026", ""):
        res = client.post(
            "/api/v1/config/llm/price",
            headers=_auth(),
            json={
                "cloud_price_input_per_mtok": 3.0,
                "cloud_price_output_per_mtok": 15.0,
                "cloud_price_updated_at": bad,
            },
        )
        assert res.status_code == 422, f"{bad!r} must be rejected, got {res.status_code}"


def test_a_price_edit_does_not_disturb_the_engine_mode(api_client):
    """
    DEC-16: engine changes come only from an explicit mode action.

    The price route shares no state with the mode, and must not — a price edit that silently
    reset the engine would change whether documents leave the machine.
    """
    client, db_mgr = api_client
    ConfigManager(db_mgr).set("llm_mode", "Option B")

    client.post(
        "/api/v1/config/llm/price",
        headers=_auth(),
        json={
            "cloud_price_input_per_mtok": 4.0,
            "cloud_price_output_per_mtok": 20.0,
            "cloud_price_updated_at": "2026-08-01T00:00:00Z",
        },
    )

    assert ConfigManager(db_mgr).get("llm_mode") == "Option B"


def test_a_price_edit_does_not_require_or_touch_the_api_key(api_client):
    """
    DEC-12: the key is write-only and must not be resent to change a price.

    A combined route would force the settings form to hold the key in state to edit a number,
    which is why this is a separate endpoint.
    """
    client, db_mgr = api_client
    cm = ConfigManager(db_mgr)
    cm.set("api_key_encrypted", "sentinel-value")

    client.post(
        "/api/v1/config/llm/price",
        headers=_auth(),
        json={
            "cloud_price_input_per_mtok": 4.0,
            "cloud_price_output_per_mtok": 20.0,
            "cloud_price_updated_at": "2026-08-01T00:00:00Z",
        },
    )

    assert cm.get("api_key_encrypted") == "sentinel-value"


def test_the_price_route_requires_the_session_token(api_client):
    """DEC-02: every /api/v1/* route passes the Bearer middleware, with no exceptions."""
    client, db_mgr = api_client

    res = client.post(
        "/api/v1/config/llm/price",
        json={
            "cloud_price_input_per_mtok": 3.0,
            "cloud_price_output_per_mtok": 15.0,
            "cloud_price_updated_at": "2026-08-01T00:00:00Z",
        },
    )

    assert res.status_code == 401


def test_the_api_key_is_never_echoed_alongside_the_prices(api_client):
    """
    DEC-12: adding fields to this response must not have introduced a key leak.

    `api_key_configured: bool` is the only permitted signal — not even a masked prefix.
    """
    client, db_mgr = api_client
    ConfigManager(db_mgr).set("api_key_encrypted", "c2VjcmV0LWtleS12YWx1ZQ==")

    body = client.get("/api/v1/config/llm", headers=_auth()).text

    assert "c2VjcmV0" not in body
    assert "api_key_encrypted" not in body
    assert "api_key_configured" in body


# --- DEC-15: no price lookup over the network --------------------------------------------


def test_no_price_fetch_button_exists_in_the_settings_ui():
    """
    AC S2 verbatim: "가격 자동 확인 버튼은 존재하지 않는다."

    Not a missing feature — a forbidden one. DEC-15 permits exactly three egress destinations, and
    DEC-16 says a price table is never fetched. Adding it would be a design-decision change.
    """
    code = _code(SETTINGS)

    for forbidden in ("자동 확인", "가격 조회", "fetchPrice", "pricing.json", "https://"):
        assert forbidden not in code, f"{forbidden} would imply a network price lookup"


def test_the_settings_page_talks_only_to_the_local_client():
    """Every call goes through the api client, which is the only thing that knows the base URL."""
    code = _code(SETTINGS)

    assert "api.setLlmPrice" in code
    for forbidden in ("fetch('http", 'fetch("http', "XMLHttpRequest", "axios"):
        assert forbidden not in code, forbidden


# --- The UI renders the date next to the figures (AC S2) ---------------------------------


def test_the_form_has_all_three_fields():
    """
    AC S2: 단가 입력 필드와 기준일이 **함께** 표시된다.

    The date is a peer of the two prices, not a footnote — a price shown without one reads as live.
    """
    code = _code(SETTINGS)

    assert "priceInput" in code
    assert "priceOutput" in code
    assert "priceDate" in code
    assert 'type="date"' in code


def test_the_cost_is_labelled_an_estimate():
    """
    DEC-16: displayed cost is an estimate from a user-editable price, never a bill.

    Required here as well as on the analytics page — this is the screen where the user sets the
    number, so it is where the caveat matters most.
    """
    code = _code(SETTINGS)

    assert "추정치" in code
    assert "실제 청구액과 다를 수 있습니다" in code


def test_the_stored_reference_date_is_displayed_and_not_only_editable():
    """
    The saved date must be visible, not just sitting in an input.

    An input alone cannot distinguish "this is what is stored" from "this is what you typed and
    have not saved" — and the stored value is the one every cost figure was computed with.
    """
    code = _code(SETTINGS)

    assert "health?.cloud_price_updated_at" in code
    assert "저장된 기준일" in code


def test_an_empty_reference_date_is_refused_rather_than_defaulted():
    """
    The client must not substitute today's date for a blank field.

    Defaulting would assert something the user never said, which is the same failure as stamping
    `now()` on the server — just moved one layer out.
    """
    code = _code(SETTINGS)
    handler = code[code.index("const handleSavePrice"):code.index("return (")]

    assert "priceDate === ''" in handler
    assert "단가 기준일을 입력하세요" in handler
    for defaulted in ("new Date()", "Date.now()"):
        assert defaulted not in handler, f"{defaulted} would invent a reference date"


def test_a_zero_price_survives_the_client_side_guard():
    """
    The client validates with `Number.isFinite` and `< 0`, not truthiness.

    `!input` would reject 0 before the request was ever made, so the server-side test above would
    pass while the UI stayed broken.
    """
    code = _code(SETTINGS)
    handler = code[code.index("const handleSavePrice"):code.index("return (")]

    assert "Number.isFinite" in handler
    assert "input < 0" in handler


def test_the_price_form_is_seeded_from_the_fetched_values():
    """
    Opening settings must show the stored prices, not empty boxes.

    Empty fields would read as "no price configured" and invite the user to retype values that
    were already correct — and a blank submit would then be a real edit.
    """
    code = _code(SETTINGS)

    assert "setPriceInput(String(res.cloud_price_input_per_mtok))" in code
    # `!= null` rather than a truthiness check, so a stored 0.00 is not treated as absent.
    assert "!= null" in code


def test_the_client_sends_an_iso_instant_for_the_date():
    """
    DEC-11: DATETIME is TEXT ISO-8601 UTC. A date input yields `YYYY-MM-DD` alone.

    Sending the bare date would fail the server's parse, and appending a local-time offset would
    shift the stored date by a day for KST users.
    """
    code = _code(SETTINGS)

    assert "T00:00:00Z" in code
