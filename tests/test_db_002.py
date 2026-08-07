"""
DB-002 / issue #16 — ChromaDB vector store acceptance tests (DEC-06 / DEC-09 / DEC-15).

These run against a real chromadb PersistentClient with a real cosine HNSW index. Only the
source of the embedding numbers is faked; see tests/fakes.py for the scope rationale.
"""

import ast
import os
import tempfile
from pathlib import Path

import pytest

from src.backend.config_manager import ConfigManager
from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.embedding_function import (
    EmbeddingDimensionError,
    EmbeddingUnavailableError,
    OllamaEmbeddingFunction,
)
from src.backend.services.vector_service import (
    DeepAnalysisService,
    EmbeddingModelChangedError,
    VectorDBManager,
)
from src.backend.services.workspace_service import WorkspaceService
from src.backend.utils.app_paths import get_vectors_dir
from src.backend.vector_settings import build_chroma_settings
from tests.fakes import FakeEmbeddingFunction, RecordingGuard

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")


def _chunks(file_id: str, count: int, workspace_id: str = "ws-1", prefix: str = "chunk") -> list:
    return [
        {
            "chunk_id": f"{file_id}:{i}",
            "chunk_index": i,
            "text": f"{prefix} body number {i} for {file_id}",
            "char_length": 20,
            "workspace_id": workspace_id,
            "folder_1depth": "docs",
        }
        for i in range(count)
    ]


@pytest.fixture
def store():
    """A real Chroma-backed manager over a temp dir, with a deterministic fake EF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = os.path.join(tmpdir, "vectors")
        manager = VectorDBManager(
            workspace_id="1e2f3a4b-0000-4000-8000-000000000001",
            persist_dir=persist_dir,
            embedding_function=FakeEmbeddingFunction(),
        )
        yield manager, persist_dir
        manager.close()


# --- AC S1: PersistentClient + per-workspace cosine collection ------------------------------

def test_s1_persistent_client_creates_cosine_collection(store):
    manager, persist_dir = store
    manager.upsert_file_chunks("file-a", _chunks("file-a", 2))

    assert os.path.exists(os.path.join(persist_dir, "chroma.sqlite3")), "vectors must be on disk, not in memory"
    assert manager.collection_name == "ws_1e2f3a4b-0000-4000-8000-000000000001"

    collection = manager._get_collection()
    # Cosine must hold in BOTH places: metadata is what our identity check reads, while the
    # configuration is what the HNSW index actually uses.
    assert collection.metadata["hnsw:space"] == "cosine"
    assert collection.configuration_json["hnsw"]["space"] == "cosine"


def test_s1_vectors_survive_client_restart(store):
    """The defect this replaces: an in-memory dict lost everything on process exit."""
    manager, persist_dir = store
    manager.upsert_file_chunks("file-a", _chunks("file-a", 3))
    workspace_id = manager.workspace_id
    manager.close()

    reopened = VectorDBManager(
        workspace_id=workspace_id,
        persist_dir=persist_dir,
        embedding_function=FakeEmbeddingFunction(),
    )
    try:
        assert reopened.count_chunks("file-a") == 3
    finally:
        reopened.close()


def test_s1_default_persist_dir_is_localappdata_vectors(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    vectors_dir = get_vectors_dir()

    assert vectors_dir.parts[-2:] == ("CorpBrain", "vectors")
    # DEC-06 note in app_paths: the \\?\ long-path prefix breaks Chroma's bundled sqlite3.
    assert not str(vectors_dir).startswith("\\\\?\\")
    assert vectors_dir.is_dir()


def test_s1_db_manager_vectors_dir_sits_beside_the_db(tmp_path):
    db_path = tmp_path / "meta" / "corpbrain_meta.db"
    db_mgr = DatabaseManager(db_path=str(db_path), migrations_dir=MIGRATIONS_DIR)
    try:
        assert Path(db_mgr.vectors_dir) == db_path.parent / "vectors"
    finally:
        db_mgr.close()


# --- AC S2: Ollama embedding function ------------------------------------------------------

def test_s2_ef_posts_correct_request_and_returns_768(tmp_path):
    """Egress contract, verifiable with no network: purpose, URL, payload, timeout, length."""
    db_mgr = DatabaseManager(db_path=str(tmp_path / "cfg.db"), migrations_dir=MIGRATIONS_DIR)
    try:
        config = ConfigManager(db_mgr=db_mgr)
        config.set("llm_timeout_embedding", "17")

        guard = RecordingGuard(dim=768)
        ef = OllamaEmbeddingFunction(
            model=config.get("embedding_model"),
            dim=int(config.get("embedding_dim")),
            timeout=float(config.get("llm_timeout_embedding")),
            network_guard=guard,
        )

        vectors = ef(["hello world"])

        assert len(vectors) == 1
        assert len(vectors[0]) == 768
        assert len(guard.calls) == 1
        call = guard.calls[0]
        assert call["purpose"] == "llm_local"                      # DEC-15
        assert call["url"] == "http://127.0.0.1:11434/api/embeddings"
        assert call["payload"] == {"model": "nomic-embed-text", "prompt": "hello world"}
        # DEC-16: the timeout came from App_Config, not a literal in the source.
        assert call["timeout"] == 17.0
    finally:
        db_mgr.close()


def test_s2_dimension_mismatch_is_not_transient():
    guard = RecordingGuard(dim=384)
    ef = OllamaEmbeddingFunction(model="nomic-embed-text", dim=768, timeout=5.0, network_guard=guard)

    with pytest.raises(EmbeddingDimensionError):
        ef(["text"])


def test_s2_unreachable_daemon_raises_transient_error():
    from src.backend.network_guard import UpstreamUnavailableError

    class DeadGuard:
        def validate_egress(self, purpose, url):
            return "127.0.0.1"

        def post_json(self, purpose, url, payload, timeout):
            raise UpstreamUnavailableError("connection refused")

    ef = OllamaEmbeddingFunction(model="nomic-embed-text", dim=768, timeout=5.0, network_guard=DeadGuard())
    with pytest.raises(EmbeddingUnavailableError):
        ef(["text"])


def test_s2_ef_defaults_to_real_network_guard():
    """A None default would mean the validated egress path is not what ships (DEC-15)."""
    from src.backend.network_guard import NetworkGuard

    ef = OllamaEmbeddingFunction(model="nomic-embed-text", dim=768, timeout=5.0)
    assert ef.network_guard is NetworkGuard


@pytest.mark.ollama
@pytest.mark.skipif(
    os.environ.get("CORPBRAIN_TEST_OLLAMA") != "1",
    reason="requires a running local Ollama with nomic-embed-text; set CORPBRAIN_TEST_OLLAMA=1",
)
def test_s2_live_ollama_returns_768():
    """AC S2's real evidence. The offline tests above pin the contract; this pins reality."""
    ef = OllamaEmbeddingFunction(model="nomic-embed-text", dim=768, timeout=30.0)
    vectors = ef(["CorpBrain deep analysis embedding smoke test."])
    assert len(vectors) == 1
    assert len(vectors[0]) == 768
    assert any(v != 0.0 for v in vectors[0])


