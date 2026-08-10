import React, { useEffect } from 'react';
import { TitleBar } from './components/TitleBar';
import { Sidebar } from './components/Sidebar';
import { ToastContainer } from './components/ToastContainer';
import { DashboardPage } from './pages/DashboardPage';
import { FilesPage } from './pages/FilesPage';
import { WikiPage } from './pages/WikiPage';
import { RenamePage } from './pages/RenamePage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { SettingsPage } from './pages/SettingsPage';
import { useAppStore } from './store/appStore';

export const App: React.FC = () => {
  const activeTab = useAppStore((state) => state.activeTab);
  const bootstrap = useAppStore((state) => state.bootstrap);

  // One backend read on mount. `bootstrap` is a stable store action, so this does not re-run
  // per tab switch — each page refetches its own data instead.
  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

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
      case 'analytics':
        return <AnalyticsPage />;
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
