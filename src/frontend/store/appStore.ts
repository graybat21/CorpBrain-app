import { create } from 'zustand';

import * as api from '../api/client';
import { errorMessage } from '../api/client';
import type { FileItemRes, WorkspaceItemRes } from '../api/types.gen';

export interface ToastMessage {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

/**
 * DEC-02 makes the OpenAPI schema the contract SSOT, so the workspace and file shapes are the
 * generated ones. The hand-written `WorkspaceItem`/`FileItem` pair that used to live here was
 * the drift issue #91 removes; re-adding a local shape re-adds the drift.
 */
export type WorkspaceItem = WorkspaceItemRes;
export type FileItem = FileItemRes;

export type LlmMode = 'Option A' | 'Option B';

export type ActiveTab = 'dashboard' | 'files' | 'wiki' | 'rename' | 'analytics' | 'settings';

interface AppState {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;

  workspaces: WorkspaceItem[];
  currentWorkspace: WorkspaceItem | null;
  setWorkspaces: (ws: WorkspaceItem[]) => void;
  setCurrentWorkspace: (ws: WorkspaceItem | null) => void;

  files: FileItem[];
  setFiles: (files: FileItem[]) => void;

  /**
   * `file_id`s of the fast-analysis top-ranked documents, most important first
   * (REQ-FUNC-012 / issue #1 AC S2).
   *
   * Held as the backend's list rather than recomputed from `files`: the cutoff (how many, and
   * whether an unanalysed score-0 file counts) is the backend's ranking definition, and a page
   * slicing `files.slice(0, 3)` itself would drift from it the moment the rule changes.
   */
  topRankedFileIds: string[];

  /** True while a backend read is in flight, so pages can distinguish "empty" from "not yet". */
  isLoading: boolean;
  /** False until the first bootstrap attempt settles, success or failure. */
  isReady: boolean;

  toasts: ToastMessage[];
  addToast: (type: ToastMessage['type'], message: string) => void;
  removeToast: (id: string) => void;

  llmMode: LlmMode;
  setLlmMode: (mode: LlmMode) => void;

  /** Load the workspace list and the selected workspace's files. Called once on mount. */
  bootstrap: () => Promise<void>;
  /** Re-read the current workspace's files, e.g. after a scan task completes. */
  refreshFiles: () => Promise<void>;
  selectWorkspace: (workspaceId: string) => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // No seeded workspace or file rows. Everything below comes from the backend; a mock row here
  // is indistinguishable from real data in the UI, which is how #91 went unnoticed.
  workspaces: [],
  currentWorkspace: null,
  setWorkspaces: (workspaces) => set({ workspaces }),
  setCurrentWorkspace: (currentWorkspace) => set({ currentWorkspace }),

  files: [],
  setFiles: (files) => set({ files }),
  topRankedFileIds: [],

  isLoading: false,
  isReady: false,

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

  bootstrap: async () => {
    set({ isLoading: true });
    try {
      const [workspaceList, llmConfig] = await Promise.all([
        api.listWorkspaces(),
        // Reflects the persisted mode, not a UI default — an engine change is a security
        // decision (DEC-16) and must not appear to have happened because a tab rendered.
        api.getLlmConfig(),
      ]);
      const workspaces = workspaceList.items;
      const current = workspaces[0] ?? null;
      set({
        workspaces,
        currentWorkspace: current,
        llmMode: llmConfig.mode === 'Option B' ? 'Option B' : 'Option A',
      });
      if (current) {
        const fileList = await api.listFiles(current.workspace_id);
        set({ files: fileList.items, topRankedFileIds: fileList.top_ranked_file_ids ?? [] });
      }
    } catch (err) {
      get().addToast('error', errorMessage(err));
    } finally {
      set({ isLoading: false, isReady: true });
    }
  },

  refreshFiles: async () => {
    const current = get().currentWorkspace;
    if (!current) {
      return;
    }
    set({ isLoading: true });
    try {
      const fileList = await api.listFiles(current.workspace_id);
      set({ files: fileList.items, topRankedFileIds: fileList.top_ranked_file_ids ?? [] });
    } catch (err) {
      get().addToast('error', errorMessage(err));
    } finally {
      set({ isLoading: false });
    }
  },

  selectWorkspace: async (workspaceId) => {
    const target = get().workspaces.find((ws) => ws.workspace_id === workspaceId);
    if (!target) {
      return;
    }
    // Clear the outgoing workspace's files first: rendering them under the new workspace's
    // name would attribute one workspace's documents to another.
    set({ currentWorkspace: target, files: [], topRankedFileIds: [] });
    await get().refreshFiles();
  },
}));
