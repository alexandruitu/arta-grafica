import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { Factory, Package, AlertTriangle, CheckCircle, Clock, Upload, X, FileSpreadsheet } from 'lucide-react';
import AIAssistant from './AIAssistant';

interface Stats {
  total_comenzi: number;
  comenzi_active: number;
  comenzi_stop: number;
  total_dispatch: number;
  total_resurse: number;
  stadiu_prepress: Record<string, number>;
}

interface PlanningInfo {
  sesiune_id: number;
  created_at: string;
  status: string;
  total_operatii: number;
  operatii_planificate: number;
  operatii_neplanificate: number;
  breakdown: Record<string, number>;
}

const EXPECTED_FILES = [
  'Stari comenzi_AS.xlsx',
  'Dispatch List_AS.xlsx',
  'OperatiiWO_AS.xlsx',
  'Lista Deficite_AS.xlsx',
  'Resurse_AS.xlsx',
];

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [planning, setPlanning] = useState<PlanningInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [showFilePicker, setShowFilePicker] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [s, p] = await Promise.all([api.getStats(), api.getLatestPlanning()]);
      setStats(s);
      if (!p.error) setPlanning(p);
    } catch {
      // DB might be empty
    }
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setSelectedFiles(Array.from(e.target.files));
  };

  const removeFile = (name: string) => {
    setSelectedFiles(prev => prev.filter(f => f.name !== name));
  };

  const missingFiles = EXPECTED_FILES.filter(name => !selectedFiles.some(f => f.name === name));
  const extraFiles = selectedFiles.filter(f => !EXPECTED_FILES.includes(f.name));

  const handleImport = async () => {
    if (!showFilePicker) { setShowFilePicker(true); return; }
    if (missingFiles.length > 0) {
      alert('Lipsesc fisierele:\n' + missingFiles.join('\n'));
      return;
    }
    setImportLoading(true);
    try {
      const fd = new FormData();
      selectedFiles.filter(f => EXPECTED_FILES.includes(f.name)).forEach(f => fd.append('files', f));
      await api.importData(fd);
      await loadData();
      setShowFilePicker(false);
      setSelectedFiles([]);
    } catch (e: any) {
      alert('Eroare import: ' + e.message);
    }
    setImportLoading(false);
  };

  const handlePlan = async () => {
    setPlanLoading(true);
    try {
      await api.runPlanning();
      await loadData();
    } catch (e: any) {
      alert('Planning error: ' + e.message);
    }
    setPlanLoading(false);
  };

  const StatCard = ({ icon: Icon, label, value, color }: any) => (
    <div className="bg-white rounded-lg shadow-sm p-4 flex items-center gap-3">
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-xl font-semibold">{value}</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Actions */}
      <div className="space-y-3">
        <div className="flex gap-3 flex-wrap">
          <button
            onClick={handleImport}
            disabled={importLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium flex items-center gap-2"
          >
            <Upload size={16} />
            {importLoading ? 'Se importa...' : 'Import Date Excel'}
          </button>
          <button
            onClick={handlePlan}
            disabled={planLoading || !stats?.total_comenzi}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium"
          >
            {planLoading ? 'Se planifica...' : 'Ruleaza Planificarea'}
          </button>
        </div>

        {/* File picker panel */}
        {showFilePicker && (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-slate-700">Selecteaza cele 5 fisiere Excel:</p>
              <button onClick={() => { setShowFilePicker(false); setSelectedFiles([]); }} className="text-slate-400 hover:text-slate-600">
                <X size={16} />
              </button>
            </div>

            {/* Hidden multi-file input */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".xlsx"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-3 py-2 border border-dashed border-slate-400 rounded-lg text-sm text-slate-600 hover:border-blue-400 hover:text-blue-600 w-full justify-center"
            >
              <FileSpreadsheet size={16} />
              Selecteaza fisierele .xlsx (poti selecta mai multe simultan)
            </button>

            {/* Selected files list */}
            {selectedFiles.length > 0 && (
              <div className="space-y-1">
                {EXPECTED_FILES.map(name => {
                  const found = selectedFiles.find(f => f.name === name);
                  return (
                    <div key={name} className={`flex items-center justify-between text-xs px-2 py-1 rounded ${found ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-500'}`}>
                      <span>{found ? '✓' : '✗'} {name}</span>
                      {found && (
                        <button onClick={() => removeFile(name)} className="ml-2 opacity-60 hover:opacity-100"><X size={11} /></button>
                      )}
                    </div>
                  );
                })}
                {extraFiles.map(f => (
                  <div key={f.name} className="flex items-center justify-between text-xs px-2 py-1 rounded bg-amber-50 text-amber-700">
                    <span>⚠ {f.name} (neasteptat)</span>
                    <button onClick={() => removeFile(f.name)} className="ml-2 opacity-60 hover:opacity-100"><X size={11} /></button>
                  </div>
                ))}
              </div>
            )}

            {/* Expected files hint when nothing selected */}
            {selectedFiles.length === 0 && (
              <div className="space-y-0.5">
                {EXPECTED_FILES.map(name => (
                  <div key={name} className="text-xs text-slate-400 px-2">• {name}</div>
                ))}
              </div>
            )}

            <button
              onClick={handleImport}
              disabled={importLoading || missingFiles.length > 0}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 font-medium text-sm flex items-center justify-center gap-2"
            >
              <Upload size={15} />
              {importLoading ? 'Se importa...' : missingFiles.length > 0 ? `Lipsesc ${missingFiles.length} fisiere` : 'Importa'}
            </button>
          </div>
        )}
      </div>

      {loading && <p className="text-slate-500">Se incarca...</p>}

      {stats && (
        <>
          {/* Stats cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <StatCard icon={Package} label="Total Comenzi" value={stats.total_comenzi} color="bg-blue-500" />
            <StatCard icon={CheckCircle} label="Comenzi Active" value={stats.comenzi_active} color="bg-green-500" />
            <StatCard icon={AlertTriangle} label="Comenzi STOP" value={stats.comenzi_stop} color="bg-red-500" />
            <StatCard icon={Clock} label="Operatii Dispatch" value={stats.total_dispatch} color="bg-amber-500" />
            <StatCard icon={Factory} label="Resurse" value={stats.total_resurse} color="bg-purple-500" />
          </div>

          {/* Stadiu Prepress breakdown */}
          <div className="bg-white rounded-lg shadow-sm p-4">
            <h3 className="font-semibold mb-3">Stadiu Prepress</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(stats.stadiu_prepress)
                .sort(([a], [b]) => b.localeCompare(a))
                .map(([stadiu, count]) => (
                  <div key={stadiu} className="flex justify-between items-center p-2 bg-slate-50 rounded">
                    <span className="text-sm">{stadiu || 'N/A'}</span>
                    <span className="font-semibold text-sm bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                      {count}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </>
      )}

      {/* Planning results */}
      {planning && (
        <div className="bg-white rounded-lg shadow-sm p-4">
          <h3 className="font-semibold mb-3">Ultima Planificare (Sesiunea #{planning.sesiune_id})</h3>
          <p className="text-sm text-slate-500 mb-3">
            {planning.created_at ? new Date(planning.created_at).toLocaleString('ro-RO') : ''}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-green-50 rounded text-center">
              <p className="text-2xl font-bold text-green-700">{planning.breakdown?.planned || 0}</p>
              <p className="text-sm text-green-600">Planificate</p>
            </div>
            <div className="p-3 bg-red-50 rounded text-center">
              <p className="text-2xl font-bold text-red-700">{planning.breakdown?.no_material || 0}</p>
              <p className="text-sm text-red-600">Fara Material</p>
            </div>
            <div className="p-3 bg-amber-50 rounded text-center">
              <p className="text-2xl font-bold text-amber-700">{planning.breakdown?.blocked_by_rank || 0}</p>
              <p className="text-sm text-amber-600">Blocate (Rank)</p>
            </div>
            <div className="p-3 bg-slate-50 rounded text-center">
              <p className="text-2xl font-bold text-slate-700">{planning.breakdown?.no_resource || 0}</p>
              <p className="text-sm text-slate-600">Fara Resursa</p>
            </div>
          </div>
        </div>
      )}

      {/* AI Assistant */}
      {stats && <AIAssistant tab="dashboard" />}
    </div>
  );
}
