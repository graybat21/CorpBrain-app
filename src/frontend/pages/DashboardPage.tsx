import React, { useEffect, useState } from 'react';
import { AlertTriangle, Files, BookOpen, ShieldCheck, Zap, ArrowUpRight, BarChart3 } from 'lucide-react';
import * as api from '../api/client';
import { errorMessage } from '../api/client';
import type { AnalyticsSummaryRes, ScanSummaryRes } from '../api/types.gen';
import { useAppStore } from '../store/appStore';

export const DashboardPage: React.FC = () => {
  const { files, topRankedFileIds, currentWorkspace, isReady, addToast, setActiveTab } = useAppStore();
  // Membership test rather than indexOf on every row: the list is at most TOP_RANKED_LIMIT long,
  // but `files` can hold 10,000 rows (SCAN-CMD-02) and this runs once per row.
  const topRanked = new Set(topRankedFileIds);
  const [summary, setSummary] = useState<AnalyticsSummaryRes | null>(null);
  const [scan, setScan] = useState<ScanSummaryRes | null>(null);

  const workspaceId = currentWorkspace?.workspace_id;

  useEffect(() => {
    if (!workspaceId) {
      setSummary(null);
      setScan(null);
      return;
    }
    let cancelled = false;
    // DEC-11: the backend never infers a period boundary, so no from_time/to_time means
    // "all time". A KST week/month view would compute its own UTC bounds and pass them here.
    //
    // Two endpoints rather than one: the scan summary carries the file count, total size and
    // the 10K guard state (WS-FE-03 / issue #64), none of which analytics knows about.
    api
      .getAnalyticsSummary(workspaceId)
      .then((res) => {
        if (!cancelled) {
          setSummary(res);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          addToast('error', errorMessage(err));
        }
      });
    api
      .getScanSummary(workspaceId)
      .then((res) => {
        if (!cancelled) {
          setScan(res);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          addToast('error', errorMessage(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, addToast]);

  // The scan summary counts every scanned row server-side; `files` is the list the explorer
  // currently holds. Preferring the server's count means the tile does not silently shrink when
  // the list is filtered or still loading.
  const totalFiles = scan ? scan.file_count : files.length;
  const highPriorityFiles = files.filter((f) => f.importance_score >= 50);

  // `compression_ratio` is the "<parsed files>:<wiki documents>" snapshot the analytics service
  // computes. Parsing the second term is cheaper than a second endpoint; `null` renders as "—"
  // rather than 0, so "not loaded" never reads as "no wiki exists".
  const wikiCount = summary ? Number(summary.compression_ratio.split(':')[1] ?? NaN) : NaN;
  const wikiCountLabel = Number.isFinite(wikiCount) ? wikiCount : null;

  const handleOpenFile = async (fileId: string, fileName: string) => {
    if (!workspaceId) {
      return;
    }
    try {
      // DEC-08: file_id only. The path is resolved server-side from File_Meta.current_path.
      await api.openDeepLink(workspaceId, { file_id: fileId });
      await api.logAnalyticsEvent(workspaceId, { event_type: 'deeplink_click', file_id: fileId });
    } catch (err) {
      addToast('error', `${fileName}: ${errorMessage(err)}`);
    }
  };

  if (!isReady) {
    return (
      <div className="p-6 text-xs text-slate-400">워크스페이스 정보를 불러오는 중입니다...</div>
    );
  }

  if (!currentWorkspace) {
    return (
      <div className="p-6 space-y-2">
        <h1 className="text-xl font-bold text-white tracking-tight">워크스페이스가 없습니다</h1>
        <p className="text-xs text-slate-400">
          분석할 폴더를 워크스페이스로 등록하면 스캔 및 중요도 분석을 시작할 수 있습니다.
        </p>
      </div>
    );
  }

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
          {/* WS-FE-03 / issue #64: the caption reflects the real guard state. It used to be the
              hardcoded string "10K Limit Guard 정상 (정상 탐색)", which stayed green on a
              truncated workspace — asserting everything was indexed at the exact moment it was
              not, on the one tile a user checks to find out. */}
          {scan === null ? (
            <p className="text-[11px] text-slate-500">스캔 통계를 불러오는 중...</p>
          ) : scan.limit_reached ? (
            <p className="text-[11px] text-amber-400 flex items-center">
              <AlertTriangle className="w-3 h-3 mr-0.5 shrink-0" /> 10,000개 제한 도달 — 일부 파일 미탐색
            </p>
          ) : (
            <p className="text-[11px] text-emerald-400 flex items-center">
              <ArrowUpRight className="w-3 h-3 mr-0.5 shrink-0" /> 10K Limit Guard 정상 ({scan.total_size_mb} MB)
            </p>
          )}
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
          <p className="text-2xl font-bold text-white font-mono">
            {wikiCountLabel ?? '—'} <span className="text-xs text-slate-400 font-sans">개</span>
          </p>
          <p className="text-[11px] text-blue-400">Late Binding [[file_id:UUID]] 유지</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">누적 절감 시간</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-emerald-300 font-mono">
            {summary ? summary.saved_time_minutes : '—'}{' '}
            <span className="text-xs text-slate-400 font-sans">분</span>
          </p>
          <p className="text-[11px] text-emerald-400">
            딥링크 열람 {summary ? summary.deeplink_clicks_count : 0}회 · 200~250 WPM 기준
          </p>
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

        {files.length === 0 && (
          <p className="text-xs text-slate-400 py-4">
            아직 스캔된 문서가 없습니다. 파일 탐색기에서 스캔을 실행하세요.
          </p>
        )}

        <div className="divide-y divide-slate-800">
          {files.map((file) => (
            <div
              key={file.file_id}
              /* AC S2: the top-ranked documents are the highlight target. The row itself is
                 highlighted, not just the score chip — REQ-FUNC-012 asks for 상위 문서를 UI
                 상단에 하이라이트, and a chip colour keyed to an absolute threshold marks every
                 70-point file, which is not the same set. */
              className={`py-3 flex items-center justify-between ${
                topRanked.has(file.file_id) ? '-mx-2 px-2 rounded-lg bg-amber-950/30 ring-1 ring-amber-700/50' : ''
              }`}
            >
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
                  <p className="text-xs font-semibold text-slate-200">
                    {file.file_name}
                    {topRanked.has(file.file_id) && (
                      <span className="ml-2 align-middle text-[10px] bg-amber-900/60 text-amber-300 border border-amber-700/60 px-1.5 py-0.5 rounded">
                        핵심 문서
                      </span>
                    )}
                  </p>
                  <p className="text-[11px] text-slate-400 font-mono truncate max-w-lg">{file.current_path}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <span className="text-[11px] bg-slate-800 text-slate-300 px-2 py-1 rounded font-mono">
                  {(file.size_bytes / 1024).toFixed(1)} KB
                </span>
                <button
                  onClick={() => void handleOpenFile(file.file_id, file.file_name)}
                  className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded transition"
                >
                  파일 열기
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
