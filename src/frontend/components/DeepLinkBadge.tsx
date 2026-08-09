import React from 'react';
import { ExternalLink, FileCheck, Unlink } from 'lucide-react';

/**
 * DL-FE-01 / DL-FE-02 — the `[[file_id:UUID]]` anchor as a clickable badge (issues #19, #20).
 *
 * Two behaviours the issue is specific about:
 *
 * - **Broken links are grey and carry a tooltip**, not hidden and not silently clickable. A
 *   broken link means the row's `current_path` is gone from disk (REQ-FUNC-022) — the anchor
 *   itself is still valid, so removing it would destroy the audit trail the wiki provides.
 * - **The browser must never navigate.** `preventDefault` + `stopPropagation`, and this is a
 *   `<button type="button">` rather than an `<a>`: a `<button>` inside a form would submit it,
 *   and an `<a href>` would be openable in a new tab via middle-click or ⌘-click, bypassing the
 *   handler entirely. There is no href to bypass.
 *
 * The badge shows a truncated id, never a path — DEC-08 keeps absolute paths off the client, and
 * `file_name` is only shown when the backend has already told us it (via the status probe).
 */

export interface DeepLinkBadgeProps {
  fileId: string;
  /** null while the status probe is in flight — rendered as neutral, not as broken. */
  isBroken: boolean | null;
  /** Resolved name from DL-QRY-01, when known. Never a path. */
  fileName?: string | null;
  onOpen: (fileId: string) => void;
}

export const DeepLinkBadge: React.FC<DeepLinkBadgeProps> = ({
  fileId,
  isBroken,
  fileName,
  onOpen,
}) => {
  const shortId = fileId.slice(0, 8);
  const label = fileName ?? `file_id:${shortId}`;

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    // AC S1 (#20): the browser must not navigate or open a tab. Both calls, deliberately —
    // preventDefault stops the default action, stopPropagation stops an ancestor handler (the
    // markdown container) from treating this as a content click.
    event.preventDefault();
    event.stopPropagation();
    onOpen(fileId);
  };

  if (isBroken === true) {
    return (
      <button
        type="button"
        onClick={handleClick}
        // Still clickable on purpose: REQ-FUNC-022 asks for a Toast when a broken link is
        // clicked, so `disabled` would suppress the very feedback the requirement wants.
        title="원본 파일을 찾을 수 없습니다"
        aria-label={`${label} — 원본 파일을 찾을 수 없습니다`}
        className="inline-flex items-center space-x-1 bg-slate-800 hover:bg-slate-700 text-slate-500 border border-slate-700 px-2 py-0.5 rounded font-mono text-xs transition mx-0.5 line-through decoration-slate-600"
      >
        <Unlink className="w-3 h-3 text-slate-500 shrink-0" />
        <span>{label}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      title={isBroken === null ? '링크 상태 확인 중' : '원본 파일 열기'}
      aria-label={`${label} 원본 파일 열기`}
      className="inline-flex items-center space-x-1 bg-indigo-950 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 px-2 py-0.5 rounded font-mono text-xs transition mx-0.5"
    >
      <FileCheck className="w-3 h-3 text-indigo-400 shrink-0" />
      <span>{label}</span>
      <ExternalLink className="w-2.5 h-2.5 ml-0.5 text-indigo-400 shrink-0" />
    </button>
  );
};
