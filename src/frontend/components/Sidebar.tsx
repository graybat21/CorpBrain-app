import React, { useState } from 'react';
import {
  LayoutDashboard,
  FolderTree,
  BookOpen,
  FileDiff,
  ShieldAlert,
  FolderPlus,
  Check,
  HardDrive
} from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { CreateWorkspaceModal } from './CreateWorkspaceModal';

export const Sidebar: React.FC = () => {
  const { activeTab, setActiveTab, currentWorkspace, workspaces, selectWorkspace, addToast, bootstrap } =
    useAppStore();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const navItems = [
    { id: 'dashboard', label: '대시보드 (Analytics)', icon: LayoutDashboard },
    { id: 'files', label: '파일 탐색 & 중요도', icon: FolderTree },
    { id: 'wiki', label: '딥링크 위키 (Late Binding)', icon: BookOpen },
    { id: 'rename', label: '파일명 일괄 추천 (Diff)', icon: FileDiff },
    { id: 'settings', label: '보안 & LLM 설정', icon: ShieldAlert },
  ] as const;

  return (
    <aside className="w-64 bg-slate-900/95 border-r border-slate-800 flex flex-col justify-between select-none">
      <div>
        {/* Workspace Selector */}
        <div className="p-3.5 border-b border-slate-800">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5 flex items-center justify-between">
            <span>현재 워크스페이스</span>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="hover:text-indigo-400 p-0.5 transition"
              title="워크스페이스 추가"
            >
              <FolderPlus className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* WS-FE-01: the real workspace list. Clicking one reloads that workspace's files. */}
          {workspaces.length === 0 ? (
            <div className="bg-slate-800/60 border border-slate-700/70 rounded-lg p-2.5 text-[11px] text-slate-400">
              등록된 워크스페이스가 없습니다.
            </div>
          ) : (
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {workspaces.map((ws) => {
                const isCurrent = ws.workspace_id === currentWorkspace?.workspace_id;
                return (
                  <button
                    key={ws.workspace_id}
                    onClick={() => void selectWorkspace(ws.workspace_id)}
                    className={`w-full text-left rounded-lg p-2.5 flex items-center justify-between transition border ${
                      isCurrent
                        ? 'bg-slate-800/90 border-indigo-500/60'
                        : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center space-x-2 overflow-hidden">
                      <HardDrive
                        className={`w-4 h-4 shrink-0 ${isCurrent ? 'text-indigo-400' : 'text-slate-500'}`}
                      />
                      <div className="truncate">
                        <p className="text-xs font-medium text-slate-200 truncate">
                          {ws.workspace_name}
                        </p>
                        {/* Issue #105: a workspace merges several folders. Showing only
                            root_paths[0] would repeat the bug this issue fixed at the UI
                            layer — the user could not tell a 1-folder workspace from a
                            3-folder one. The full list is in the tooltip; the line stays
                            one row tall so the sidebar item height is unchanged. */}
                        <p
                          className="text-[10px] text-slate-400 font-mono truncate"
                          title={ws.root_paths.join('\n')}
                        >
                          {ws.root_paths[0] ?? '(폴더 없음)'}
                          {ws.root_paths.length > 1 && (
                            <span className="text-slate-500"> +{ws.root_paths.length - 1}</span>
                          )}
                        </p>
                      </div>
                    </div>
                    {isCurrent && <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Navigation Menu */}
        <nav className="p-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-xs font-medium transition ${
                  isActive
                    ? 'bg-indigo-600/90 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* System Status Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/40 text-[11px] text-slate-400 space-y-1">
        <div className="flex justify-between items-center">
          <span>PIIFilter 게이트:</span>
          <span className="text-emerald-400 font-mono">Fail-Closed ON</span>
        </div>
        <div className="flex justify-between items-center">
          <span>로컬 로그 보관:</span>
          <span className="text-slate-300 font-mono">Max 7일 / 10MB</span>
        </div>
      </div>

      {/* Create Workspace Modal (WS-FE-02 / Issue #63) */}
      <CreateWorkspaceModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={() => {
          addToast('success', '워크스페이스가 생성되었습니다.');
          void bootstrap(); // Reload workspace list
        }}
        onError={(msg) => addToast('error', msg)}
      />
    </aside>
  );
};
