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

    #: How many files the UI highlights as "핵심 문서" (issue #1 AC Scenario 2).
    #: REQ-FUNC-012 says "상위 문서를 UI 상단에 하이라이트" without fixing a count; the number 3
    #: comes from the issue's acceptance criteria. It lives here rather than in the route or the
    #: React page because the rank cutoff is a property of what the fast analysis *means* — two
    #: consumers picking different cutoffs would highlight different files for the same scores.
    TOP_RANKED_LIMIT = 3

    @classmethod
    def rank_key(cls, record: Dict[str, Any]) -> tuple:
        """
        Sort key for the importance ranking: score descending, then file name ascending.

        The tiebreaker is not cosmetic. Files that were never analysed all sit at score 0, and
        without a second key their relative order is whatever SQLite's scan happens to produce
        — which makes the highlighted set change between two identical requests.
        """
        return (-(record.get("importance_score") or 0), record.get("file_name") or "")

    @classmethod
    def select_top_ranked(cls, records: List[Dict[str, Any]], limit: int | None = None) -> List[str]:
        """
        The `file_id`s of the highest-scoring files, most important first (ANA-CMD-01 AC S2).

        Score-0 files are excluded rather than padded in. A freshly scanned workspace has not run
        fast analysis yet, so every row sits at 0; returning three of them would have the
        dashboard label arbitrary files as 핵심 문서 before any analysis produced that judgement.
        Fewer than `limit` entries is therefore a valid answer, including an empty list.
        """
        if limit is None:
            limit = cls.TOP_RANKED_LIMIT
        scored = [r for r in records if (r.get("importance_score") or 0) > 0]
        scored.sort(key=cls.rank_key)
        return [r["file_id"] for r in scored[:limit]]


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

        # Return files sorted by importance_score descending, same ordering the file list query
        # and the UI highlight use — one ranking definition, three consumers.
        updated_records.sort(key=FastAnalysisEngine.rank_key)
        return updated_records
