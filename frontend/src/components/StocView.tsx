import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { Search } from 'lucide-react';

export default function StocView() {
  const [stoc, setStoc] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  const loadStoc = async () => {
    setLoading(true);
    try {
      const data = await api.getStoc(search || undefined);
      setStoc(data);
    } catch { setStoc([]); }
    setLoading(false);
  };

  useEffect(() => { loadStoc(); }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadStoc();
  };

  const stats = useMemo(() => ({
    total:            stoc.length,
    disponibil:       stoc.filter(s => s.disponibil_final > 0).length,
    epuizat:          stoc.filter(s => s.disponibil_final === 0).length,
    deficit:          stoc.filter(s => s.disponibil_final < 0).length,
    in_aprovizionare: stoc.filter(s => s.disponibil < 0 && s.disponibil_final >= 0).length,
    totalRezervat:    stoc.reduce((sum, s) => sum + (s.total_rezervat || 0), 0),
  }), [stoc]);

  const [filterStatus, setFilterStatus] = useState<'deficit' | 'epuizat' | 'in_aprovizionare' | ''>('');

  const visibleStoc = useMemo(() => {
    if (filterStatus === 'deficit') return stoc.filter(s => s.disponibil_final < 0);
    if (filterStatus === 'epuizat') return stoc.filter(s => s.disponibil_final === 0);
    if (filterStatus === 'in_aprovizionare') return stoc.filter(s => s.disponibil < 0 && s.disponibil_final >= 0);
    return stoc;
  }, [stoc, filterStatus]);

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Cauta articol..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm w-full"
          />
        </div>
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">
          Cauta
        </button>
      </form>

      {/* Stats cards */}
      {stoc.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="bg-white rounded-lg border border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-500 mb-0.5">Total articole</p>
            <p className="text-2xl font-bold text-slate-800">{stats.total}</p>
            <p className="text-xs text-slate-400">{stats.totalRezervat.toLocaleString('ro-RO')} rezervat</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-500 mb-0.5">Disponibil</p>
            <p className="text-2xl font-bold text-green-600">{stats.disponibil}</p>
            <p className="text-xs text-slate-400">stoc pozitiv final</p>
          </div>
          <button
            onClick={() => setFilterStatus(filterStatus === 'in_aprovizionare' ? '' : 'in_aprovizionare')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${filterStatus === 'in_aprovizionare' ? 'bg-blue-100 border-blue-400' : 'bg-white border-slate-200 hover:bg-blue-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">In aprovizionare</p>
            <p className="text-2xl font-bold text-blue-600">{stats.in_aprovizionare}</p>
            <p className="text-xs text-slate-400">vine material</p>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'epuizat' ? '' : 'epuizat')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${filterStatus === 'epuizat' ? 'bg-amber-100 border-amber-400' : 'bg-white border-slate-200 hover:bg-amber-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Epuizat</p>
            <p className="text-2xl font-bold text-amber-600">{stats.epuizat}</p>
            <p className="text-xs text-slate-400">sold zero</p>
          </button>
          <button
            onClick={() => setFilterStatus(filterStatus === 'deficit' ? '' : 'deficit')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${filterStatus === 'deficit' ? 'bg-red-100 border-red-400' : 'bg-white border-slate-200 hover:bg-red-50'}`}
          >
            <p className="text-xs text-slate-500 mb-0.5">Deficit</p>
            <p className="text-2xl font-bold text-red-600">{stats.deficit}</p>
            <p className="text-xs text-slate-400">disponibil final negativ</p>
          </button>
        </div>
      )}

      {loading && <p className="text-slate-500 text-sm">Se incarca...</p>}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-3 py-2 text-left">Articol</th>
              <th className="px-3 py-2 text-right">Sold Actual</th>
              <th className="px-3 py-2 text-right">Total Rezervat</th>
              <th className="px-3 py-2 text-right">Disponibil</th>
              <th className="px-3 py-2 text-right">APROV.</th>
              <th className="px-3 py-2 text-right">Disp. Final</th>
              <th className="px-3 py-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {visibleStoc.map((s, i) => (
              <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{s.articol}</td>
                <td className="px-3 py-2 text-right">{s.sold_actual?.toLocaleString('ro-RO')}</td>
                <td className="px-3 py-2 text-right">{s.total_rezervat?.toLocaleString('ro-RO')}</td>
                <td className={`px-3 py-2 text-right font-medium ${s.disponibil < 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {s.disponibil?.toLocaleString('ro-RO')}
                </td>
                <td className="px-3 py-2 text-right text-blue-600">
                  {s.total_aprovizionare > 0 ? `+${s.total_aprovizionare?.toLocaleString('ro-RO')}` : '-'}
                </td>
                <td className={`px-3 py-2 text-right font-semibold ${s.disponibil_final < 0 ? 'text-red-700' : s.disponibil_final === 0 ? 'text-amber-600' : 'text-green-700'}`}>
                  {s.disponibil_final?.toLocaleString('ro-RO')}
                </td>
                <td className="px-3 py-2">
                  {s.disponibil_final < 0 ? (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">Deficit</span>
                  ) : s.disponibil < 0 ? (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">In aprovizionare</span>
                  ) : s.disponibil === 0 ? (
                    <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">Epuizat</span>
                  ) : (
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">Disponibil</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {stoc.length === 0 && !loading && (
          <p className="text-center py-8 text-slate-400">Nu exista date stoc. Importa din Dashboard.</p>
        )}
      </div>
    </div>
  );
}
