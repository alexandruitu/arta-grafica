import { useEffect, useState } from 'react';
import { api } from '../api/client';

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

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = {
      planned: 'bg-green-100 text-green-700',
      no_material: 'bg-red-100 text-red-700',
      no_resource: 'bg-slate-100 text-slate-700',
      blocked_by_rank: 'bg-amber-100 text-amber-700',
      no_bt: 'bg-orange-100 text-orange-700',
    };
    const labels: Record<string, string> = {
      planned: 'Planificat',
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
          <option value="no_material">Fara Material</option>
          <option value="no_resource">Fara Resursa</option>
          <option value="blocked_by_rank">Blocat Rank</option>
          <option value="no_bt">Fara BT</option>
        </select>
      </div>

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
                  <td className="px-3 py-2 text-xs text-slate-500 max-w-[250px] truncate" title={r.motiv}>
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
