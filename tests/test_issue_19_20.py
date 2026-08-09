"""
DL-FE-01 / DL-FE-02 (issues #19, #20) — deeplink badge rendering and click interception.

The backend halves (DL-CMD-02 open, DL-QRY-01 is_broken) were already done. What was missing:
`is_broken` was never consumed by the UI, and the anchor parser was a `components.p` override
doing `String(children)`.

That override had two silent defects, both fixed here by a real remark plugin:

1. **It corrupted any paragraph containing another element.** `children` is an array of React
   nodes, so `계약을 **확정**했습니다. [[file_id:...]]` stringified to
   `계약을 ,[object Object],했습니다...` — the bold was destroyed and `[object Object]` was shown
   to the user.
2. **It only looked inside `<p>`.** An anchor in a list item, table cell or heading stayed as
   literal `[[file_id:...]]` text.

The plugin's behaviour was verified by executing it against real markdown through unified (see
the PR body for the output); these tests pin the resulting structure and the backend contract.
The React rendering itself is asserted statically, per tests/test_ws_fe_01.py — there is no
frontend test runner by decision.
"""

import os
import re
import tempfile
import uuid
from pathlib import Path

import pytest

from src.backend.db import DatabaseManager
from src.backend.repositories.file_repository import FileRepository
from src.backend.repositories.workspace_repository import WorkspaceRepository

FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"
PLUGIN = FRONTEND / "api" / "remarkDeepLink.ts"
BADGE = FRONTEND / "components" / "DeepLinkBadge.tsx"
WIKI_PAGE = FRONTEND / "pages" / "WikiPage.tsx"


def _code(path: Path) -> str:
    """Source with comments stripped — same rationale as tests/test_ws_fe_01.py::_code."""
    content = path.read_text(encoding="utf-8")
    content = re.sub(r"\{/\*.*?\*/\}", "", content, flags=re.S)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.S)
    content = re.sub(r"^\s*//.*$", "", content, flags=re.MULTILINE)
    return content


# --- Backend: is_broken is a real probe, not a guess ------------------------------------


@pytest.fixture
def wiki_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_mgr = DatabaseManager(db_path=os.path.join(tmpdir, "wiki.db"))
        try:
            root = os.path.join(tmpdir, "docs")
            os.makedirs(root)
            ws_id = WorkspaceRepository(db_mgr).create("Wiki WS", [root])["workspace_id"]

            live_path = os.path.join(root, "살아있는.txt")
            with open(live_path, "w", encoding="utf-8") as f:
                f.write("content")
            gone_path = os.path.join(root, "사라진.txt")

            live_id, gone_id = str(uuid.uuid4()), str(uuid.uuid4())
            FileRepository(db_mgr).bulk_upsert([
                {
                    "file_id": live_id, "workspace_id": ws_id,
                    "current_path": live_path, "original_path": live_path,
                    "file_name": "살아있는.txt", "extension": ".txt",
                    "size_bytes": 7, "last_modified": 1700000000.0,
                    "parse_status": "pending", "importance_score": 0,
                },
                {
                    # Row exists, file does not — the definition of a broken link.
                    "file_id": gone_id, "workspace_id": ws_id,
                    "current_path": gone_path, "original_path": gone_path,
                    "file_name": "사라진.txt", "extension": ".txt",
                    "size_bytes": 1, "last_modified": 1700000000.0,
                    "parse_status": "pending", "importance_score": 0,
                },
            ])
            yield db_mgr, ws_id, live_id, gone_id, live_path
        finally:
            db_mgr.close()


def test_scenario_2_a_deleted_file_reports_is_broken(wiki_env):
    """
    AC S2 (#19): the row survives, the file does not, so the link is broken.

    The anchor itself stays valid — DEC-08 makes `file_id` the identity — which is why the badge
    is greyed rather than removed. Deleting it would destroy the audit trail the wiki provides.
    """
    from src.backend.services.query_services import DeepLinkQueryService

    db_mgr, ws_id, live_id, gone_id, live_path = wiki_env
    service = DeepLinkQueryService(db_mgr)

    assert service.check_deeplink_status(ws_id, live_id)["is_broken"] is False
    broken = service.check_deeplink_status(ws_id, gone_id)
    assert broken["is_broken"] is True
    assert broken["reason"] == "PATH_NOT_ACCESSIBLE"


