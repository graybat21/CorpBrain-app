import React from 'react';
import { FileDiff, Sparkles, Check, AlertCircle } from 'lucide-react';
import { useAppStore } from '../store/appStore';

export const RenamePage: React.FC = () => {
  const { files, addToast } = useAppStore();

  const mockDiffList = [
    {
      oldName: '2026년_사업기획서_최종.docx',
      newName: '2026-08_2026년_사업기획서_최종.docx',
      status: 'pending',
      note: '추천 완료 (규칙 적용)',
    },
    {
      oldName: '임시_아이디어_노트.txt',
      newName: '2026-08_임시_아이디어_노트.txt',
      status: 'pending',
      note: '추천 완료 (규칙 적용)',
    },
    {
      oldName: '홍길동_주민등록증_900101-1234567.pdf',
      newName: '홍길동_주민등록증_900101-1234567.pdf',
      status: 'PII_TOKEN_LEFT',
      note: 'PII 포함 — 수동 확인 필요 (DEC-17)',
    },
  ];

  const handleApplyAll = () => {
    addToast('success', '대기 중인 파일명 일괄 변경(Rename Diff)이 적용되었습니다.');
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">파일명 일괄 추천 & Diff (RN-CMD-01)</h1>
          <p className="text-xs text-slate-400">
            LLM을 통한 파일명 일괄 변경 추천 결과를 확인하고 일괄 적용합니다. (DEC-17 PII 게이트 연동)
          </p>
        </div>

        <button
          onClick={handleApplyAll}
          className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg transition"
        >
          <Check className="w-3.5 h-3.5" />
          <span>안전 파일명 일괄 적용</span>
        </button>
      </div>

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
            {mockDiffList.map((item, idx) => (
              <tr key={idx} className="hover:bg-slate-800/40 transition">
                <td className="p-3.5 font-medium text-slate-300 font-mono">{item.oldName}</td>
                <td className="p-3.5 font-medium text-indigo-300 font-mono flex items-center space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>{item.newName}</span>
                </td>
                <td className="p-3.5">
                  {item.status === 'pending' ? (
                    <span className="inline-block bg-blue-950 text-blue-400 border border-blue-800/60 px-2 py-0.5 rounded text-[10px] font-mono">
                      Pending
                    </span>
                  ) : (
                    <span className="inline-block bg-rose-950 text-rose-300 border border-rose-800/60 px-2 py-0.5 rounded text-[10px] font-mono">
                      Rejected
                    </span>
                  )}
                </td>
                <td className="p-3.5 text-slate-400">
                  {item.status === 'PII_TOKEN_LEFT' ? (
                    <span className="text-rose-400 font-medium flex items-center space-x-1">
                      <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                      <span>{item.note}</span>
                    </span>
                  ) : (
                    <span>{item.note}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
