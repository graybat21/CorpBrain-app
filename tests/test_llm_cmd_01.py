import os
import tempfile
import pytest
from src.backend.config_manager import ConfigManager
from src.backend.db import DatabaseManager


@pytest.fixture
def config_mgr():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "cfg_test.db")
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        db_mgr = DatabaseManager(db_path=db_path, migrations_dir=migrations_dir)
        cm = ConfigManager(db_mgr)
        yield cm, db_mgr, db_path
        db_mgr.close()


def test_scenario_1_default_config_initialization(config_mgr):
    cm, db_mgr, db_path = config_mgr

    assert cm.get("llm_mode") == "Option A"
    assert cm.get("llm_cloud_model") == "claude-sonnet-5"
    assert cm.get("llm_timeout_connect") == "10"
    assert cm.get("local_embedding_model") == "nomic-embed-text"


def test_scenario_2_dpapi_api_key_encryption(config_mgr):
    cm, db_mgr, db_path = config_mgr
    raw_key = "sk-ant-api03-test-secret-key-12345"

    assert cm.is_api_key_configured() is False
    assert cm.get_api_key() == ""

    # Set API Key (Encrypts via DPAPI)
    cm.set_api_key(raw_key)

    assert cm.is_api_key_configured() is True
    # Decrypt in-memory
    decrypted_key = cm.get_api_key()
    assert decrypted_key == raw_key


def test_scenario_3_plaintext_key_absent_in_db(config_mgr):
    cm, db_mgr, db_path = config_mgr
    raw_key = "sk-ant-api03-very-secret-string-9999"

    cm.set_api_key(raw_key)

    # Check raw value stored in DB table
    conn = db_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM App_Config WHERE config_key = 'api_key_encrypted';")
    stored_val = cursor.fetchone()[0]

    # Stored value must be base64 DPAPI blob, NOT raw_key
    assert stored_val != raw_key
    assert raw_key not in stored_val
    assert len(stored_val) > 20


def test_scenario_4_mode_change_and_price_edit(config_mgr):
    cm, db_mgr, db_path = config_mgr

    cm.set("llm_mode", "Option B")
    assert cm.get("llm_mode") == "Option B"

    cm.set("cloud_price_input_per_mtok", "2.50")
    assert cm.get("cloud_price_input_per_mtok") == "2.50"
