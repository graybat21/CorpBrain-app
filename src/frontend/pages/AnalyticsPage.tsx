import React, { useCallback, useEffect, useState } from 'react';
import { Activity, BarChart3, Clock, FileStack, MousePointerClick, RefreshCw } from 'lucide-react';

import * as api from '../api/client';
import { errorMessage } from '../api/client';
import type { AnalyticsSummaryRes } from '../api/types.gen';
import { useAppStore } from '../store/appStore';

/**
 * STAT-FE-01 — My Analytics: the four metric cards and the compression visual (issue #50).
 *
 * NO CHART LIBRARY. The issue's task breakdown suggests "Recharts 등 경량 차트 라이브러리", but
 * Recharts is not in CLAUDE.md §4's pre-approved dependency list, and a new runtime package also
 * enters the PyInstaller-embedded bundle (DEC-01). The one visual the AC actually asks for is a
 * compression ratio — two counts and a bar — which is a div with a width. Recorded as CORE 2 in
 * docs/loop/CHECKPOINT.md so the deviation from the issue text is visible rather than silent.
 *
 * All four metrics come from one `GET /analytics/summary` call (REQ-NF-005: local API only, no
 * external telemetry).
 *
 * The period boundary is computed HERE, in the user's timezone, and sent as UTC instants — DEC-11
 * puts this on the frontend precisely because the server cannot know the user's zone, and a
 * server-inferred "this week" would be up to 9 hours off from KST's.
 */

/** `knowledge_ratio_scope` is always "current", so the ratio card must not claim a period. */
const SNAPSHOT_SCOPE = 'current';

