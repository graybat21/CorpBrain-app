import React, { useState } from 'react';
import { Search, RefreshCw, FileText, Filter, CheckCircle2 } from 'lucide-react';
import { useAppStore } from '../store/appStore';

export const FilesPage: React.FC = () => {
  const { files, addToast } = useAppStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [isScanning, setIsScanning] = useState(false);

  const filteredFiles = files.filter((f) =>
    f.file_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleRunScan = () => {
    setIsScanning(true);
    addToast('info', '워크스페이스 파일 스캔 및 고속 분석을 시작합니다...');
    setTimeout(() => {
      setIsScanning(false);
      addToast('success', '스캔 및 중요도 가중치 업데이트가 완료되었습니다.');
    }, 1500);
  };

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">파일 탐색기 & 중요도 관리</h1>
          <p className="text-xs text-slate-400">
            ScannerService(SCAN-CMD-01) 및 FastAnalysisEngine(ANA-CMD-01) 기반 탐색기입니다.
          </p>
        </div>

        <button
          onClick={handleRunScan}
          disabled={isScanning}
          className="flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-lg transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
          <span>{isScanning ? '스캔 중...' : '재스캔 및 분석 실행'}</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex items-center space-x-3 bg-slate-900/80 p-3 rounded-xl border border-slate-800">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="파일명 검색 (예: 기획서, pdf, 주민등록증)..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>
        <button className="flex items-center space-x-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs px-3 py-2 rounded-lg transition border border-slate-700/60">
          <Filter className="w-3.5 h-3.5" />
          <span>확장자 필터</span>
        </button>
      </div>

      {/* Files Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800 uppercase text-[10px] tracking-wider">
            <tr>
              <th className="p-3.5">파일명</th>
              <th className="p-3.5">확장자</th>
              <th className="p-3.5">중요도 점수</th>
              <th className="p-3.5">파일 크기</th>
              <th className="p-3.5">파싱 상태</th>
              <th className="p-3.5 text-right">작업</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredFiles.map((file) => (
              <tr key={file.file_id} className="hover:bg-slate-800/40 transition">
                <td className="p-3.5 font-medium text-slate-200">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span>{file.file_name}</span>
                  </div>
                </td>
                <td className="p-3.5 font-mono text-slate-400">{file.extension}</td>
                <td className="p-3.5">
                  <span
                    className={`inline-block px-2 py-0.5 rounded font-mono font-semibold ${
                      file.importance_score >= 70
                        ? 'bg-amber-950 text-amber-300 border border-amber-800/60'
                        : file.importance_score >= 40
                        ? 'bg-blue-950 text-blue-300 border border-blue-800/60'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {file.importance_score}점
                  </span>
                </td>
                <td className="p-3.5 font-mono text-slate-400">{(file.size_bytes / 1024).toFixed(1)} KB</td>
                <td className="p-3.5">
                  <span className="inline-flex items-center space-x-1 bg-emerald-950 text-emerald-400 border border-emerald-800/60 px-2 py-0.5 rounded text-[10px]">
                    <CheckCircle2 className="w-3 h-3 mr-1" /> Ready
                  </span>
                </td>
                <td className="p-3.5 text-right">
                  <button
                    onClick={() => addToast('info', `${file.file_name} 위치: ${file.current_path}`)}
                    className="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded transition"
                  >
                    경로 확인
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
