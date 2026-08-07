import logging
from typing import List, Dict, Any, Optional
from src.backend.db import DatabaseManager
from src.backend.services.document_parser import DocumentParser, TextChunker
from src.backend.services.llm_resilience_service import LLMResilienceService

logger = logging.getLogger("CorpBrain.VectorService")


class VectorDBManager:
    """
    Local Vector DB Manager (ChromaDB SSOT).
    Maintains collection mapping for file_id chunks (DEC-06 / DEC-09).
    """

    def __init__(self, collection_name: str = "corpbrain_chunks"):
        self.collection_name = collection_name
        # In-memory vector store mapping: file_id -> list of chunk dicts
        self._store: Dict[str, List[Dict[str, Any]]] = {}

    def delete_file(self, file_id: str):
        """Delete all chunks for file_id prior to upserting (DEC-09)."""
        if file_id in self._store:
            del self._store[file_id]
            logger.info(f"[VectorDBManager] Deleted existing chunks for file {file_id}")

    def upsert_file_chunks(self, file_id: str, chunks: List[Dict[str, Any]]):
        """
        Upsert chunks into collection (DEC-09).
        Enforces delete -> upsert sequence.
        """
        self.delete_file(file_id)
        self._store[file_id] = list(chunks)
        logger.info(f"[VectorDBManager] Upserted {len(chunks)} chunks for file {file_id}")

    def get_file_chunks(self, file_id: str) -> List[Dict[str, Any]]:
        return self._store.get(file_id, [])

    def count_chunks(self, file_id: Optional[str] = None) -> int:
        if file_id:
            return len(self._store.get(file_id, []))
        return sum(len(c) for c in self._store.values())


class DeepAnalysisService:
    """
    Executes deep document parsing, chunking, and vector DB insertion (ANA-CMD-02).
    Enforces DEC-09 write order and DEC-16 resilience.
    """

    def __init__(
        self,
        db_mgr: DatabaseManager,
        vector_db: Optional[VectorDBManager] = None,
        resilience_service: Optional[LLMResilienceService] = None,
    ):
        self.db_mgr = db_mgr
        self.vector_db = vector_db or VectorDBManager()
        self.resilience_service = resilience_service or LLMResilienceService()
        self.chunker = TextChunker()

    def process_single_file(self, file_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process single file: Extract text -> Chunk -> Delete old vector -> Upsert -> Set parse_status='parsed' (DEC-09).
        """
        file_id = file_record["file_id"]
        file_path = file_record["current_path"]
        extension = file_record.get("extension", "")

        # 1. Extract text
        raw_text = DocumentParser.extract_text(file_path, extension)

        # 2. Chunk text
        chunks = self.chunker.chunk_text(raw_text, file_id)

        # 3. Vector DB Delete -> Upsert (DEC-09)
        self.vector_db.delete_file(file_id)
        self.vector_db.upsert_file_chunks(file_id, chunks)

        # 4. Short commit SQLite parse_status='parsed' (DEC-09)
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

    def run_deep_analysis_batch(self, workspace_id: str) -> Dict[str, Any]:
        """
        Runs deep analysis batch on unparsed files for workspace_id with isolation (DEC-16).
        """
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_id, current_path, extension
            FROM File_Meta
            WHERE workspace_id = ? AND parse_status != 'parsed';
            """,
            (workspace_id,),
        )
        unparsed_files = [dict(r) for r in cursor.fetchall()]

        if not unparsed_files:
            return {
                "status": "completed",
                "processed_count": 0,
                "succeeded_count": 0,
                "failed": [],
            }

        return self.resilience_service.process_file_batch(
            unparsed_files,
            lambda f: self.process_single_file(f),
        )
