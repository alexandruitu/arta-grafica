import { useEffect, useState } from 'react';
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

      {loading && <p className="text-slate-500 text-sm">Se incarca...</p>}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-3 py-2 text-left">Articol</th>
              <th className="px-3 py-2 text-right">Sold Actual</th>
              <th className="px-3 py-2 text-right">Total Rezervat</th>
              <th className="px-3 py-2 text-right">Disponibil</th>
              <th className="px-3 py-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {stoc.map((s, i) => (
              <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-2 font-mono text-xs">{s.articol}</td>
                <td className="px-3 py-2 text-right">{s.sold_actual?.toLocaleString('ro-RO')}</td>
                <td className="px-3 py-2 text-right">{s.total_rezervat?.toLocaleString('ro-RO')}</td>
                <td className={`px-3 py-2 text-right font-medium ${s.disponibil < 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {s.disponibil?.toLocaleString('ro-RO')}
                </td>
                <td className="px-3 py-2">
                  {s.disponibil < 0 ? (
                    <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">Deficit</span>
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
