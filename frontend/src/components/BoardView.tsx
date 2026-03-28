import { useEffect, useRef, useState } from 'react';
// Use standalone build so Timeline + DataSet are bundled together
import { Timeline } from 'vis-timeline/standalone';
import { DataSet } from 'vis-data';
import { api } from '../api/client';

export default function BoardView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<any>(null);
  const [loading, setLoading] = useState(false);
  const [centreLucru, setCentreLucru] = useState<any[]>([]);
  const [selectedCL, setSelectedCL] = useState('');
  const [stats, setStats] = useState({ total: 0, late: 0, machines: 0 });

  useEffect(() => {
    api.getCentreLucru().then(setCentreLucru).catch(() => {});
  }, []);

  const loadBoard = async () => {
    setLoading(true);
    try {
      const data = await api.getBoardData();

      let groups = data.groups as any[];
      let items = data.items as any[];

      if (selectedCL) {
        groups = groups.filter((g: any) => g.cl === selectedCL);
        const gIds = new Set(groups.map((g: any) => g.id));
        items = items.filter((i: any) => gIds.has(i.group));
      }

      setStats({
        total: items.length,
        late: items.filter((i: any) => i.late).length,
        machines: groups.length,
      });

      renderTimeline(groups, items);
    } catch (e) {
      console.error('Board error:', e);
    }
    setLoading(false);
  };

  const renderTimeline = (groupsData: any[], itemsData: any[]) => {
    if (!containerRef.current) return;

    const groups = new DataSet(groupsData.map(g => ({
      id: g.id,
      content: `<div class="board-group-label">
        <span class="board-cl">${g.cl}</span>
        <span class="board-res">${g.content}</span>
      </div>`,
    })));

    const items = new DataSet(itemsData.map(i => ({
      id: i.id,
      group: i.group,
      start: new Date(i.start),
      end: new Date(i.end),
      content: `<span class="board-bar-text">${i.content}</span>`,
      title: i.title,  // tooltip HTML
      style: i.style,
    })));

    const now = new Date();

    // Dynamic height: fixed row height × number of groups, capped at viewport
    const ROW_H = 54;
    const HEADER_H = 44;
    const timelineH = Math.max(
      HEADER_H + groupsData.length * ROW_H,
      200
    );

    const options = {
      stack: false,
      showCurrentTime: true,
      orientation: { axis: 'top' as const },
      // No start/end — will call fit() so all items are visible
      min: new Date(now.getFullYear(), now.getMonth() - 3, 1),
      max: new Date(now.getFullYear(), now.getMonth() + 6, 1),
      zoomMin: 1000 * 60 * 60 * 2,
      zoomMax: 1000 * 60 * 60 * 24 * 90,
      timeAxis: { scale: 'hour' as const, step: 2 },
      tooltip: { followMouse: true, overflowMethod: 'cap' as const },
      groupOrder: (a: any, b: any) => a.id.localeCompare(b.id),
      margin: { item: { horizontal: 0, vertical: 2 } },
      groupHeightMode: 'fixed' as const,
      height: timelineH,
      zoomKey: 'ctrlKey',   // scroll = pan, Ctrl+scroll = zoom
      moveable: true,
      zoomable: true,
    } as any;

    if (timelineRef.current) {
      timelineRef.current.destroy();
    }
    timelineRef.current = new Timeline(containerRef.current, items, groups, options);

    // Auto-fit to show all items; if none, fall back to today ±4 days
    if (itemsData.length > 0) {
      timelineRef.current.fit({ animation: false });
      // Add 10% padding on each side
      setTimeout(() => {
        const tl = timelineRef.current;
        if (!tl) return;
        const w = tl.getWindow();
        const pad = (w.end.getTime() - w.start.getTime()) * 0.08;
        tl.setWindow(
          new Date(w.start.getTime() - pad),
          new Date(w.end.getTime() + pad),
          { animation: false }
        );
      }, 50);
    } else {
      const s = new Date(now); s.setDate(now.getDate() - 1); s.setHours(0, 0, 0, 0);
      const e = new Date(now); e.setDate(now.getDate() + 7); e.setHours(23, 59, 0, 0);
      timelineRef.current.setWindow(s, e, { animation: false });
    }
  };

  useEffect(() => {
    loadBoard();
    return () => {
      if (timelineRef.current) {
        timelineRef.current.destroy();
        timelineRef.current = null;
      }
    };
  }, [selectedCL]);

  const goToday = () => {
    if (timelineRef.current) {
      const now = new Date();
      const start = new Date(now); start.setHours(now.getHours() - 4);
      const end = new Date(now); end.setDate(now.getDate() + 3);
      timelineRef.current.setWindow(start, end, { animation: true });
    }
  };

  return (
    <div className="flex flex-col gap-3" style={{ height: 'calc(100vh - 140px)' }}>
      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={selectedCL}
          onChange={e => setSelectedCL(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm"
        >
          <option value="">Toate centrele de lucru</option>
          {centreLucru.map(cl => (
            <option key={cl.cl} value={cl.cl}>{cl.cl} – {cl.denumire}</option>
          ))}
        </select>

        <button onClick={loadBoard}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          Reincarca
        </button>

        <button onClick={goToday}
          className="px-3 py-2 bg-slate-100 text-slate-700 rounded-lg text-sm hover:bg-slate-200 border border-slate-300">
          ⏱ Azi
        </button>

        {/* Quick stats */}
        <div className="flex gap-3 ml-auto text-sm">
          <span className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg border border-blue-200">
            🖨 <b>{stats.machines}</b> mașini
          </span>
          <span className="px-3 py-1.5 bg-slate-50 text-slate-700 rounded-lg border border-slate-200">
            📋 <b>{stats.total}</b> operații
          </span>
          {stats.late > 0 && (
            <span className="px-3 py-1.5 bg-red-50 text-red-700 rounded-lg border border-red-200">
              ⚠ <b>{stats.late}</b> întârziate
            </span>
          )}
        </div>
      </div>

      {loading && <p className="text-slate-500 text-sm">Se incarca board-ul...</p>}

      {/* Legend */}
      <div className="flex gap-4 text-xs text-slate-600">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-blue-500 inline-block"></span> Planificat (culoare per CL)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-500 inline-block"></span> Întârziat
        </span>
        <span className="text-slate-400">Scroll: navighează stânga/dreapta · Ctrl+Scroll: zoom · Drag: pan</span>
      </div>

      {/* Board container — overflow-auto so many-group scenarios scroll vertically */}
      <div className="bg-white rounded-lg shadow-sm border border-slate-200 flex-1 overflow-auto">
        <div ref={containerRef} style={{ width: '100%' }} />
      </div>
    </div>
  );
}
