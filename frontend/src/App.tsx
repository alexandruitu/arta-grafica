import { useState } from 'react';
import Dashboard from './components/Dashboard';
import GanttView from './components/GanttView';
import BoardView from './components/BoardView';
import ComenziList from './components/ComenziList';
import PlanningList from './components/PlanningList';
import StocView from './components/StocView';
import LoginPage from './components/LoginPage';
import { LayoutDashboard, GanttChart, LayoutGrid, Package, ListChecks, Boxes, LogOut } from 'lucide-react';
import { getToken, clearToken } from './api/client';
import './index.css';

type Tab = 'dashboard' | 'gantt' | 'board' | 'comenzi' | 'planificare' | 'stoc';

const tabs: { id: Tab; label: string; icon: any }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'gantt', label: 'Gantt', icon: GanttChart },
  { id: 'board', label: 'Board Mașini', icon: LayoutGrid },
  { id: 'comenzi', label: 'Comenzi', icon: Package },
  { id: 'planificare', label: 'Planificare', icon: ListChecks },
  { id: 'stoc', label: 'Stoc Materiale', icon: Boxes },
];

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean>(() => !!getToken());
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  const handleLogout = () => {
    clearToken();
    setAuthenticated(false);
  };

  if (!authenticated) {
    return <LoginPage onLogin={() => setAuthenticated(true)} />;
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">AG</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold text-slate-900 leading-tight">Arta Grafica</h1>
              <p className="text-xs text-slate-500">Planificare Productie</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-red-600 transition-colors px-2 py-1 rounded-lg hover:bg-red-50"
            title="Deconectare"
          >
            <LogOut size={15} />
            <span className="hidden sm:inline">Deconectare</span>
          </button>
        </div>
      </header>

      <div className="max-w-[1400px] mx-auto flex">
        {/* Sidebar */}
        <nav className="w-56 bg-white border-r border-slate-200 min-h-[calc(100vh-60px)] p-3 flex-shrink-0">
          {tabs.map(tab => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm mb-1 transition-colors ${
                  active
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <Icon size={18} />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Main content — min-w-0 prevents flex item from overflowing past parent */}
        <main className="flex-1 min-w-0 p-6">
          <h2 className="text-xl font-semibold text-slate-800 mb-4">
            {tabs.find(t => t.id === activeTab)?.label}
          </h2>
          {activeTab === 'dashboard' && <Dashboard />}
          {activeTab === 'gantt' && <GanttView />}
          {activeTab === 'board' && <BoardView />}
          {activeTab === 'comenzi' && <ComenziList />}
          {activeTab === 'planificare' && <PlanningList />}
          {activeTab === 'stoc' && <StocView />}
        </main>
      </div>
    </div>
  );
}