def test_ollama_down_never_falls_back_to_onnx(monkeypatch, tmp_path):
    """
    REQ-NF-005: with Ollama unreachable the upsert must FAIL, never silently reach for
    Chroma's DefaultEmbeddingFunction (which downloads an ONNX model at runtime).
    """
    from src.backend.network_guard import UpstreamUnavailableError

    class DeadGuard:
        def validate_egress(self, purpose, url):
            return "127.0.0.1"

        def post_json(self, purpose, url, payload, timeout):
            raise UpstreamUnavailableError("connection refused")

    import chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 as onnx_mod

    def _explode(*args, **kwargs):
        raise AssertionError("ONNX embedding function must never be constructed (REQ-NF-005)")

    monkeypatch.setattr(onnx_mod.ONNXMiniLM_L6_V2, "__init__", _explode)

    persist_dir = str(tmp_path / "vectors")
    manager = VectorDBManager(
        workspace_id="ws-onnx",
        persist_dir=persist_dir,
        embedding_function=OllamaEmbeddingFunction(
            model="nomic-embed-text", dim=768, timeout=1.0, network_guard=DeadGuard()
        ),
    )
    try:
        with pytest.raises(EmbeddingUnavailableError):
            manager.upsert_file_chunks("file-a", _chunks("file-a", 2))
        assert manager.count_chunks("file-a") == 0
        assert not (Path.home() / ".cache" / "chroma" / "onnx_models").exists()
    finally:
        manager.close()


# --- AC S3: embedding identity change requires consent --------------------------------------

