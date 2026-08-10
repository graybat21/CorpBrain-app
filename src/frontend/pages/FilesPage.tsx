import React, { useEffect, useState } from 'react';
import { Search, RefreshCw, FileText, Filter, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import * as api from '../api/client';
import { errorMessage } from '../api/client';
import type { TaskProgressRes } from '../api/types.gen';
import { useAppStore } from '../store/appStore';

/** Parse status as File_Meta records it. Anything unrecognised falls through to a neutral badge. */
const PARSE_STATUS_BADGES: Record<string, { label: string; className: string; icon: 'ok' | 'wait' | 'warn' }> = {
  parsed: {
    label: 'Parsed',
    className: 'bg-emerald-950 text-emerald-400 border-emerald-800/60',
    icon: 'ok',
  },
  pending: {
    label: 'Pending',
    className: 'bg-slate-800 text-slate-400 border-slate-700',
    icon: 'wait',
  },
  failed: {
    label: 'Failed',
    className: 'bg-rose-950 text-rose-300 border-rose-800/60',
    icon: 'warn',
  },
};

const ParseStatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const badge = PARSE_STATUS_BADGES[status] ?? {
    label: status,
    className: 'bg-slate-800 text-slate-400 border-slate-700',
    icon: 'wait' as const,
  };
  const Icon = badge.icon === 'ok' ? CheckCircle2 : badge.icon === 'warn' ? AlertTriangle : Clock;
  return (
    <span
      className={`inline-flex items-center space-x-1 border px-2 py-0.5 rounded text-[10px] ${badge.className}`}
    >
      <Icon className="w-3 h-3 mr-1" /> {badge.label}
    </span>
  );
};

