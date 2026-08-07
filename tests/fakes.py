"""
Test doubles for the vector store.

Scope note (DECISION_LOG rule 4: "tests that validate mocks are not DoD evidence"): the only
thing faked here is the *source of the embedding numbers*. Real chromadb, a real
PersistentClient, a real cosine HNSW index, real `where` filter deletes and the real services
all execute in the tests that use these. The one claim that cannot be verified offline — that
a live Ollama returns 768 floats — is covered by the opt-in `@pytest.mark.ollama` test instead.
"""

import hashlib
import struct
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