def test_s3_model_change_requires_consent(tmp_path):
    db_mgr = DatabaseManager(db_path=str(tmp_path / "s3.db"), migrations_dir=MIGRATIONS_DIR)
    persist_dir = str(tmp_path / "vectors")
    try:
        config = ConfigManager(db_mgr=db_mgr)
        manager = VectorDBManager(
            workspace_id="ws-s3",
            persist_dir=persist_dir,
            config_mgr=config,
            embedding_function=FakeEmbeddingFunction(),
        )
        manager.upsert_file_chunks("file-a", _chunks("file-a", 3))
        manager.close()

        # Same 768 dimensions, DIFFERENT model — Chroma's own InvalidDimensionException would
        # not fire here, which is why we stamp and check identity ourselves.
        config.set("embedding_model", "some-other-embed")

        changed = VectorDBManager(
            workspace_id="ws-s3",
            persist_dir=persist_dir,
            config_mgr=config,
            embedding_function=FakeEmbeddingFunction(),
        )
        try:
            with pytest.raises(EmbeddingModelChangedError):
                changed._get_collection()
            assert config.get("embedding_reembed_consent") == "pending"
        finally:
            changed.close()

        # Nothing was destroyed or mixed: reverting the config restores access intact.
        config.set("embedding_model", "nomic-embed-text")
        config.set("embedding_reembed_consent", "")
        reverted = VectorDBManager(
            workspace_id="ws-s3",
            persist_dir=persist_dir,
            config_mgr=config,
            embedding_function=FakeEmbeddingFunction(),
        )
        try:
            assert reverted.count_chunks("file-a") == 3
        finally:
            reverted.close()
    finally:
        db_mgr.close()


def test_s3_missing_identity_metadata_fails_closed(tmp_path):
    """A collection with no identity stamp cannot be proven compatible, so it is rejected."""
    import chromadb

    persist_dir = str(tmp_path / "vectors")
    settings = build_chroma_settings(persist_dir)
    client = chromadb.PersistentClient(path=persist_dir, settings=settings)
    client.create_collection(
        "ws_legacy",
        embedding_function=FakeEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},  # no corpbrain:* identity keys
    )
    client.close()

    manager = VectorDBManager(
        workspace_id="legacy",
        persist_dir=persist_dir,
        embedding_function=FakeEmbeddingFunction(),
    )
    try:
        with pytest.raises(EmbeddingModelChangedError):
            manager._get_collection()
    finally:
        manager.close()


def test_s3_consent_grant_drops_and_recreates(tmp_path):
    db_mgr = DatabaseManager(db_path=str(tmp_path / "s3b.db"), migrations_dir=MIGRATIONS_DIR)
    persist_dir = str(tmp_path / "vectors")
    try:
        config = ConfigManager(db_mgr=db_mgr)
        manager = VectorDBManager(
            workspace_id="ws-s3b",
            persist_dir=persist_dir,
            config_mgr=config,
            embedding_function=FakeEmbeddingFunction(),
        )
        try:
            manager.upsert_file_chunks("file-a", _chunks("file-a", 3))
            assert manager.count_chunks("file-a") == 3

            with pytest.raises(ValueError):
                manager.reset_workspace_for_reembedding("granted:wrong-model:768")

            manager.reset_workspace_for_reembedding("granted:nomic-embed-text:768")
            assert manager.count_chunks("file-a") == 0
        finally:
            manager.close()
    finally:
        db_mgr.close()


# --- AC S4: re-analysis is delete -> upsert, never upsert alone ------------------------------

def test_s4_shrink_leaves_exactly_three(store):
    manager, _ = store
    manager.upsert_file_chunks("file-a", _chunks("file-a", 5))
    assert manager.count_chunks("file-a") == 5

    manager.delete_file("file-a")
    manager.upsert_file_chunks("file-a", _chunks("file-a", 3))

    assert manager.count_chunks("file-a") == 3
    assert [c["chunk_index"] for c in manager.get_file_chunks("file-a")] == [0, 1, 2]
    ids = [c["chunk_id"] for c in manager.get_file_chunks("file-a")]
    assert "file-a:3" not in ids and "file-a:4" not in ids


def test_s4_upsert_alone_would_leave_stale(store):
    """
    Negative control. If this passes, the delete step in process_single_file is load-bearing;
    without it, a shrunk document keeps its trailing chunks forever.
    """
    manager, _ = store
    manager.upsert_file_chunks("file-a", _chunks("file-a", 5))
    manager.upsert_file_chunks("file-a", _chunks("file-a", 3))  # no delete first

    assert manager.count_chunks("file-a") == 5


def test_s4_get_file_chunks_is_sorted_by_chunk_index(store):
    """Chroma's get() has no ordering guarantee; the sort is this manager's contract."""
    manager, _ = store
    manager.upsert_file_chunks("file-a", list(reversed(_chunks("file-a", 6))))

    chunks = manager.get_file_chunks("file-a")
    assert [c["chunk_index"] for c in chunks] == [0, 1, 2, 3, 4, 5]


