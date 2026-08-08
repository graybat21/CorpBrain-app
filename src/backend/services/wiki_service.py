"""
Wiki generation service (ANA-CMD-03).

Generates structured markdown wiki per 1-depth folder using RAG + LLM.
"""

import json
import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger("CorpBrain.WikiService")


class WikiGenerationService:
    """
    Generate wiki markdown documents per folder_1depth using vector context + LLM.

    DEC-08: Wiki contains [[file_id:UUID]] anchors, never absolute paths.
    DEC-09: Vectors are the SSOT for chunk context.
    """

    def __init__(self, db_mgr, llm_router=None, vector_db=None):
        self.db_mgr = db_mgr

        if llm_router is None:
            from src.backend.services.llm_router import LLMRouter
            llm_router = LLMRouter(db_mgr)
        self.llm_router = llm_router

        self.vector_db = vector_db

    def generate_wiki_for_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """
        Generate wiki documents for all 1-depth folders in a workspace.

        Returns:
            {
                "status": "completed",
                "succeeded_count": int,
                "failed": []
            }
        """
        # Get all unique folder_1depth values from vectors
        folders = self._get_folders(workspace_id)

        succeeded = 0
        failed = []

        for folder in folders:
            try:
                self._generate_wiki_for_folder(workspace_id, folder)
                succeeded += 1
            except Exception as e:
                logger.error(f"[WikiService] Failed to generate wiki for folder {folder}: {e}")
                failed.append({
                    "folder_1depth": folder,
                    "error_code": type(e).__name__,
                    "error_message": str(e)
                })

        return {
            "status": "completed",
            "succeeded_count": succeeded,
            "failed": failed
        }

    def _get_folders(self, workspace_id: str) -> List[str]:
        """
        Get all unique folder_1depth values for this workspace.

        Reads from vector metadata (Chroma is the SSOT for chunks).
        """
        if self.vector_db is None:
            from src.backend.services.vector_service import VectorDBManager
            self.vector_db = VectorDBManager(
                workspace_id=workspace_id,
                persist_dir=self.db_mgr.vectors_dir
            )

        try:
            # Query all chunks for this workspace
            collection = self.vector_db._get_or_create_collection()

            # Get all metadata
            all_data = collection.get(
                where={"workspace_id": workspace_id},
                include=["metadatas"]
            )

            # Extract unique folder_1depth values
            folders = set()
            if all_data and "metadatas" in all_data:
                for meta in all_data["metadatas"]:
                    if meta and "folder_1depth" in meta:
                        folders.add(meta["folder_1depth"])

            return sorted(list(folders))

        except Exception as e:
            logger.warning(f"[WikiService] Failed to get folders from vectors: {e}")
            # Fallback: get from File_Meta
            conn = self.db_mgr.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT current_path FROM File_Meta
                WHERE workspace_id = ? AND parse_status = 'parsed'
            """, (workspace_id,))

            folders = set()
            from src.backend.utils.file_utils import derive_folder_1depth
            for row in cursor.fetchall():
                folder = derive_folder_1depth(row["current_path"])
                folders.add(folder)

            return sorted(list(folders))

    def _generate_wiki_for_folder(self, workspace_id: str, folder_1depth: str):
        """
        Generate wiki markdown for one folder using RAG.

        1. Retrieve relevant chunks from vectors (filtered by folder_1depth)
        2. Build RAG prompt with context
        3. Call LLM to generate wiki markdown
        4. Insert into Wiki_Content table
        """
        # Step 1: Retrieve chunks
        chunks = self._retrieve_chunks(workspace_id, folder_1depth)

        if not chunks:
            logger.info(f"[WikiService] No chunks found for folder {folder_1depth}, skipping")
            return

        # Step 2: Build prompt
        prompt = self._build_rag_prompt(folder_1depth, chunks)

        # Step 3: Call LLM
        from src.backend.services.llm_resilience_service import LLMResilienceService
        resilience = LLMResilienceService()

        def llm_call():
            return self.llm_router.generate(prompt, max_tokens=3000)

        result = resilience.execute_with_retry(
            llm_call,
            file_id=f"wiki:{folder_1depth}",
            is_transient_error=lambda e: self._is_transient(e)
        )

        markdown_content = result["content"]
        cost_usd = result["cost_usd"]
        tokens_used = result["usage"]["input_tokens"] + result["usage"]["output_tokens"]

        # Step 4: Insert wiki with anchors
        markdown_with_anchors = self._insert_deeplink_anchors(
            markdown_content,
            [c["file_id"] for c in chunks]
        )

        self._save_wiki(workspace_id, folder_1depth, markdown_with_anchors, chunks)

        # Log analytics
        self._log_analytics(workspace_id, folder_1depth, tokens_used, cost_usd)

        logger.info(f"[WikiService] Generated wiki for {folder_1depth}: {len(markdown_with_anchors)} chars")

    def _retrieve_chunks(self, workspace_id: str, folder_1depth: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve top N chunks for this folder using vector search.

        Uses a generic query like "summarize this folder" to get diverse content.
        """
        if self.vector_db is None:
            from src.backend.services.vector_service import VectorDBManager
            self.vector_db = VectorDBManager(
                workspace_id=workspace_id,
                persist_dir=self.db_mgr.vectors_dir
            )

        # Generic query to get diverse chunks
        query_text = f"Summarize the contents of the {folder_1depth} folder"

        # Get file_ids that exist in DB (for lazy delete)
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_id FROM File_Meta WHERE workspace_id = ?",
            (workspace_id,)
        )
        live_file_ids = {row["file_id"] for row in cursor.fetchall()}

        # Search with folder filter
        results = self.vector_db.search(
            query_text=query_text,
            n_results=limit,
            folder_1depth=folder_1depth,
            live_file_ids=live_file_ids
        )

        return results

    def _build_rag_prompt(self, folder_1depth: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Build RAG prompt for wiki generation.

        Prompt structure:
        - Task: Summarize folder contents into a structured wiki
        - Context: Chunk texts
        - Output format: Markdown with sections
        """
        context_text = "\n\n---\n\n".join([
            f"[File: {c.get('file_id', 'unknown')[:8]}]\n{c['text']}"
            for c in chunks[:30]  # Limit to prevent token overflow
        ])

        prompt = f"""You are a technical documentation assistant. Create a comprehensive wiki document for the "{folder_1depth}" folder.

**Context** (relevant document excerpts):

{context_text}

**Task**:
Write a well-structured markdown wiki that:
1. Summarizes the main purpose and contents of this folder
2. Organizes information into clear sections with headers
3. Highlights key files, concepts, or patterns
4. Uses bullet points and lists for clarity
5. Keeps the tone professional and concise

**Output** (markdown only, no preamble):
"""

        return prompt

    def _insert_deeplink_anchors(self, markdown: str, file_ids: List[str]) -> str:
        """
        Insert [[file_id:UUID]] anchors into markdown (DEC-08).

        Strategy: Append anchors at the end of paragraphs or sections where relevant files are mentioned.
        For now, simple append at the end of each major section.
        """
        # Simple implementation: append all file_ids as a reference section
        if not file_ids:
            return markdown

        anchors_section = "\n\n---\n\n## 참조 파일\n\n"
        for fid in file_ids[:20]:  # Limit to 20 deeplinks
            anchors_section += f"- [[file_id:{fid}]]\n"

        return markdown + anchors_section

    def _save_wiki(self, workspace_id: str, folder_1depth: str, markdown: str, chunks: List[Dict]):
        """
        Insert or update Wiki_Content table.

        DEC-09: Wiki_Content has unique(workspace_id, folder_1depth) constraint.
        """
        wiki_id = str(uuid.uuid4())

        # Build deeplink_mappings (sentence_index -> file_id)
        # Simple mapping: all file_ids used
        mappings = {str(i): chunk["file_id"] for i, chunk in enumerate(chunks[:20])}

        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()

        # Check if wiki already exists
        cursor.execute("""
            SELECT wiki_id FROM Wiki_Content
            WHERE workspace_id = ? AND folder_1depth = ?
        """, (workspace_id, folder_1depth))

        existing = cursor.fetchone()

        if existing:
            # Update existing
            cursor.execute("""
                UPDATE Wiki_Content
                SET markdown_content = ?,
                    deeplink_mappings = ?,
                    updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                WHERE workspace_id = ? AND folder_1depth = ?
            """, (markdown, json.dumps(mappings), workspace_id, folder_1depth))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO Wiki_Content
                (wiki_id, workspace_id, folder_1depth, markdown_content, deeplink_mappings)
                VALUES (?, ?, ?, ?, ?)
            """, (wiki_id, workspace_id, folder_1depth, markdown, json.dumps(mappings)))

        conn.commit()

    def _log_analytics(self, workspace_id: str, folder_1depth: str, tokens: int, cost: float):
        """Log wiki generation event to Analytics_Log."""
        conn = self.db_mgr.get_connection()
        cursor = conn.cursor()

        # Get wiki_id for this folder
        cursor.execute("""
            SELECT wiki_id FROM Wiki_Content
            WHERE workspace_id = ? AND folder_1depth = ?
        """, (workspace_id, folder_1depth))

        row = cursor.fetchone()
        wiki_id = row["wiki_id"] if row else None

        log_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Analytics_Log
            (log_id, workspace_id, wiki_id, event_type, tokens_used, cost_usd)
            VALUES (?, ?, ?, 'wiki_generated', ?, ?)
        """, (log_id, workspace_id, wiki_id, tokens, cost))

        conn.commit()

    def _is_transient(self, exception: Exception) -> bool:
        """Check if exception is transient (DEC-16: retry only transients)."""
        error_str = str(exception)

        # Transient: 429, 5xx, timeouts
        if "429" in error_str or "rate" in error_str.lower():
            return True
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return True
        if "timeout" in error_str.lower() or "timed out" in error_str.lower():
            return True

        # Non-transient: 401, 400, validation errors
        if "401" in error_str or "unauthorized" in error_str.lower():
            return False
        if "400" in error_str or "bad request" in error_str.lower():
            return False

        # Default: consider transient (safer for retries)
        return True
