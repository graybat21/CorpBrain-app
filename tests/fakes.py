"""
Test doubles for the vector store.

Scope note (DECISION_LOG rule 4: "tests that validate mocks are not DoD evidence"): the only
thing faked here is the *source of the embedding numbers*. Real chromadb, a real
PersistentClient, a real cosine HNSW index, real `where` filter deletes and the real services
all execute in the tests that use these. The one claim that cannot be verified offline — that
a live Ollama returns 768 floats — is covered by the opt-in `@pytest.mark.ollama` test instead.
"""

import hashlib
import shutil
import struct
import tempfile
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings, Space
from chromadb.utils.embedding_functions import register_embedding_function


@register_embedding_function
class FakeEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Deterministic 768-dim embeddings derived from the text's sha256.

    Deterministic, not random: a random embedding function makes cosine-similarity ranking
    assertions flaky, and a flaky ordering test gets deleted rather than fixed.

    Registration is required for the same reason the real one needs it — this is a non-legacy
    embedding function, so its name is persisted into the collection config and reopening the
    collection fails if the name is not in `known_embedding_functions`.
    """

    def __init__(self, dim: int = 768, model: str = "nomic-embed-text"):
        self.dim = dim
        self.model = model

    def __call__(self, input: Documents) -> Embeddings:
        # Parameter must be named `input` — chromadb's validate_embedding_function compares
        # the signature against the protocol exactly.
        return [self._embed(text) for text in input]  # type: ignore[return-value]

    def _embed(self, text: str) -> List[float]:
        values: List[float] = []
        counter = 0
        while len(values) < self.dim:
            digest = hashlib.sha256(f"{text}:{counter}".encode("utf-8")).digest()
            for offset in range(0, len(digest), 4):
                if len(values) >= self.dim:
                    break
                (raw,) = struct.unpack(">I", digest[offset:offset + 4])
                values.append((raw / 0xFFFFFFFF) * 2.0 - 1.0)
            counter += 1
        return values

    @staticmethod
    def name() -> str:
        return "corpbrain_fake"

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self.dim, "model": self.model}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "FakeEmbeddingFunction":
        return FakeEmbeddingFunction(dim=config.get("dim", 768), model=config.get("model", "nomic-embed-text"))

    def default_space(self) -> Space:
        return "cosine"

    def supported_spaces(self) -> List[Space]:
        return ["cosine"]


class RecordingGuard:
    """
    NetworkGuard stand-in that records post_json calls and returns a canned embedding.

    Records the full (purpose, url, payload, timeout) tuple so tests can assert that the
    timeout came from App_Config rather than a hardcoded literal (DEC-16) and that the purpose
    is `llm_local` (DEC-15).
    """

    def __init__(self, dim: int = 768):
        self.dim = dim
        self.calls: List[Dict[str, Any]] = []

    def validate_egress(self, purpose: str, url: str) -> str:
        return "127.0.0.1"

    def post_json(self, purpose: str, url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        self.calls.append({"purpose": purpose, "url": url, "payload": payload, "timeout": timeout})
        return {"embedding": [0.01] * self.dim}


def insert_workspace(conn, workspace_id: str, name: str, *root_paths: str) -> None:
    """
    Insert a Workspace_Meta row plus its Workspace_Root children (issue #105).

    Fixtures that build a workspace with raw SQL used to write a single
    `Workspace_Meta.root_path` column. v004 moved roots into a child table, and a fixture that
    inserts only the parent row produces a workspace whose scan finds nothing — which looks
    like the bug #105 fixed rather than a fixture gap. Centralised here so the next schema
    change touches one place instead of seventeen.

    Prefer `WorkspaceRepository.create` where the test is not specifically exercising
    pre-existing rows; this exists for fixtures that need a fixed workspace_id.
    """
    conn.execute(
        "INSERT INTO Workspace_Meta (workspace_id, workspace_name) VALUES (?, ?);",
        (workspace_id, name),
    )
    for order, root_path in enumerate(root_paths):
        conn.execute(
            """INSERT INTO Workspace_Root (root_id, workspace_id, root_path, sort_order)
               VALUES (?, ?, ?, ?);""",
            (str(uuid.uuid4()), workspace_id, root_path, order),
        )


@contextmanager
def chroma_temp_dir():
    """
    A temp directory that tolerates Windows releasing a Chroma file handle late (issue #110).

    `TemporaryDirectory` deletes on `__exit__` with no retry. On Windows the CI job failed
    intermittently with `PermissionError [WinError 32]` on `chroma.sqlite3`, followed by
    `NotADirectoryError [WinError 267]` from `shutil.rmtree`'s own error handler — even though
    `VectorDBManager.close()` had already run and the test body itself passed.

    The cause is not a missing `close()`: Chroma's Rust/SQLite layer can drop the OS handle a
    moment after `client.close()` returns, and Windows refuses to unlink a file with any open
    handle. That is a race, so the fix is a bounded retry rather than another close call. On
    POSIX this loop never iterates — unlinking an open file is legal there, which is exactly
    why the failure only ever appeared on `windows-latest`.

    Last resort is `ignore_errors=True`: a leaked temp directory is the OS's problem at
    reboot, whereas a teardown exception fails a green test run and — worse — buries the real
    assertion error when the body *did* fail.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        yield tmpdir
    finally:
        # `break`, never `return`: a `return` inside `finally` discards an in-flight exception,
        # which would silently swallow the very assertion failure this helper exists to keep
        # visible (ruff B012 flags it, and it is right to).
        for attempt in range(10):
            try:
                shutil.rmtree(tmpdir)
                break
            except (PermissionError, NotADirectoryError, OSError):
                if attempt == 9:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    break
                # Short, growing sleep: the handle is normally gone within a few tens of ms.
                time.sleep(0.05 * (attempt + 1))