def test_chunk_metadata_carries_no_path(store):
    """DEC-08: an absolute path must never be persisted in vector metadata."""
    manager, _ = store
    manager.upsert_file_chunks("file-a", _chunks("file-a", 2))

    collection = manager._get_collection()
    result = collection.get(where={"file_id": "file-a"}, include=["metadatas"])
    for metadata in result["metadatas"]:
        assert set(metadata.keys()) == {"workspace_id", "file_id", "chunk_index", "folder_1depth"}
        for value in metadata.values():
            assert ":\\" not in str(value) and not str(value).startswith("\\\\")


def test_empty_chunks_is_a_noop(store):
    """A whitespace-only document yields zero chunks; Chroma rejects an empty ids list."""
    manager, _ = store
    manager.upsert_file_chunks("file-a", [])
    assert manager.count_chunks("file-a") == 0


def test_deep_analysis_requires_workspace_id():
    """A silently missing workspace_id would send writes to the wrong collection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "d.db"), migrations_dir=MIGRATIONS_DIR)
        try:
            service = DeepAnalysisService(db_mgr)
            with pytest.raises(KeyError):
                service.process_single_file({"file_id": "f1", "current_path": "x.txt", "extension": ".txt"})
        finally:
            db_mgr.close()


# --- AC S5: workspace deletion drops the collection before the SQLite row --------------------

def test_s5_drops_collection_before_sqlite_row(tmp_path):
    db_mgr = DatabaseManager(db_path=str(tmp_path / "s5.db"), migrations_dir=MIGRATIONS_DIR)
    persist_dir = str(tmp_path / "vectors")
    root = tmp_path / "root"
    root.mkdir()
    try:
        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)
        workspace = ws_repo.create("S5 WS", str(root))
        workspace_id = workspace["workspace_id"]

        manager = VectorDBManager(
            workspace_id=workspace_id,
            persist_dir=persist_dir,
            embedding_function=FakeEmbeddingFunction(),
        )
        manager.upsert_file_chunks("file-a", _chunks("file-a", 2, workspace_id=workspace_id))
        file_repo.bulk_upsert([{
            "workspace_id": workspace_id,
            "file_id": "file-a",
            "current_path": str(root / "a.txt"),
            "original_path": str(root / "a.txt"),
            "file_name": "a.txt",
            "extension": ".txt",
            "size_bytes": 10,
            "last_modified": 1700000000.0,
        }])

        order = []

        class OrderRecordingStore:
            """Wraps the REAL manager — records order without replacing behaviour."""

            def delete_collection(self, name):
                order.append("chroma_delete_collection")
                manager.delete_collection(name)

        class OrderRecordingRepo:
            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, item):
                return getattr(self._inner, item)

            def delete(self, ws_id):
                order.append("sqlite_delete")
                return self._inner.delete(ws_id)

        service = WorkspaceService(OrderRecordingRepo(ws_repo), vector_store=OrderRecordingStore())
        assert service.delete_workspace(workspace_id) is True

        # DEC-09: vectors first. Reversed, a failure would leak vectors nothing can name.
        assert order == ["chroma_delete_collection", "sqlite_delete"]

        from chromadb.errors import NotFoundError
        with pytest.raises(NotFoundError):
            manager._client.get_collection(
                f"ws_{workspace_id}", embedding_function=FakeEmbeddingFunction()
            )

        # ON DELETE CASCADE removed the child File_Meta rows.
        assert file_repo.list_by_workspace(workspace_id) == []
        manager.close()
    finally:
        db_mgr.close()


def test_s5_absent_collection_is_not_an_error(tmp_path):
    """A workspace that analysed nothing never had a collection; deletion must still work."""
    db_mgr = DatabaseManager(db_path=str(tmp_path / "s5b.db"), migrations_dir=MIGRATIONS_DIR)
    root = tmp_path / "root2"
    root.mkdir()
    try:
        ws_repo = WorkspaceRepository(db_mgr)
        workspace_id = ws_repo.create("Empty WS", str(root))["workspace_id"]
        manager = VectorDBManager(workspace_id=None, persist_dir=str(tmp_path / "vectors"))
        try:
            service = WorkspaceService(ws_repo, vector_store=manager)
            assert service.delete_workspace(workspace_id) is True
        finally:
            manager.close()
    finally:
        db_mgr.close()


def test_admin_mode_rejects_collection_operations(tmp_path):
    manager = VectorDBManager(workspace_id=None, persist_dir=str(tmp_path / "vectors"))
    try:
        with pytest.raises(ValueError):
            manager.count_chunks()
        with pytest.raises(ValueError):
            manager.drop_workspace()
    finally:
        manager.close()


# --- DEC-09 lazy delete ---------------------------------------------------------------------

def test_lazy_delete_drops_orphans_during_search(store):
    manager, _ = store
    manager.upsert_file_chunks("file-live", _chunks("file-live", 3, prefix="alpha"))
    manager.upsert_file_chunks("file-dead", _chunks("file-dead", 3, prefix="alpha"))
    assert manager.count_chunks() == 6

    hits = manager.search("alpha body", n_results=10, live_file_ids={"file-live"})

    assert {h["file_id"] for h in hits} == {"file-live"}
    # Physically gone, not merely filtered out of the response.
    assert manager.count_chunks("file-dead") == 0
    assert manager.count_chunks("file-live") == 3


def test_search_without_live_ids_deletes_nothing(store):
    """live_file_ids=None means "caller didn't say", not "nothing is alive"."""
    manager, _ = store
    manager.upsert_file_chunks("file-a", _chunks("file-a", 3, prefix="beta"))

    hits = manager.search("beta body", n_results=10)

    assert len(hits) == 3
    assert manager.count_chunks("file-a") == 3


def test_select_existing_file_ids_backs_the_lazy_delete(tmp_path):
    db_mgr = DatabaseManager(db_path=str(tmp_path / "ids.db"), migrations_dir=MIGRATIONS_DIR)
    root = tmp_path / "root3"
    root.mkdir()
    try:
        ws_repo = WorkspaceRepository(db_mgr)
        file_repo = FileRepository(db_mgr)
        workspace_id = ws_repo.create("IDs WS", str(root))["workspace_id"]
        file_repo.bulk_upsert([{
            "workspace_id": workspace_id,
            "file_id": "file-live",
            "current_path": str(root / "live.txt"),
            "original_path": str(root / "live.txt"),
            "file_name": "live.txt",
            "extension": ".txt",
            "size_bytes": 1,
            "last_modified": 1700000000.0,
        }])

        live = file_repo.select_existing_file_ids(workspace_id, ["file-live", "file-dead"])
        assert live == {"file-live"}
        assert file_repo.select_existing_file_ids(workspace_id, []) == set()
        # Above the 999-parameter SQLite limit — must batch rather than raise.
        assert file_repo.select_existing_file_ids(workspace_id, [f"f{i}" for i in range(1500)]) == set()
    finally:
        db_mgr.close()


# --- DEC-15 telemetry and import discipline --------------------------------------------------

def test_telemetry_is_disabled_and_inert(tmp_path):
    """
    Fails loudly if a chromadb upgrade revives telemetry — the enforcement an import lint
    cannot provide, since chromadb bundles its own HTTP stack.
    """
    import chromadb

    persist_dir = str(tmp_path / "vectors")
    settings = build_chroma_settings(persist_dir)
    assert settings.anonymized_telemetry is False
    assert settings.chroma_otel_granularity is None
    assert settings.allow_reset is False

    client = chromadb.PersistentClient(path=persist_dir, settings=settings)
    try:
        assert client.get_settings().anonymized_telemetry is False

        from chromadb.telemetry.product import ProductTelemetryClient
        telemetry = client._system.instance(ProductTelemetryClient)

        class _Event:
            name = "test_event"
            properties = {"a": 1}

        assert telemetry.capture(_Event()) is None  # no-op stub in the pinned version

        from chromadb.telemetry.opentelemetry import tracer
        assert tracer is None
    finally:
        client.close()


def test_no_forbidden_network_imports():
    """
    DEC-15: NetworkGuard is the only module allowed to import a network library.

    Defence in depth alongside ruff's banned-api rule, since the CI lint DEC-15 calls for does
    not exist yet (tracked as issue #85).
    """
    forbidden = {"httpx", "requests", "socket", "urllib.request", "websockets"}
    src_root = Path(__file__).resolve().parent.parent / "src"
    offenders = []

    for path in src_root.rglob("*.py"):
        if path.name == "network_guard.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden or alias.name in forbidden:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in forbidden or node.module.split(".")[0] in forbidden:
                    offenders.append(f"{path.name}: from {node.module} import ...")

    assert offenders == [], f"DEC-15 violation — route these through NetworkGuard: {offenders}"


# NetworkGuard.post_json's own contract (payload encoding, DEC-16 status classification,
# body non-leakage, egress blocking) is covered in tests/test_inf_cmd_03.py against a live
# loopback server. It lives there rather than here because it is a DEC-15 concern, not a
# vector-store one.