interface MetricCardProps {
  label: string;
  value: string;
  hint: string;
  icon: React.ReactNode;
  accent: string;
  /** Staggered entry, so the four cards animate in sequence rather than all at once (AC S1). */
  delayMs: number;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, hint, icon, accent, delayMs }) => {
  const [shown, setShown] = useState(false);

  useEffect(() => {
    // A timeout rather than a CSS animation-delay: the card must mount hidden and transition in,
    // and `animation-delay` would leave it visible for the first frame on a slow render.
    const timer = setTimeout(() => setShown(true), delayMs);
    return () => clearTimeout(timer);
  }, [delayMs]);

  return (
    <div
      className={`bg-slate-900/80 border border-slate-800 rounded-2xl p-5 transition-all duration-500 ${
        shown ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] text-slate-400 font-medium">{label}</span>
        <span className={accent}>{icon}</span>
      </div>
      <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
      <p className="text-[10px] text-slate-500 mt-1">{hint}</p>
    </div>
  );
};

/**
 * Compression ratio as a two-segment bar (AC's "압축률 시각화").
 *
 * `parsed:wiki` — e.g. "40:3" means 40 documents were condensed into 3 pages. Rendered as
 * proportional widths with the numbers written out, because a bar alone cannot be read precisely
 * and these two counts are the whole point.
 */
const CompressionBar: React.FC<{ ratio: string; scope: string }> = ({ ratio, scope }) => {
  const [parsedRaw, wikiRaw] = ratio.split(':');
  const parsed = Number(parsedRaw) || 0;
  const wiki = Number(wikiRaw) || 0;
  const total = parsed + wiki;
  // 50/50 when there is nothing yet, so the empty bar is not a single colour block.
  const parsedPct = total === 0 ? 50 : Math.round((parsed / total) * 100);

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-100 font-semibold text-xs">
          <BarChart3 className="w-4 h-4 text-indigo-400" />
          <span>지식 압축률</span>
        </div>
        {/* DEC-07: the ratio is a snapshot, so it must not be labelled with the selected period —
            saying "이번 주 압축률" would attribute a period to a period-independent number. */}
        {scope === SNAPSHOT_SCOPE && (
          <span className="text-[10px] text-slate-500 font-mono">현재 시점 기준</span>
        )}
      </div>

      <div className="flex h-3 rounded-full overflow-hidden bg-slate-800">
        <div
          className="bg-indigo-500 transition-all duration-700"
          style={{ width: `${parsedPct}%` }}
          aria-hidden="true"
        />
        <div
          className="bg-emerald-500 transition-all duration-700"
          style={{ width: `${100 - parsedPct}%` }}
          aria-hidden="true"
        />
      </div>

      {/* The numbers are text, not only bar widths — a proportional bar cannot be read precisely,
          and colour alone fails for colour-blind users. */}
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-indigo-300">
          분석된 문서 <strong className="tabular-nums">{parsed}</strong>건
        </span>
        <span className="text-emerald-300">
          위키 문서 <strong className="tabular-nums">{wiki}</strong>건
        </span>
      </div>
      {parsed > 0 && wiki > 0 && (
        <p className="text-[10px] text-slate-500">
          문서 {parsed}건이 위키 {wiki}건으로 정리되었습니다.
        </p>
      )}
    </div>
  );
};

/** Minutes → a gamified phrase (REQ-FUNC-028~030), without claiming precision it does not have. */
function formatSavedTime(minutes: number): string {
  if (minutes < 1) {
    return '0분';
  }
  if (minutes < 60) {
    return `${Math.round(minutes)}분`;
  }
  const hours = Math.floor(minutes / 60);
  const rest = Math.round(minutes % 60);
  return rest === 0 ? `${hours}시간` : `${hours}시간 ${rest}분`;
}

export const AnalyticsPage: React.FC = () => {
  const { currentWorkspace, addToast } = useAppStore();
  const [summary, setSummary] = useState<AnalyticsSummaryRes | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const workspaceId = currentWorkspace?.workspace_id ?? null;

  const load = useCallback(async () => {
    if (!workspaceId) {
      setSummary(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      // DEC-11: the week boundary is computed here, in local time, and sent as UTC instants. The
      // server must never be asked to infer "this week" — it does not know the user's timezone.
      const now = new Date();
      const weekStart = new Date(now);
      weekStart.setDate(now.getDate() - now.getDay());
      weekStart.setHours(0, 0, 0, 0);

      const result = await api.getAnalyticsSummary(workspaceId, {
        from_time: weekStart.toISOString(),
        to_time: now.toISOString(),
      });
      setSummary(result);
    } catch (err) {
      const message = errorMessage(err);
      setError(message);
      addToast('error', `통계를 불러오지 못했습니다: ${message}`);
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId, addToast]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-xs text-slate-400">
        워크스페이스를 선택하면 통계가 표시됩니다.
      </div>
    );
  }

  // AC S2: every metric at zero means nothing has been analysed yet. Checked across all four
  // rather than on one, so a workspace with only deeplink clicks still shows its real numbers.
  const isEmpty =
    summary !== null &&
    summary.saved_time_minutes === 0 &&
    summary.deeplink_clicks_count === 0 &&
    summary.watcher_updates_count === 0 &&
    summary.compression_ratio === '0:0';

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">My Analytics</h1>
          <p className="text-xs text-slate-400">
            이번 주 생산성 지표입니다. 모든 수치는 로컬에서만 계산되며 외부로 전송되지 않습니다.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={isLoading}
          className="flex items-center gap-1.5 text-[11px] text-indigo-400 hover:text-indigo-300 disabled:text-slate-600 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>{isLoading ? '불러오는 중...' : '다시 계산'}</span>
        </button>
      </div>

      {error !== null && (
        <p className="text-[11px] text-rose-300 bg-rose-950/30 border border-rose-900/60 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {/* AC S2 — Empty State. Shown instead of four zeros, because a wall of 0s reads as a broken
          dashboard rather than "you have not started yet". */}
      {isEmpty && (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <Activity className="w-8 h-8 text-slate-600" />
          <p className="text-sm text-slate-300">분석을 시작하면 통계가 표시됩니다.</p>
          <p className="text-[11px] text-slate-500">
            워크스페이스를 스캔하고 심층 분석을 실행하면 절약 시간과 압축률이 집계됩니다.
          </p>
        </div>
      )}

      {summary !== null && !isEmpty && (
        <>
          {/* AC S1 — four metric cards, staggered in. */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="절약한 시간"
              value={formatSavedTime(summary.saved_time_minutes)}
              hint={`이번 주 · 읽기 속도 ${250} WPM 기준 추정치`}
              icon={<Clock className="w-4 h-4" />}
              accent="text-amber-400"
              delayMs={0}
            />
            <MetricCard
              label="팩트체크"
              value={`${summary.deeplink_clicks_count}번`}
              hint="원문을 직접 확인한 횟수"
              icon={<MousePointerClick className="w-4 h-4" />}
              accent="text-indigo-400"
              delayMs={80}
            />
            <MetricCard
              label="지식 압축률"
              value={summary.compression_ratio}
              hint="분석 문서 : 위키 문서 (현재 시점)"
              icon={<FileStack className="w-4 h-4" />}
              accent="text-emerald-400"
              delayMs={160}
            />
            <MetricCard
              label="자동화"
              value={`${summary.watcher_updates_count}번`}
              hint="Watcher 가 자동 갱신한 횟수"
              icon={<Activity className="w-4 h-4" />}
              accent="text-purple-400"
              delayMs={240}
            />
          </div>

          <CompressionBar
            ratio={summary.compression_ratio}
            scope={summary.knowledge_ratio_scope}
          />

          {/* The cost figure is an estimate by construction (DEC-16), and saying so is required —
              a number presented as a bill would be confidently wrong whenever the seeded price is
              stale. */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">이번 주 LLM 사용 토큰</span>
              <span className="font-mono text-slate-200 tabular-nums">
                {summary.total_tokens_used.toLocaleString('ko-KR')}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">추정 비용</span>
              <span className="font-mono text-slate-200 tabular-nums">
                ${summary.total_cost_usd.toFixed(4)}
              </span>
            </div>
            <p className="text-[10px] text-slate-500 pt-1">
              설정에 저장된 단가로 계산한 <strong>추정치</strong>입니다. 실제 청구액과 다를 수 있습니다.
            </p>
          </div>
        </>
      )}
    </div>
  );
};
