import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import AIAssistant from './AIAssistant';

export default function PlanningList() {
  const [results, setResults] = useState<any[]>([]);
  const [centreLucru, setCentreLucru] = useState<any[]>([]);
  const [selectedCL, setSelectedCL] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getCentreLucru().then(setCentreLucru).catch(() => {});
  }, []);

  const loadResults = async () => {
    setLoading(true);
    const params: Record<string, string> = { limit: '300' };
    if (selectedCL) params.cl = selectedCL;
    if (selectedStatus) params.status = selectedStatus;
    try {
      const data = await api.getPlanningOperatii(params);
      setResults(data);
    } catch { setResults([]); }
    setLoading(false);
  };

  useEffect(() => { loadResults(); }, [selectedCL, selectedStatus]);

  const stats = useMemo(() => {
    const planned        = results.filter(r => r.status === 'planned');
    const plannedOrPrev  = results.filter(r => r.status === 'planned' || r.status === 'previzionat');
    const oreTotal       = plannedOrPrev.reduce((s, r) => s + (r.durata_ore || 0), 0);
    return {
      total:        results.length,
      planned:      planned.length,
      previzionat:  results.filter(r => r.status === 'previzionat').length,
      no_material:  results.filter(r => r.status === 'no_material').length,
      blocked:      results.filter(r => r.status === 'blocked_by_rank').length,
      no_bt:        results.filter(r => r.status === 'no_bt').length,
      no_resource:  results.filter(r => r.status === 'no_resource').length,
      ore:          oreTotal,
    };
  }, [results]);

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = {
      planned: 'bg-green-100 text-green-700',
      previzionat: 'bg-blue-100 text-blue-700',
      no_material: 'bg-red-100 text-red-700',
      no_resource: 'bg-slate-100 text-slate-700',
      blocked_by_rank: 'bg-amber-100 text-amber-700',
      no_bt: 'bg-orange-100 text-orange-700',
    };
    const labels: Record<string, string> = {
      planned: 'Planificat',
      previzionat: 'Previzionat',
      no_material: 'Fara Material',
      no_resource: 'Fara Resursa',
      blocked_by_rank: 'Blocat Rank',
      no_bt: 'Fara BT',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs ${styles[status] || 'bg-slate-100'}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-center">
        <select
          value={selectedCL}
          onChange={e => setSelectedCL(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm"
        >
          <option value="">Toate centrele de lucru</option>
          {centreLucru.map(cl => (
            <option key={cl.cl} value={cl.cl}>{cl.cl} - {cl.denumire}</option>
          ))}
        </select>
        <select
          value={selectedStatus}
          onChange={e => setSelectedStatus(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm"
        >
          <option value="">Toate statusurile</option>
          <option value="planned">Planificat</option>
          <option value="previzionat">Previzionat</option>
          <option value="no_material">Fara Material</option>
          <option value="no_resource">Fara Resursa</option>
          <option value="blocked_by_rank">Blocat Rank</option>
          <option value="no_bt">Fara BT</option>
        </select>
      </div>

      {/* AI Assistant — sus */}
      <AIAssistant tab="planificare" />

      {/* Stats cards — reflect current filter */}
      {results.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          <div className="bg-white rounded-lg border border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-500 mb-0.5">Total afișate</p>
            <p className="text-2xl font-bold text-slate-800">{stats.total}</p>
            <p className="text-xs text-slate-400">operații</p>
          </div>
          <button
            onClick={() => setSelectedStatus(selectedStatus === 'planned' ? '' : 'planned')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${selectedStatus === 'planned' ? 'bg-green-100 border-green-400' : 'bg-white border-slate-200 hover:bg-green-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Planificate</p>
            <p className="text-2xl font-bold text-green-700">{stats.planned}</p>
            <p className="text-xs text-slate-400">{stats.ore.toFixed(0)} ore totale</p>
          </button>
          <button
            onClick={() => setSelectedStatus(selectedStatus === 'previzionat' ? '' : 'previzionat')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${selectedStatus === 'previzionat' ? 'bg-blue-100 border-blue-400' : 'bg-white border-slate-200 hover:bg-blue-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Previzionate</p>
            <p className="text-2xl font-bold text-blue-600">{stats.previzionat}</p>
            <p className="text-xs text-slate-400">programate viitor</p>
          </button>
          <button
            onClick={() => setSelectedStatus(selectedStatus === 'no_material' ? '' : 'no_material')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${selectedStatus === 'no_material' ? 'bg-red-100 border-red-400' : 'bg-white border-slate-200 hover:bg-red-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Fara Material</p>
            <p className="text-2xl font-bold text-red-600">{stats.no_material}</p>
            <p className="text-xs text-slate-400">stoc insuficient</p>
          </button>
          <button
            onClick={() => setSelectedStatus(selectedStatus === 'no_bt' ? '' : 'no_bt')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${selectedStatus === 'no_bt' ? 'bg-orange-100 border-orange-400' : 'bg-white border-slate-200 hover:bg-orange-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Fara BT</p>
            <p className="text-2xl font-bold text-orange-600">{stats.no_bt}</p>
            <p className="text-xs text-slate-400">bun de tipar</p>
          </button>
          <button
            onClick={() => setSelectedStatus(selectedStatus === 'blocked_by_rank' ? '' : 'blocked_by_rank')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${selectedStatus === 'blocked_by_rank' ? 'bg-amber-100 border-amber-400' : 'bg-white border-slate-200 hover:bg-amber-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Blocate Rank</p>
            <p className="text-2xl font-bold text-amber-600">{stats.blocked}</p>
            <p className="text-xs text-slate-400">asteapta predec.</p>
          </button>
          <button
            onClick={() => setSelectedStatus(selectedStatus === 'no_resource' ? '' : 'no_resource')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${selectedStatus === 'no_resource' ? 'bg-slate-200 border-slate-400' : 'bg-white border-slate-200 hover:bg-slate-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Fara Resursa</p>
            <p className="text-2xl font-bold text-slate-600">{stats.no_resource}</p>
            <p className="text-xs text-slate-400">nemapate</p>
          </button>
        </div>
      )}

      {loading && <p className="text-slate-500 text-sm">Se incarca...</p>}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left">WO</th>
                <th className="px-3 py-2 text-left">OP</th>
                <th className="px-3 py-2 text-left">CL</th>
                <th className="px-3 py-2 text-left">Resursa</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Start</th>
                <th className="px-3 py-2 text-left">End</th>
                <th className="px-3 py-2 text-right">Durata (h)</th>
                <th className="px-3 py-2 text-left">Motiv</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2 font-mono">{r.wo}</td>
                  <td className="px-3 py-2 font-mono">{r.op}</td>
                  <td className="px-3 py-2">{r.cl}</td>
                  <td className="px-3 py-2">{r.resursa_nume || '-'}</td>
                  <td className="px-3 py-2">{statusBadge(r.status)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.data_start ? new Date(r.data_start).toLocaleDateString('ro-RO') : '-'}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.data_end ? new Date(r.data_end).toLocaleDateString('ro-RO') : '-'}
                  </td>
                  <td className="px-3 py-2 text-right">{r.durata_ore?.toFixed(1)}</td>
                  <td className="px-3 py-2 text-xs text-slate-500 min-w-[320px]">
                    {r.motiv || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {results.length === 0 && !loading && (
          <p className="text-center py-8 text-slate-400">Nicio planificare. Ruleaza din Dashboard.</p>
        )}
      </div>
    </div>
  );
}
