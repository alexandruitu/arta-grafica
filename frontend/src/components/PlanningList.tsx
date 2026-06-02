import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import AIAssistant from './AIAssistant';
import { Download } from 'lucide-react';

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('ro-RO', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

const STATUS_LABEL: Record<string, string> = {
  planned:                  'Planificat',
  previzionat_bt:           'Previzionat (fără BT)',
  previzionat_material:     'Previzionat (fără mat.)',
  previzionat_semifabricat: 'Previzionat (semifabricat)',
  no_material:              'Fără Material',
  no_resource:              'Fără Resursă',
  blocked_by_rank:          'Blocat Rank',
  no_bt:                    'Fără BT',
  blocat_semifabricat:      'Blocat Semifabricat',
  blocat_prefabricat:       'Blocat Prefabricat',  // backward compat
};

const STATUS_STYLE: Record<string, string> = {
  planned:                  'bg-green-100 text-green-700',
  previzionat_bt:           'bg-blue-100 text-blue-700',
  previzionat_material:     'bg-cyan-100 text-cyan-700',
  previzionat_semifabricat: 'bg-violet-100 text-violet-700',
  no_material:              'bg-red-100 text-red-700',
  no_resource:              'bg-slate-100 text-slate-600',
  blocked_by_rank:          'bg-amber-100 text-amber-700',
  no_bt:                    'bg-orange-100 text-orange-700',
  blocat_semifabricat:      'bg-fuchsia-100 text-fuchsia-700',
  blocat_prefabricat:       'bg-fuchsia-100 text-fuchsia-700',
};

const PREVIZIONAT_SET = new Set([
  'previzionat_bt', 'previzionat_material', 'previzionat_semifabricat',
]);
const PLACED_SET = new Set([
  'planned', 'previzionat_bt', 'previzionat_material', 'previzionat_semifabricat',
]);

function statusBadge(status: string) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLE[status] ?? 'bg-slate-100 text-slate-600'}`}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

/** Shortened version of motiv for inline display (with full text on hover) */
function shortMotiv(motiv: string | null | undefined): string {
  if (!motiv) return '';
  // "prefabricat:<wos>:<article>" — show just the article code
  if (motiv.startsWith('prefabricat:')) {
    const parts = motiv.split(':');
    const art = parts.length >= 3 ? parts[2] : '';
    return art.slice(0, 30) || motiv.slice(0, 30);
  }
  // "Stoc insuficient ART: …" — show article code
  const matMatch = motiv.match(/Stoc insuficient ([^:]+)/);
  if (matMatch) return matMatch[1].slice(0, 30);
  // Generic truncation
  return motiv.length > 38 ? motiv.slice(0, 38) + '…' : motiv;
}

// ── component ─────────────────────────────────────────────────────────────────

export default function PlanningList() {
  const [allResults,     setAllResults]     = useState<any[]>([]);
  const [centreLucru,    setCentreLucru]    = useState<any[]>([]);
  const [selectedCL,     setSelectedCL]     = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedResursa, setSelectedResursa] = useState('');
  const [search,         setSearch]         = useState('');
  const [loading,        setLoading]        = useState(false);
  const [exporting,      setExporting]      = useState(false);

  useEffect(() => {
    api.getCentreLucru().then(setCentreLucru).catch(() => {});
  }, []);

  const loadResults = async () => {
    setLoading(true);
    // Only server-side filter by CL (stable, high-cardinality).
    // Status + resource + search are applied client-side for instant response.
    const params: Record<string, string> = {};
    if (selectedCL) params.cl = selectedCL;
    try {
      const data = await api.getPlanningOperatii(params);
      setAllResults(data);
    } catch { setAllResults([]); }
    setLoading(false);
  };

  useEffect(() => { loadResults(); }, [selectedCL]);

  // ── Distinct resources (for filter dropdown) ───────────────────────────────
  const resurseList = useMemo(() => {
    const seen = new Set<string>();
    const list: string[] = [];
    for (const r of allResults) {
      if (r.resursa_nume && !seen.has(r.resursa_nume)) {
        seen.add(r.resursa_nume);
        list.push(r.resursa_nume);
      }
    }
    return list.sort();
  }, [allResults]);

  // ── Client-side filtering ──────────────────────────────────────────────────
  const filteredResults = useMemo(() => {
    const s = search.toLowerCase().trim();
    return allResults.filter(r => {
      // Status filter — "previzionat" matches all sub-types
      if (selectedStatus) {
        if (selectedStatus === 'previzionat') {
          if (!PREVIZIONAT_SET.has(r.status)) return false;
        } else {
          if (r.status !== selectedStatus) return false;
        }
      }
      // Resource filter
      if (selectedResursa && r.resursa_nume !== selectedResursa) return false;
      // Search: WO (numeric string), client, articol
      if (s) {
        const woMatch     = String(r.wo).includes(s);
        const clientMatch = (r.client  || '').toLowerCase().includes(s);
        const artMatch    = (r.articol || '').toLowerCase().includes(s);
        if (!woMatch && !clientMatch && !artMatch) return false;
      }
      return true;
    });
  }, [allResults, selectedStatus, selectedResursa, search]);

  // ── Stats computed from ALL results for current CL — stable under status/resource/search filters
  const stats = useMemo(() => {
    const planned     = allResults.filter(r => r.status === 'planned').length;
    const previzionat = allResults.filter(r => PREVIZIONAT_SET.has(r.status)).length;
    const no_material = allResults.filter(r => r.status === 'no_material').length;
    const no_bt       = allResults.filter(r => r.status === 'no_bt').length;
    const blocked     = allResults.filter(r => r.status === 'blocked_by_rank').length;
    const no_resource = allResults.filter(r => r.status === 'no_resource').length;
    const ore         = allResults
      .filter(r => PLACED_SET.has(r.status))
      .reduce((s, r) => s + (r.durata_ore || 0), 0);
    return { total: allResults.length, planned, previzionat, no_material, no_bt, blocked, no_resource, ore };
  }, [allResults]);

  const handleToggleFrozen = async (id: number, currentFrozen: boolean) => {
    try {
      await api.toggleFrozen(id, !currentFrozen);
      setAllResults(prev => prev.map(r => r.id === id ? { ...r, frozen: !currentFrozen } : r));
    } catch {
      alert('Nu s-a putut schimba starea frozen.');
    }
  };

  const toggleStatusFilter = (s: string) =>
    setSelectedStatus(prev => (prev === s ? '' : s));

  const handleExport = async () => {
    setExporting(true);
    try {
      const params: Record<string, string> = {};
      if (selectedCL)      params.cl      = selectedCL;
      if (selectedResursa) params.resursa  = selectedResursa;
      if (selectedStatus) {
        params.status = selectedStatus === 'previzionat'
          ? 'previzionat_bt,previzionat_material,previzionat_semifabricat'
          : selectedStatus;
      }
      if (search) params.search = search;
      const res = await api.exportPlanningXlsx(params);
      if (!res.ok) throw new Error(`Export eșuat: ${res.status}`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      const cd   = res.headers.get('Content-Disposition') || '';
      const m    = cd.match(/filename\*?=(?:UTF-8'')?([^;]+)/i);
      a.href     = url;
      a.download = m ? decodeURIComponent(m[1].replace(/"/g, '')) : 'planificare.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert('Eroare export: ' + e.message);
    }
    setExporting(false);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* CL filter */}
        <select value={selectedCL} onChange={e => setSelectedCL(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm">
          <option value="">Toate centrele de lucru</option>
          {centreLucru.filter(cl => cl.cl).map(cl => (
            <option key={cl.cl} value={cl.cl}>{cl.cl} – {cl.denumire}</option>
          ))}
        </select>

        {/* Resource filter (2.6) */}
        <select value={selectedResursa} onChange={e => setSelectedResursa(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm">
          <option value="">Toate resursele</option>
          {resurseList.map(r => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        {/* Status filter */}
        <select value={selectedStatus} onChange={e => setSelectedStatus(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm">
          <option value="">Toate statusurile</option>
          <option value="planned">Planificat</option>
          <option value="previzionat">Previzionat (toate)</option>
          <option value="previzionat_bt">Previzionat – fără BT</option>
          <option value="previzionat_material">Previzionat – fără material</option>
          <option value="previzionat_semifabricat">Previzionat – semifabricat</option>
          <option value="no_material">Fără Material (blocat)</option>
          <option value="no_resource">Fără Resursă</option>
          <option value="blocked_by_rank">Blocat Rank</option>
          <option value="no_bt">Fără BT (blocat)</option>
          <option value="blocat_semifabricat">Blocat Semifabricat</option>
        </select>

        {/* Search */}
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Caută WO, client, articol…"
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-56" />

        <button onClick={loadResults}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 font-medium">
          ↺ Reîncarcă
        </button>

        <button
          onClick={handleExport}
          disabled={exporting || filteredResults.length === 0}
          title="Exportă rezultatele afișate ca Excel"
          className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 font-medium disabled:opacity-50"
        >
          <Download size={14} />
          {exporting ? 'Se exportă…' : 'Export Excel'}
        </button>

        <span className="ml-auto text-xs text-slate-400">
          {filteredResults.length} / {allResults.length} operații
        </span>
      </div>

      {/* ── AI Assistant ── */}
      <AIAssistant tab="planificare" />

      {/* ── Stats cards (clickable, reflect filtered results — 2.5) ── */}
      {allResults.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          <div className="bg-white rounded-lg border border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-500 mb-0.5">Total afișat</p>
            <p className="text-2xl font-bold text-slate-800">{stats.total}</p>
            <p className="text-xs text-slate-400">din {allResults.length} op.</p>
          </div>

          {[
            { key: 'planned',         label: 'Planificate',   value: stats.planned,     color: 'green',  sub: `${stats.ore.toFixed(0)} ore` },
            { key: 'previzionat',     label: 'Previzionate',  value: stats.previzionat, color: 'blue',   sub: 'programate viitor' },
            { key: 'no_material',     label: 'Fără Material', value: stats.no_material, color: 'red',    sub: 'stoc insuficient' },
            { key: 'no_bt',           label: 'Fără BT',       value: stats.no_bt,       color: 'orange', sub: 'bun de tipar' },
            { key: 'blocked_by_rank', label: 'Blocate Rank',  value: stats.blocked,     color: 'amber',  sub: 'aşteaptă predec.' },
            { key: 'no_resource',     label: 'Fără Resursă',  value: stats.no_resource, color: 'slate',  sub: 'nemapate' },
          ].map(({ key, label, value, color, sub }) => {
            const active = selectedStatus === key;
            return (
              <button key={key} onClick={() => toggleStatusFilter(key)}
                className={`rounded-lg border px-4 py-3 text-left transition-colors ${
                  active
                    ? `bg-${color}-100 border-${color}-400`
                    : `bg-white border-slate-200 hover:bg-${color}-50`
                }`}>
                <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                <p className={`text-2xl font-bold text-${color}-${color === 'slate' ? '600' : '700'}`}>{value}</p>
                <p className="text-xs text-slate-400">{sub}</p>
              </button>
            );
          })}
        </div>
      )}

      {loading && <p className="text-slate-500 text-sm">Se încarcă…</p>}

      {/* ── Table ── */}
      <div className="bg-white rounded-lg shadow-sm">
        <div className="overflow-x-auto rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="px-3 py-2 text-left">WO</th>
                <th className="px-3 py-2 text-left">OP</th>
                <th className="px-3 py-2 text-left">CL</th>
                <th className="px-3 py-2 text-left">Resursă</th>
                <th className="px-3 py-2 text-left">Client</th>
                <th className="px-3 py-2 text-left">Articol</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Freeze</th>
                <th className="px-3 py-2 text-left whitespace-nowrap">Start</th>
                <th className="px-3 py-2 text-left whitespace-nowrap">Stop</th>
                <th className="px-3 py-2 text-right whitespace-nowrap">Durata (h)</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((r, i) => (
                <tr key={r.id ?? i} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2 font-mono text-xs">{r.wo}</td>
                  <td className="px-3 py-2 font-mono text-xs">{r.op}</td>
                  <td className="px-3 py-2 text-xs">{r.cl}</td>
                  <td className="px-3 py-2 text-xs">{r.resursa_nume || '—'}</td>
                  <td className="px-3 py-2 text-xs max-w-[120px] truncate" title={r.client}>
                    {r.client || '—'}
                  </td>
                  <td className="px-3 py-2 text-xs max-w-[160px] truncate" title={r.articol}>
                    {r.articol || '—'}
                  </td>
                  {/* Status cell — badge + inline motiv (2.4) */}
                  <td className="px-3 py-2 min-w-[160px]">
                    {r.frozen && <span className="text-purple-400 mr-1 text-xs">❄</span>}
                    {statusBadge(r.status)}
                    {r.motiv && (
                      <span
                        className="block text-xs text-slate-400 mt-0.5 leading-tight"
                        title={r.motiv}
                      >
                        ({shortMotiv(r.motiv)})
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {PLACED_SET.has(r.status) ? (
                      <button
                        onClick={() => handleToggleFrozen(r.id, r.frozen)}
                        className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                          r.frozen
                            ? 'bg-purple-100 text-purple-700 hover:bg-purple-200'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                        title={r.frozen ? 'Unfreeze' : 'Freeze (fixează poziția)'}
                      >
                        {r.frozen ? '❄ Frozen' : 'Freeze'}
                      </button>
                    ) : (
                      <span className="text-slate-300 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs whitespace-nowrap">{fmtDateTime(r.data_start)}</td>
                  <td className="px-3 py-2 text-xs whitespace-nowrap">{fmtDateTime(r.data_end)}</td>
                  <td className="px-3 py-2 text-right text-xs">{r.durata_ore?.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredResults.length === 0 && !loading && (
          <p className="text-center py-8 text-slate-400">
            {allResults.length === 0
              ? 'Nicio planificare. Rulează din Dashboard.'
              : 'Niciun rezultat pentru filtrele aplicate.'}
          </p>
        )}
      </div>
    </div>
  );
}
