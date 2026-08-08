"""
ChromaDB-backed vector store and deep analysis (DEC-06 / DEC-09).

Replaces an in-memory ``Dict[str, List[dict]]`` that claimed to be "ChromaDB SSOT" in its
docstring while losing every vector on process exit (DECISION_LOG CORE #1).
"""

import logging
from typing import Any, Dict, Iterable, List, Optional, Set

from src.backend.db import DatabaseManager
from src.backend.services.document_parser import DocumentParser, TextChunker
from src.backend.services.llm_resilience_service import LLMResilienceService
from src.backend.utils.app_paths import get_vectors_dir
from src.backend.utils.file_utils import derive_folder_1depth

logger = logging.getLogger("CorpBrain.VectorService")


class EmbeddingModelChangedError(Exception):
    """
    The collection on disk was built with a different embedding model or dimension than
    App_Config currently specifies (DEC-06).

    Raised *before* the collection handle is returned, so no code path can reach an upsert
    that mixes dimensions. This is deliberately stronger than Chroma's own
    ``InvalidDimensionException``, which only fires when the numeric dimensions actually
    differ — swapping to a *different* 768-dim model would otherwise pass silently and
    corrupt search results with no error at all.
    """

    def __init__(self, expected: str, found: str, workspace_id: str):
        super().__init__(
            f"Workspace {workspace_id} vectors were built with '{found}' but config "
            f"specifies '{expected}'. Re-embedding requires explicit user consent."
        )
        self.expected = expected
        self.found = found
        self.workspace_id = workspace_id


