import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Eye, EyeOff, Loader2, Moon, Radio, RefreshCw } from 'lucide-react';

import * as api from '../api/client';
import { errorMessage } from '../api/client';
import type { WatcherStatusRes } from '../api/types.gen';
import { useAppStore } from '../store/appStore';

/**
 * WA-FE-01 + WA-FE-02 — watcher mode control, status icon, queue badge, and the background
 * wiki-update toast (issues #56, #57).
 *
 * There is no push channel by design (DEC-04), so "the wiki was updated in the background" is
 * detected by comparing the newest `updated_at` across wiki tabs between polls. A WebSocket
 * broadcast is explicitly not adopted.
 *
 * REQ-NF-002 caps idle cost, so polling is deliberately restrained:
 *  - only while a watcher mode that actually watches is selected (`manual`/`off` poll nothing),
 *  - 3s for status rather than 1s. DEC-04's 1s interval is for a *task* the user is waiting on;
 *    a watcher badge is ambient, and 1s would triple the wakeups for no visible benefit.
 */

/** REQ-FUNC-023's four modes. Kept in this order so the select reads from least to most active. */
const MODES: { value: string; label: string; hint: string }[] = [
  { value: 'off', label: '끄기', hint: '파일 변경을 감시하지 않습니다.' },
  { value: 'manual', label: '수동', hint: '직접 실행할 때만 분석합니다.' },
  { value: 'idle', label: '유휴', hint: 'PC가 유휴 상태일 때 갱신합니다.' },
  { value: 'realtime', label: '실시간', hint: '변경을 감지하면 즉시 갱신합니다.' },
];

/** Modes that actually watch. `manual`/`off` need no polling at all (REQ-NF-002). */
const ACTIVE_MODES = new Set(['realtime', 'idle']);

const STATUS_POLL_MS = 3000;

export const WatcherControl: React.FC = () => {
  const { currentWorkspace, addToast } = useAppStore();
  const [status, setStatus] = useState<WatcherStatusRes | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  /**
   * Newest wiki `updated_at` seen so far, for AC S1 of #57.
   *
   * A ref, not state: it must not trigger a re-render, and comparing against a stale closure
   * value would fire the toast repeatedly for one update. `null` means "not yet established" —
   * the first observation only records the baseline, because announcing an update on page load
   * would claim something happened when nothing did.
   */
  const lastWikiUpdate = useRef<string | null>(null);

  const workspaceId = currentWorkspace?.workspace_id ?? null;

  // Reset the baseline when the workspace changes: another workspace's timestamps say nothing
  // about this one, and carrying them over would fire a spurious toast on every switch.
  useEffect(() => {
    lastWikiUpdate.current = null;
    setStatus(null);
  }, [workspaceId]);

  const poll = useCallback(async () => {
    if (!workspaceId) {
      return;
    }
    try {
      const next = await api.getWatcherStatus(workspaceId);
      setStatus(next);

      // Only look for wiki changes while something is actually watching.
      if (!ACTIVE_MODES.has(next.mode)) {
        return;
      }
      const wiki = await api.getWorkspaceWiki(workspaceId);
      const newest = wiki.tabs.reduce<string | null>(
        (max, tab) => (max === null || tab.updated_at > max ? tab.updated_at : max),
        null,
      );
      if (newest === null) {
        return;
      }
      if (lastWikiUpdate.current === null) {
        lastWikiUpdate.current = newest;
        return;
      }
      if (newest > lastWikiUpdate.current) {
        lastWikiUpdate.current = newest;
        // AC S1 (#57): a non-blocking toast, not a modal — the update happened in the
        // background and must not interrupt what the user is doing (CLAUDE.md §6).
        addToast('success', '위키가 최신화되었습니다.');
      }
    } catch {
      // A failed poll is silent on purpose. This runs every 3 seconds, so a toast per failure
      // would bury every other notification while the backend is briefly unavailable —
      // REQ-NF-010 wants the UI usable with services down, not narrating it. The status icon
      // going stale is the visible signal.
    }
  }, [workspaceId, addToast]);

  useEffect(() => {
    if (!workspaceId) {
      return;
    }
    void poll();
    // Poll only for modes that watch. `manual`/`off` settle after the first read, which is what
    // keeps an idle app near zero background work (REQ-NF-002).
    if (status !== null && !ACTIVE_MODES.has(status.mode)) {
      return;
    }
    const timer = setInterval(() => void poll(), STATUS_POLL_MS);
    return () => clearInterval(timer);
    // `status?.mode` rather than `status`: the object is replaced on every poll, so depending on
    // it would tear down and recreate the interval each tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, status?.mode, poll]);

  /** AC S1 (#56): the select calls WA-CMD-01 and reflects the result. */
  const handleModeChange = async (mode: string) => {
    if (!workspaceId || isSaving) {
      return;
    }
    setIsSaving(true);
    try {
      const updated = await api.setWatcherConfig(workspaceId, { mode, debounce_ms: 500 });
      setStatus((prev) =>
        prev === null
          ? null
          : { ...prev, mode: updated.mode, is_enabled: updated.is_enabled },
      );
      addToast('success', `Watcher 모드를 '${MODES.find((m) => m.value === mode)?.label ?? mode}'로 변경했습니다.`);
      await poll();
    } catch (err) {
      // DoD: failure gets its own toast. A silent failure would leave the select showing a mode
      // the backend never accepted.
      addToast('error', `Watcher 모드 변경 실패: ${errorMessage(err)}`);
      await poll();
    } finally {
      setIsSaving(false);
    }
  };

  if (!currentWorkspace) {
    return null;
  }

  const mode = status?.mode ?? 'manual';
  const isWatching = status?.is_enabled === true;
  const queued = status?.queued_items_count ?? 0;
  const ModeIcon = mode === 'realtime' ? Radio : mode === 'idle' ? Moon : isWatching ? Eye : EyeOff;

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex items-center">
        <ModeIcon
          className={`w-4 h-4 ${isWatching ? 'text-emerald-400' : 'text-slate-500'}`}
          aria-hidden="true"
        />
        {/* AC S2 (#56): the pending count for THIS workspace, beside the icon. Hidden at 0 so a
            quiet watcher does not display a permanent "0". */}
        {queued > 0 && (
          <span
            aria-label={`대기 중인 변경 ${queued}건`}
            className="absolute -top-1.5 -right-2 min-w-[15px] px-1 bg-amber-500 text-slate-950 text-[9px] font-bold rounded-full text-center leading-[15px]"
          >
            {queued}
          </span>
        )}
      </div>

      {/* Status as text too, not colour alone — a green/grey icon is unreadable for a
          colour-blind user and invisible to a screen reader. */}
      <span className="text-[10px] font-mono text-slate-400 hidden sm:inline">
        {isWatching ? '감시 중' : '중지'}
      </span>

      <select
        value={mode}
        onChange={(e) => void handleModeChange(e.target.value)}
        disabled={isSaving}
        aria-label="Watcher 모드"
        title={MODES.find((m) => m.value === mode)?.hint}
        className="bg-slate-900 border border-slate-700 text-slate-200 text-[11px] rounded-lg px-2 py-1 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
      >
        {MODES.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>

      {isSaving ? (
        <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" aria-label="저장 중" />
      ) : (
        <button
          type="button"
          onClick={() => void poll()}
          aria-label="Watcher 상태 새로고침"
          className="text-slate-500 hover:text-indigo-400 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};
