/**
 * Remark plugin turning `[[file_id:UUID]]` into a node the renderer can map to a badge
 * (DL-FE-01, issue #19).
 *
 * Replaces a `components.p` override that did `String(children)`. That approach had two defects,
 * both silent:
 *
 * 1. **It corrupted any paragraph containing another element.** `children` is an array of React
 *    nodes, so a paragraph mixing `**bold**` with an anchor stringified to
 *    `text ,[object Object], more` — the bold was lost and `[object Object]` was rendered to the
 *    user.
 * 2. **It only looked inside `<p>`.** An anchor in a list item, table cell, blockquote or heading
 *    was left as literal `[[file_id:...]]` text. The wiki generator has no rule keeping anchors
 *    out of those, so this was a matter of luck rather than design.
 *
 * Operating on the mdast instead fixes both: every `text` node is visited wherever it sits, and
 * sibling formatting is untouched because we only ever split `text` nodes.
 *
 * No new dependency (CLAUDE.md §4). `mdast-util-find-and-replace` would be the idiomatic tool but
 * it is only present as a `remark-gfm` transitive — importing a package we do not declare would
 * break the moment that transitive changes. The traversal below is ~30 lines of plain recursion.
 */

/** UUID as DEC-11 stores it: 36-char hyphenated. Case-insensitive because markdown is hand-editable. */
const ANCHOR_PATTERN =
  /\[\[file_id:([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]\]/gi;

interface MdastNode {
  type: string;
  value?: string;
  children?: MdastNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

/**
 * Split one text node into text/anchor pieces.
 *
 * Anchors become an `inlineCode`-like custom node carrying `hName: 'corpbrain-deeplink'` and the
 * file_id as a property, which react-markdown surfaces to a component of that name. Emitting a
 * real element name rather than raw HTML keeps this XSS-free: the id has already been matched
 * against a strict UUID pattern, and nothing else from the document reaches an attribute.
 */
function splitTextNode(node: MdastNode): MdastNode[] | null {
  const value = node.value ?? '';
  if (!value.includes('[[file_id:')) {
    return null;
  }

  const pieces: MdastNode[] = [];
  let lastIndex = 0;
  ANCHOR_PATTERN.lastIndex = 0;

  let match: RegExpExecArray | null;
  while ((match = ANCHOR_PATTERN.exec(value)) !== null) {
    if (match.index > lastIndex) {
      pieces.push({ type: 'text', value: value.slice(lastIndex, match.index) });
    }
    pieces.push({
      type: 'deeplink',
      data: {
        hName: 'corpbrain-deeplink',
        // Lowercased so a hand-edited uppercase UUID still matches the DB (DEC-11 stores
        // lowercase). The status lookup and the open call both key on this value.
        hProperties: { fileid: match[1].toLowerCase() },
      },
      children: [],
    });
    lastIndex = match.index + match[0].length;
  }

  // A malformed anchor (`[[file_id:not-a-uuid]]`) matches nothing and falls through here as
  // literal text — visible to the user, which is the honest outcome. Silently deleting it would
  // hide a corrupted wiki row.
  if (pieces.length === 0) {
    return null;
  }
  if (lastIndex < value.length) {
    pieces.push({ type: 'text', value: value.slice(lastIndex) });
  }
  return pieces;
}

function transform(node: MdastNode): void {
  if (!node.children || node.children.length === 0) {
    return;
  }

  const next: MdastNode[] = [];
  for (const child of node.children) {
    if (child.type === 'text') {
      const split = splitTextNode(child);
      if (split) {
        next.push(...split);
        continue;
      }
    } else {
      // `code` and `inlineCode` have no children, so a literal `[[file_id:...]]` inside a fenced
      // block is left alone by construction — documentation showing the anchor format must not
      // turn into a button.
      transform(child);
    }
    next.push(child);
  }
  node.children = next;
}

/** Collect every file_id an anchor references, so their status can be probed in one pass. */
export function extractFileIds(markdown: string): string[] {
  const ids = new Set<string>();
  ANCHOR_PATTERN.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = ANCHOR_PATTERN.exec(markdown)) !== null) {
    ids.add(match[1].toLowerCase());
  }
  return Array.from(ids);
}

export function remarkDeepLink() {
  return (tree: MdastNode) => {
    transform(tree);
  };
}
