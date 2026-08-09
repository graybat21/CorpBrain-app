import React, { useCallback, useEffect, useState } from 'react';
import { BookOpen, Link2, Loader2, AlertCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import * as api from '../api/client';
import { errorMessage } from '../api/client';
import { extractFileIds, remarkDeepLink } from '../api/remarkDeepLink';
import { DeepLinkBadge } from '../components/DeepLinkBadge';
import { useAppStore } from '../store/appStore';
import type { WikiTabRes } from '../api/types.gen';

export const WikiPage: React.FC = () => {
  const { currentWorkspace, addToast } = useAppStore();
  const [tabs, setTabs] = useState<WikiTabRes[]>([]);
  const [selectedTab, setSelectedTab] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /**
   * file_id -> is_broken, from DL-QRY-01 (AC S2, issue #19).
   *
   * Absent means "not probed yet", which renders as a neutral badge rather than as broken — a
   * link shown grey before its status is known would accuse a perfectly good file.
   */
  const [brokenById, setBrokenById] = useState<Record<string, boolean>>({});

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
   * Probe every anchor in the visible tab (DL-QRY-01 / AC S2).
   *
   * Per-tab rather than for the whole workspace: only the rendered tab's badges can be seen, and
   * a workspace-wide sweep would issue a request per anchor across every folder on first load.
   * `Promise.allSettled` because one unreachable probe must not blank out the rest — an
   * unresolved id simply stays neutral.
   */
  const probeAnchors = useCallback(
    async (workspaceId: string, markdown: string) => {
      const ids = extractFileIds(markdown);
      if (ids.length === 0) {
        return;
      }
      const settled = await Promise.allSettled(
        ids.map((id) => api.getDeepLinkStatus(workspaceId, id)),
      );
      const next: Record<string, boolean> = {};
      settled.forEach((outcome, index) => {
        if (outcome.status === 'fulfilled') {
          next[ids[index]] = outcome.value.is_broken;
        }
      });
      setBrokenById((prev) => ({ ...prev, ...next }));
    },
    [],
  );

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
    if (brokenById[fileId] === true) {
      // REQ-FUNC-022: a broken link answers with a Toast rather than a failed open. The badge is
      // deliberately still clickable so this feedback is reachable at all.
      addToast('warning', '원본 파일을 찾을 수 없습니다. 파일이 이동되었거나 삭제되었습니다.');
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
      // The open failed, so re-probe: the most likely cause is that the file has just gone
      // missing, and the badge should go grey rather than stay inviting.
      void probeAnchors(currentWorkspace.workspace_id, `[[file_id:${fileId}]]`);
    }
  };

  const currentTabData = tabs.find((t) => t.folder_1depth === selectedTab);

  // Probe the visible tab's anchors once its content is available (AC S2).
  useEffect(() => {
    if (currentWorkspace && currentTabData) {
      void probeAnchors(currentWorkspace.workspace_id, currentTabData.markdown_content);
    }
  }, [currentWorkspace, currentTabData, probeAnchors]);

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
              remarkPlugins={[remarkGfm, remarkDeepLink]}
              components={{
                /* The plugin emits `corpbrain-deeplink` nodes wherever an anchor appears —
                   paragraphs, list items, table cells, headings. The previous implementation
                   overrode `p` and called String(children), which stringified sibling elements
                   to "[object Object]" and never looked outside a paragraph at all. */
                'corpbrain-deeplink': ({ node }: any) => {
                  const fileId = String(node?.properties?.fileid ?? '');
                  if (!fileId) {
                    return null;
                  }
                  return (
                    <DeepLinkBadge
                      fileId={fileId}
                      isBroken={fileId in brokenById ? brokenById[fileId] : null}
                      onOpen={(id) => void handleAnchorClick(id)}
                    />
                  );
                },
              } as any}
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