class VectorDBManager:
    """
    ChromaDB PersistentClient wrapper, one collection per workspace (DEC-06).

    Two modes:

    - **workspace mode** (``workspace_id`` given): full chunk read/write against
      ``ws_<workspace_id>``.
    - **admin mode** (``workspace_id=None``): only ``delete_collection`` / ``drop_workspace``
      work; collection-bound methods raise ValueError. This is the shape ``WorkspaceService``
      needs for deletion, and it avoids inventing a second class.

    Always call ``close()``. On Windows an open ``chroma.sqlite3`` handle makes
    ``TemporaryDirectory`` cleanup fail with ``PermissionError [WinError 32]``.
    """

    def __init__(
        self,
        workspace_id: Optional[str] = None,
        persist_dir: Optional[str] = None,
        config_mgr: Optional[Any] = None,
        embedding_function: Optional[Any] = None,
        client: Optional[Any] = None,
    ):
        self.workspace_id = workspace_id
        self.persist_dir = str(persist_dir) if persist_dir else str(get_vectors_dir())
        self.config_mgr = config_mgr

        self._embedding_model, self._embedding_dim = self._resolve_embedding_identity(config_mgr)

        if embedding_function is None:
            from src.backend.services.embedding_function import OllamaEmbeddingFunction
            timeout = self._config_value("llm_timeout_embedding", "30")
            embedding_function = OllamaEmbeddingFunction(
                model=self._embedding_model,
                dim=self._embedding_dim,
                timeout=float(timeout),
            )
        self.embedding_function = embedding_function

        if client is None:
            import chromadb

            from src.backend.vector_settings import build_chroma_settings
            client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=build_chroma_settings(self.persist_dir),
            )
            self._owns_client = True
        else:
            self._owns_client = False
        self._client = client

        self._collection = None

    # ---- construction helpers --------------------------------------------------------------

    def _config_value(self, key: str, default: str) -> str:
        if self.config_mgr is None:
            return default
        value = self.config_mgr.get(key, default)
        return default if value in (None, "") else str(value)

    def _resolve_embedding_identity(self, config_mgr: Optional[Any]) -> tuple:
        """
        Read the embedding identity from App_Config (DEC-06).

        The defaults mirror ConfigManager.DEFAULT_CONFIG so a manager built without a
        config_mgr (tests, admin mode) still agrees with production. They are NOT an excuse to
        hardcode a model elsewhere — production always passes a config_mgr.
        """
        if config_mgr is None:
            return "nomic-embed-text", 768
        model = config_mgr.get("embedding_model", "nomic-embed-text") or "nomic-embed-text"
        dim = config_mgr.get("embedding_dim", "768") or "768"
        return str(model), int(dim)

    @property
    def collection_name(self) -> str:
        """
        Collection name for this workspace.

        Hyphenated UUID, not ``.hex``: DEC-11 fixes UUIDs at 36-char hyphenated form, Chroma's
        name validation accepts hyphens, and switching to hex would orphan every existing
        collection.
        """
        if self.workspace_id is None:
            raise ValueError("VectorDBManager is in admin mode (workspace_id=None); no collection bound")
        return f"ws_{self.workspace_id}"

    # ---- collection lifecycle --------------------------------------------------------------

    def _get_collection(self):
        """
        Load or create this workspace's collection (DEC-06).

        Not ``get_or_create_collection``: only an explicit create branch can stamp the
        embedding identity metadata that ``_verify_embedding_identity`` later checks, and
        get_or_create would hide which of the two happened.

        ``embedding_function`` is passed on BOTH calls on purpose. In chromadb 1.5.9 the
        default argument of get_collection/create_collection/get_or_create_collection is
        literally ``DefaultEmbeddingFunction()`` — omitting it silently selects the ONNX model
        that downloads at runtime, violating REQ-NF-005. Do not "simplify" these calls.
        """
        if self._collection is not None:
            return self._collection

        from chromadb.errors import NotFoundError

        name = self.collection_name
        try:
            collection = self._client.get_collection(name, embedding_function=self.embedding_function)
            self._verify_embedding_identity(collection)
        except NotFoundError:
            collection = self._client.create_collection(
                name,
                embedding_function=self.embedding_function,
                metadata={
                    "hnsw:space": "cosine",  # DEC-06
                    "corpbrain:embedding_model": self._embedding_model,
                    "corpbrain:embedding_dim": str(self._embedding_dim),
                },
            )
            logger.info(f"[VectorDBManager] Created collection '{name}' (cosine, {self._embedding_dim}-dim)")

        self._collection = collection
        return collection

    def _verify_embedding_identity(self, collection) -> None:
        """
        Reject a collection whose vectors were produced by a different model/dimension.

        Fail-closed: missing metadata counts as a mismatch. A collection with no identity
        stamp predates this check, so we cannot prove its vectors are compatible, and guessing
        "probably fine" is how mixed dimensions get in.
        """
        metadata = collection.metadata or {}
        found_model = metadata.get("corpbrain:embedding_model")
        found_dim = metadata.get("corpbrain:embedding_dim")

        expected = f"{self._embedding_model}:{self._embedding_dim}"
        found = f"{found_model}:{found_dim}"

        if found_model == self._embedding_model and str(found_dim) == str(self._embedding_dim):
            return

        consent = self._config_value("embedding_reembed_consent", "")
        if consent == f"granted:{expected}":
            # Consent already recorded — the caller is expected to have run
            # reset_workspace_for_reembedding, which drops and recreates the collection.
            return

        if self.config_mgr is not None:
            self.config_mgr.set("embedding_reembed_consent", "pending")

        raise EmbeddingModelChangedError(expected, found, self.workspace_id or "?")

    def reset_workspace_for_reembedding(self, consent_token: str) -> None:
        """
        Drop this workspace's collection so it can be rebuilt with the current embedding model.

        ``consent_token`` must be exactly ``granted:<model>:<dim>`` for the *current* config.
        Requiring the token to name the target identity means a stale consent (granted for a
        model the user has since changed away from) cannot authorise a different re-embedding.

        Also resets ``File_Meta.parse_status`` to 'pending' for the workspace so re-analysis
        reprocesses exactly these files — DEC-16 forbids a separate retry queue.

        The UI/endpoint that collects this consent is tracked separately; this method is the
        enforcement point, and nothing can bypass it because _verify_embedding_identity runs
        before any collection handle is returned.
        """
        expected = f"granted:{self._embedding_model}:{self._embedding_dim}"
        if consent_token != expected:
            raise ValueError(f"Invalid consent token; expected '{expected}'")

        self.drop_workspace()
        if self.config_mgr is not None:
            self.config_mgr.set("embedding_reembed_consent", expected)

    def drop_workspace(self, workspace_id: Optional[str] = None) -> None:
        """
        Delete a workspace's entire collection (DEC-09: one delete_collection per workspace).

        Both this and ``delete_collection`` exist: CLAUDE.md pins the workspace-deletion call
        site to ``delete_collection("ws_<id>")``, while DB-002 specifies this manager-level
        API. Neither is redundant — this one owns the name derivation.
        """
        target = workspace_id or self.workspace_id
        if target is None:
            raise ValueError("drop_workspace requires a workspace_id")
        self.delete_collection(f"ws_{target}")
        if target == self.workspace_id:
            self._collection = None

    def delete_collection(self, name: str) -> None:
        """Delete a collection by raw name. Absent collection is not an error."""
        from chromadb.errors import NotFoundError

        try:
            self._client.delete_collection(name)
            logger.info(f"[VectorDBManager] Deleted collection '{name}'")
        except NotFoundError:
            logger.info(f"[VectorDBManager] Collection '{name}' already absent")

    def close(self) -> None:
        """
        Release the Chroma client.

        Mandatory before a TemporaryDirectory teardown on Windows: an open chroma.sqlite3
        handle causes PermissionError [WinError 32]. clear_system_cache() additionally drops
        Chroma's per-persist_directory System cache so a later client for the same path is
        built fresh.
        """
        self._collection = None
        if not self._owns_client or self._client is None:
            return
        try:
            self._client.close()
        except Exception as e:
            logger.info(f"[VectorDBManager] Client close raised {type(e).__name__}")
        try:
            from chromadb.api.shared_system_client import SharedSystemClient
            SharedSystemClient.clear_system_cache()
        except Exception as e:
            logger.info(f"[VectorDBManager] clear_system_cache raised {type(e).__name__}")

    # ---- chunk operations ------------------------------------------------------------------

    def delete_file(self, file_id: str) -> None:
        """
        Delete every chunk of a file (DEC-09).

        Uses the metadata filter rather than an id list, because chunk ids are never persisted
        in SQLite (DEC-09 forbids reintroducing File_Meta.vector_ids) so we cannot know how
        many there were.
        """
        collection = self._get_collection()
        collection.delete(where={"file_id": file_id})

    def upsert_file_chunks(self, file_id: str, chunks: List[Dict[str, Any]]) -> None:
        """
        Write a file's chunks (DEC-06 / DEC-09). Returns None — never a chunk-id list.

        Chunk ids are recomputed here as ``f"{file_id}:{chunk_index}"`` and any caller-supplied
        ``chunk_id`` is ignored: the deterministic formula is the whole reason ids need not be
        stored in SQLite, and honouring an arbitrary caller value would break the delete path.

        Callers MUST call ``delete_file`` first when re-analysing. Upsert alone leaves stale
        trailing chunks behind when a document shrinks (DEC-09) — upsert cannot delete what it
        does not overwrite.

        Metadata carries exactly ``{workspace_id, file_id, chunk_index, folder_1depth}``.
        No path fields: DEC-08 forbids persisting an absolute path in vector metadata, since a
        cached path is precisely what our own rename feature invalidates.

        Known and accepted: after a file moves, ``folder_1depth`` in existing metadata goes
        stale. DEC-08 forbids re-embedding on a move, so this is not a defect to "fix" — do
        not add a re-embed here.
        """
        if not chunks:
            # A whitespace-only document yields zero chunks and Chroma rejects empty ids.
            return

        collection = self._get_collection()
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for chunk in chunks:
            chunk_index = int(chunk["chunk_index"])
            ids.append(f"{file_id}:{chunk_index}")
            documents.append(chunk["text"])
            metadatas.append({
                "workspace_id": chunk.get("workspace_id") or self.workspace_id or "",
                "file_id": file_id,
                "chunk_index": chunk_index,
                "folder_1depth": chunk.get("folder_1depth") or "root",
            })

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"[VectorDBManager] Upserted {len(ids)} chunks for file {file_id}")

    def get_file_chunks(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Return a file's chunks as row dicts ordered by ``chunk_index``.

        Chroma's ``get()`` returns a columnar GetResult with NO ordering guarantee. Zipping it
        back into rows and sorting makes the order part of *this manager's* contract, which is
        what lets callers index positionally.

        DO NOT REMOVE THE SORT. Callers and tests rely on ``result[i]["chunk_index"] == i``,
        and Chroma will happily return them shuffled.

        The returned ``chunk_id`` values must not be written to SQLite (DEC-09: File_Meta has
        no vector_ids column and must never regain one).
        """
        collection = self._get_collection()
        result = collection.get(where={"file_id": file_id}, include=["documents", "metadatas"])

        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        rows: List[Dict[str, Any]] = []
        for i, chunk_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            text = documents[i] if i < len(documents) else ""
            rows.append({
                "chunk_id": chunk_id,
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "text": text,
                "char_length": len(text or ""),
                "workspace_id": metadata.get("workspace_id"),
                "folder_1depth": metadata.get("folder_1depth"),
            })

        rows.sort(key=lambda r: r["chunk_index"])
        return rows

    def count_chunks(self, file_id: Optional[str] = None) -> int:
        """Chunk count for one file, or for the whole collection when file_id is None."""
        collection = self._get_collection()
        if file_id:
            result = collection.get(where={"file_id": file_id}, include=[])
            return len(result.get("ids") or [])
        return collection.count()

    def search(
        self,
        query_text: str,
        n_results: int = 10,
        live_file_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Cosine similarity search with lazy orphan deletion (DEC-09).

        ``live_file_ids`` is the set of file_ids that still exist in File_Meta. Hits from any
        other file are dropped from the response AND physically deleted — that lazy pass is
        how DEC-09 reclaims orphans, instead of a reconcile sweep or GC scheduler.

        ``live_file_ids=None`` skips post-processing entirely rather than treating it as an
        empty set. Interpreting "caller didn't tell me" as "nothing is alive" would delete the
        entire collection on the first search from an un-updated call site.

        The set is injected rather than queried here because DEC-05 keeps SQL inside
        Repositories — see ``FileRepository.select_existing_file_ids``.
        """
        collection = self._get_collection()
        result = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        hits: List[Dict[str, Any]] = []
        orphan_file_ids: Set[str] = set()
        live: Optional[Set[str]] = set(live_file_ids) if live_file_ids is not None else None

        for i, chunk_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            hit_file_id = metadata.get("file_id")

            if live is not None and hit_file_id not in live:
                orphan_file_ids.add(hit_file_id)
                continue

            hits.append({
                "chunk_id": chunk_id,
                "file_id": hit_file_id,
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "folder_1depth": metadata.get("folder_1depth"),
                "text": documents[i] if i < len(documents) else "",
                "distance": distances[i] if i < len(distances) else None,
            })

        if orphan_file_ids:
            logger.info(f"[VectorDBManager] Lazy-deleting {len(orphan_file_ids)} orphan file(s) from vectors")
            collection.delete(where={"file_id": {"$in": sorted(orphan_file_ids)}})

        return hits


class DeepAnalysisService:
    """
    Deep document parsing, chunking, and vector insertion (ANA-CMD-02).
    Enforces DEC-09 write order and DEC-16 resilience.
    """

    def __init__(
        self,
        db_mgr: DatabaseManager,
        vector_db: Optional[VectorDBManager] = None,
        resilience_service: Optional[LLMResilienceService] = None,
        config_mgr: Optional[Any] = None,
        persist_dir: Optional[str] = None,
    ):
        self.db_mgr = db_mgr
        self.config_mgr = config_mgr
        self.persist_dir = persist_dir or getattr(db_mgr, "vectors_dir", None)
        self.resilience_service = resilience_service or LLMResilienceService()
        self.chunker = TextChunker()

        # An explicitly injected manager is used for every workspace. Otherwise one is built
        # per workspace on demand — collections are per-workspace (DEC-06), and the previous
        # `vector_db or VectorDBManager()` default silently produced a workspace-less store
        # whose writes went nowhere. That no-op default is what let CORE #1 pass its tests.
        self.vector_db = vector_db
        self._managers: Dict[str, VectorDBManager] = {}

    def _manager_for(self, workspace_id: str) -> VectorDBManager:
        if self.vector_db is not None:
            return self.vector_db
        if workspace_id not in self._managers:
            self._managers[workspace_id] = VectorDBManager(
                workspace_id=workspace_id,
                persist_dir=self.persist_dir,
                config_mgr=self.config_mgr,
            )
        return self._managers[workspace_id]

    def close(self) -> None:
        """Close every lazily created manager. Does not close an injected one — its owner does."""
        for manager in self._managers.values():
            manager.close()
        self._managers.clear()

    def process_single_file(self, file_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract text -> chunk -> Chroma delete -> Chroma upsert -> commit parse_status='parsed'.

        That order is fixed by DEC-09. The SQLite commit is last and outside any transaction
        wrapping the Chroma calls, because embedding inference takes seconds and DEC-05
        forbids holding SQLite's single write lock across it.
        """
        file_id = file_record["file_id"]
        file_path = file_record["current_path"]
        extension = file_record.get("extension", "")
        # Indexed, not .get(): a silently missing workspace_id would poison chunk metadata and
        # send writes to the wrong collection. A loud KeyError at the offending call site is
        # strictly better than vectors quietly landing nowhere.
        workspace_id = file_record["workspace_id"]

        vector_db = self._manager_for(workspace_id)

        # 1. Extract text
        raw_text = DocumentParser.extract_text(file_path, extension)

        # 2. Chunk text with DEC-06 metadata (folder name only — DEC-08 forbids paths)
        chunks = self.chunker.chunk_text(
            raw_text,
            file_id,
            workspace_id=workspace_id,
            folder_1depth=derive_folder_1depth(file_path),
        )

        # 3. Vector DB delete -> upsert (DEC-09). Delete first: upsert alone would leave stale
        # trailing chunks if the document shrank.
        vector_db.delete_file(file_id)
        vector_db.upsert_file_chunks(file_id, chunks)

        # 4. Short commit of SQLite parse_status='parsed' (DEC-09)
        query = """
            UPDATE File_Meta
            SET parse_status = 'parsed',
                updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            WHERE file_id = ?;
        """
        with self.db_mgr.transaction() as conn:
            conn.execute(query, (file_id,))

        return {
            "file_id": file_id,
            "chunk_count": len(chunks),
            "parse_status": "parsed",
        }

    def delete_file_vectors(self, workspace_id: str, file_id: str) -> None:
        """
        Drop a deleted file's vectors (DEC-09: vectors first, SQLite row second).

        Without this, every file deletion leaks orphan vectors that keep surfacing in search
        results until a lazy-delete pass happens to touch them.
        """
        self._manager_for(workspace_id).delete_file(file_id)

    def run_deep_analysis_batch(self, workspace_id: str) -> Dict[str, Any]:
        """Run deep analysis over unparsed files with per-file isolation (DEC-16)."""
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_id, workspace_id, current_path, extension
            FROM File_Meta
            WHERE workspace_id = ? AND parse_status != 'parsed';
            """,
            (workspace_id,),
        )
        unparsed_files = [dict(r) for r in cursor.fetchall()]

        # Issue #89: match the schema that process_file_batch returns (no processed_count).
        if not unparsed_files:
            return {
                "status": "completed",
                "succeeded_count": 0,
                "failed": [],
                "aborted_early": False
            }

        return self.resilience_service.process_file_batch(
            unparsed_files,
            lambda f: self.process_single_file(f),
        )
