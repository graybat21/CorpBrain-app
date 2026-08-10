"""
DL-CMD-01 (issue #17) — wiki deeplink anchors and the `deeplink_mappings` key (DEC-08).

Three defects in the anchor path, all of which produced a wiki that looked complete:

1. **Silent truncation at 20.** `_insert_deeplink_anchors` sliced `file_ids[:20]` and
   `_save_wiki` independently sliced `chunks[:20]`. On a folder of more than 20 documents the
   rest simply had no anchor, and absence is indistinguishable from "not relevant" — the user
   had no way to tell the reference list was partial.

2. **No de-duplication.** The caller passes one entry per *chunk*, and one document usually
   produces many chunks. So `[:20]` could list the same file twenty times and show one or two
   distinct documents while presenting itself as the folder's reference list. This made defect 1
   much worse than the number 20 suggests.

3. **The two lists were computed separately.** Anchors came from de-duplicated file_ids; the
   mapping enumerated raw chunks. Both truncated at their own `[:20]`, so mapping index N did
   not refer to the Nth rendered anchor — a deeplink resolved through it could open a different
   file than the one clicked.

**Scope, stated rather than implied.** DEC-08 specifies `deeplink_mappings` as *sentence* index →
file_id, for per-sentence fact-checking. Reaching that requires the generation prompt to return
per-sentence provenance — a prompt-contract change, not a slice fix — and is tracked separately.
What this change does is make the mapping an accurate description of the anchors the document
actually contains, and stop losing files. The tests below assert that honestly: they pin the
anchor-index contract, not a sentence-index one.
"""

import json
import os
import tempfile
import uuid

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.services.wiki_service import WikiGenerationService


@pytest.fixture
def wiki_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wiki17.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            ws_id = WorkspaceRepository(db_mgr).create("Wiki17", [root])["workspace_id"]
            # llm_router/vector_db are not exercised: every test here drives the two pure
            # methods that build the anchor list and the mapping.
            yield WikiGenerationService(db_mgr, llm_router=None), db_mgr, ws_id
        finally:
            db_mgr.close()


def _chunks(file_ids):
    """Chunk hits in the shape `_retrieve_chunks` returns."""
    return [
        {"file_id": fid, "chunk_index": i, "text": f"content {i}"}
        for i, fid in enumerate(file_ids)
    ]


def _anchor_ids(markdown: str):
    """The file_ids rendered as [[file_id:UUID]] anchors, in document order."""
    import re

    return re.findall(r"\[\[file_id:([^\]]+)\]\]", markdown)


# --- Defect 1: no more silent truncation -------------------------------------------------


def test_a_folder_with_more_than_twenty_documents_keeps_every_anchor(wiki_env):
    """
    The original defect: document 21 onward had no anchor at all.

    30 distinct files is an ordinary folder, not an edge case, and the user's only signal that
    ten of them were missing was their absence — which reads as "not relevant to the summary".
    """
    service, db_mgr, ws_id = wiki_env
    file_ids = [str(uuid.uuid4()) for _ in range(30)]

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)

    assert _anchor_ids(markdown) == file_ids, "every distinct file must get an anchor"


def test_exceeding_the_cap_is_stated_and_not_hidden(wiki_env):
    """
    A cap still exists, but going over it must be visible in the markdown.

    CLAUDE.md forbids silent caps: a truncated list that does not say it is truncated reads as
    "this is all of them". The count is what makes it actionable.
    """
    service, db_mgr, ws_id = wiki_env
    over = WikiGenerationService.MAX_ANCHORS + 7
    file_ids = [str(uuid.uuid4()) for _ in range(over)]

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)

    assert len(_anchor_ids(markdown)) == WikiGenerationService.MAX_ANCHORS
    assert "7건이 더 있으나" in markdown, "the omitted count must be stated"


def test_a_list_at_exactly_the_cap_does_not_claim_an_omission(wiki_env):
    """
    Off-by-one guard: exactly MAX_ANCHORS files means nothing was dropped.

    A "0건이 더 있습니다" note would be a false warning, and `>= 0` instead of `> 0` is the easy
    way to write it.
    """
    service, db_mgr, ws_id = wiki_env
    file_ids = [str(uuid.uuid4()) for _ in range(WikiGenerationService.MAX_ANCHORS)]

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)

    assert len(_anchor_ids(markdown)) == WikiGenerationService.MAX_ANCHORS
    assert "생략되었습니다" not in markdown


