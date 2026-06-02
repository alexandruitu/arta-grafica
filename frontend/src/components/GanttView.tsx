import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
// @ts-ignore – frappe-gantt has no type declarations
import Gantt from 'frappe-gantt';
import { api } from '../api/client';
import { Search, Lock, Unlock, X, List, RefreshCw, ChevronLeft, ChevronRight, Calendar } from 'lucide-react';

interface GanttTask {
  id: string;
  name: string;
  start: string;
  end: string;
  progress: number;
  dependencies: string;
  custom_class: string;
  wo: number;
  op: number;
  cl: string;
  resursa: string;
  status: string;
  client?: string;
  articol?: string;
}

interface SelectedOp {
  id: string;         // "wo-op"
  resultId?: number;  // PlanificareRezultat.id — needed for freeze/start APIs
  wo: number;
  op: number;
  cl: string;
  resursa: string;
  status: string;
  start: string;
  end: string;
  client?: string;
  articol?: string;
  frozen: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  planned:                  'Planificat',
  previzionat:              'Previzionat',
  previzionat_bt:           'Previzionat (BT lipsă)',
  previzionat_material:     'Previzionat (material insuficient)',
  previzionat_semifabricat: 'Previzionat (semifabricat în producție)',
  no_material:              'Fără material',
  no_resource:              'Fără resursă',
  no_bt:                    'Fără BT',
  blocked_by_rank:          'Blocat (rank)',
};

const PREVIZIONAT_STATUSES = new Set([
  'previzionat', 'previzionat_bt', 'previzionat_material', 'previzionat_semifabricat',
]);

function taskPlanStadiu(t: GanttTask): 'planificat' | 'previzionat' | 'other' {
  if (t.status === 'planned') return 'planificat';
  if (PREVIZIONAT_STATUSES.has(t.status)) return 'previzionat';
  return 'other';
}

function taskIsLate(t: GanttTask): boolean {
  return t.custom_class.includes('late');
}

