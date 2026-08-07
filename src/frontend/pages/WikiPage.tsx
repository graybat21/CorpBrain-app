import React from 'react';
import { BookOpen, ExternalLink, Link2, FileCheck } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAppStore } from '../store/appStore';

export const WikiPage: React.FC = () => {
  const { files, addToast } = useAppStore();
  const sampleFileId = files[0]?.file_id || 'f1-uuid-111';

  const wikiContent = `
# 2026년 기업 지능화 사업기획 종합 분석 보고서

## 1. 개요 및 사업 방향
본 문서에는 2026년 상반기 전략 기획 내용이 수록되어 있습니다.
관련 세부 마스터 플랜 문서 출처는 다음과 같습니다:

- 핵심 사업기획 마스터 플랜: [[file_id:${sampleFileId}]]

## 2. 보안 및 개인정보 관리 수칙
- 모든 로컬 파일 스캔 시 PII 마스킹 방어막이 작동합니다.
- 절대 경로는 위키에 직접 저장되지 않으며, **Late Binding (DL-CMD-01 / DEC-08)** 앵커를 통해서만 참조됩니다.

> [!NOTE]
> 위 [[file_id:${sampleFileId}]] 앵커 링크를 클릭하면 SQLite 메타 DB에서 실시간으로 역추적된 최신 파일 경로가 해석됩니다.
`;

  const handleAnchorClick = (fileId: string) => {
    const targetFile = files.find((f) => f.file_id === fileId);
    if (targetFile) {
      addToast(
        'success',
        `Late Binding 해석 성공! [[file_id:${fileId}]] -> ${targetFile.current_path}`
      );
    } else {
      addToast('warning', `해당 file_id (${fileId})의 로컬 경로를 찾을 수 없습니다.`);
    }
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">딥링크 위키 (Late Binding Wiki)</h1>
          <p className="text-xs text-slate-400">
            react-markdown 기반 위키 렌더링 엔진입니다. (DL-CMD-01 / DEC-08 규약 준수)
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-blue-950/80 border border-blue-800/60 px-3 py-1.5 rounded-lg text-xs text-blue-300 font-mono">
          <Link2 className="w-3.5 h-3.5 text-blue-400" />
          <span>Late Binding: [[file_id:UUID]]</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Markdown Content Area */}
        <div className="lg:col-span-2 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-2xl text-slate-200 text-sm leading-relaxed prose prose-invert max-w-none">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => {
                const text = String(children);
                if (text.includes('[[file_id:')) {
                  const parts = text.split(/(\[\[file_id:[0-9a-zA-F\-]+\]\])/);
                  return (
                    <p>
                      {parts.map((part, idx) => {
                        const match = part.match(/\[\[file_id:([0-9a-zA-F\-]+)\]\]/);
                        if (match) {
                          const fid = match[1];
                          return (
                            <button
                              key={idx}
                              onClick={() => handleAnchorClick(fid)}
                              className="inline-flex items-center space-x-1 bg-indigo-950 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/60 px-2 py-0.5 rounded font-mono text-xs transition mx-1"
                            >
                              <FileCheck className="w-3 h-3 text-indigo-400" />
                              <span>[[file_id:{fid.substring(0, 8)}...]]</span>
                              <ExternalLink className="w-2.5 h-2.5 ml-0.5 text-indigo-400" />
                            </button>
                          );
                        }
                        return part;
                      })}
                    </p>
                  );
                }
                return <p>{children}</p>;
              },
            }}
          >
            {wikiContent}
          </ReactMarkdown>
        </div>

        {/* DeepLink Mappings Info Panel */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4 h-fit">
          <div className="flex items-center space-x-2 text-slate-200 font-semibold text-xs border-b border-slate-800 pb-3">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            <span>딥링크 앵커 매핑 현황 (DEC-08)</span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
              <span className="text-[10px] text-slate-400 uppercase font-mono">Anchor Format</span>
              <p className="font-mono text-indigo-400">[[file_id:UUID]]</p>
              <p className="text-[11px] text-slate-400 mt-1">
                위키 본문에는 절대 경로 문자열이 저장되지 않으므로 파일 이동/이름 변경 시 링크가 깨지지 않습니다.
              </p>
            </div>

            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
              <span className="text-[10px] text-slate-400 uppercase font-mono">연결된 로컬 파일</span>
              {files.slice(0, 2).map((f) => (
                <div key={f.file_id} className="text-[11px] font-mono text-slate-300 truncate">
                  • {f.file_name}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