def test_the_cap_is_above_the_old_hardcoded_twenty(wiki_env):
    """
    Pins the intent: the fix was not "rename 20".

    Documented so a later tuning change has to be deliberate rather than quietly reintroducing
    the original loss at a different number.
    """
    assert WikiGenerationService.MAX_ANCHORS > 20


# --- Defect 2: de-duplication ------------------------------------------------------------


def test_many_chunks_from_one_file_produce_one_anchor(wiki_env):
    """
    The caller passes per-chunk entries, so one document arrives many times.

    Without de-duplication a 25-chunk document filled the entire old 20-slot list with itself,
    and every other file in the folder was dropped — defect 1 triggered by a single document.
    """
    service, db_mgr, ws_id = wiki_env
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    file_ids = [a] * 25 + [b] * 3

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)

    assert _anchor_ids(markdown) == [a, b]


def test_de_duplication_preserves_relevance_order(wiki_env):
    """
    First-seen order, because the caller passes vector-search hits ranked by relevance.

    A `set()` would make the reference list order arbitrary between runs on identical input,
    which reads as the wiki changing on its own.
    """
    service, db_mgr, ws_id = wiki_env
    a, b, c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    file_ids = [c, a, c, b, a, c]

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)

    assert _anchor_ids(markdown) == [c, a, b]


def test_the_cap_counts_distinct_files_not_chunks(wiki_env):
    """
    The cap applies after de-duplication.

    Counting chunks would let one heavily chunked document exhaust the budget, which is the
    behaviour being removed.
    """
    service, db_mgr, ws_id = wiki_env
    file_ids = [str(uuid.uuid4()) for _ in range(30)]
    inflated = [fid for fid in file_ids for _ in range(5)]  # 150 chunk entries, 30 files

    markdown = service._insert_deeplink_anchors("# 요약", inflated)

    assert _anchor_ids(markdown) == file_ids
    assert "생략되었습니다" not in markdown


# --- Defect 3: the mapping matches the rendered anchors ----------------------------------


def test_the_mapping_index_refers_to_the_rendered_anchor(wiki_env):
    """
    The load-bearing invariant: mapping key N is the Nth anchor in the document.

    Before, anchors were de-duplicated while the mapping enumerated raw chunks, so on any folder
    with a multi-chunk document the two disagreed — a deeplink resolved through the mapping
    opened a different file than the one the user clicked. Silently wrong, and worse than a
    missing link, because the user trusts what opens.
    """
    service, db_mgr, ws_id = wiki_env
    a, b, c = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    chunks = _chunks([a, a, a, b, b, c])

    markdown = service._insert_deeplink_anchors("# 요약", [ch["file_id"] for ch in chunks])
    service._save_wiki(ws_id, "docs", markdown, chunks)

    row = db_mgr.get_connection().execute(
        "SELECT markdown_content, deeplink_mappings FROM Wiki_Content WHERE workspace_id = ?;",
        (ws_id,),
    ).fetchone()
    mappings = json.loads(row["deeplink_mappings"])
    rendered = _anchor_ids(row["markdown_content"])

    assert rendered == [a, b, c]
    for index, file_id in mappings.items():
        assert rendered[int(index)] == file_id, f"mapping[{index}] must be the {index}th anchor"


def test_the_mapping_covers_every_rendered_anchor(wiki_env):
    """
    No anchor may be missing from the mapping.

    An anchor the mapping does not know about cannot be resolved — it renders as a link and
    then does nothing when clicked, which is the failure DEC-08's late binding exists to avoid.
    """
    service, db_mgr, ws_id = wiki_env
    file_ids = [str(uuid.uuid4()) for _ in range(30)]
    chunks = _chunks(file_ids)

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)
    service._save_wiki(ws_id, "docs", markdown, chunks)

    row = db_mgr.get_connection().execute(
        "SELECT markdown_content, deeplink_mappings FROM Wiki_Content WHERE workspace_id = ?;",
        (ws_id,),
    ).fetchone()
    mappings = json.loads(row["deeplink_mappings"])

    assert len(mappings) == 30, "all 30 documents must be resolvable, not the first 20"
    assert set(mappings.values()) == set(file_ids)