export const FilesPage: React.FC = () => {
  const { files, currentWorkspace, isReady, addToast, refreshFiles } = useAppStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [progress, setProgress] = useState<TaskProgressRes | null>(null);

  /**
   * Search narrows the list without reordering it (issue #4).
   *
   * `filter` is order-preserving, so the importance ranking the backend returns
   * (`ORDER BY importance_score DESC` — REQ-FUNC-012) survives the search. Re-sorting here
   * would create a second source of truth for the ranking; see FileRepository for why the
   * ordering belongs in the query.
   */
  const filteredFiles = files.filter((f) =>
    f.file_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  /**
   * Windowing: render a slice, grow it as the user scrolls (issue #4).
   *
   * The constraint is "1,000건 리스트 가상 스크롤". Implemented with a scroll handler over a
   * fixed-height container instead of `react-window`/`react-virtuoso` — CLAUDE.md §4 forbids
   * adding a dependency without documented justification, and a new runtime package would also
   * enter the PyInstaller-embedded bundle (DEC-01). ~40 lines of state covers the actual
   * requirement: keep the DOM node count bounded so 1,000 rows do not mount at once.
   *
   * Incremental growth rather than a true fixed window: rows here have variable height
   * (filename wrapping), and absolute positioning by index would misplace them. Appending keeps
   * the initial mount cheap — which is what the 1,000-row constraint is about — without
   * pretending to a precision this table cannot deliver.
   */
  const VISIBLE_STEP = 100;
  const [visibleCount, setVisibleCount] = useState(VISIBLE_STEP);

  // Reset the window whenever the list identity changes, or a narrowed search would keep
  // scrolling from a stale offset and appear to have fewer results than it does.
  useEffect(() => {
    setVisibleCount(VISIBLE_STEP);
  }, [searchTerm, files]);

  const visibleFiles = filteredFiles.slice(0, visibleCount);
  const hasMore = visibleCount < filteredFiles.length;

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (!hasMore) {
      return;
    }
    const { scrollTop, clientHeight, scrollHeight } = e.currentTarget;
    // 200px of runway so the next slice is mounted before the user reaches the end.
    if (scrollHeight - scrollTop - clientHeight < 200) {
      setVisibleCount((n) => n + VISIBLE_STEP);
    }
  };

  /**
   * Scan, then fast-analyse, polling each task to a terminal state (DEC-04).
   *
   * Sequential rather than concurrent: fast analysis scores the rows the scan writes, so
   * starting both at once would score whatever happened to be committed already.
   */
  const handleRunScan = async () => {
    if (!currentWorkspace) {
      addToast('warning', '먼저 워크스페이스를 선택하세요.');
      return;
    }
    const workspaceId = currentWorkspace.workspace_id;
    setIsScanning(true);
    setProgress(null);
    try {
      addToast('info', '워크스페이스 파일 스캔을 시작합니다...');
      const scanTask = await api.startScan(workspaceId);
      const scanDone = await api.pollTask(scanTask.task_id, { onProgress: setProgress });
      if (scanDone.status === 'failed') {
        // DEC-03: the code, not a stack trace.
        addToast('error', `스캔이 실패했습니다 (${scanDone.error_code ?? 'INTERNAL_ERROR'}).`);
        return;
      }
      const scanTruncated =
        scanDone.status === 'multi_status' && scanDone.error_code === 'SCAN_LIMIT_REACHED';
      if (scanTruncated) {
        // SCAN-CMD-02 / issue #64: the walk stopped at 10,000 files. The scan succeeded, so
        // this is a 207 partial result and the flow continues — but it must be said out loud.
        // Falling through to the success toast would report "완료" over a workspace that is
        // missing files, and the user would trust an index they cannot see the edge of.
        //
        // A Toast rather than the AC's "에러 다이얼로그": CLAUDE.md §6 mandates non-blocking
        // Toasts for polling outcomes, and this is not an error — the indexed files are usable.
        addToast(
          'warning',
          '파일이 너무 많아 10,000개까지만 탐색했습니다. 워크스페이스 폴더 범위를 좁혀 다시 스캔하세요.',
        );
      }
      // Files land in the DB at scan time, so show them before analysis starts.
      await refreshFiles();

      addToast('info', '중요도 고속 분석을 시작합니다...');
      const analysisTask = await api.startFastAnalysis(workspaceId);
      const analysisDone = await api.pollTask(analysisTask.task_id, { onProgress: setProgress });
      if (analysisDone.status === 'failed') {
        addToast('error', `분석이 실패했습니다 (${analysisDone.error_code ?? 'INTERNAL_ERROR'}).`);
        return;
      }
      await refreshFiles();

      if (analysisDone.status === 'multi_status') {
        // DEC-16: a partially failed batch must never read as a plain success.
        addToast('warning', '일부 파일의 분석이 실패했습니다. 재실행하면 실패한 파일만 처리됩니다.');
      } else if (scanTruncated) {
        // The analysis finished cleanly, but only over the truncated file set — so the closing
        // message must not be the word "완료" on its own (issue #64).
        addToast(
          'warning',
          `중요도 분석 완료 (${analysisDone.processed}건) — 단, 10,000개 제한으로 일부 파일은 탐색되지 않았습니다.`,
        );
      } else {
        addToast('success', `스캔 및 중요도 분석 완료 (${analysisDone.processed}건).`);
      }
    } catch (err) {
      addToast('error', errorMessage(err));
    } finally {
      setIsScanning(false);
      setProgress(null);
    }
  };

  const handleOpenFile = async (fileId: string, fileName: string) => {
    if (!currentWorkspace) {
      return;
    }
    try {
      // DEC-08: the server resolves current_path from file_id; the client never sends a path.
      await api.openDeepLink(currentWorkspace.workspace_id, { file_id: fileId });
    } catch (err) {
      addToast('error', `${fileName}: ${errorMessage(err)}`);
    }
  };

  if (!isReady) {
    return <div className="p-6 text-xs text-slate-400">파일 목록을 불러오는 중입니다...</div>;
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">파일 탐색기 & 중요도 관리</h1>
          <p className="text-xs text-slate-400">
            ScannerService(SCAN-CMD-01) 및 FastAnalysisEngine(ANA-CMD-01) 기반 탐색기입니다.
          </p>
        </div>

        <button
          onClick={() => void handleRunScan()}
          disabled={isScanning || !currentWorkspace}
          className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
          <span>{isScanning ? '스캔 중...' : '재스캔 및 분석 실행'}</span>
        </button>
      </div>

      {/* Task progress, from the 1s poll (DEC-04). Non-blocking, not a modal. */}
      {progress && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium">
              {progress.task_type === 'scan' ? '파일 스캔' : '중요도 고속 분석'} 진행 중
            </span>
            <span className="font-mono text-indigo-300">
              {progress.processed} / {progress.total} ({progress.percent.toFixed(1)}%)
            </span>
          </div>
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 transition-all"
              style={{ width: `${Math.min(100, progress.percent)}%` }}
            />
          </div>
          {progress.eta_sec !== null && progress.eta_sec !== undefined && (
            <p className="text-[11px] text-slate-400">예상 남은 시간 {progress.eta_sec}초</p>
          )}
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex items-center space-x-3 bg-slate-900/80 p-3 rounded-xl border border-slate-800">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="파일명 검색 (예: 기획서, pdf, 주민등록증)..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>
        <button className="flex items-center space-x-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-2 rounded-lg transition border border-slate-700/60">
          <Filter className="w-3.5 h-3.5" />
          <span>확장자 필터</span>
        </button>
      </div>

      {/* Files Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        {/* Fixed-height scroll container: what bounds the mounted row count (issue #4). */}
        <div className="max-h-[60vh] overflow-y-auto" onScroll={handleScroll}>
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800 uppercase text-[10px] tracking-wider">
            <tr>
              <th className="p-3.5">파일명</th>
              <th className="p-3.5">확장자</th>
              <th className="p-3.5">중요도 점수</th>
              <th className="p-3.5">파일 크기</th>
              <th className="p-3.5">파싱 상태</th>
              <th className="p-3.5 text-right">작업</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {visibleFiles.map((file) => (
              <tr key={file.file_id} className="hover:bg-slate-800/40 transition">
                <td className="p-3.5 font-medium text-slate-200">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span>{file.file_name}</span>
                  </div>
                </td>
                <td className="p-3.5 font-mono text-slate-400">{file.extension}</td>
                <td className="p-3.5">
                  <span
                    className={`inline-block px-2 py-0.5 rounded font-mono font-semibold ${
                      file.importance_score >= 70
                        ? 'bg-amber-950 text-amber-300 border border-amber-800/60'
                        : file.importance_score >= 40
                        ? 'bg-blue-950 text-blue-300 border border-blue-800/60'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {file.importance_score}점
                  </span>
                </td>
                <td className="p-3.5 font-mono text-slate-400">{(file.size_bytes / 1024).toFixed(1)} KB</td>
                <td className="p-3.5">
                  <ParseStatusBadge status={file.parse_status} />
                </td>
                <td className="p-3.5 text-right">
                  <button
                    onClick={() => void handleOpenFile(file.file_id, file.file_name)}
                    className="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded transition"
                  >
                    파일 열기
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {hasMore && (
          <p className="p-3 text-center text-[10px] text-slate-500 font-mono">
            {visibleFiles.length} / {filteredFiles.length} 건 표시 — 스크롤하면 더 불러옵니다
          </p>
        )}
        </div>

        {/* AC S2: an Empty State that carries its own run button (issue #4). The top-right
            button was previously expected to serve double duty, but the AC asks for the action
            where the user is looking — and "실행하세요" with no button to press is an
            instruction, not an affordance. The two branches are distinct: nothing scanned yet
            is a first-run state, while a search that matched nothing must not offer a rescan as
            though the workspace were empty. */}
        {filteredFiles.length === 0 && (
          <div className="p-6 flex flex-col items-center gap-3 text-center">
            {files.length === 0 ? (
              <>
                <FileText className="w-6 h-6 text-slate-600" />
                <p className="text-xs text-slate-400">
                  고속 분석을 실행하세요. 파일 중요도가 산출되면 높은 순으로 표시됩니다.
                </p>
                <button
                  onClick={() => void handleRunScan()}
                  disabled={isScanning || !currentWorkspace}
                  className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:text-indigo-200/60 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg transition"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                  <span>{isScanning ? '분석 중...' : '고속 분석 실행'}</span>
                </button>
                {!currentWorkspace && (
                  <p className="text-[10px] text-slate-500">먼저 워크스페이스를 선택하세요.</p>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-400">검색 조건에 맞는 파일이 없습니다.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
