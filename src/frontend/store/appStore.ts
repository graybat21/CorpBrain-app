import { create } from 'zustand';

export interface ToastMessage {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export interface WorkspaceItem {
  workspace_id: string;
  workspace_name: string;
  root_path: string;
}

export interface FileItem {
  file_id: string;
  file_name: string;
  extension: string;
  importance_score: number;
  current_path: string;
  size_bytes: number;
}

interface AppState {
  activeTab: 'dashboard' | 'files' | 'wiki' | 'rename' | 'settings';
  setActiveTab: (tab: 'dashboard' | 'files' | 'wiki' | 'rename' | 'settings') => void;

  workspaces: WorkspaceItem[];
  currentWorkspace: WorkspaceItem | null;
  setWorkspaces: (ws: WorkspaceItem[]) => void;
  setCurrentWorkspace: (ws: WorkspaceItem | null) => void;

  files: FileItem[];
  setFiles: (files: FileItem[]) => void;

  toasts: ToastMessage[];
  addToast: (type: 'info' | 'success' | 'warning' | 'error', message: string) => void;
  removeToast: (id: string) => void;

  llmMode: 'Option A' | 'Option B';
  setLlmMode: (mode: 'Option A' | 'Option B') => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),

  workspaces: [
    {
      workspace_id: 'ws-demo-001',
      workspace_name: '2026_전략기획_워크스페이스',
      root_path: 'C:\\CorpBrain\\Workspace',
    },
  ],
  currentWorkspace: {
    workspace_id: 'ws-demo-001',
    workspace_name: '2026_전략기획_워크스페이스',
    root_path: 'C:\\CorpBrain\\Workspace',
  },
  setWorkspaces: (workspaces) => set({ workspaces }),
  setCurrentWorkspace: (currentWorkspace) => set({ currentWorkspace }),

  files: [
    {
      file_id: 'f1-uuid-111',
      file_name: '2026년_사업기획서_최종.docx',
      extension: '.docx',
      importance_score: 80,
      current_path: 'C:\\CorpBrain\\Workspace\\2026년_사업기획서_최종.docx',
      size_bytes: 35840,
    },
    {
      file_id: 'f2-uuid-222',
      file_name: '홍길동_주민등록증_900101-1234567.pdf',
      extension: '.pdf',
      importance_score: 45,
      current_path: 'C:\\CorpBrain\\Workspace\\홍길동_주민등록증_900101-1234567.pdf',
      size_bytes: 124000,
    },
    {
      file_id: 'f3-uuid-333',
      file_name: '임시_아이디어_노트.txt',
      extension: '.txt',
      importance_score: 10,
      current_path: 'C:\\CorpBrain\\Workspace\\임시_아이디어_노트.txt',
      size_bytes: 2048,
    },
  ],
  setFiles: (files) => set({ files }),

  toasts: [],
  addToast: (type, message) => {
    const id = Math.random().toString(36).substring(2, 9);
    set((state) => ({ toasts: [...state.toasts, { id, type, message }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  llmMode: 'Option A',
  setLlmMode: (llmMode) => set({ llmMode }),
}));