def test_the_mapping_de_duplicates_like_the_anchors(wiki_env):
    """
    The mapping used to enumerate raw chunks, so a 25-chunk document produced 20 mapping entries
    all pointing at the same file while the document rendered one anchor.
    """
    service, db_mgr, ws_id = wiki_env
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    chunks = _chunks([a] * 25 + [b] * 3)

    service._save_wiki(ws_id, "docs", "# 요약", chunks)

    row = db_mgr.get_connection().execute(
        "SELECT deeplink_mappings FROM Wiki_Content WHERE workspace_id = ?;", (ws_id,)
    ).fetchone()

    assert json.loads(row["deeplink_mappings"]) == {"0": a, "1": b}


def test_the_mapping_respects_the_same_cap(wiki_env):
    """
    Both lists must stop at the same place.

    A mapping longer than the anchor list would carry indices with no anchor to click; shorter,
    and the tail anchors would be dead. Either way the two disagree.
    """
    service, db_mgr, ws_id = wiki_env
    over = WikiGenerationService.MAX_ANCHORS + 5
    file_ids = [str(uuid.uuid4()) for _ in range(over)]
    chunks = _chunks(file_ids)

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)
    service._save_wiki(ws_id, "docs", markdown, chunks)

    row = db_mgr.get_connection().execute(
        "SELECT markdown_content, deeplink_mappings FROM Wiki_Content WHERE workspace_id = ?;",
        (ws_id,),
    ).fetchone()

    assert len(json.loads(row["deeplink_mappings"])) == WikiGenerationService.MAX_ANCHORS
    assert len(_anchor_ids(row["markdown_content"])) == WikiGenerationService.MAX_ANCHORS


def test_an_update_rewrites_the_mapping_rather_than_merging(wiki_env):
    """
    Regenerating a wiki must replace the mapping.

    A merge would leave indices from the previous run pointing at files the new document no
    longer anchors — stale entries that resolve to the wrong file, the same class of bug as
    defect 3.
    """
    service, db_mgr, ws_id = wiki_env
    first = [str(uuid.uuid4()) for _ in range(4)]
    service._save_wiki(ws_id, "docs", "# 1차", _chunks(first))

    second = [str(uuid.uuid4()) for _ in range(2)]
    service._save_wiki(ws_id, "docs", "# 2차", _chunks(second))

    rows = db_mgr.get_connection().execute(
        "SELECT deeplink_mappings FROM Wiki_Content WHERE workspace_id = ?;", (ws_id,)
    ).fetchall()

    assert len(rows) == 1, "DEC-09: one row per (workspace, folder)"
    assert json.loads(rows[0]["deeplink_mappings"]) == {"0": second[0], "1": second[1]}


# --- DEC-08 invariants that must survive the change --------------------------------------


def test_no_absolute_path_reaches_the_markdown_or_the_mapping(wiki_env):
    """
    DEC-08: `[[file_id:UUID]]` is the only anchor form; a cached path is what rename invalidates.

    Checked on both columns because the mapping is the easier place to "helpfully" store a path.
    """
    service, db_mgr, ws_id = wiki_env
    file_ids = [str(uuid.uuid4()) for _ in range(3)]

    markdown = service._insert_deeplink_anchors("# 요약", file_ids)
    service._save_wiki(ws_id, "docs", markdown, _chunks(file_ids))

    row = db_mgr.get_connection().execute(
        "SELECT markdown_content, deeplink_mappings FROM Wiki_Content WHERE workspace_id = ?;",
        (ws_id,),
    ).fetchone()

    for column in (row["markdown_content"], row["deeplink_mappings"]):
        for leak in ("C:\\", "/Users/", "\\\\", ".docx", ".md"):
            assert leak not in column, f"{leak!r} must not appear in persisted wiki data"


def test_an_empty_folder_adds_no_reference_section(wiki_env):
    """No chunks means no anchors — and no empty "참조 파일" header either."""
    service, db_mgr, ws_id = wiki_env

    assert service._insert_deeplink_anchors("# 요약", []) == "# 요약"


def test_the_original_markdown_is_preserved(wiki_env):
    """The anchors are appended; the LLM's summary must not be altered."""
    service, db_mgr, ws_id = wiki_env
    body = "# 요약\n\n본문 내용입니다.\n"

    markdown = service._insert_deeplink_anchors(body, [str(uuid.uuid4())])

    assert markdown.startswith(body)
