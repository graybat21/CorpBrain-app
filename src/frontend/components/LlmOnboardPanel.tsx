import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, HardDriveDownload, Loader2, WifiOff, XCircle } from 'lucide-react';

import * as api from '../api/client';
import { errorMessage } from '../api/client';
import type { LlmHealthCheckRes, TaskProgressRes, TaskResultRes } from '../api/types.gen';
import { useAppStore } from '../store/appStore';

/**
 * LLM-FE-02 — Ollama provisioning progress and per-model readiness (issue #31).
 *
 * Two rules from DEC-13 shape this component, and both are about *not* doing the obvious thing:
 *
 * 1. **The two models are never one progress bar.** The embedder is ~274MB and required by
 *    every user including Option A (DEC-06); the generation model is ~4.7GB and Option B only.
 *    A combined percentage makes a user reading "40%" wrong about the remaining time by an
 *    order of magnitude, and hides the fact that Option A never needed the big one.
 * 2. **`detect_only` gets no retry button.** On a closed network the app must not attempt an
 *    install at all, so a retry can only fail again. The button is rendered for `assisted`
 *    failures only; a closed network gets the manual procedure instead.
 *
 * Progress comes from polling `GET /api/v1/analyze/{task_id}/progress` (DEC-04). The 202 from
 * `POST /llm/onboard` carries a task_id and nothing else — there is no push channel by design.
 */

/** REQ-FUNC-011: health is re-probed every 5s so the icon reflects a daemon that just died. */
const HEALTH_POLL_MS = 5000;

interface ModelRowProps {
  label: string;
  sizeHint: string;
  scopeNote: string;
  ready: boolean;
  /** Set while this specific model is the one being downloaded, read from progress_message. */
  active: boolean;
}

/**
 * One model's readiness as its own row.
 *
 * Deliberately not a shared percentage: `progress_message` names the model currently
 * downloading (the backend writes it per step), so this shows which one is moving without
 * inventing a merged number the backend never reported.
 */
const ModelRow: React.FC<ModelRowProps> = ({ label, sizeHint, scopeNote, ready, active }) => (
  <div className="flex items-start justify-between gap-3 bg-slate-950/60 border border-slate-800 rounded-xl px-3 py-2.5">
    <div className="min-w-0">
      <p className="text-[11px] font-semibold text-slate-200 truncate">
        {label} <span className="font-mono text-slate-400">({sizeHint})</span>
      </p>
      <p className="text-[10px] text-slate-500">{scopeNote}</p>
    </div>
    <div className="shrink-0 flex items-center gap-1.5">
      {ready ? (
        <>
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[10px] font-mono text-emerald-400">READY</span>
        </>
      ) : active ? (
        <>
          <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
          <span className="text-[10px] font-mono text-indigo-400">받는 중</span>
        </>
      ) : (
        <>
          <XCircle className="w-3.5 h-3.5 text-slate-600" />
          <span className="text-[10px] font-mono text-slate-500">NOT READY</span>
        </>
      )}
    </div>
  </div>
);

interface LlmOnboardPanelProps {
  health: LlmHealthCheckRes | null;
  /** Called after a terminal task so the parent re-reads health from the backend. */
  onProvisioned: () => void | Promise<void>;
}

