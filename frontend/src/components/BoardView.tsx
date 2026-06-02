import { useEffect, useRef, useState, useMemo } from 'react';
import { Timeline } from 'vis-timeline/standalone';
import { DataSet } from 'vis-data';
import { api } from '../api/client';

interface SelectedOp {
  resultId: number;
  wo: number;
  op: number;
  cl: string;
  resursa: string;
  status: string;
  frozen: boolean;
  late: boolean;
  client: string;
  articol: string;
  start: string;
  end: string;
  durata_ore: number;
}

const LEGEND = [
  { color: '#16a34a', label: 'Planificat' },
  { color: '#2563eb', label: 'Previzionat (fără BT)' },
  { color: '#7c3aed', label: 'Frozen – posibil' },
  { color: '#ea580c', label: 'Frozen – imposibil' },
  { color: '#dc2626', label: 'Întârziat' },
];

export default function BoardView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef  = useRef<any>(null);

  const [loading, setLoading]         = useState(false);
  const [allGroups, setAllGroups]     = useState<any[]>([]);
  const [allItems,  setAllItems]      = useState<any[]>([]);
  const [centreLucru, setCentreLucru] = useState<any[]>([]);

  // Filters
  const [selectedCL,   setSelectedCL]   = useState('');
  const [search,       setSearch]       = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'late' | 'ontime'>('all');

  // Sidebar
  const [selectedOp,  setSelectedOp]  = useState<SelectedOp | null>(null);
  const [manualStart, setManualStart] = useState('');
  const [saving,      setSaving]      = useState(false);

  // Refs so the click handler (closed over at mount) always sees current data
  const filteredItemsRef  = useRef<any[]>([]);
  const filteredGroupsRef = useRef<any[]>([]);

  // ── Initial load ────────────────────────────────────────────────────────────
  useEffect(() => {
    api.getCentreLucru().then(setCentreLucru).catch(() => {});
    loadBoard();
    return () => {
      timelineRef.current?.destroy();
      timelineRef.current = null;
    };
  }, []);

  const loadBoard = async () => {
    setLoading(true);
    try {
      const data = await api.getBoardData();
      setAllGroups(data.groups as any[]);
      setAllItems(data.items  as any[]);
    } catch (e) {
      console.error('Board error:', e);
    }
    setLoading(false);
  };

  // ── Filtering (client-side) ─────────────────────────────────────────────────
  const filteredItems = useMemo(() => {
    const s = search.toLowerCase().trim();
    return allItems.filter(item => {
      if (selectedCL && item.cl !== selectedCL) return false;
      if (statusFilter === 'late'   && !item.late) return false;
      if (statusFilter === 'ontime' &&  item.late) return false;
      if (s) {
        const woMatch     = String(item.wo).includes(s);
        const clientMatch = (item.client  || '').toLowerCase().includes(s);
        const artMatch    = (item.articol || '').toLowerCase().includes(s);
        if (!woMatch && !clientMatch && !artMatch) return false;
      }
      return true;
    });
  }, [allItems, selectedCL, search, statusFilter]);

  const filteredGroups = useMemo(() => {
    const activeResIds = new Set(filteredItems.map(i => i.group));
    const activeCLKeys = new Set<string>();
    allGroups.forEach(g => {
      if (!g.isParent && activeResIds.has(g.id)) activeCLKeys.add(`cl__${g.cl}`);
    });
    return allGroups
      .filter(g => g.isParent ? activeCLKeys.has(g.id) : activeResIds.has(g.id))
      .map(g => {
        if (!g.isParent) return g;
        // Restrict nestedGroups to only active resource IDs — eliminates empty rows
        const activeNested = (g.nestedGroups || []).filter((id: string) => activeResIds.has(id));
        return { ...g, nestedGroups: activeNested };
      });
  }, [allGroups, filteredItems]);

  // Keep refs in sync
  filteredItemsRef.current  = filteredItems;
  filteredGroupsRef.current = filteredGroups;

  const stats = useMemo(() => ({
    total:    filteredItems.length,
    late:     filteredItems.filter(i => i.late).length,
    machines: filteredGroups.filter(g => !g.isParent).length,
  }), [filteredItems, filteredGroups]);

  // ── Render / update vis-timeline ────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    const groups = new DataSet(filteredGroups.map(g => {
      if (g.isParent) {
        return {
          id: g.id,
          content: `<div class="board-cl-parent">${g.content}</div>`,
          nestedGroups: g.nestedGroups,
        };
      }
      return {
        id: g.id,
        content: `<div class="board-group-label">
          <span class="board-cl">${g.cl}</span>
          <span class="board-res">${g.content}</span>
        </div>`,
      };
    }));

    const items = new DataSet(filteredItems.map(i => ({
      id:      i.id,
      group:   i.group,
      start:   new Date(i.start),
      end:     new Date(i.end),
      content: `<span class="board-bar-text">${i.content}${i.frozen ? ' 🔒' : ''}</span>`,
      title:   i.title,
      style:   i.style,
    })));

    // ── Update existing timeline (preserves window position) ────────────────
    if (timelineRef.current) {
      timelineRef.current.setData({ groups, items });
      return;
    }

    // ── Create timeline ─────────────────────────────────────────────────────
    const now = new Date();
    const options: any = {
      stack:           false,
      showCurrentTime: true,
      orientation:     { axis: 'top' },
      min: new Date(now.getFullYear(), now.getMonth() - 1, 1),
      max: new Date(now.getFullYear(), now.getMonth() + 6, 1),
      zoomMin:         1000 * 60 * 60 * 2,
      zoomMax:         1000 * 60 * 60 * 24 * 90,
      timeAxis:        { scale: 'hour', step: 4 },
      tooltip:         { followMouse: true, overflowMethod: 'cap' },
      margin:          { item: { horizontal: 0, vertical: 2 } },
      groupHeightMode: 'fixed',
      height:          '100%',
      zoomKey:         'ctrlKey',
      moveable:        true,
      zoomable:        true,
      verticalScroll:  true,
    };

    const tl = new Timeline(containerRef.current, items, groups, options);
    timelineRef.current = tl;

    // Click handler uses refs — always sees current data
    tl.on('click', (props: any) => {
      if (!props.item) { setSelectedOp(null); return; }
      const item  = filteredItemsRef.current.find((i: any) => i.id === props.item);
      if (!item) return;
      const group = filteredGroupsRef.current.find((g: any) => g.id === item.group);
      setSelectedOp({
        resultId:  item.result_id,
        wo:        item.wo,
        op:        item.op,
        cl:        item.cl,
        resursa:   group?.content || '',
        status:    item.status,
        frozen:    item.frozen,
        late:      item.late,
        client:    item.client  || '',
        articol:   item.articol || '',
        start:     item.start,
        end:       item.end,
        durata_ore: item.durata_ore,
      });
      setManualStart(item.start.replace('T', ' ').substring(0, 16));
    });

    // Initial fit
    if (filteredItems.length > 0) {
      setTimeout(() => {
        if (!timelineRef.current) return;
        tl.fit({ animation: false });
        const w = tl.getWindow();
        const pad = (w.end.getTime() - w.start.getTime()) * 0.05;
        tl.setWindow(
          new Date(w.start.getTime() - pad),
          new Date(w.end.getTime() + pad),
          { animation: false }
        );
      }, 100);
    }
  }, [filteredGroups, filteredItems]);

  // ── Zoom helpers ─────────────────────────────────────────────────────────────
  const goToday = () => {
    if (!timelineRef.current) return;
    const now = new Date();
    const s = new Date(now); s.setHours(6,  0, 0, 0);
    const e = new Date(now); e.setHours(22, 0, 0, 0);
    timelineRef.current.setWindow(s, e, { animation: true });
  };

  const goWeek = () => {
    if (!timelineRef.current) return;
    const now = new Date();
    const s = new Date(now); s.setHours(0, 0, 0, 0);
    const e = new Date(s);   e.setDate(s.getDate() + 7);
    timelineRef.current.setWindow(s, e, { animation: true });
  };

  // ── Sidebar actions ──────────────────────────────────────────────────────────
  const handleSetStart = async () => {
    if (!selectedOp || !manualStart) return;
    setSaving(true);
    try {
      await api.setOperatieStart(selectedOp.resultId, manualStart);
      setSelectedOp(null);
      await loadBoard();
    } catch (e: any) {
      alert('Eroare: ' + (e.message || e));
    }
    setSaving(false);
  };

  const handleToggleFrozen = async () => {
    if (!selectedOp) return;
    setSaving(true);
    try {
      await api.toggleFrozen(selectedOp.resultId, !selectedOp.frozen);
      setSelectedOp(null);
      await loadBoard();
    } catch (e: any) {
      alert('Eroare: ' + (e.message || e));
    }
    setSaving(false);
  };

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-3" style={{ height: 'calc(100vh - 140px)' }}>

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* CL filter */}
        <select value={selectedCL} onChange={e => setSelectedCL(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm">
          <option value="">Toate CL</option>
          {centreLucru.filter(cl => cl.cl).map(cl => (
            <option key={cl.cl} value={cl.cl}>{cl.cl} – {cl.denumire}</option>
          ))}
        </select>

        {/* Search */}
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Caută WO, client, articol…"
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-52" />

        {/* Status filter */}
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value as any)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm">
          <option value="all">Toate comenzile</option>
          <option value="late">Întârziate</option>
          <option value="ontime">Neîntârziate</option>
        </select>

        {/* Actions */}
        <button onClick={loadBoard}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 font-medium">
          ↺ Reîncarcă
        </button>

        {/* Zoom */}
        <div className="flex gap-1">
          <button onClick={goToday}
            className="px-3 py-2 bg-slate-100 text-slate-700 rounded-lg text-sm hover:bg-slate-200 border border-slate-300">
            Azi
          </button>
          <button onClick={goWeek}
            className="px-3 py-2 bg-slate-100 text-slate-700 rounded-lg text-sm hover:bg-slate-200 border border-slate-300">
            7 zile
          </button>
        </div>

        {/* Stats */}
        <div className="flex gap-2 ml-auto text-sm">
          <span className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg border border-blue-200">
            🖨 <b>{stats.machines}</b> mașini
          </span>
          <span className="px-3 py-1.5 bg-slate-50 text-slate-700 rounded-lg border border-slate-200">
            📋 <b>{stats.total}</b> op.
          </span>
          {stats.late > 0 && (
            <span className="px-3 py-1.5 bg-red-50 text-red-700 rounded-lg border border-red-200">
              ⚠ <b>{stats.late}</b> întârziate
            </span>
          )}
        </div>
      </div>

      {loading && <p className="text-slate-500 text-sm">Se încarcă board-ul…</p>}

      {/* ── Legend ── */}
      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
        {LEGEND.map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded inline-block" style={{ background: color }} />
            {label}
          </span>
        ))}
        <span className="text-slate-400 ml-1">
          Scroll: pan · Ctrl+Scroll: zoom · Click bara: detalii
        </span>
      </div>

      {/* ── Main area: board + sidebar ── */}
      <div className="flex gap-3 flex-1 min-h-0">

        {/* Timeline */}
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 flex-1 min-w-0 overflow-hidden">
          <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
        </div>

        {/* Sidebar */}
        {selectedOp && (
          <div className="w-72 bg-white rounded-lg shadow-sm border border-slate-200 p-4
                          flex flex-col gap-3 overflow-y-auto flex-shrink-0">

            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-800">Detalii operație</h3>
              <button onClick={() => setSelectedOp(null)}
                className="text-slate-400 hover:text-slate-600 text-xl leading-none">✕</button>
            </div>

            {/* Op details */}
            <div className="space-y-1.5">
              {([
                ['WO',     selectedOp.wo],
                ['OP',     selectedOp.op],
                ['CL',     selectedOp.cl],
                ['Client', selectedOp.client  || '—'],
                ['Articol', selectedOp.articol || '—'],
                ['Start',  selectedOp.start.replace('T', ' ').substring(0, 16)],
                ['Stop',   selectedOp.end.replace('T',   ' ').substring(0, 16)],
                ['Durata', `${selectedOp.durata_ore.toFixed(1)} h`],
                ['Status', selectedOp.status],
              ] as [string, any][]).map(([k, v]) => (
                <div key={k} className="flex gap-2">
                  <span className="text-slate-500 w-16 flex-shrink-0 text-xs">{k}:</span>
                  <span className="text-slate-800 font-medium text-xs break-all">{v}</span>
                </div>
              ))}
              <div className="flex gap-1.5 flex-wrap mt-1">
                {selectedOp.frozen && (
                  <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs font-semibold">
                    🔒 Frozen
                  </span>
                )}
                {selectedOp.late && (
                  <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs font-semibold">
                    ⚠ Întârziat
                  </span>
                )}
              </div>
            </div>

            {/* Manual start */}
            <div className="border-t pt-3">
              <p className="text-xs text-slate-500 mb-1.5 font-medium">
                Reprogramare + freeze
              </p>
              <input type="datetime-local" value={manualStart}
                onChange={e => setManualStart(e.target.value)}
                className="w-full px-2 py-1.5 border border-slate-300 rounded text-sm mb-2" />
              <button onClick={handleSetStart} disabled={saving || !manualStart}
                className="w-full py-2 bg-blue-600 text-white rounded text-sm
                           hover:bg-blue-700 disabled:opacity-50 font-medium">
                {saving ? 'Se salvează…' : '📌 Setează și Freeze'}
              </button>
            </div>

            {/* Unfreeze */}
            {selectedOp.frozen && (
              <button onClick={handleToggleFrozen} disabled={saving}
                className="w-full py-2 bg-orange-100 text-orange-700 border border-orange-300
                           rounded text-sm hover:bg-orange-200 disabled:opacity-50 font-medium">
                🔓 Eliberează Freeze
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