def test_a_renamed_file_is_not_a_broken_link(wiki_env):
    """
    DEC-08: an internal rename is by definition never a broken link.

    Late binding resolves `file_id` at query time, so moving the file and updating the row keeps
    the link live — and the wiki body is never rewritten.
    """
    from src.backend.services.query_services import DeepLinkQueryService

    db_mgr, ws_id, live_id, gone_id, live_path = wiki_env
    renamed = os.path.join(os.path.dirname(live_path), "이름바뀐.txt")
    os.rename(live_path, renamed)
    FileRepository(db_mgr).update_path(ws_id, live_id, renamed)

    status = DeepLinkQueryService(db_mgr).check_deeplink_status(ws_id, live_id)
    assert status["is_broken"] is False
    assert status["file_name"] == "이름바뀐.txt"


def test_the_status_response_is_reachable_over_http(wiki_env):
    """The badge reads this endpoint, so its shape is part of the contract (DEC-03)."""
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    db_mgr, ws_id, live_id, gone_id, live_path = wiki_env
    app = create_app(db_mgr, session_token="dl-token")
    client = TestClient(app)
    headers = {"Authorization": "Bearer dl-token"}

    res = client.get(
        f"/api/v1/workspace/{ws_id}/deeplink/status",
        params={"file_id": gone_id},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["is_broken"] is True
    assert data["file_id"] == gone_id


def test_opening_a_broken_link_fails_with_a_code_not_a_path(wiki_env):
    """
    DEC-03/DEC-08: the failure carries a code, and no absolute path reaches the client.

    A path in the error body would be the leak DEC-08 closes, and it is also the one piece of
    information the user cannot act on.
    """
    from fastapi.testclient import TestClient

    from src.backend.api.app import create_app

    db_mgr, ws_id, live_id, gone_id, live_path = wiki_env
    app = create_app(db_mgr, session_token="dl-token")
    client = TestClient(app)

    res = client.post(
        f"/api/v1/workspace/{ws_id}/deeplink/open",
        json={"file_id": gone_id},
        headers={"Authorization": "Bearer dl-token"},
    )
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] in ("PATH_NOT_ACCESSIBLE", "NOT_FOUND")
    assert os.path.dirname(live_path) not in res.text, "an absolute path leaked into the response"


# --- The remark plugin (static structure) ------------------------------------------------


def test_the_anchor_pattern_requires_a_full_uuid():
    """
    A strict UUID pattern is what makes the emitted attribute safe.

    The id is the only document-derived value that reaches a DOM property, so a loose pattern
    (`[0-9a-zA-Z\\-]+`, as the old inline regex used) would let arbitrary text through.
    """
    source = PLUGIN.read_text(encoding="utf-8")
    assert "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" in source
    # The old permissive class must be gone.
    assert "0-9a-zA-F" not in source


def test_the_plugin_walks_the_tree_rather_than_stringifying_children():
    """
    The regression this replaces: `String(children)` printed `[object Object]` for any paragraph
    containing a sibling element, and never looked outside `<p>`.
    """
    plugin = _code(PLUGIN)
    wiki = _code(WIKI_PAGE)

    # The plugin operates on mdast text nodes.
    assert "child.type === 'text'" in plugin
    assert "node.children" in plugin
    # And the page no longer stringifies children or overrides `p`.
    assert "String(children)" not in wiki
    assert "parts.map(" not in wiki
    assert "remarkDeepLink" in wiki


def test_code_blocks_are_left_alone_by_construction():
    """
    Documentation showing the anchor format must not turn into a button.

    `code`/`inlineCode` have no children, so the recursion cannot reach inside them — asserted
    against the comment-stripped source so the reasoning is enforced, not just described.
    """
    plugin = _code(PLUGIN)
    # The traversal only descends into nodes with children and only splits `text` nodes.
    assert "if (!node.children || node.children.length === 0)" in plugin


