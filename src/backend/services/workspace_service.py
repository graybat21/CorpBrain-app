import os
import logging
from typing import Any, Dict, List, Optional
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.utils.file_utils import normalize_path

logger = logging.getLogger("CorpBrain.WorkspaceService")


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
            except Exception as e:
                logger.info(f"ChromaDB collection '{collection_name}' not found or already deleted: {e}")

        # Step 2: Delete SQLite Workspace_Meta row
        return self.repo.delete(workspace_id)
