"""
Ollama-backed ChromaDB embedding function (DEC-06 / DEC-15).

DEC-06 requires that embeddings come from Ollama ``nomic-embed-text`` (768-dim) and be
**explicitly injected** into every collection. The reason is REQ-NF-005: Chroma's
``DefaultEmbeddingFunction`` downloads an ONNX model from the network on first use, which is
an undeclared outbound destination and would break the offline guarantee.

Critically, ``embedding_function=DefaultEmbeddingFunction()`` is the literal default argument
of ``create_collection``, ``get_collection`` AND ``get_or_create_collection`` in chromadb
1.5.9 — omitting the argument does not mean "no embedding function", it means "silently opt
into ONNX". Every call site must pass an instance of this class.
"""

import logging
from typing import Any, Dict, List, Optional

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings, Space
from chromadb.utils.embedding_functions import register_embedding_function

logger = logging.getLogger("CorpBrain.EmbeddingFunction")


class EmbeddingUnavailableError(Exception):
    """
    Ollama could not be reached, or returned an empty/garbled embedding.

    Transient per DEC-16 — LLMResilienceService may retry this with backoff.
    """
    pass


class EmbeddingDimensionError(Exception):
    """
    Ollama returned a vector of the wrong length.

    NOT transient: retrying produces the same wrong length. This means the configured
    ``embedding_dim`` disagrees with the model actually serving requests, and mixing lengths
    into one collection is exactly what DEC-06 forbids.
    """
    pass


@register_embedding_function
class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Compute embeddings via the local Ollama daemon on 127.0.0.1 (DEC-06).

    Registration via ``@register_embedding_function`` is mandatory, not cosmetic. Because this
    class implements ``name()``/``get_config()``/``build_from_config()`` it is a *non-legacy*
    embedding function, so Chroma persists its name into the collection's configuration JSON.
    Reopening that collection in a process where the name is not in
    ``known_embedding_functions`` fails with ``ValueError: Embedding function ... not found``.
    """

    # DEC-15: llm_local is whitelisted for 127.0.0.1 only. Loopback, so no document content
    # leaves the machine and PII masking does not gate this path (DEC-14 covers egress).
    OLLAMA_EMBEDDINGS_URL = "http://127.0.0.1:11434/api/embeddings"

    def __init__(
        self,
        model: str,
        dim: int,
        timeout: float,
        network_guard: Optional[Any] = None,
    ):
        """
        Args:
            model: Ollama model id, from ``App_Config.embedding_model``. Never hardcode a
                model name here (DEC-13).
            dim: expected vector length, from ``App_Config.embedding_dim``.
            timeout: seconds, from ``App_Config.llm_timeout_embedding``. Never hardcode a
                timeout (DEC-16).
            network_guard: injection seam for tests. Defaults to the real NetworkGuard.
        """
        if not model:
            raise ValueError("OllamaEmbeddingFunction requires a model id (App_Config.embedding_model)")

        self.model = model
        self.dim = int(dim)
        self.timeout = float(timeout)

        # DEC-15: all egress goes through NetworkGuard. Default to the real guard rather than
        # None so the validated path is what actually runs in production — a None default
        # means "the code we tested is not the code that ships", which is how the P0 bugs hid.
        if network_guard is None:
            from src.backend.network_guard import NetworkGuard
            network_guard = NetworkGuard
        self.network_guard = network_guard

    # ---- Chroma EmbeddingFunction protocol -------------------------------------------------

    def __call__(self, input: Documents) -> Embeddings:
        """
        Embed a batch of documents.

        The parameter MUST be named ``input``: ``chromadb.api.types.validate_embedding_function``
        compares ``signature(__call__).parameters.keys()`` against the protocol's exactly, and
        it runs on every collection create/get. Renaming it to ``texts`` raises ValueError.

        No retry loop lives here. ``LLMResilienceService.execute_with_retry`` already wraps
        callers with DEC-16's 3-attempt backoff; retrying inside as well would compound to 9
        attempts and violate the documented maximum.
        """
        embeddings: List[List[float]] = []
        for text in input:
            embeddings.append(self._embed_one(text))
        return embeddings  # type: ignore[return-value]

    def _embed_one(self, text: str) -> List[float]:
        from src.backend.network_guard import UpstreamStatusError, UpstreamUnavailableError

        payload = {"model": self.model, "prompt": text}
        try:
            response = self.network_guard.post_json(
                "llm_local",
                self.OLLAMA_EMBEDDINGS_URL,
                payload,
                timeout=self.timeout,
            )
        except UpstreamUnavailableError as e:
            # DEC-14/DEC-15: never log `text` or a response body. Type name only.
            logger.warning(f"[EmbeddingFunction] Ollama unreachable: {type(e).__name__}")
            raise EmbeddingUnavailableError("Local embedding daemon unavailable") from e
        except UpstreamStatusError as e:
            logger.warning(f"[EmbeddingFunction] Ollama returned HTTP {e.status_code}")
            raise EmbeddingUnavailableError(f"Local embedding daemon returned HTTP {e.status_code}") from e
        except ValueError as e:
            logger.warning(f"[EmbeddingFunction] Malformed embedding response: {type(e).__name__}")
            raise EmbeddingUnavailableError("Malformed embedding response") from e

        vector = (response or {}).get("embedding")
        if not vector:
            raise EmbeddingUnavailableError("Embedding response contained no vector")

        if len(vector) != self.dim:
            # Non-transient: a length mismatch means the serving model is not the configured
            # one. Letting this through would mix dimensions in one collection (DEC-06).
            raise EmbeddingDimensionError(
                f"Expected {self.dim}-dim embedding from '{self.model}', got {len(vector)}"
            )

        return [float(v) for v in vector]

    @staticmethod
    def name() -> str:
        """Stable identifier persisted into collection config. Do not rename — it would
        orphan every existing collection on reopen."""
        return "corpbrain_ollama"

    def get_config(self) -> Dict[str, Any]:
        """
        Serializable config stored in the collection.

        Deliberately excludes ``network_guard`` (not serializable) and includes no secrets —
        Ollama is loopback and unauthenticated, so there is nothing to leak here.
        """
        return {"model": self.model, "dim": self.dim, "timeout": self.timeout}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "OllamaEmbeddingFunction":
        return OllamaEmbeddingFunction(
            model=config["model"],
            dim=config["dim"],
            timeout=config.get("timeout", 30.0),
        )

    def default_space(self) -> Space:
        """DEC-06 fixes the metric at cosine. The base class default is l2."""
        return "cosine"

    def supported_spaces(self) -> List[Space]:
        """Only cosine. Narrowing this from the base's [cosine, l2, ip] makes an accidental
        l2 collection a Chroma-level error rather than a silently different metric."""
        return ["cosine"]
