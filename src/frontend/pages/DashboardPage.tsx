import React from 'react';
import { Files, BookOpen, ShieldCheck, Zap, ArrowUpRight, BarChart3 } from 'lucide-react';
import { useAppStore } from '../store/appStore';

export const DashboardPage: React.FC = () => {
  const { files, currentWorkspace, addToast, setActiveTab } = useAppStore();

  const totalFiles = files.length;
  const highPriorityFiles = files.filter((f) => f.importance_score >= 50);

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-indigo-900/60 via-slate-900 to-slate-900 border border-indigo-500/30 rounded-2xl p-6 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl -z-0 pointer-events-none" />
        <div className="relative z-10 space-y-2">
          <div className="inline-flex items-center space-x-2 bg-indigo-950/80 border border-indigo-700/50 px-3 py-1 rounded-full text-xs text-indigo-300 font-medium">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>CorpBrain 오프라인 전용 AI 지능 엔진 구동 중</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            {currentWorkspace?.workspace_name} 대시보드
          </h1>
          <p className="text-sm text-slate-400 max-w-2xl">
            로컬 문서 스캔, 구조 기반 중요도 가중치 산출, PII 사전 마스킹 게이트 및 딥링크 위키 연동 현황을 한눈에 관리합니다.
          </p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">총 스캔 문서</span>
            <Files className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-white font-mono">{totalFiles} <span className="text-xs text-slate-400 font-sans">개</span></p>
          <p className="text-[11px] text-emerald-400 flex items-center">
            <ArrowUpRight className="w-3 h-3 mr-0.5" /> 10K Limit Guard 정상 (정상 탐색)
          </p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">핵심 중요 문서 (50점+)</span>
            <BarChart3 className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-amber-300 font-mono">{highPriorityFiles.length} <span className="text-xs text-slate-400 font-sans">개</span></p>
          <p className="text-[11px] text-slate-400">키워드 사전(기획·설계·최종) 가중치 적용</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">생성된 딥링크 위키</span>
            <BookOpen className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-2xl font-bold text-white font-mono">1 <span className="text-xs text-slate-400 font-sans">개</span></p>
          <p className="text-[11px] text-blue-400">Late Binding [[file_id:UUID]] 유지</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">PII 마스킹 방어건수</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-emerald-300 font-mono">1 <span className="text-xs text-slate-400 font-sans">건</span></p>
          <p className="text-[11px] text-emerald-400">Fail-Closed 2조건 AND 검증 완료</p>
        </div>
      </div>

      {/* High Priority Documents Section */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-100">구조 기반 고속 분석 하이라이트 (ANA-CMD-01)</h2>
            <p className="text-xs text-slate-400">파일 확장자, 트리 뎁스, 가중치 키워드를 기반으로 산출된 중요도 순위입니다.</p>
          </div>
          <button
            onClick={() => setActiveTab('files')}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition flex items-center space-x-1"
          >
            <span>전체 파일 탐색기 이동</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="divide-y divide-slate-800">
          {files.map((file) => (
            <div key={file.file_id} className="py-3 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs ${
                    file.importance_score >= 70
                      ? 'bg-amber-950 text-amber-400 border border-amber-800/60'
                      : file.importance_score >= 40
                      ? 'bg-blue-950 text-blue-400 border border-blue-800/60'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {file.importance_score}점
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-200">{file.file_name}</p>
                  <p className="text-[11px] text-slate-400 font-mono truncate max-w-lg">{file.current_path}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <span className="text-[11px] bg-slate-800 text-slate-300 px-2 py-1 rounded font-mono">
                  {(file.size_bytes / 1024).toFixed(1)} KB
                </span>
                <button
                  onClick={() => addToast('info', `${file.file_name} 상세 매핑 정보를 확인합니다.`)}
                  className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded transition"
                >
                  상세 보기
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
