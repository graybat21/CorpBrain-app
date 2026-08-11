import React, { useState } from 'react';
import { X, FolderPlus, AlertCircle, Loader2, FolderSearch } from 'lucide-react';
import * as api from '../api/client';
import { errorMessage } from '../api/client';
import { deriveWorkspaceName } from '../utils/pathName';

interface CreateWorkspaceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  onError: (message: string) => void;
}

/**
 * The pywebview shell bridge (issue #167). Present only when running inside CorpBrain.exe; a plain
 * browser (dev_serve) leaves `window.pywebview` undefined, and the modal falls back to manual entry.
 */
interface PywebviewBridge {
  api?: {
    select_folder?: () => Promise<string | null>;
  };
}
declare global {
  interface Window {
    pywebview?: PywebviewBridge;
  }
}

/** The native folder picker is only reachable inside the shell. */
function nativeFolderPickerAvailable(): boolean {
  return typeof window.pywebview?.api?.select_folder === 'function';
}

export const CreateWorkspaceModal: React.FC<CreateWorkspaceModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  onError,
}) => {
  const [workspaceName, setWorkspaceName] = useState('');
  const [rootPaths, setRootPaths] = useState<string[]>(['']);
  const [loading, setLoading] = useState(false);
  // Whether the user has typed a name themselves. Once true, folder selection stops overwriting it
  // — the folder-name default is a convenience, never a thing that clobbers a deliberate choice.
  const [nameEdited, setNameEdited] = useState(false);
  const hasNativePicker = nativeFolderPickerAvailable();

  const handleAddPath = () => {
    setRootPaths([...rootPaths, '']);
  };

  const handleRemovePath = (index: number) => {
    if (rootPaths.length > 1) {
      setRootPaths(rootPaths.filter((_, i) => i !== index));
    }
  };

  const handlePathChange = (index: number, value: string) => {
    const newPaths = [...rootPaths];
    newPaths[index] = value;
    setRootPaths(newPaths);
  };

  const handleNameChange = (value: string) => {
    setWorkspaceName(value);
    setNameEdited(true);
  };

  /**
   * Open the native folder picker (shell only) and drop the chosen path into row `index`. If the
   * user has not named the workspace yet, default the name to the selected folder (issue #167).
   */
  const handleBrowseFolder = async (index: number) => {
    if (!window.pywebview?.api?.select_folder) {
      return;
    }
    try {
      const selected = await window.pywebview.api.select_folder();
      if (!selected) {
        return; // cancelled
      }
      handlePathChange(index, selected);
      if (!nameEdited && !workspaceName.trim()) {
        setWorkspaceName(deriveWorkspaceName(selected));
      }
    } catch (err) {
      onError(`폴더 선택 실패: ${errorMessage(err)}`);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Client-side validation (AC: 2개 이상 폴더 선택)
    const validPaths = rootPaths.filter((p) => p.trim().length > 0);
    if (!workspaceName.trim()) {
      onError('워크스페이스 이름을 입력하세요.');
      return;
    }
    if (validPaths.length === 0) {
      onError('최소 1개 이상의 폴더 경로를 입력하세요.');
      return;
    }

    setLoading(true);
    try {
      await api.createWorkspace({
        workspace_name: workspaceName.trim(),
        root_paths: validPaths,
      });
      onSuccess();
      // Reset form
      setWorkspaceName('');
      setRootPaths(['']);
      setNameEdited(false);
      onClose();
    } catch (err) {
      onError(`워크스페이스 생성 실패: ${errorMessage(err)}`);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-950/50 p-2 rounded-lg border border-indigo-800/50">
              <FolderPlus className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">새 워크스페이스 생성</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                로컬 폴더를 병합하여 워크스페이스를 만듭니다 (WS-FE-02)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition p-1 rounded-lg hover:bg-slate-800"
            disabled={loading}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Workspace Name */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-200">워크스페이스 이름</label>
            <input
              type="text"
              value={workspaceName}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="예: 회사 문서 통합 (폴더 선택 시 폴더명으로 자동 입력)"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition"
              disabled={loading}
              required
            />
          </div>

          {/* Root Paths */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-slate-200">폴더 경로</label>
              <button
                type="button"
                onClick={handleAddPath}
                className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                disabled={loading}
              >
                + 경로 추가
              </button>
            </div>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {rootPaths.map((path, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={path}
                    onChange={(e) => handlePathChange(index, e.target.value)}
                    placeholder={`C:\\Users\\Documents\\Folder${index + 1}`}
                    className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition font-mono"
                    disabled={loading}
                  />
                  {hasNativePicker && (
                    <button
                      type="button"
                      onClick={() => handleBrowseFolder(index)}
                      className="shrink-0 flex items-center space-x-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg px-3 py-2.5 text-sm transition"
                      disabled={loading}
                      title="폴더 찾아보기"
                    >
                      <FolderSearch className="w-4 h-4 text-indigo-400" />
                      <span>폴더 찾기</span>
                    </button>
                  )}
                  {rootPaths.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemovePath(index)}
                      className="text-slate-400 hover:text-red-400 transition p-2"
                      disabled={loading}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>

            {/* Folder-picker note — differs by whether the native picker is available. */}
            <div className="flex items-start space-x-2 bg-blue-950/20 border border-blue-800/40 rounded-lg p-3 mt-3">
              <AlertCircle className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              {hasNativePicker ? (
                <p className="text-xs text-blue-300">
                  <strong>안내:</strong> <strong>폴더 찾기</strong> 로 폴더를 선택하면 경로가 채워지고,
                  이름을 아직 입력하지 않았으면 폴더명이 워크스페이스 이름으로 자동 입력됩니다. 경로를
                  직접 입력하거나 붙여넣어도 됩니다.
                </p>
              ) : (
                <p className="text-xs text-blue-300">
                  <strong>개발 노트:</strong> 네이티브 폴더 선택기는 <strong>CorpBrain.exe</strong> 셸에서
                  동작합니다(브라우저 개발 모드에서는 표시되지 않음). 여기서는 경로를 직접 입력하세요.
                </p>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition"
              disabled={loading}
            >
              취소
            </button>
            <button
              type="submit"
              className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>생성 중...</span>
                </>
              ) : (
                <>
                  <FolderPlus className="w-4 h-4" />
                  <span>생성</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