export const LlmOnboardPanel: React.FC<LlmOnboardPanelProps> = ({ health, onProvisioned }) => {
  const { addToast, llmMode } = useAppStore();
  const [progress, setProgress] = useState<TaskProgressRes | null>(null);
  const [failure, setFailure] = useState<TaskResultRes | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  // Aborts the in-flight poll when the panel unmounts, so a resolved promise cannot call
  // setState on a dead component (and the loop does not keep polling for 10 minutes).
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  /**
   * AC S2: re-probe health every 5s so the icon reflects a daemon that died since page load.
   *
   * The callback is held in a ref rather than listed as a dependency: a parent that re-creates
   * `onProvisioned` each render would otherwise tear down and restart the interval on every
   * render, and the probe would fire far more often than every 5 seconds.
   *
   * A failed probe is not fatal here — REQ-NF-010 requires the settings UI to work with the LLM
   * down, and the parent already surfaces the error once.
   */
  const onProvisionedRef = useRef(onProvisioned);
  onProvisionedRef.current = onProvisioned;

  useEffect(() => {
    const timer = setInterval(() => void onProvisionedRef.current(), HEALTH_POLL_MS);
    return () => clearInterval(timer);
  }, []);

  const startOnboard = useCallback(
    async (purpose: 'embedding' | 'generation') => {
      if (isRunning) {
        return;
      }
      setIsRunning(true);
      setFailure(null);
      setProgress(null);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const accepted = await api.onboardLlm({ purpose });
        const finalProgress = await api.pollTask(accepted.task_id, {
          signal: controller.signal,
          onProgress: setProgress,
        });

        if (finalProgress.status === 'failed') {
          // The task result carries provision_mode and the missing-model list, which is what
          // decides between "retry" and "manual procedure" below. Read it rather than guessing
          // from error_code alone — LLM_PROVISION_REQUIRED occurs in both modes.
          const result = await api.getTaskResult(accepted.task_id).catch(() => null);
          setFailure(result);
          addToast('error', '로컬 LLM 준비를 완료하지 못했습니다. 아래 안내를 확인하세요.');
        } else {
          addToast('success', '로컬 LLM 준비가 완료되었습니다.');
        }
        await onProvisioned();
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        addToast('error', errorMessage(err));
      } finally {
        setIsRunning(false);
      }
    },
    [addToast, isRunning, onProvisioned],
  );

  const provisionMode = (failure?.result?.provision_mode as string | undefined) ?? null;
  const missingModels = (failure?.result?.missing_models as string[] | undefined) ?? [];
  const failureReason = (failure?.result?.reason as string | undefined) ?? null;
  const isClosedNetwork = provisionMode === 'detect_only';

  const embeddingReady = health?.embedding_model_ready ?? false;
  const generationReady = health?.generation_model_ready ?? false;
  const message = progress?.progress_message ?? null;
  // The backend names the model in progress_message, so "which row is moving" needs no
  // second source of truth and no merged percentage.
  const embeddingActive = isRunning && message !== null && /embed/i.test(message);
  const generationActive = isRunning && message !== null && /qwen|generat/i.test(message);

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2 text-slate-100 font-semibold text-xs">
          <HardDriveDownload className="w-4 h-4 text-indigo-400" />
          <span>로컬 LLM 준비 (LLM-CMD-03)</span>
        </div>
        <span
          className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
            health?.daemon_online
              ? 'text-emerald-400 border-emerald-900 bg-emerald-950/40'
              : 'text-slate-500 border-slate-800 bg-slate-950/60'
          }`}
        >
          {/* 5s polling (AC S2). OFFLINE is a normal state, not an error — REQ-NF-010. */}
          데몬 {health?.daemon_online ? 'ONLINE' : 'OFFLINE'}
        </span>
      </div>

      {/* AC S4 / DEC-13: two separate rows, never one summed bar. */}
      <div className="space-y-2">
        <ModelRow
          label="임베딩 모델 nomic-embed-text"
          sizeHint="약 274MB"
          scopeNote="모든 사용자 필수 — Option A 에서도 검색·분석에 사용됩니다"
          ready={embeddingReady}
          active={embeddingActive}
        />
        <ModelRow
          label="생성 모델 qwen2.5:7b-instruct"
          sizeHint="약 4.7GB"
          scopeNote="Option B 전용 — 로컬에서 위키를 생성할 때만 필요합니다"
          ready={generationReady}
          active={generationActive}
        />
      </div>

      {/* DEC-06 파급: an Option A user still needs the embedder, so say so explicitly rather
          than letting a later 'deep analysis' click fail with an opaque error. */}
      {!embeddingReady && (
        <p className="flex items-start gap-1.5 text-[11px] text-amber-300 bg-amber-950/30 border border-amber-900/60 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>
            임베딩 모델이 준비되지 않아 <strong>심층 분석을 실행할 수 없습니다</strong>. 이 모델은
            Option A(클라우드)를 사용하더라도 문서 검색을 위해 필요합니다.
          </span>
        </p>
      )}

      {/* Live progress. A percentage is shown only when the backend reported a total — the
          counters are 0/0 for provisioning's non-uniform steps, and a fabricated bar would be
          worse than the step text. */}
      {isRunning && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-[11px] text-indigo-300">
            <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
            <span className="truncate">{message ?? '준비 상태를 확인하는 중입니다...'}</span>
          </div>
          {progress !== null && progress.total > 0 && (
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 transition-all duration-300"
                style={{ width: `${progress.percent}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* AC S3 / DEC-13: closed network gets the manual procedure and NO retry button. */}
      {failure !== null && isClosedNetwork && (
        <div className="space-y-2 bg-slate-950/70 border border-slate-800 rounded-xl px-3 py-3">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-300">
            <WifiOff className="w-3.5 h-3.5 shrink-0" />
            폐쇄망 감지 — 수동 프로비저닝이 필요합니다
          </p>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            {failureReason ?? '인터넷에 연결할 수 없어 설치 파일을 내려받지 않았습니다.'} 이 환경에서는
            앱이 설치를 시도하지 않습니다 — 관리자가 아래 절차로 미리 준비해야 합니다.
          </p>
          {missingModels.length > 0 && (
            <div className="text-[11px] text-slate-300">
              <p className="text-slate-400 mb-1">필요한 모델:</p>
              <ul className="space-y-0.5">
                {missingModels.map((model) => (
                  <li key={model} className="font-mono text-amber-200">
                    · {model}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <ol className="text-[10px] text-slate-400 space-y-0.5 list-decimal list-inside leading-relaxed">
            <li>인터넷이 되는 PC 에 Ollama 를 설치합니다.</li>
            <li>
              위 모델을 <span className="font-mono text-slate-300">ollama pull &lt;모델명&gt;</span> 으로
              받습니다.
            </li>
            <li>
              <span className="font-mono text-slate-300">%USERPROFILE%\.ollama\models</span> 폴더를 이 PC 의
              같은 위치로 복사합니다.
            </li>
            <li>Ollama 를 실행한 뒤 이 화면에서 상태를 다시 확인합니다.</li>
          </ol>
          {/* No retry button here, on purpose (DEC-13): there is no internet to retry against,
              so the only thing a button could produce is a repeated failure. */}
        </div>
      )}

      {/* An `assisted` failure DOES get a retry — the network was reachable, so the failure may
          be transient (DoD). */}
      {failure !== null && !isClosedNetwork && (
        <div className="space-y-2 bg-rose-950/30 border border-rose-900/60 rounded-xl px-3 py-3">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold text-rose-300">
            <XCircle className="w-3.5 h-3.5 shrink-0" />
            설치에 실패했습니다
          </p>
          <p className="text-[11px] text-slate-400">{failureReason ?? '설치를 완료하지 못했습니다.'}</p>
          <button
            onClick={() => void startOnboard(llmMode === 'Option B' ? 'generation' : 'embedding')}
            disabled={isRunning}
            className="text-[11px] font-semibold px-3 py-1.5 rounded-lg bg-rose-800 hover:bg-rose-700 disabled:bg-rose-950 disabled:text-rose-300/50 text-white transition"
          >
            설치 재시도
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          onClick={() => void startOnboard('embedding')}
          disabled={isRunning}
          className="flex items-center gap-1.5 text-[11px] font-semibold px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-500 text-slate-100 transition"
        >
          <Download className="w-3.5 h-3.5" />
          임베딩 모델만 준비 (274MB)
        </button>
        <button
          onClick={() => void startOnboard('generation')}
          disabled={isRunning}
          className="flex items-center gap-1.5 text-[11px] font-semibold px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-950 disabled:text-indigo-300/50 text-white transition"
        >
          <Download className="w-3.5 h-3.5" />
          Option B 전체 준비 (임베딩 + 생성)
        </button>
      </div>

      {/* DEC-13 / REQ-NF-005: the internet use is stated rather than hidden, and so is its
          boundary. Concealing either half is what makes a security review fail. */}
      <p className="text-[10px] text-slate-500 leading-relaxed border-t border-slate-800 pt-2.5">
        준비 단계에서는 <strong className="text-slate-400">인터넷에서 설치 파일과 모델 가중치를 내려받습니다</strong>.
        이때 <strong className="text-slate-400">문서 내용과 파일 경로는 전송되지 않습니다</strong>. 준비가 끝난
        뒤 Option B 의 정상 상태 통신은 <span className="font-mono">127.0.0.1</span> 뿐입니다.
      </p>
    </div>
  );
};
