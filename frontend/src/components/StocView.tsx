import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';

export default function StocView() {
  const [allStoc, setAllStoc]   = useState<any[]>([]);
  const [search,  setSearch]    = useState('');
  const [loading, setLoading]   = useState(false);
  const [filterStatus, setFilterStatus] = useState<'deficit' | 'epuizat' | 'in_aprovizionare' | ''>('');

  const loadStoc = async () => {
    setLoading(true);
    try {
      const data = await api.getStoc();
      setAllStoc(data);
    } catch { setAllStoc([]); }
    setLoading(false);
  };

  useEffect(() => { loadStoc(); }, []);

  // ── Client-side filtering ──────────────────────────────────────────────────
  const visibleStoc = useMemo(() => {
    const s = search.toLowerCase().trim();
    return allStoc.filter(item => {
      if (filterStatus === 'deficit'         && !(item.disponibil_final < 0))                          return false;
      if (filterStatus === 'epuizat'         && !(item.disponibil_final === 0))                        return false;
      if (filterStatus === 'in_aprovizionare' && !(item.disponibil < 0 && item.disponibil_final >= 0)) return false;
      if (s && !(item.articol || '').toLowerCase().includes(s)) return false;
      return true;
    });
  }, [allStoc, search, filterStatus]);

  // ── Stats (always over full dataset) ──────────────────────────────────────
  const stats = useMemo(() => ({
    total:            allStoc.length,
    disponibil:       allStoc.filter(s => s.disponibil_final > 0).length,
    epuizat:          allStoc.filter(s => s.disponibil_final === 0).length,
    deficit:          allStoc.filter(s => s.disponibil_final < 0).length,
    in_aprovizionare: allStoc.filter(s => s.disponibil < 0 && s.disponibil_final >= 0).length,
    totalRezervat:    allStoc.reduce((sum, s) => sum + (s.total_rezervat || 0), 0),
  }), [allStoc]);

  const toggleFilter = (f: typeof filterStatus) =>
    setFilterStatus(prev => (prev === f ? '' : f));

  const fmt = (v: number | undefined) =>
    v == null ? '—' : v.toLocaleString('ro-RO', { maximumFractionDigits: 0 });

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap gap-2 items-center">
        <input
          type="text"
          placeholder="Caută articol…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-64"
        />
        <button onClick={loadStoc}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 font-medium">
          ↺ Reîncarcă
        </button>
        <span className="ml-auto text-xs text-slate-400">
          {visibleStoc.length} / {allStoc.length} articole
        </span>
      </div>

      {/* ── Stats cards ── */}
      {allStoc.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="bg-white rounded-lg border border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-500 mb-0.5">Total articole</p>
            <p className="text-2xl font-bold text-slate-800">{stats.total}</p>
            <p className="text-xs text-slate-400">{fmt(stats.totalRezervat)} rezervat</p>
          </div>

          <div className="bg-white rounded-lg border border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-500 mb-0.5">Disponibil</p>
            <p className="text-2xl font-bold text-green-600">{stats.disponibil}</p>
            <p className="text-xs text-slate-400">stoc pozitiv final</p>
          </div>

          <button
            onClick={() => toggleFilter('in_aprovizionare')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${
              filterStatus === 'in_aprovizionare'
                ? 'bg-blue-100 border-blue-400'
                : 'bg-white border-slate-200 hover:bg-blue-50'
            }`}>
            <p className="text-xs text-slate-500 mb-0.5">În aprovizionare</p>
            <p className="text-2xl font-bold text-blue-600">{stats.in_aprovizionare}</p>
            <p className="text-xs text-slate-400">vine material</p>
          </button>

          <button
            onClick={() => toggleFilter('epuizat')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${
              filterStatus === 'epuizat'
                ? 'bg-amber-100 border-amber-400'
                : 'bg-white border-slate-200 hover:bg-amber-50'
            }`}>
            <p className="text-xs text-slate-500 mb-0.5">Epuizat</p>
            <p className="text-2xl font-bold text-amber-600">{stats.epuizat}</p>
            <p className="text-xs text-slate-400">sold zero</p>
          </button>

          <button
            onClick={() => toggleFilter('deficit')}
            className={`rounded-lg border px-4 py-3 text-left transition-colors ${
              filterStatus === 'deficit'
                ? 'bg-red-100 border-red-400'
                : 'bg-white border-slate-200 hover:bg-red-50'
            }`}>
            <p className="text-xs text-slate-500 mb-0.5">Deficit</p>
            <p className="text-2xl font-bold text-red-600">{stats.deficit}</p>
            <p className="text-xs text-slate-400">disponibil final negativ</p>
          </button>
        </div>
      )}

      {loading && <p className="text-slate-500 text-sm">Se încarcă…</p>}

      {/* ── Table ── */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="px-3 py-2 text-left">Articol</th>
                <th className="px-3 py-2 text-right whitespace-nowrap">SOLD</th>
                <th className="px-3 py-2 text-right whitespace-nowrap">REZERVAT</th>
                <th className="px-3 py-2 text-right whitespace-nowrap">DISPONIBIL</th>
                <th className="px-3 py-2 text-right whitespace-nowrap">APROV.</th>
                <th className="px-3 py-2 text-right whitespace-nowrap">DISP. FINAL</th>
                <th className="px-3 py-2 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleStoc.map((s, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2 font-mono text-xs">{s.articol}</td>
                  <td className="px-3 py-2 text-right text-xs">{fmt(s.sold_actual)}</td>
                  <td className="px-3 py-2 text-right text-xs text-slate-600">
                    {s.total_rezervat > 0 ? `-${fmt(s.total_rezervat)}` : '—'}
                  </td>
                  <td className={`px-3 py-2 text-right text-xs font-medium ${s.disponibil < 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {fmt(s.disponibil)}
                  </td>
                  <td className="px-3 py-2 text-right text-xs text-blue-600">
                    {s.total_aprovizionare > 0 ? `+${fmt(s.total_aprovizionare)}` : '—'}
                  </td>
                  <td className={`px-3 py-2 text-right text-xs font-semibold ${
                    s.disponibil_final < 0  ? 'text-red-700'
                    : s.disponibil_final === 0 ? 'text-amber-600'
                    : 'text-green-700'
                  }`}>
                    {fmt(s.disponibil_final)}
                  </td>
                  <td className="px-3 py-2">
                    {s.disponibil_final < 0 ? (
                      <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">Deficit</span>
                    ) : s.disponibil < 0 ? (
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">În aprovizionare</span>
                    ) : s.disponibil_final === 0 ? (
                      <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">Epuizat</span>
                    ) : (
                      <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">Disponibil</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {allStoc.length === 0 && !loading && (
          <p className="text-center py-8 text-slate-400">Nu există date stoc. Importă din Dashboard.</p>
        )}
        {allStoc.length > 0 && visibleStoc.length === 0 && (
          <p className="text-center py-8 text-slate-400">Niciun rezultat pentru filtrele aplicate.</p>
        )}
      </div>
    </div>
  );
}
