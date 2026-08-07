import React from 'react';
import { Info, CheckCircle2, AlertTriangle, AlertCircle, X } from 'lucide-react';
import { useAppStore } from '../store/appStore';

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useAppStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col space-y-2 max-w-sm pointer-events-none">
      {toasts.map((toast) => {
        const icons = {
          info: <Info className="w-4 h-4 text-blue-400 shrink-0" />,
          success: <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />,
          warning: <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />,
          error: <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />,
        };

        const bgBorders = {
          info: 'bg-slate-900/95 border-blue-500/40 text-blue-100',
          success: 'bg-slate-900/95 border-emerald-500/40 text-emerald-100',
          warning: 'bg-slate-900/95 border-amber-500/40 text-amber-100',
          error: 'bg-slate-900/95 border-rose-500/40 text-rose-100',
        };

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start space-x-3 p-3 rounded-lg border shadow-xl backdrop-blur-md transition-all duration-300 transform translate-y-0 text-xs ${
              bgBorders[toast.type]
            }`}
          >
            {icons[toast.type]}
            <p className="flex-1 font-medium leading-relaxed">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-slate-400 hover:text-slate-200 transition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
