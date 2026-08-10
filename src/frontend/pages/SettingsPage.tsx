import React, { useCallback, useEffect, useState } from 'react';
import { ShieldCheck, Cpu, Lock, Globe, Key, RefreshCw, CircleDollarSign } from 'lucide-react';
import * as api from '../api/client';
import { errorMessage } from '../api/client';
import { LlmOnboardPanel } from '../components/LlmOnboardPanel';
import type { LlmHealthCheckRes } from '../api/types.gen';
import { useAppStore, type LlmMode } from '../store/appStore';

/** `YYYY-MM-DD` for a date input, from the stored ISO-8601 UTC instant (DEC-11). */
function toDateInput(iso: string | null | undefined): string {
  if (!iso) {
    return '';
  }
  return iso.slice(0, 10);
}

export const SettingsPage: React.FC = () => {
  const { llmMode, setLlmMode, addToast } = useAppStore();
  const [health, setHealth] = useState<LlmHealthCheckRes | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  // AC S2 (issue #30): the price fields are editable, so they are form state rather than read
  // straight off `health` — a controlled input bound to the fetched value cannot be typed in.
  const [priceInput, setPriceInput] = useState('');
  const [priceOutput, setPriceOutput] = useState('');
  const [priceDate, setPriceDate] = useState('');
  const [isSavingPrice, setIsSavingPrice] = useState(false);

  /**
   * `quiet` suppresses the toast for the 5s background probe (issue #31).
   *
   * Without it the LLM-FE-02 panel's polling raises a toast every 5 seconds whenever the
   * backend is unreachable — a stack of identical errors that buries every other notification.
   * The state still updates, so the ❌ icon reports the failure; only the interruption is
   * dropped. REQ-NF-010 wants the settings UI usable with the LLM down, not shouting about it.
   */
  const loadHealth = useCallback(
    async (quiet = false) => {
      try {
        const res = await api.getLlmConfig();
        setHealth(res);
        setLlmMode(res.mode === 'Option B' ? 'Option B' : 'Option A');
        // Seed the price form from what is stored. Guarded on `null` rather than falsy: a
        // legitimately free tier at 0.00 must not be replaced by the previous value.
        if (res.cloud_price_input_per_mtok != null) {
          setPriceInput(String(res.cloud_price_input_per_mtok));
        }
        if (res.cloud_price_output_per_mtok != null) {
          setPriceOutput(String(res.cloud_price_output_per_mtok));
        }
        setPriceDate(toDateInput(res.cloud_price_updated_at));
      } catch (err) {
        setHealth(null);
        if (!quiet) {
          addToast('error', errorMessage(err));
        }
      }
    },
    [addToast, setLlmMode],
  );

  /** Stable callback for the panel's 5s interval, so it never toasts. */
  const loadHealthQuietly = useCallback(() => loadHealth(true), [loadHealth]);

  useEffect(() => {
    void loadHealth();
  }, [loadHealth]);

  /**
   * DEC-16: an engine change is a security decision and only ever comes from this explicit
   * action — nothing else in the app may switch modes, including on an Option A failure.
   */
  const handleModeChange = async (mode: LlmMode) => {
    if (isSaving || mode === llmMode) {
      return;
    }
    setIsSaving(true);
    try {
      await api.setLlmConfig({ llm_mode: mode });
      setLlmMode(mode);
      addToast('success', `LLM 구동 모드가 ${mode}로 변경되었습니다.`);
      await loadHealth();
    } catch (err) {
      addToast('error', errorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * DEC-12: the key goes to the loopback server, which encrypts it with DPAPI. It is cleared
   * from this component's state immediately and is never put in the store, localStorage, or a
   * log; afterwards the backend reports only `api_key_configured`.
   */
  const handleSaveApiKey = async () => {
    const key = apiKeyInput.trim();
    if (!key) {
      addToast('warning', 'API Key를 입력하세요.');
      return;
    }
    setIsSaving(true);
    try {
      await api.setLlmConfig({ llm_mode: llmMode, api_key: key });
      setApiKeyInput('');
      addToast('success', 'API Key가 DPAPI로 암호화되어 저장되었습니다.');
      await loadHealth();
    } catch (err) {
      addToast('error', errorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * AC S2 / DEC-16: prices are user-editable and never fetched over the network.
   *
   * The reference date is the user's, not `now()` — it says which published price list these
   * figures came from, so stamping the save time would relabel a rate copied from last quarter
   * as current. That is the whole reason the field exists.
   */
  const handleSavePrice = async () => {
    const input = Number(priceInput);
    const output = Number(priceOutput);
    if (!Number.isFinite(input) || !Number.isFinite(output) || input < 0 || output < 0) {
      addToast('warning', '단가는 0 이상의 숫자여야 합니다.');
      return;
    }
    if (priceDate === '') {
      // Refused rather than defaulted: a price with no reference date is the ambiguity this
      // feature exists to remove, and silently substituting today's date would assert something
      // the user never said.
      addToast('warning', '단가 기준일을 입력하세요.');
      return;
    }
    setIsSavingPrice(true);
    try {
      await api.setLlmPrice({
        cloud_price_input_per_mtok: input,
        cloud_price_output_per_mtok: output,
        // DEC-11: TEXT ISO-8601 UTC. The date input yields YYYY-MM-DD; midnight UTC is the
        // instant that round-trips back to the same date in the field.
        cloud_price_updated_at: `${priceDate}T00:00:00Z`,
      });
      addToast('success', '단가와 기준일이 저장되었습니다.');
      await loadHealth();
    } catch (err) {
      addToast('error', errorMessage(err));
    } finally {
      setIsSavingPrice(false);
    }
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight">보안 & LLM 설정</h1>
        <p className="text-xs text-slate-400">
          NetworkGuard 3층 무단 외부 유출 방어막 및 PII 사전 마스킹 게이트 설정 현황입니다.
        </p>
      </div>

      {/* LLM Engine Option Selection */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex items-center space-x-2 text-slate-100 font-semibold text-sm">
          <Cpu className="w-4 h-4 text-indigo-400" />
          <span>LLM 구동 엔진 선택 (Cloud vs Local)</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            onClick={() => void handleModeChange('Option A')}
            className={`p-4 rounded-xl border cursor-pointer transition ${
              llmMode === 'Option A'
                ? 'bg-indigo-950/60 border-indigo-500 text-white shadow-lg'
                : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-xs">Option A: Anthropic Claude Sonnet 5 (Cloud)</span>
              <Globe className="w-4 h-4 text-indigo-400" />
            </div>
            <p className="text-[11px] leading-relaxed text-slate-300">
              클라우드 LLM을 호출하며, **NetworkGuard(purpose='llm_cloud')** 경유 및 **PIIFilter(7종 정규식)** 사전 마스킹 게이트를 필수 수반합니다.
            </p>
          </div>

          <div
            onClick={() => void handleModeChange('Option B')}
            className={`p-4 rounded-xl border cursor-pointer transition ${
              llmMode === 'Option B'
                ? 'bg-indigo-950/60 border-indigo-500 text-white shadow-lg'
                : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-xs">Option B: Ollama Local LLM (100% Offline)</span>
              <Lock className="w-4 h-4 text-emerald-400" />
            </div>
            <p className="text-[11px] leading-relaxed text-slate-300">
              외부 네트워크 통신이 전혀 없는 100% 오프라인 로컬 LLM을 호출합니다. Zero-Telemetry 오프라인 완벽 보장.
            </p>
          </div>
        </div>
      </div>

      {/* LLM-FE-02 (issue #31): provisioning progress + per-model readiness. Rendered for both
          modes on purpose — DEC-06 makes the embedding model a requirement for Option A too, so
          hiding this panel behind `llmMode === 'Option B'` would leave an Option A user unable
          to see why deep analysis is unavailable. */}
      <LlmOnboardPanel health={health} onProvisioned={loadHealthQuietly} />

      {/* Security Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center space-x-2 text-slate-100 font-semibold text-xs">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>NetworkGuard 3층 Egress 방어막 (INF-CMD-03)</span>
          </div>
          <div className="space-y-1.5 text-[11px] text-slate-400">
            <p className="flex justify-between">
              <span>Layer 1 (Domain Whitelist):</span>
              <span className="text-emerald-400 font-mono">api.anthropic.com ONLY</span>
            </p>
            <p className="flex justify-between">
              <span>Layer 2 (IP Loopback Isolation):</span>
              <span className="text-emerald-400 font-mono">127.0.0.1 ONLY</span>
            </p>
            <p className="flex justify-between">
              <span>Layer 3 (Network Switch Lock):</span>
              <span className="text-emerald-400 font-mono">Active</span>
            </p>
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center space-x-2 text-slate-100 font-semibold text-xs">
            <Key className="w-4 h-4 text-amber-400" />
            <span>Windows DPAPI 보안 키 관리 (INF-CMD-02)</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            API Key는 Windows DPAPI(`CryptProtectData`)로 암호화되어 로컬 SQLite에 보관됩니다. 저장된
            키는 화면에 다시 표시되지 않으며, 설정 조회 시 등록 여부만 확인할 수 있습니다 (DEC-12).
          </p>
          <p className="text-[11px]">
            <span className="text-slate-400">현재 등록 상태: </span>
            <span
              className={
                health?.api_key_configured ? 'text-emerald-400 font-mono' : 'text-amber-400 font-mono'
              }
            >
              {health ? (health.api_key_configured ? '등록됨' : '미등록') : '확인 중...'}
            </span>
          </p>
          <div className="flex items-center space-x-2">
            <input
              type="password"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              autoComplete="off"
              placeholder="Anthropic API Key 입력"
              className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-[11px] text-slate-200 font-mono focus:outline-none focus:border-indigo-500 transition"
            />
            <button
              onClick={() => void handleSaveApiKey()}
              disabled={isSaving || apiKeyInput.trim() === ''}
              className="bg-amber-600 hover:bg-amber-500 disabled:bg-amber-900 disabled:text-amber-200/60 text-white text-[11px] font-semibold px-3 py-2 rounded-lg transition"
            >
              저장
            </button>
          </div>
        </div>
      </div>

      {/* Engine health (LLM-QRY-01) — a real probe, never a hardcoded value (DEC-13). */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-slate-100 font-semibold text-xs">
            <Cpu className="w-4 h-4 text-indigo-400" />
            <span>엔진 상태 점검 (LLM-QRY-01)</span>
          </div>
          <button
            onClick={() => void loadHealth()}
            className="flex items-center space-x-1.5 text-[11px] text-indigo-400 hover:text-indigo-300 transition"
          >
            <RefreshCw className="w-3 h-3" />
            <span>다시 점검</span>
          </button>
        </div>

        {health ? (
          <div className="space-y-1.5 text-[11px] text-slate-400">
            <p className="flex justify-between">
              <span>종합 사용 가능 여부:</span>
              <span className={health.is_healthy ? 'text-emerald-400 font-mono' : 'text-rose-400 font-mono'}>
                {health.is_healthy ? 'READY' : (health.error_code ?? 'UNAVAILABLE')}
              </span>
            </p>
            {/* DEC-13: daemon reachability and per-model presence are reported separately —
                a live daemon with no models still cannot run analysis. */}
            <p className="flex justify-between">
              <span>Ollama 데몬 (127.0.0.1:11434):</span>
              <span className={health.daemon_online ? 'text-emerald-400 font-mono' : 'text-slate-500 font-mono'}>
                {health.daemon_online ? 'ONLINE' : 'OFFLINE'}
              </span>
            </p>
            <p className="flex justify-between">
              <span>임베딩 모델 (전 사용자 필수):</span>
              <span className={health.embedding_model_ready ? 'text-emerald-400 font-mono' : 'text-slate-500 font-mono'}>
                {health.embedding_model_ready ? 'READY' : 'NOT READY'}
              </span>
            </p>
            <p className="flex justify-between">
              <span>생성 모델 (Option B 전용):</span>
              <span className={health.generation_model_ready ? 'text-emerald-400 font-mono' : 'text-slate-500 font-mono'}>
                {health.generation_model_ready ? 'READY' : 'NOT READY'}
              </span>
            </p>
          </div>
        ) : (
          <p className="text-[11px] text-slate-400">엔진 상태를 확인하는 중입니다...</p>
        )}
      </div>

      {/* AC S2 (issue #30) / DEC-16 — cloud price table with its reference date.
          Deliberately absent: any "현재 단가 자동 확인" button. Fetching a price list would be a
          fourth egress destination, which DEC-15 makes a design-decision change rather than a
          code change. The prices are migration-seeded and edited here by hand. */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
        <div className="flex items-center space-x-2 text-slate-100 font-semibold text-xs">
          <CircleDollarSign className="w-4 h-4 text-emerald-400" />
          <span>클라우드 단가 (Option A)</span>
        </div>

        <p className="text-[11px] text-slate-400">
          입력·출력 100만 토큰당 단가입니다. 표시되는 비용은 이 단가로 계산한{' '}
          <strong className="text-amber-300">추정치</strong>이며, 실제 청구액과 다를 수 있습니다.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label className="space-y-1">
            <span className="text-[10px] text-slate-400 block">입력 ($/MTok)</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={priceInput}
              onChange={(e) => setPriceInput(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-emerald-500 transition"
            />
          </label>
          <label className="space-y-1">
            <span className="text-[10px] text-slate-400 block">출력 ($/MTok)</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={priceOutput}
              onChange={(e) => setPriceOutput(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-emerald-500 transition"
            />
          </label>
          <label className="space-y-1">
            {/* The date is a peer of the prices, not a footnote: DEC-16 requires the figures to
                carry the date they are current as of, because a price shown alone reads as live. */}
            <span className="text-[10px] text-slate-400 block">단가 기준일</span>
            <input
              type="date"
              value={priceDate}
              onChange={(e) => setPriceDate(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-emerald-500 transition"
            />
          </label>
        </div>

        <div className="flex items-center justify-between">
          <p className="text-[10px] text-slate-500">
            {health?.cloud_price_updated_at
              ? `저장된 기준일: ${toDateInput(health.cloud_price_updated_at)} (${health.cloud_price_input_per_mtok} / ${health.cloud_price_output_per_mtok} $per MTok)`
              : '저장된 단가 정보를 불러오는 중입니다...'}
          </p>
          <button
            onClick={() => void handleSavePrice()}
            disabled={isSavingPrice}
            className="bg-emerald-700 hover:bg-emerald-600 disabled:bg-emerald-900 disabled:text-emerald-200/60 text-white text-[11px] font-semibold px-3 py-2 rounded-lg transition"
          >
            {isSavingPrice ? '저장 중...' : '단가 저장'}
          </button>
        </div>
      </div>
    </div>
  );
};
