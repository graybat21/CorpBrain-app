import React from 'react';
import { ShieldCheck, Cpu, Minus, Square, X } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { WatcherControl } from './WatcherControl';

export const TitleBar: React.FC = () => {
  const llmMode = useAppStore((state) => state.llmMode);

  return (
    <div className="h-10 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-3 select-none pywebview-drag-region text-xs">
      <div className="flex items-center space-x-2.5">
        <div className="w-5 h-5 rounded-md bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center font-bold text-white shadow-sm">
          C
        </div>
        <span className="font-semibold tracking-wide text-slate-200">CorpBrain</span>
        <span className="text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-800/60 px-1.5 py-0.5 rounded font-mono">
          v1.0 MVP
        </span>
      </div>

      <div className="flex items-center space-x-3 pywebview-no-drag">
        {/* AC S2 (#56): the queue badge sits beside the watcher icon in the header, which is
            where it is visible regardless of which page is open. */}
        <WatcherControl />

        <div className="flex items-center space-x-1.5 bg-slate-800/80 px-2 py-1 rounded-full text-[11px] border border-slate-700/60">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-slate-300">NetworkGuard:</span>
          <span className="text-emerald-400 font-medium">3-Layer Defense</span>
        </div>

        <div className="flex items-center space-x-1.5 bg-slate-800/80 px-2 py-1 rounded-full text-[11px] border border-slate-700/60">
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-slate-300">LLM Mode:</span>
          <span className="text-indigo-400 font-medium">{llmMode}</span>
        </div>

        <div className="flex items-center space-x-1 text-slate-400 ml-2">
          <button className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 transition">
            <Minus className="w-3.5 h-3.5" />
          </button>
          <button className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 transition">
            <Square className="w-3 h-3" />
          </button>
          <button className="p-1 hover:bg-rose-600 rounded text-slate-400 hover:text-white transition">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
