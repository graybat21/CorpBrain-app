import React from 'react';
import { TitleBar } from './components/TitleBar';
import { Sidebar } from './components/Sidebar';
import { ToastContainer } from './components/ToastContainer';
import { DashboardPage } from './pages/DashboardPage';
import { FilesPage } from './pages/FilesPage';
import { WikiPage } from './pages/WikiPage';
import { RenamePage } from './pages/RenamePage';
import { SettingsPage } from './pages/SettingsPage';
import { useAppStore } from './store/appStore';

export const App: React.FC = () => {
  const activeTab = useAppStore((state) => state.activeTab);

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardPage />;
      case 'files':
        return <FilesPage />;
      case 'wiki':
        return <WikiPage />;
      case 'rename':
        return <RenamePage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      <TitleBar />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 bg-slate-950 overflow-hidden relative">
          {renderContent()}
        </main>
      </div>

      <ToastContainer />
    </div>
  );
};
