import { useEffect, useState, useMemo } from 'react';
import { api } from '../api/client';
import { ChevronDown, ChevronRight, Search } from 'lucide-react';

export default function ComenziList() {
  const [comenzi, setComenzi] = useState<any[]>([]);
  const [_totalCount, setTotalCount] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [stadiuFilter, setStadiuFilter] = useState('');
  const [expandedCP, setExpandedCP] = useState<number | null>(null);
  const [operatii, setOperatii] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [planningMap, setPlanningMap] = useState<Record<string, any>>({});

  const loadComenzi = async () => {
    setLoading(true);
    const params: Record<string, string> = { limit: '2000' };
    if (search) params.search = search;
    // '__intarziate__' is a client-side pseudo-filter — never send to server
    if (statusFilter && statusFilter !== '__intarziate__') params.status = statusFilter;
    if (stadiuFilter) params.stadiu = stadiuFilter;
    try {
      const data = await api.getComenzi(params);
      setComenzi(data);
      setTotalCount(null);
    } catch { setComenzi([]); }
    setLoading(false);
  };

  useEffect(() => { loadComenzi(); }, [statusFilter, stadiuFilter]);

  useEffect(() => {
    api.getPlanningByComanda().then(setPlanningMap).catch(() => {});
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadComenzi();
  };

  const toggleExpand = async (cp: number) => {
    if (expandedCP === cp) { setExpandedCP(null); return; }
    setExpandedCP(cp);
    try {
      const ops = await api.getComandaOperatii(cp);
      setOperatii(ops);
    } catch { setOperatii([]); }
  };

  const stadiuColor = (stadiu: string | null) => {
    if (!stadiu) return 'bg-slate-100 text-slate-600';
    if (stadiu.startsWith('06')) return 'bg-green-100 text-green-700';
    if (stadiu.startsWith('05')) return 'bg-blue-100 text-blue-700';
    if (stadiu.startsWith('04')) return 'bg-cyan-100 text-cyan-700';
    if (stadiu.startsWith('03')) return 'bg-amber-100 text-amber-700';
    if (stadiu.startsWith('02')) return 'bg-orange-100 text-orange-700';
    return 'bg-slate-100 text-slate-600';
  };

  const statusPlanificareColor = (status: string) => {
    const map: Record<string, string> = {
      'Planificat': 'bg-green-100 text-green-700',
      'Previzionat': 'bg-blue-100 text-blue-700',
      'Partial': 'bg-cyan-100 text-cyan-700',
      'Blocat': 'bg-red-100 text-red-700',
    };
    return map[status] || 'bg-slate-100 text-slate-600';
  };

  const statusMaterialColor = (status: string) => {
    const map: Record<string, string> = {
      'Disponibil': 'bg-green-100 text-green-700',
      'In aprovizionare': 'bg-orange-100 text-orange-700',
      'Lipsa': 'bg-red-100 text-red-700',
    };
    return map[status] || 'bg-slate-100 text-slate-600';
  };

  const liveStats = useMemo(() => ({
    total:      comenzi.length,
    stadiu06:   comenzi.filter(c => c.stadiu_prepress === '06 - In productie').length,
    liber:      comenzi.filter(c => c.status_cda === 'LIBER').length,
    stop:       comenzi.filter(c => c.status_cda === 'STOP').length,
    intarziate: comenzi.filter(c => {
      const ps = planningMap[String(c.cp)];
      return ps?.intarziere_zile != null && ps.intarziere_zile > 0;
    }).length,
  }), [comenzi, planningMap]);

  const hasFilter = !!(search || statusFilter || stadiuFilter);

  const filteredComenzi = useMemo(() => {
    if (statusFilter !== '__intarziate__') return comenzi;
    return comenzi.filter(c => {
      const ps = planningMap[String(c.cp)];
      return ps?.intarziere_zile != null && ps.intarziere_zile > 0;
    });
  }, [comenzi, statusFilter, planningMap]);

  const overviewCards = [
    {
      label: hasFilter ? 'Rezultate filtrate' : 'Total comenzi',
      value: liveStats.total,
      color: 'bg-slate-100 text-slate-700 border-slate-200',
      active: !statusFilter && !stadiuFilter,
      onClick: () => { setStatusFilter(''); setStadiuFilter(''); },
    },
    {
      label: '06 – În producție',
      value: liveStats.stadiu06,
      color: 'bg-green-50 text-green-700 border-green-200',
      active: stadiuFilter === '06 - In productie',
      onClick: () => { setStadiuFilter('06 - In productie'); setStatusFilter(''); },
    },
    {
      label: 'LIBER',
      value: liveStats.liber,
      color: 'bg-blue-50 text-blue-700 border-blue-200',
      active: statusFilter === 'LIBER',
      onClick: () => { setStatusFilter('LIBER'); setStadiuFilter(''); },
    },
    {
      label: 'STOP',
      value: liveStats.stop,
      color: 'bg-red-50 text-red-700 border-red-200',
      active: statusFilter === 'STOP',
      onClick: () => { setStatusFilter('STOP'); setStadiuFilter(''); },
    },
    {
      label: 'Întârziate',
      value: liveStats.intarziate,
      color: 'bg-orange-50 text-orange-700 border-orange-200',
      active: statusFilter === '__intarziate__',
      onClick: () => { setStatusFilter('__intarziate__'); setStadiuFilter(''); },
    },
  ];

  // Split cards: status (exclusive) vs subsets (transversal)
  const statusCards  = overviewCards.slice(0, 4); // Total, 06, LIBER, STOP
  const subsetCards  = overviewCards.slice(4);    // Întârziate

  return (
    <div className="space-y-4">
      {/* ── Status breakdown (exclusive: LIBER + STOP = Total) ── */}
      <div className="flex flex-wrap gap-3 items-start">
        {statusCards.map(card => (
          <button
            key={card.label}
            onClick={card.onClick}
            className={`flex flex-col items-start px-4 py-3 rounded-xl border transition-all text-left min-w-[110px]
              ${card.color}
              ${card.active ? 'ring-2 ring-offset-1 ring-current shadow-sm' : 'hover:shadow-sm hover:brightness-95'}`}
          >
            <span className="text-2xl font-bold leading-tight">{card.value}</span>
            <span className="text-xs font-medium mt-0.5 opacity-80">{card.label}</span>
          </button>
        ))}

        {/* Divider + subset cards */}
        <div className="h-12 w-px bg-slate-200 self-center mx-1" />
        <div className="flex flex-col justify-center mr-1">
          <span className="text-[10px] text-slate-400 uppercase tracking-wide leading-none mb-1">Subseturi</span>
        </div>
        {subsetCards.map(card => (
          <button
            key={card.label}
            onClick={card.onClick}
            className={`flex flex-col items-start px-4 py-3 rounded-xl border transition-all text-left min-w-[110px]
              ${card.color}
              ${card.active ? 'ring-2 ring-offset-1 ring-current shadow-sm' : 'hover:shadow-sm hover:brightness-95'}`}
          >
            <span className="text-2xl font-bold leading-tight">{card.value}</span>
            <span className="text-xs font-medium mt-0.5 opacity-80">{card.label}</span>
          </button>
        ))}
      </div>

      <div className="flex gap-3 items-center">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1">
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Cauta comanda, articol, client..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-3 py-2 border border-slate-300 rounded-lg text-sm w-full"
            />
          </div>
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">
            Cauta
          </button>
        </form>
        <select
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setStadiuFilter(''); }}
          className="px-3 py-2 border border-slate-300 rounded-lg bg-white text-sm"
        >
          <option value="">Toate statusurile</option>
          <option value="LIBER">LIBER</option>
          <option value="STOP">STOP</option>
        </select>
        {(statusFilter || stadiuFilter) && (
          <button
            onClick={() => { setStatusFilter(''); setStadiuFilter(''); }}
            className="px-3 py-2 text-sm text-slate-500 hover:text-slate-700 underline"
          >
            Sterge filtru
          </button>
        )}
      </div>

      {loading && <p className="text-slate-500 text-sm">Se incarca...</p>}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 text-left w-8"></th>
                <th className="px-3 py-2 text-left">CP</th>
                <th className="px-3 py-2 text-left">CV</th>
                <th className="px-3 py-2 text-left">Client</th>
                <th className="px-3 py-2 text-left">Articol</th>
                <th className="px-3 py-2 text-left">Tip</th>
                <th className="px-3 py-2 text-left">Stadiu Prepress</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Cant.</th>
                <th className="px-3 py-2 text-left">Data Estimată</th>
                <th className="px-3 py-2 text-left">Data Livrare</th>
                <th className="px-3 py-2 text-left">Data Plan.</th>
                <th className="px-3 py-2 text-left">Intarziere</th>
                <th className="px-3 py-2 text-left">St. Plan.</th>
                <th className="px-3 py-2 text-left">St. Material</th>
                <th className="px-3 py-2 text-left">Plata</th>
              </tr>
            </thead>
            <tbody>
              {filteredComenzi.map(c => {
                const ps = planningMap[String(c.cp)];
                return (
                  <>
                    <tr
                      key={c.cp}
                      onClick={() => toggleExpand(c.cp)}
                      className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer"
                    >
                      <td className="px-3 py-2">
                        {expandedCP === c.cp ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </td>
                      <td className="px-3 py-2 font-mono font-medium">{c.cp || '-'}</td>
                      <td className="px-3 py-2 font-mono">{c.cv || '-'}</td>
                      <td className="px-3 py-2">{c.client}</td>
                      <td className="px-3 py-2 max-w-[200px] truncate" title={c.articol}>{c.articol}</td>
                      <td className="px-3 py-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs ${c.tip_comanda === 'V' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                          {c.tip_comanda === 'V' ? 'Vanzare' : 'Productie'}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${stadiuColor(c.stadiu_prepress)}`}>
                          {c.stadiu_prepress || '-'}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${c.status_cda === 'STOP' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                          {c.status_cda}
                        </span>
                      </td>
                      <td className="px-3 py-2">{c.cant_vnz}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs">{c.data_estimata_livrare || '-'}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{c.data_actualizata_livrare || c.dt_livr_prod || '-'}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs">
                        {ps?.data_planificare || <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs">
                        {ps?.intarziere_zile != null ? (
                          <span className={ps.intarziere_zile > 0 ? 'text-red-600 font-medium' : 'text-green-600'}>
                            {ps.intarziere_zile > 0 ? `+${ps.intarziere_zile}z` : `${ps.intarziere_zile}z`}
                          </span>
                        ) : <span className="text-slate-400">-</span>}
                      </td>
                      <td className="px-3 py-2">
                        {ps?.status_planificare ? (
                          <span className={`px-2 py-0.5 rounded text-xs ${statusPlanificareColor(ps.status_planificare)}`}>
                            {ps.status_planificare}
                          </span>
                        ) : <span className="text-slate-400 text-xs">-</span>}
                      </td>
                      <td className="px-3 py-2">
                        {ps?.status_material ? (
                          <span className={`px-2 py-0.5 rounded text-xs ${statusMaterialColor(ps.status_material)}`}>
                            {ps.status_material}
                          </span>
                        ) : <span className="text-slate-400 text-xs">-</span>}
                      </td>
                      <td className="px-3 py-2">
                        {c.val_de_platit > 0 && c.val_platita >= c.val_de_platit ? (
                          <span className="text-green-600 text-xs">Achitat</span>
                        ) : c.val_de_platit > 0 ? (
                          <span className="text-red-600 text-xs">Neachitat</span>
                        ) : (
                          <span className="text-slate-400 text-xs">-</span>
                        )}
                      </td>
                    </tr>
                    {expandedCP === c.cp && (
                      <tr key={`ops-${c.cp}`}>
                        <td colSpan={16} className="px-6 py-3 bg-slate-50">
                          <p className="text-xs font-semibold text-slate-600 mb-2">Operatii pentru WO {c.cp}:</p>
                          {operatii.length === 0 ? (
                            <p className="text-xs text-slate-400">Nicio operatie gasita</p>
                          ) : (
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-slate-500">
                                  <th className="text-left py-1">CL</th>
                                  <th className="text-left py-1">OP</th>
                                  <th className="text-left py-1">Descriere</th>
                                  <th className="text-left py-1">Resursă</th>
                                  <th className="text-left py-1">Start plan.</th>
                                  <th className="text-left py-1">Stop plan.</th>
                                  <th className="text-left py-1">Status</th>
                                  <th className="text-right py-1">P Runtime</th>
                                  <th className="text-right py-1">R Runtime</th>
                                  <th className="text-right py-1">Rest</th>
                                </tr>
                              </thead>
                              <tbody>
                                {operatii.map((op: any, i: number) => {
                                  const statusColors: Record<string, string> = {
                                    planned: 'text-green-600',
                                    previzionat: 'text-blue-600',
                                    no_material: 'text-red-500',
                                    no_resource: 'text-orange-500',
                                    no_bt: 'text-amber-500',
                                    blocked_by_rank: 'text-slate-500',
                                  };
                                  return (
                                  <tr key={i} className="border-t border-slate-200">
                                    <td className="py-1">{op.cl}</td>
                                    <td className="py-1 font-mono">{op.op}</td>
                                    <td className="py-1">{op.descr_op}</td>
                                    <td className="py-1 text-slate-600">{op.resursa_plan || '-'}</td>
                                    <td className="py-1 font-mono">{op.data_start_plan || '-'}</td>
                                    <td className="py-1 font-mono">{op.data_end_plan || '-'}</td>
                                    <td className={`py-1 text-xs ${statusColors[op.status_plan] || 'text-slate-400'}`}>
                                      {op.status_plan || '-'}
                                    </td>
                                    <td className="py-1 text-right">{op.p_runtime}</td>
                                    <td className="py-1 text-right">{op.r_runtime}</td>
                                    <td className="py-1 text-right font-medium">{op.q_rest}</td>
                                  </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
        {comenzi.length === 0 && !loading && (
          <p className="text-center py-8 text-slate-400">Nu exista date. Importa din Dashboard.</p>
        )}
      </div>
    </div>
  );
}
