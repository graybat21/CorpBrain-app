import React, { useEffect, useState } from 'react';
import { BookOpen, ExternalLink, Link2, FileCheck, Loader2, AlertCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import * as api from '../api/client';
import { errorMessage } from '../api/client';
import { useAppStore } from '../store/appStore';
import type { WikiTabRes } from '../api/types.gen';

export const WikiPage: React.FC = () => {
  const { currentWorkspace, addToast } = useAppStore();
  const [tabs, setTabs] = useState<WikiTabRes[]>([]);
  const [selectedTab, setSelectedTab] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!currentWorkspace) {
      setTabs([]);
      setSelectedTab(null);
      return;
    }

    const fetchWiki = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.getWorkspaceWiki(currentWorkspace.workspace_id);
        setTabs(result.tabs);
        if (result.tabs.length > 0 && !selectedTab) {
          setSelectedTab(result.tabs[0].folder_1depth);
        }
      } catch (err) {
        const msg = errorMessage(err);
        setError(msg);
        addToast('error', `위키 로드 실패: ${msg}`);
      } finally {
        setLoading(false);
      }
    };

    void fetchWiki();
  }, [currentWorkspace, selectedTab, addToast]);

  /**
   * DL-FE-02: resolve and open through the backend.
   *
   * The path is never sent or displayed — DEC-08 resolves `file_id` server-side. A missing row
   * or a file gone from disk comes back as an error code, which is what a broken link is.
   */
  const handleAnchorClick = async (fileId: string) => {
    if (!currentWorkspace) {
      addToast('warning', '워크스페이스를 먼저 선택하세요.');
      return;
    }
    try {
      await api.openDeepLink(currentWorkspace.workspace_id, { file_id: fileId });
      await api.logAnalyticsEvent(currentWorkspace.workspace_id, {
        event_type: 'deeplink_click',
        file_id: fileId,
      });
    } catch (err) {
      addToast('warning', `링크를 열 수 없습니다: ${errorMessage(err)}`);
    }
  };

  const currentTabData = tabs.find((t) => t.folder_1depth === selectedTab);

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">
            딥링크 위키 (Late Binding Wiki)
          </h1>
          <p className="text-xs text-slate-400">
            1-Depth 폴더별 독립 탭 렌더링 (ANA-FE-02 / DEC-08 규약 준수)
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-blue-950/80 border border-blue-800/60 px-3 py-1.5 rounded-lg text-xs text-blue-300 font-mono">
          <Link2 className="w-3.5 h-3.5 text-blue-400" />
          <span>Late Binding: [[file_id:UUID]]</span>
        </div>
      </div>

      {/* Folder Tabs (AC S1) */}
      {tabs.length > 0 && (
        <div className="flex space-x-2 border-b border-slate-700 pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.folder_1depth}
              onClick={() => setSelectedTab(tab.folder_1depth)}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium transition ${
                selectedTab === tab.folder_1depth
                  ? 'bg-slate-800 text-white border-b-2 border-indigo-500'
                  : 'bg-slate-900/50 text-slate-400 hover:bg-slate-800/70 hover:text-slate-300'
              }`}
            >
              {tab.folder_1depth}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center h-64 space-x-2 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>위키 로딩 중...</span>
        </div>
      )}

      {error && !loading && (
        <div className="flex items-center justify-center h-64 space-x-2 text-red-400 bg-red-950/20 border border-red-800/40 rounded-lg p-6">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && tabs.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 space-y-3 text-slate-400">
          <BookOpen className="w-12 h-12 text-slate-600" />
          <p className="text-sm">생성된 위키가 없습니다.</p>
          <p className="text-xs text-slate-500">
            먼저 워크스페이스를 스캔하고 심층 분석을 실행하세요.
          </p>
        </div>
      )}

      {!loading && !error && currentTabData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Markdown Content Area (AC S2) */}
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
                                onClick={() => void handleAnchorClick(fid)}
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
              {currentTabData.markdown_content}
            </ReactMarkdown>
          </div>

          {/* Wiki Metadata Info Panel */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4 h-fit">
            <div className="flex items-center space-x-2 text-slate-200 font-semibold text-xs border-b border-slate-800 pb-3">
              <BookOpen className="w-4 h-4 text-indigo-400" />
              <span>위키 메타데이터</span>
            </div>

            <div className="space-y-3 text-xs">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 uppercase font-mono">Folder</span>
                <p className="font-mono text-indigo-400">{currentTabData.folder_1depth}</p>
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 uppercase font-mono">Wiki ID</span>
                <p className="font-mono text-slate-300 text-[10px] truncate">
                  {currentTabData.wiki_id}
                </p>
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 uppercase font-mono">
                  Last Updated
                </span>
                <p className="text-[11px] text-slate-300">
                  {new Date(currentTabData.updated_at).toLocaleString('ko-KR')}
                </p>
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1">
                <span className="text-[10px] text-slate-400 uppercase font-mono">
                  Anchor Format
                </span>
                <p className="font-mono text-indigo-400 text-[10px]">[[file_id:UUID]]</p>
                <p className="text-[11px] text-slate-400 mt-1">
                  위키 본문에는 절대 경로 문자열이 저장되지 않으므로 파일 이동/이름 변경 시 링크가
                  깨지지 않습니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
