import React, { useState } from 'react';
import { FileDiff, Sparkles, Check, AlertCircle, RefreshCw, Undo2 } from 'lucide-react';
import * as api from '../api/client';
import { errorMessage } from '../api/client';
import type { RenameDiffItemRes } from '../api/types.gen';
import { useAppStore } from '../store/appStore';

/**
 * Only `pending` rows are applied. `PII_TOKEN_LEFT` / `PII_MASKING_FAILED` / `INVALID_FILENAME`
 * mean the backend excluded that file (DEC-17) — the UI must not offer a way to force them
 * through, because un-masking a suggested name is exactly what DEC-17 forbids.
 */
const APPLICABLE_STATUS = 'pending';

export const RenamePage: React.FC = () => {
  const { currentWorkspace, isReady, addToast, refreshFiles } = useAppStore();
  const [items, setItems] = useState<RenameDiffItemRes[]>([]);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [appliedHistoryId, setAppliedHistoryId] = useState<string | null>(null);

  const pendingCount = items.filter((item) => item.status === APPLICABLE_STATUS).length;
  const excludedCount = items.length - pendingCount;

  const handleGenerate = async () => {
    if (!currentWorkspace) {
      addToast('warning', '먼저 워크스페이스를 선택하세요.');
      return;
    }
    setIsGenerating(true);
    try {
      // POST, not GET: GET on the same path returns the persisted pending diff and is a known
      // 500 until issue #90 lands.
      const diff = await api.generateRenameDiff(currentWorkspace.workspace_id);
      setItems(diff.items);
      setHistoryId(diff.history_id ?? null);
      setAppliedHistoryId(null);
      addToast('success', `파일명 추천 ${diff.items.length}건을 생성했습니다.`);
    } catch (err) {
      addToast('error', errorMessage(err));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApplyAll = async () => {
    if (!currentWorkspace || !historyId) {
      addToast('warning', '적용할 추천 결과가 없습니다. 먼저 추천을 생성하세요.');
      return;
    }
    setIsApplying(true);
    try {
      // history_id rather than an items array: the server holds the path pairs (DEC-08), so the
      // client never sends a path and cannot rename a file outside the generated diff.
      const task = await api.applyRename(currentWorkspace.workspace_id, { history_id: historyId });
      const done = await api.pollTask(task.task_id);

      if (done.status === 'failed') {
        addToast('error', `일괄 변경이 실패했습니다 (${done.error_code ?? 'INTERNAL_ERROR'}).`);
        return;
      }

      // DEC-16: a partial batch is 207 + failed[], never a plain success. The per-file detail
      // lives in result_json, which the progress row deliberately does not carry (DEC-04).
      const result = await api.getTaskResult(task.task_id);
      const failed = (result.result?.failed as unknown[] | undefined) ?? [];
      if (done.status === 'multi_status' || failed.length > 0) {
        addToast('warning', `일부 파일(${failed.length}건)의 변경이 실패했습니다. 나머지는 적용되었습니다.`);
      } else {
        addToast('success', '대기 중인 파일명 일괄 변경이 적용되었습니다.');
      }

      setAppliedHistoryId(historyId);
      await refreshFiles();
      // The diff is spent: its old_paths no longer exist on disk, so re-applying it would fail
      // every row. Regenerating is the only correct next step.
      setItems([]);
      setHistoryId(null);
    } catch (err) {
      addToast('error', errorMessage(err));
    } finally {
      setIsApplying(false);
    }
  };

  const handleUndo = async () => {
    if (!currentWorkspace || !appliedHistoryId) {
      return;
    }
    setIsApplying(true);
    try {
      const task = await api.undoRename(currentWorkspace.workspace_id, {
        history_id: appliedHistoryId,
      });
      const done = await api.pollTask(task.task_id);
      if (done.status === 'failed') {
        // ALREADY_UNDONE is the expected code for a second undo of the same batch.
        addToast('error', `되돌리기가 실패했습니다 (${done.error_code ?? 'INTERNAL_ERROR'}).`);
        return;
      }
      addToast('success', '파일명 변경을 되돌렸습니다.');
      setAppliedHistoryId(null);
      await refreshFiles();
    } catch (err) {
      addToast('error', errorMessage(err));
    } finally {
      setIsApplying(false);
    }
  };

  if (!isReady) {
    return <div className="p-6 text-xs text-slate-400">워크스페이스 정보를 불러오는 중입니다...</div>;
  }

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">파일명 일괄 추천 & Diff (RN-CMD-01)</h1>
          <p className="text-xs text-slate-400">
            LLM을 통한 파일명 일괄 변경 추천 결과를 확인하고 일괄 적용합니다. (DEC-17 PII 게이트 연동)
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {appliedHistoryId && (
            <button
              onClick={() => void handleUndo()}
              disabled={isApplying}
              className="flex items-center space-x-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-60 text-slate-200 text-xs font-semibold px-4 py-2 rounded-lg border border-slate-700 transition"
            >
              <Undo2 className="w-3.5 h-3.5" />
              <span>변경 되돌리기</span>
            </button>
          )}
          <button
            onClick={() => void handleGenerate()}
            disabled={isGenerating || isApplying || !currentWorkspace}
            className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? '추천 생성 중...' : '파일명 추천 생성'}</span>
          </button>
          <button
            onClick={() => void handleApplyAll()}
            disabled={isApplying || isGenerating || pendingCount === 0}
            className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-900 disabled:text-emerald-300/60 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg transition"
          >
            <Check className="w-3.5 h-3.5" />
            <span>{isApplying ? '적용 중...' : `안전 파일명 일괄 적용 (${pendingCount})`}</span>
          </button>
        </div>
      </div>

      {excludedCount > 0 && (
        <div className="flex items-start space-x-2 bg-rose-950/40 border border-rose-900/60 rounded-xl p-3 text-[11px] text-rose-200">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-rose-400" />
          <span>
            {excludedCount}건은 PII 또는 파일명 규칙 위반으로 일괄 적용 대상에서 제외되었습니다. 원본
            파일명이 유지되며 수동 확인이 필요합니다 (DEC-17).
          </span>
        </div>
      )}

      {/* Diff Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800 uppercase text-[10px] tracking-wider">
            <tr>
              <th className="p-3.5">기존 파일명</th>
              <th className="p-3.5">제안된 새로운 파일명</th>
              <th className="p-3.5">상태</th>
              <th className="p-3.5">비고 / PII 여부</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {items.map((item) => (
              <tr key={item.file_id} className="hover:bg-slate-800/40 transition">
                <td className="p-3.5 font-medium text-slate-300 font-mono">{item.old_name}</td>
                <td className="p-3.5 font-medium text-indigo-300 font-mono flex items-center space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>{item.new_name}</span>
                </td>
                <td className="p-3.5">
                  {item.status === APPLICABLE_STATUS ? (
                    <span className="inline-block bg-blue-950 text-blue-400 border border-blue-800/60 px-2 py-0.5 rounded text-[10px] font-mono">
                      Pending
                    </span>
                  ) : (
                    <span className="inline-block bg-rose-950 text-rose-300 border border-rose-800/60 px-2 py-0.5 rounded text-[10px] font-mono">
                      {item.status}
                    </span>
                  )}
                </td>
                <td className="p-3.5 text-slate-400">
                  {item.status === APPLICABLE_STATUS ? (
                    <span>{item.note}</span>
                  ) : (
                    <span className="text-rose-400 font-medium flex items-center space-x-1">
                      <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                      <span>{item.note}</span>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {items.length === 0 && (
          <p className="p-4 text-xs text-slate-400 flex items-center space-x-2">
            <FileDiff className="w-3.5 h-3.5 text-slate-500" />
            <span>추천 결과가 없습니다. '파일명 추천 생성'을 실행하세요.</span>
          </p>
        )}
      </div>
    </div>
  );
};
