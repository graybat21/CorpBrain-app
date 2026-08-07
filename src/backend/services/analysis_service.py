import logging
from typing import Any, Dict, List

from src.backend.repositories.file_repository import FileRepository

logger = logging.getLogger("CorpBrain.AnalysisService")


class FastAnalysisEngine:
    EXTENSION_BASE_SCORES = {
        ".docx": 50,
        ".pdf": 45,
        ".md": 40,
        ".txt": 30,
    }

    HIGH_PRIORITY_KEYWORDS = ["기획", "설계", "완료", "최종", "prd", "srs", "spec", "plan", "master"]
    LOW_PRIORITY_KEYWORDS = ["임시", "draft", "temp", "old", "backup", "copy", "사본", "test"]

    @classmethod
    def calculate_score(cls, file_name: str, extension: str, path: str) -> int:
        score = cls.EXTENSION_BASE_SCORES.get(extension.lower(), 20)
        fname_lower = file_name.lower()

        # High priority keyword bonuses
        for kw in cls.HIGH_PRIORITY_KEYWORDS:
            if kw in fname_lower:
                score += 15

        # Low priority keyword penalties
        for kw in cls.LOW_PRIORITY_KEYWORDS:
            if kw in fname_lower:
                score -= 20

        # Depth check: shallow files in 1-depth folder get a bonus
        normalized_path = path.replace("\\", "/")
        depth = len([p for p in normalized_path.split("/") if p])
        if depth <= 4:
            score += 10

        # Clamp between 0 and 100
        return max(0, min(100, score))


class FastAnalysisService:
    def __init__(self, file_repo: FileRepository):
        self.file_repo = file_repo

    def run_fast_analysis(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Run fast analysis on workspace files and update importance_score in DB (ANA-CMD-01)."""
        files = self.file_repo.list_by_workspace(workspace_id)
        if not files:
            return []

        updated_records = []
        for f in files:
            score = FastAnalysisEngine.calculate_score(
                file_name=f["file_name"],
                extension=f["extension"],
                path=f["current_path"],
            )
            f_copy = dict(f)
            f_copy["importance_score"] = score
            updated_records.append(f_copy)

        self.file_repo.bulk_upsert(updated_records)

        # Return files sorted by importance_score descending
        updated_records.sort(key=lambda item: item["importance_score"], reverse=True)
        return updated_records
