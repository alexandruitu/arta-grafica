import { useEffect, useRef, useState } from 'react';
// @ts-ignore – frappe-gantt has no type declarations
import Gantt from 'frappe-gantt';
import { api } from '../api/client';

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
}

export default function GanttView() {
  const wrapperRef = useRef<HTMLDivElement>(null);   // scrollable outer div
  const containerRef = useRef<HTMLDivElement>(null); // frappe-gantt target
  const ganttRef = useRef<any>(null);
  const [tasks, setTasks] = useState<GanttTask[]>([]);
  const [centreLucru, setCentreLucru] = useState<any[]>([]);
  const [selectedCL, setSelectedCL] = useState('');
  const [searchWO, setSearchWO] = useState('');
  const [viewMode, setViewMode] = useState('Half Day');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getCentreLucru().then(setCentreLucru).catch(() => {});
  }, []);

  const loadGantt = async () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (selectedCL) params.cl = selectedCL;
    if (searchWO) params.wo = searchWO;
    try {
      const data = await api.getGanttData(params);
      setTasks(data);
    } catch {
      setTasks([]);
    }
    setLoading(false);
  };

  useEffect(() => { loadGantt(); }, [selectedCL, searchWO]);

  useEffect(() => {
    if (!containerRef.current || !wrapperRef.current || tasks.length === 0) return;

    containerRef.current.innerHTML = '';

    const ganttTasks = tasks.map(t => ({
      id: t.id,
      name: t.name,
      start: t.start,
      end: t.end || t.start,
      progress: t.progress,
      dependencies: t.dependencies || '',
      custom_class: t.custom_class,
    }));

    try {
      ganttRef.current = new Gantt(containerRef.current, ganttTasks, {
        view_mode: viewMode as any,
        date_format: 'YYYY-MM-DD HH:mm',
        bar_height: 24,
        bar_corner_radius: 3,
        padding: 14,
        on_click: (task: any) => {
          const t = tasks.find(x => x.id === task.id);
          if (t) {
            alert(`WO: ${t.wo}\nOP: ${t.op} (${t.cl})\nResursa: ${t.resursa}\nStart: ${t.start}\nEnd: ${t.end}`);
          }
        },
      });

      const wrapper = wrapperRef.current;

      // Intercept wheel events: both axes scroll the gantt wrapper, not the page
      const handleWheel = (e: WheelEvent) => {
        e.stopPropagation();
        e.preventDefault();
        wrapper.scrollTop += e.deltaY;
        wrapper.scrollLeft += e.deltaX;
      };
      wrapper.addEventListener('wheel', handleWheel, { capture: true, passive: false });

      // Scroll wrapper to today after render
      setTimeout(() => {
        const svgEl = containerRef.current?.querySelector('svg.gantt') as SVGElement | null;
        if (!svgEl || !wrapper) return;

        // Find today marker (rect or g element) and scroll to it
        const todayEl = svgEl.querySelector('.current-highlight') as SVGElement | null;
        if (todayEl) {
          const x = parseFloat(todayEl.getAttribute('x') || '0') ||
                    (() => {
                      const m = (todayEl.getAttribute('transform') || '').match(/translate\(([^,)]+)/);
                      return m ? parseFloat(m[1]) : 0;
                    })();
          if (x > 0) {
            wrapper.scrollLeft = Math.max(0, x - wrapper.clientWidth / 2);
            return;
          }
        }
        // Fallback: scroll to first bar
        const firstBar = svgEl.querySelector('.bar-wrapper rect.bar') as SVGRectElement | null;
        if (firstBar) {
          wrapper.scrollLeft = Math.max(0, parseFloat(firstBar.getAttribute('x') || '0') - 100);
        }
      }, 300);

    } catch (e) {
      console.error('Gantt render error:', e);
    }
  }, [tasks, viewMode]);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
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

        <input
          type="text"
          placeholder="Cauta WO..."
          value={searchWO}
          onChange={e => setSearchWO(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-40"
        />

        <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
          {['Half Day', 'Day', 'Week', 'Month'].map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-3 py-1 rounded text-sm ${
                viewMode === mode ? 'bg-white shadow-sm font-medium' : 'text-slate-600'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>

        <button
          onClick={loadGantt}
          className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          Reincarca
        </button>
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-sm">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-blue-500 inline-block"></span> Planificat
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-500 inline-block"></span> Intarziat
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-indigo-500 inline-block"></span> Frozen
        </span>
      </div>

      {loading && <p className="text-slate-500 text-sm">Se incarca...</p>}

      {tasks.length === 0 && !loading && (
        <div className="bg-white rounded-lg shadow-sm p-8 text-center text-slate-500">
          Nu exista operatii planificate. Ruleaza planificarea din Dashboard.
        </div>
      )}

      {/* Gantt chart: wrapperRef scrolls in both directions, containerRef holds the SVG */}
      <div
        ref={wrapperRef}
        className="bg-white rounded-lg shadow-sm p-2 overflow-auto"
        style={{ height: 'calc(100vh - 280px)', minHeight: '400px' }}
      >
        <div ref={containerRef} style={{ minWidth: '100%' }} />
      </div>
    </div>
  );
}