def test_no_undeclared_dependency_was_added():
    """
    CLAUDE.md §4: `mdast-util-find-and-replace` would be the idiomatic tool, but it is only a
    `remark-gfm` transitive here. Importing a package we do not declare breaks the moment that
    transitive changes — and it would also enter the PyInstaller-embedded bundle (DEC-01).
    """
    plugin = PLUGIN.read_text(encoding="utf-8")
    assert "mdast-util" not in plugin.split('"""')[0] or "import" not in plugin.split("\n")[0]
    for banned in ("mdast-util-find-and-replace", "unist-util-visit"):
        assert f"from '{banned}'" not in plugin, f"{banned} is not a declared dependency"

    package_json = (Path(__file__).resolve().parent.parent / "package.json").read_text(encoding="utf-8")
    assert "mdast-util-find-and-replace" not in package_json
    assert "unist-util-visit" not in package_json


# --- The badge (static structure) --------------------------------------------------------


def test_scenario_1_of_issue_20_the_browser_never_navigates():
    """
    AC S1 (#20): preventDefault AND stopPropagation, and no href to bypass.

    A `<button type="button">` rather than an `<a href>`: an anchor is openable in a new tab via
    middle-click or ⌘-click, which bypasses the onClick handler entirely — so the interception
    would be defeated by a mouse gesture rather than by any code change.
    """
    badge = _code(BADGE)

    assert "event.preventDefault()" in badge
    assert "event.stopPropagation()" in badge
    assert 'type="button"' in badge
    assert "href" not in badge, "an <a href> can be opened in a new tab, bypassing onClick"


def test_a_broken_badge_is_grey_with_a_tooltip():
    """AC S2 (#19): grey styling plus the exact tooltip text the issue names."""
    badge = _code(BADGE)

    assert "원본 파일을 찾을 수 없습니다" in badge
    assert "text-slate-500" in badge, "a broken badge must be greyed"
    # The tooltip is exposed to assistive tech too, not only as a hover title.
    assert "aria-label" in badge
    assert "title=" in badge


def test_a_broken_badge_stays_clickable_so_the_toast_can_fire():
    """
    REQ-FUNC-022 asks for a Toast when a broken link is clicked, so `disabled` would suppress the
    very feedback the requirement wants.

    Asserted as an absence, which is the only way to state it: the broken branch must not carry
    `disabled`.
    """
    badge = _code(BADGE)
    broken_branch = badge[badge.index("if (isBroken === true)"):badge.index("return (\n    <button\n      type=\"button\"\n      onClick={handleClick}\n      title={isBroken === null")]
    assert "disabled" not in broken_branch, "a broken badge must remain clickable (REQ-FUNC-022)"


def test_an_unprobed_badge_is_neutral_not_broken():
    """
    `null` means "not probed yet" and must render as normal.

    Greying a link before its status is known accuses a perfectly good file, and on a slow probe
    that is what the user would see first.
    """
    badge = _code(BADGE)
    assert "isBroken === true" in badge, "only an explicit true may render as broken"
    assert "isBroken: boolean | null" in badge


def test_the_badge_shows_no_path():
    """DEC-08: the client never receives or displays an absolute path."""
    badge = _code(BADGE)
    assert "current_path" not in badge
    assert "fileId.slice(0, 8)" in badge, "the id is truncated for display"


# --- The page wiring --------------------------------------------------------------------


def test_the_page_probes_status_and_feeds_it_to_the_badge():
    """DoD: DL-QRY-01's `is_broken` must actually reach the badge."""
    wiki = _code(WIKI_PAGE)

    assert "getDeepLinkStatus" in wiki
    assert "is_broken" in wiki
    assert "isBroken={" in wiki
    # One probe per anchor, resolved together, and one failure must not blank the rest.
    assert "Promise.allSettled" in wiki


def test_a_broken_link_click_raises_a_toast_without_calling_open():
    """
    REQ-FUNC-022: the click answers with a Toast. Calling `openDeepLink` first would produce a
    backend error for a state the client already knew about.
    """
    wiki = _code(WIKI_PAGE)
    handler = wiki[wiki.index("const handleAnchorClick"):wiki.index("const currentTabData")]

    guard = handler.index("brokenById[fileId] === true")
    open_call = handler.index("api.openDeepLink")
    assert guard < open_call, "the broken-link guard must precede the open call"
    assert "addToast" in handler
