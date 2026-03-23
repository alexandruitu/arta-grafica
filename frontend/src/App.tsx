import { useState } from 'react';
import Dashboard from './components/Dashboard';
import GanttView from './components/GanttView';
import ComenziList from './components/ComenziList';
import PlanningList from './components/PlanningList';
import StocView from './components/StocView';
import { LayoutDashboard, GanttChart, Package, ListChecks, Boxes } from 'lucide-react';
import './index.css';

type Tab = 'dashboard' | 'gantt' | 'comenzi' | 'planificare' | 'stoc';

const tabs: { id: Tab; label: string; icon: any }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'gantt', label: 'Gantt', icon: GanttChart },
  { id: 'comenzi', label: 'Comenzi', icon: Package },
  { id: 'planificare', label: 'Planificare', icon: ListChecks },
  { id: 'stoc', label: 'Stoc Materiale', icon: Boxes },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

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

        {/* Main content */}
        <main className="flex-1 p-6">
          <h2 className="text-xl font-semibold text-slate-800 mb-4">
            {tabs.find(t => t.id === activeTab)?.label}
          </h2>
          {activeTab === 'dashboard' && <Dashboard />}
          {activeTab === 'gantt' && <GanttView />}
          {activeTab === 'comenzi' && <ComenziList />}
          {activeTab === 'planificare' && <PlanningList />}
          {activeTab === 'stoc' && <StocView />}
        </main>
      </div>
    </div>
  );
}