export default function GanttView() {
  const wrapperRef   = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const ganttRef     = useRef<any>(null);

  const [tasks,       setTasks]       = useState<GanttTask[]>([]);
  const [planFilter,  setPlanFilter]  = useState<'all' | 'planificat' | 'previzionat'>('all');
  const [lateFilter,  setLateFilter]  = useState<'all' | 'late' | 'ontime'>('all');

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      if (planFilter === 'planificat'  && taskPlanStadiu(t) !== 'planificat')  return false;
      if (planFilter === 'previzionat' && taskPlanStadiu(t) !== 'previzionat') return false;
      if (lateFilter === 'late'   && !taskIsLate(t))  return false;
      if (lateFilter === 'ontime' &&  taskIsLate(t))  return false;
      return true;
    });
  }, [tasks, planFilter, lateFilter]);

  const [centreLucru, setCentreLucru] = useState<any[]>([]);
  const [selectedCL,  setSelectedCL]  = useState('');
  const [search,      setSearch]      = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [viewMode,    setViewMode]    = useState('Day');
  const [loading,     setLoading]     = useState(false);

  // Sidebar – selected operation
  const [selected,    setSelected]    = useState<SelectedOp | null>(null);
  const [editStart,   setEditStart]   = useState('');
  const [saving,      setSaving]      = useState(false);

  // Frozen list panel
  const [showFrozen,  setShowFrozen]  = useState(false);
  const [frozenOps,   setFrozenOps]   = useState<any[]>([]);
  const [frozenLoading, setFrozenLoading] = useState(false);

  useEffect(() => {
    api.getCentreLucru().then(setCentreLucru).catch(() => {});
  }, []);

  const loadGantt = useCallback(async () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (selectedCL) params.cl = selectedCL;
    if (search)     params.search = search;
    try {
      const data = await api.getGanttData(params);
      setTasks(data);
    } catch {
      setTasks([]);
    }
    setLoading(false);
  }, [selectedCL, search]);

  useEffect(() => { loadGantt(); }, [loadGantt]);

  const loadFrozen = async () => {
    setFrozenLoading(true);
    try { setFrozenOps(await api.getFrozenOps()); }
    catch { setFrozenOps([]); }
    setFrozenLoading(false);
  };

  const toggleFrozenPanel = () => {
    if (!showFrozen) loadFrozen();
    setShowFrozen(v => !v);
  };

  const scrollToToday = useCallback(() => {
    const wrapper = wrapperRef.current;
    const svgEl = containerRef.current?.querySelector('svg.gantt') as SVGElement | null;
    if (!wrapper || !svgEl) return;
    const todayEl = svgEl.querySelector('.current-highlight') as SVGElement | null;
    if (todayEl) {
      const x = parseFloat(todayEl.getAttribute('x') || '0') ||
        (() => { const m = (todayEl.getAttribute('transform') || '').match(/translate\(([^,)]+)/); return m ? parseFloat(m[1]) : 0; })();
      if (x > 0) { wrapper.scrollLeft = Math.max(0, x - wrapper.clientWidth / 2); return; }
    }
    const firstBar = svgEl.querySelector('.bar-wrapper rect.bar') as SVGRectElement | null;
    if (firstBar) wrapper.scrollLeft = Math.max(0, parseFloat(firstBar.getAttribute('x') || '0') - 100);
  }, []);

  const scrollPrev = useCallback(() => {
    if (wrapperRef.current) wrapperRef.current.scrollLeft -= wrapperRef.current.clientWidth * 0.75;
  }, []);

  const scrollNext = useCallback(() => {
    if (wrapperRef.current) wrapperRef.current.scrollLeft += wrapperRef.current.clientWidth * 0.75;
  }, []);

  // Build and render Gantt chart
  useEffect(() => {
    if (!containerRef.current || !wrapperRef.current || filteredTasks.length === 0) return;
    containerRef.current.innerHTML = '';

    // Use real times — no visual inflation, so dependency arrows render correctly (FS).
    // Short ops (< 1h) get a minimum of 1h so bars remain clickable.
    const ganttTasks = filteredTasks.map(t => {
      const startMs  = new Date(t.start.replace(' ', 'T')).getTime();
      const endMs    = new Date((t.end || t.start).replace(' ', 'T')).getTime();
      const minEndMs = startMs + 1 * 3600 * 1000; // 1h minimum so bar is clickable
      const realEnd  = endMs < minEndMs ? new Date(minEndMs) : new Date(endMs);
      const fmt = (d: Date) => d.toISOString().slice(0, 16).replace('T', ' ');
      return {
        id: t.id, name: t.name, start: t.start,
        end: fmt(realEnd), progress: t.progress,
        dependencies: t.dependencies || '',
        custom_class: t.custom_class,
      };
    });

    try {
      ganttRef.current = new Gantt(containerRef.current, ganttTasks, {
        view_mode: viewMode as any,
        date_format: 'YYYY-MM-DD HH:mm',
        bar_height: 24,
        bar_corner_radius: 3,
        padding: 14,
        on_click: async (task: any) => {
          const t = filteredTasks.find(x => x.id === task.id);
          if (!t) return;
          const isFrozen = t.custom_class.startsWith('bar-frozen');
          setSelected({
            id: t.id, resultId: undefined,
            wo: t.wo, op: t.op, cl: t.cl,
            resursa: t.resursa, status: t.status,
            start: t.start, end: t.end,
            client: t.client, articol: t.articol,
            frozen: isFrozen,
          });
          setEditStart(t.start);
          // Fetch resultId for freeze/unfreeze actions
          try {
            const ops = await api.getPlanningOperatii({ wo: String(t.wo) });
            const match = ops.find((o: any) => o.wo === t.wo && o.op === t.op);
            if (match) {
              setSelected(prev => prev ? { ...prev, resultId: match.id } : prev);
            }
          } catch { /* silent */ }
        },
      });

      const wrapper = wrapperRef.current;
      const handleWheel = (e: WheelEvent) => {
        e.stopPropagation(); e.preventDefault();
        wrapper.scrollTop  += e.deltaY;
        wrapper.scrollLeft += e.deltaX;
      };
      wrapper.addEventListener('wheel', handleWheel, { capture: true, passive: false });

      setTimeout(() => {
        const svgEl = containerRef.current?.querySelector('svg.gantt') as SVGElement | null;
        if (!svgEl || !wrapper) return;
        const todayEl = svgEl.querySelector('.current-highlight') as SVGElement | null;
        if (todayEl) {
          const x = parseFloat(todayEl.getAttribute('x') || '0') ||
            (() => { const m = (todayEl.getAttribute('transform') || '').match(/translate\(([^,)]+)/); return m ? parseFloat(m[1]) : 0; })();
          if (x > 0) { wrapper.scrollLeft = Math.max(0, x - wrapper.clientWidth / 2); return; }
        }
        const firstBar = svgEl.querySelector('.bar-wrapper rect.bar') as SVGRectElement | null;
        if (firstBar) wrapper.scrollLeft = Math.max(0, parseFloat(firstBar.getAttribute('x') || '0') - 100);
      }, 300);
    } catch (e) { console.error('Gantt render error:', e); }
  }, [filteredTasks, viewMode]);

  // --- Actions ---
  const handleSetStart = async () => {
    if (!selected || !editStart) return;
    setSaving(true);
    try {
      // Find result ID from planificare/operatii endpoint by wo+op
      const ops = await api.getPlanningOperatii({ wo: String(selected.wo) });
      const match = ops.find((o: any) => o.wo === selected.wo && o.op === selected.op);
      if (!match) { alert('Operatie negăsită în planificare'); setSaving(false); return; }
      await api.setOperatieStart(match.id, editStart);
      await loadGantt();
      setSelected(null);
    } catch (e: any) {
      alert('Eroare: ' + e.message);
    }
    setSaving(false);
  };

  const handleToggleFrozen = async (resultId: number, frozen: boolean) => {
    try {
      await api.toggleFrozen(resultId, !frozen);
      await loadFrozen();
      await loadGantt();
    } catch (e: any) { alert('Eroare: ' + e.message); }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
  };

  const LEGEND = [
    { color: '#16a34a', label: 'Planificat' },
    { color: '#2563eb', label: 'Previzionat (BT / material / semifabricat)' },
    { color: '#7c3aed', label: 'Frozen (în termen)' },
    { color: '#ea580c', label: 'Frozen (depășit termen)' },
    { color: '#dc2626', label: 'Întârziat față de livrare' },
  ];

  return (
    <div className="space-y-3">
      {/* ── Filters row ── */}
      <div className="flex flex-wrap gap-2 items-center">
        <select
          value={selectedCL}
          onChange={e => setSelectedCL(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm"
        >
          <option value="">Toate centrele de lucru</option>
          {centreLucru.filter(cl => cl.cl).map(cl => (
            <option key={cl.cl} value={cl.cl}>{cl.cl} – {cl.denumire}</option>
          ))}
        </select>

        <form onSubmit={handleSearch} className="flex gap-1">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="WO, client, articol..."
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              className="pl-8 pr-3 py-2 border border-slate-300 rounded-lg text-sm w-48"
            />
          </div>
          <button type="submit" className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm">
            Caută
          </button>
          {search && (
            <button type="button" onClick={() => { setSearch(''); setSearchInput(''); }}
              className="px-3 py-2 text-slate-500 hover:text-slate-700 text-sm underline">
              Șterge
            </button>
          )}
        </form>

        <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
          {['Half Day', 'Day', 'Week', 'Month'].map(mode => (
            <button key={mode} onClick={() => setViewMode(mode)}
              className={`px-3 py-1 rounded text-sm ${viewMode === mode ? 'bg-white shadow-sm font-medium' : 'text-slate-600'}`}>
              {mode}
            </button>
          ))}
        </div>

        {/* Navigation: prev / today / next */}
        <div className="flex items-center gap-1">
          <button onClick={scrollPrev}
            title="Înainte"
            className="p-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50">
            <ChevronLeft size={15} />
          </button>
          <button onClick={scrollToToday}
            title="Mergi la azi"
            className="flex items-center gap-1 px-3 py-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50 text-sm">
            <Calendar size={13} /> Azi
          </button>
          <button onClick={scrollNext}
            title="Înainte"
            className="p-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50">
            <ChevronRight size={15} />
          </button>
        </div>

        {/* ── Filtre 3 nivele ── */}
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-slate-500 font-medium">Plan:</span>
          {(['all', 'planificat', 'previzionat'] as const).map(v => (
            <button key={v} onClick={() => setPlanFilter(v)}
              className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                planFilter === v
                  ? v === 'planificat'  ? 'bg-green-100 border-green-400 text-green-700 font-medium'
                  : v === 'previzionat' ? 'bg-blue-100 border-blue-400 text-blue-700 font-medium'
                  : 'bg-slate-200 border-slate-400 text-slate-700 font-medium'
                  : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
              }`}>
              {v === 'all' ? 'Toate' : v === 'planificat' ? 'Planificat' : 'Previzionat'}
            </button>
          ))}
          <span className="text-slate-300 mx-1">|</span>
          <span className="text-xs text-slate-500 font-medium">Livrare:</span>
          {(['all', 'ontime', 'late'] as const).map(v => (
            <button key={v} onClick={() => setLateFilter(v)}
              className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                lateFilter === v
                  ? v === 'late'   ? 'bg-red-100 border-red-400 text-red-700 font-medium'
                  : v === 'ontime' ? 'bg-green-100 border-green-400 text-green-700 font-medium'
                  : 'bg-slate-200 border-slate-400 text-slate-700 font-medium'
                  : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
              }`}>
              {v === 'all' ? 'Toate' : v === 'ontime' ? 'La timp' : 'Întârziat'}
            </button>
          ))}
          {(planFilter !== 'all' || lateFilter !== 'all') && (
            <span className="text-xs text-slate-400 ml-1">
              {filteredTasks.length}/{tasks.length} op.
            </span>
          )}
        </div>

        <button onClick={loadGantt}
          title="Reîncarcă"
          className="p-2 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50">
          <RefreshCw size={15} />
        </button>

        <button onClick={toggleFrozenPanel}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border transition-colors
            ${showFrozen ? 'bg-violet-600 text-white border-violet-600' : 'border-violet-300 text-violet-700 hover:bg-violet-50'}`}>
          <Lock size={14} />
          Frozen ({frozenOps.length || '…'})
        </button>
      </div>

      {/* ── Legend ── */}
      <div className="flex flex-wrap gap-4 text-xs text-slate-600">
        {LEGEND.map(l => (
          <span key={l.label} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm inline-block flex-shrink-0" style={{ backgroundColor: l.color }} />
            {l.label}
          </span>
        ))}
      </div>

      {loading && <p className="text-slate-500 text-sm">Se încarcă...</p>}

      {/* ── Frozen ops panel ── */}
      {showFrozen && (
        <div className="bg-violet-50 border border-violet-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-violet-800 flex items-center gap-2">
              <Lock size={15} /> Operații Frozen
            </h3>
            <button onClick={() => setShowFrozen(false)} className="text-slate-400 hover:text-slate-600">
              <X size={15} />
            </button>
          </div>
          {frozenLoading ? (
            <p className="text-sm text-slate-500">Se încarcă...</p>
          ) : frozenOps.length === 0 ? (
            <p className="text-sm text-slate-500">Nicio operație frozen.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-violet-700 border-b border-violet-200">
                    <th className="text-left py-1 pr-3">WO</th>
                    <th className="text-left py-1 pr-3">OP</th>
                    <th className="text-left py-1 pr-3">Resursă</th>
                    <th className="text-left py-1 pr-3">Client</th>
                    <th className="text-left py-1 pr-3">Start</th>
                    <th className="text-left py-1 pr-3">Stop</th>
                    <th className="text-left py-1 pr-3">Ore</th>
                    <th className="py-1"></th>
                  </tr>
                </thead>
                <tbody>
                  {frozenOps.map((f: any) => (
                    <tr key={f.id} className="border-t border-violet-100">
                      <td className="py-1 pr-3 font-mono">{f.wo}</td>
                      <td className="py-1 pr-3 font-mono">{f.op}</td>
                      <td className="py-1 pr-3">{f.resursa_nume || '-'}</td>
                      <td className="py-1 pr-3 max-w-[150px] truncate" title={f.client}>{f.client || '-'}</td>
                      <td className="py-1 pr-3 font-mono whitespace-nowrap">{f.data_start || '-'}</td>
                      <td className="py-1 pr-3 font-mono whitespace-nowrap">{f.data_end || '-'}</td>
                      <td className="py-1 pr-3">{f.durata_ore?.toFixed(1)}</td>
                      <td className="py-1">
                        <button
                          onClick={() => handleToggleFrozen(f.id, true)}
                          className="flex items-center gap-1 px-2 py-0.5 bg-white border border-violet-300 text-violet-700 rounded hover:bg-violet-100 text-xs"
                        >
                          <Unlock size={11} /> Eliberează
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tasks.length === 0 && !loading && (
        <div className="bg-white rounded-lg shadow-sm p-8 text-center text-slate-500">
          Nu există operații planificate. Rulează planificarea din Dashboard.
        </div>
      )}

      {/* ── Main layout: Gantt + Sidebar ── */}
      <div className="flex gap-3" style={{ height: 'calc(100vh - 290px)', minHeight: '400px' }}>
        {/* Gantt */}
        <div ref={wrapperRef} className="bg-white rounded-lg shadow-sm p-2 overflow-auto flex-1">
          <div ref={containerRef} style={{ minWidth: '100%' }} />
        </div>

        {/* Sidebar – selected operation */}
        {selected && (
          <div className="w-72 bg-white rounded-lg shadow-sm p-4 flex flex-col gap-3 overflow-y-auto flex-shrink-0">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-semibold text-sm">WO {selected.wo} · OP {selected.op}</p>
                <p className="text-xs text-slate-500">{selected.cl} – {selected.resursa}</p>
              </div>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600">
                <X size={15} />
              </button>
            </div>

            {selected.client && (
              <div className="text-xs text-slate-600 space-y-0.5">
                <p><span className="font-medium">Client:</span> {selected.client}</p>
                {selected.articol && <p className="truncate" title={selected.articol}><span className="font-medium">Articol:</span> {selected.articol}</p>}
              </div>
            )}

            <div className="text-xs space-y-1 bg-slate-50 rounded p-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Start</span>
                <span className="font-mono">{selected.start}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Stop</span>
                <span className="font-mono">{selected.end}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Status</span>
                <span>{STATUS_LABEL[selected.status] || selected.status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Frozen</span>
                <span className={selected.frozen ? 'text-violet-700 font-medium' : 'text-slate-400'}>
                  {selected.frozen ? '🔒 Da' : 'Nu'}
                </span>
              </div>
            </div>

            {/* Unfreeze button — only when frozen */}
            {selected.frozen && selected.resultId && (
              <button
                onClick={async () => {
                  try {
                    await api.toggleFrozen(selected.resultId!, false);
                    await loadGantt();
                    setSelected(null);
                  } catch (e: any) { alert('Eroare: ' + e.message); }
                }}
                className="w-full py-1.5 bg-slate-100 text-slate-700 border border-slate-300 rounded text-xs font-medium hover:bg-slate-200 flex items-center justify-center gap-1"
              >
                <Unlock size={12} /> Elimină Freeze
              </button>
            )}

            {/* Manual start */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-slate-700">Setează start manual</p>
              <input
                type="datetime-local"
                value={editStart.replace(' ', 'T')}
                onChange={e => setEditStart(e.target.value.replace('T', ' '))}
                className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs"
                step="900"
              />
              <button
                onClick={handleSetStart}
                disabled={saving || !editStart}
                className="w-full py-1.5 bg-violet-600 text-white rounded text-xs font-medium hover:bg-violet-700 disabled:opacity-50 flex items-center justify-center gap-1"
              >
                <Lock size={12} />
                {saving ? 'Se salvează...' : 'Setează și Freeze'}
              </button>
              <p className="text-xs text-slate-400">Operația va fi frozen automat. Stop = Start + durată.</p>
            </div>

            <div className="border-t border-slate-100 pt-2">
              <button
                onClick={() => { setShowFrozen(true); loadFrozen(); setSelected(null); }}
                className="w-full py-1.5 border border-violet-200 text-violet-700 rounded text-xs hover:bg-violet-50 flex items-center justify-center gap-1"
              >
                <List size={12} /> Vezi toate frozen
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
