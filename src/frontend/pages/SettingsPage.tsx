import React from 'react';
import { ShieldCheck, Cpu, Lock, Globe, Key } from 'lucide-react';
import { useAppStore } from '../store/appStore';

export const SettingsPage: React.FC = () => {
  const { llmMode, setLlmMode, addToast } = useAppStore();

  const handleModeChange = (mode: 'Option A' | 'Option B') => {
    setLlmMode(mode);
    addToast('success', `LLM 구동 모드가 ${mode}로 변경되었습니다.`);
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
            onClick={() => handleModeChange('Option A')}
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
            onClick={() => handleModeChange('Option B')}
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
            API Key 및 사용자 보안 자격 증명은 Windows DPAPI(`CryptProtectData`)로 암호화되어 로컬 SQLite에 안전하게 보관됩니다.
          </p>
        </div>
      </div>
    </div>
  );
};
