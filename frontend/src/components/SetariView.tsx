import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function SetariView() {
  const [threshold, setThreshold] = useState('0.01');
  const [loading,   setLoading]   = useState(false);
  const [saved,     setSaved]     = useState(false);

  useEffect(() => {
    api.getSetari()
      .then((s: Record<string, string>) => {
        if (s.material_threshold !== undefined) setThreshold(s.material_threshold);
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setLoading(true);
    setSaved(false);
    try {
      await api.updateSetari({ material_threshold: threshold });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      alert('Eroare la salvare');
    }
    setLoading(false);
  };

  return (
    <div className="max-w-lg space-y-6">
      <h2 className="text-lg font-semibold text-slate-800">Setări Planificare</h2>

      <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Prag ignorare material (cantitate / tiraj comandat)
          </label>
          <p className="text-xs text-slate-500 mb-2">
            Materialele cu consum per bucată ≤ prag sunt ignorate la verificarea stocului.
            Setează <code className="bg-slate-100 px-1 rounded">0</code> pentru a verifica toate materialele.
          </p>
          <div className="flex items-center gap-3">
            <input
              type="number"
              step="0.001"
              min="0"
              max="1"
              value={threshold}
              onChange={e => setThreshold(e.target.value)}
              className="w-32 px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
            <span className="text-xs text-slate-400">0.01 = ignoră dacă consum/tiraj ≤ 1%</span>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2 border-t border-slate-100">
          <button
            onClick={handleSave}
            disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Se salvează…' : 'Salvează'}
          </button>
          {saved && <span className="text-green-600 text-sm font-medium">✓ Salvat</span>}
        </div>
      </div>

      <p className="text-xs text-slate-400">
        Modificările se aplică la următoarea rulare a algoritmului de planificare.
      </p>
    </div>
  );
}
