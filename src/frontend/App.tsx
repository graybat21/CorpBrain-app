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
import { subscribeToRoute } from './router';

export const App: React.FC = () => {
  const activeTab = useAppStore((state) => state.activeTab);
  const bootstrap = useAppStore((state) => state.bootstrap);
  const setActiveTab = useAppStore((state) => state.setActiveTab);
  const selectWorkspace = useAppStore((state) => state.selectWorkspace);

  // One backend read on mount. `bootstrap` is a stable store action, so this does not re-run
  // per tab switch — each page refetches its own data instead.
  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  // DEC-01 hash routing: the URL drives the render, not the other way round. `subscribeToRoute`
  // reports the current hash immediately, which is what applies the entry route the shell opens
  // the window at (`#/dashboard`, see src/main.py) — `hashchange` does not fire on first load.
  useEffect(() => {
    return subscribeToRoute((route) => {
      setActiveTab(route.tab);
      if (route.workspaceId) {
        // `#/workspace/<id>` addresses which workspace is open. Guarded inside the store: an id
        // that is not in the loaded list is ignored rather than blanking the current one.
        void selectWorkspace(route.workspaceId);
      }
    });
  }, [setActiveTab, selectWorkspace]);

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
