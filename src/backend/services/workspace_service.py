import logging
import os
from typing import Any, Dict, List, Optional

from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.utils.file_utils import normalize_path

logger = logging.getLogger("CorpBrain.WorkspaceService")


def _collection_absent_errors() -> tuple:
    """
    Exception types that mean "that collection isn't there", for the deletion path.

    chromadb is imported lazily and defensively: this service must stay usable with a
    duck-typed vector store (and in a process that never touches Chroma), so an import failure
    degrades to KeyError/ValueError rather than breaking workspace deletion outright.
    """
    absent: tuple = (KeyError, ValueError)
    try:
        from chromadb.errors import NotFoundError
        absent = (NotFoundError,) + absent
    except ImportError:
        pass
    return absent


class WorkspaceService:
    def __init__(self, repo: WorkspaceRepository, vector_store: Optional[Any] = None):
        self.repo = repo
        self.vector_store = vector_store

    def create_workspace(self, name: str, root_paths: List[str]) -> Dict[str, Any]:
        """Validate all paths exist and create a merged workspace (WS-CMD-01)."""
        if not root_paths:
            raise ValueError("At least one root path must be provided")

        validated_paths = []
        for p in root_paths:
            norm_p = normalize_path(p)
            if not os.path.exists(norm_p):
                raise FileNotFoundError(f"Path does not exist: {p}")
            validated_paths.append(norm_p)

        primary_path = validated_paths[0]
        return self.repo.create(name=name, root_path=primary_path)

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        return self.repo.get_by_id(workspace_id)

    def list_workspaces(self) -> List[Dict[str, Any]]:
        return self.repo.list_all()

    def delete_workspace(self, workspace_id: str) -> bool:
        """
        Delete workspace with strict order DEC-09:
        1) Delete ChromaDB vector collection `ws_<id>` (if vector store available)
        2) Delete SQLite Workspace_Meta row (ON DELETE CASCADE deletes child records)
        """
        # Step 1: Delete ChromaDB collection if vector_store is provided
        if self.vector_store is not None:
            collection_name = f"ws_{workspace_id}"
            try:
                self.vector_store.delete_collection(collection_name)
            except _collection_absent_errors() as e:
                # Narrowed from a bare `except Exception` (CLAUDE.md: no silent failures).
                # An absent collection is benign — a workspace analysed zero files never had
                # one. Any other error must propagate: swallowing it would delete the SQLite
                # row while leaving the vectors behind, stranding them permanently since
                # nothing else knows that collection name.
                logger.info(f"ChromaDB collection '{collection_name}' already absent: {type(e).__name__}")

        # Step 2: Delete SQLite Workspace_Meta row
        return self.repo.delete(workspace_id)
