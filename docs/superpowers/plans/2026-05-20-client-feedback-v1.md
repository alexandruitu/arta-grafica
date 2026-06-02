# Client Feedback V1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rezolvă 5 bug-uri confirmate și implementează 2 funcționalități noi (filtrare 3 nivele Gantt + Board) din feedback-ul clientului, fără a atinge cele 2 întrebări pendinte (Î3 consum/unitate, Î5 frozen-posibil/imposibil).

**Architecture:** Modificări în 3 straturi independente: (1) backend Python — timezone fix în planner.py + fly.toml; (2) frontend React — GanttView.tsx pentru săgeți și filtre; (3) frontend React — BoardView.tsx + PlanningList.tsx pentru bug-uri UI. Fiecare task este auto-conținut și poate fi comis separat.

**Tech Stack:** FastAPI/Python 3.11+, React 18 + TypeScript + TailwindCSS, frappe-gantt, vis-timeline, SQLite/SQLAlchemy, Fly.io (deploy)

---

## File Map

| Fișier | Ce se schimbă |
|---|---|
| `fly.toml` | Adaugă `TZ = "Europe/Bucharest"` în `[env]` |
| `backend/planner.py` | `datetime.now()` → `datetime.now(tz_ro)` cu `ZoneInfo` |
| `backend/main.py` | `datetime.now()` în sesiune + timestamps în gantt/board |
| `frontend/src/components/GanttView.tsx` | Elimină MIN_VISUAL_HOURS; adaugă filtre 3 nivele |
| `frontend/src/components/BoardView.tsx` | Fix nestedGroups; extinde filtrare la 3 dimensiuni |
| `frontend/src/components/PlanningList.tsx` | Stats din `allResults`; fix overflow tabel |

---

## Task 1: Fix Timezone — Europe/Bucharest

**Problema:** Serverul Fly.io rulează în UTC. `datetime.now()` returnează ora UTC. România e UTC+2 (iarnă) / UTC+3 (vară). Toate orele planificate sunt afișate cu 2-3h mai devreme.

**Soluție:** Setează `TZ=Europe/Bucharest` în fly.toml (simplest fix) ȘI folosește `ZoneInfo("Europe/Bucharest")` în cod pentru robustețe.

**Files:**
- Modify: `fly.toml`
- Modify: `backend/planner.py:19,168,345`
- Modify: `backend/main.py:168` (și oriunde alt `datetime.now()`)

- [ ] **Step 1: Adaugă TZ în fly.toml**

```toml
[env]
  DATA_DIR = "/data"
  PORT     = "8080"
  TZ       = "Europe/Bucharest"
```

- [ ] **Step 2: Actualizează planner.py să folosească ZoneInfo**

La linia 19, modifică importul:
```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ_RO = ZoneInfo("Europe/Bucharest")
```

Înlocuiește TOATE aparițiile `datetime.now()` din planner.py cu `datetime.now(TZ_RO)`:

Linia 168:
```python
created_at=datetime.now(TZ_RO),
```

Linia 345-356 (blocul now/today):
```python
now = datetime.now(TZ_RO)
today = now.date()
shift_start_today = datetime(today.year, today.month, today.day, SHIFT_START_H, tzinfo=TZ_RO)
shift_end_today   = datetime(today.year, today.month, today.day, SHIFT_END_H,   tzinfo=TZ_RO)
if now < shift_start_today:
    today_dt = shift_start_today
elif now >= shift_end_today:
    next_day = today + timedelta(days=1)
    today_dt = datetime(next_day.year, next_day.month, next_day.day, SHIFT_START_H, tzinfo=TZ_RO)
else:
    today_dt = now.replace(second=0, microsecond=0)
```

Atenție: `find_slot_precise` creează `datetime` fără tz la liniile 125-128 și 137-140. Adaugă `tzinfo=TZ_RO` la toate:
```python
slot_start = datetime(
    check_date.year, check_date.month, check_date.day,
    start_hour, start_minute, tzinfo=TZ_RO,
)
# ... și la slot_end
slot_end = datetime(
    check_date.year, check_date.month, check_date.day,
    end_hour, end_minute, tzinfo=TZ_RO,
)
# ... și la linia 148:
slot_end = datetime(
    check_date.year, check_date.month, check_date.day,
    SHIFT_END_H, 0, tzinfo=TZ_RO,
)
```

- [ ] **Step 3: Actualizează main.py — sesiune created_at**

Caută toate `datetime.now()` în main.py:
```bash
grep -n "datetime.now" backend/main.py
```

Adaugă la importuri (linia 1 din main.py):
```python
from zoneinfo import ZoneInfo
TZ_RO = ZoneInfo("Europe/Bucharest")
```

Înlocuiește fiecare `datetime.now()` cu `datetime.now(TZ_RO)`.

- [ ] **Step 4: Verificare locală**

```bash
cd backend
TZ=Europe/Bucharest python3 -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('Europe/Bucharest')))"
```

Expected output: ora curentă Bucuresti (UTC+3 vara, UTC+2 iarna).

- [ ] **Step 5: Commit**

```bash
git add fly.toml backend/planner.py backend/main.py
git commit -m "fix: set timezone to Europe/Bucharest in planner and server config

All datetime.now() calls now use ZoneInfo('Europe/Bucharest').
fly.toml sets TZ=Europe/Bucharest at OS level for full coverage."
```

---

## Task 2: Fix Gantt — Săgeți STOP→START corecte

**Problema:** `MIN_VISUAL_HOURS = 4` extinde bara vizuală a operației. frappe-gantt calculează originea săgeții din capătul drept al barei afișate. Dacă bara vizuală depășește startul operației dependente, săgeata merge înapoi (de la dreapta spre stânga), ceea ce arată eronat.

Exemplu:
- Op A: start 08:00, end real 10:00, end vizual 12:00 (min 4h)
- Op B: start 10:00 (după A)
- Săgeata pleacă din 12:00 → ajunge la 10:00 → merge stânga = GREȘIT

**Soluție:** Elimină `MIN_VISUAL_HOURS`. Operațiile scurte vor fi vizualizate cu bare mici — corect din punct de vedere temporal. Alternativ, aplică minimum vizual doar pe `name` tooltip, nu pe bara reală.

**Files:**
- Modify: `frontend/src/components/GanttView.tsx:128-149`

- [ ] **Step 1: Înlocuiește blocul ganttTasks (liniile ~128-149)**

Înainte:
```tsx
const MIN_VISUAL_HOURS = 4;
const ganttTasks = tasks.map(t => {
  const startMs = new Date(t.start.replace(' ', 'T')).getTime();
  const endMs   = new Date((t.end || t.start).replace(' ', 'T')).getTime();
  const minEndMs = startMs + MIN_VISUAL_HOURS * 3600 * 1000;
  const visualEnd = endMs < minEndMs ? new Date(minEndMs) : new Date(endMs);
  const fmt = (d: Date) =>
    d.toISOString().slice(0, 16).replace('T', ' ');
  return {
    id: t.id, name: t.name, start: t.start,
    end: fmt(visualEnd), progress: t.progress,
    dependencies: t.dependencies || '',
    custom_class: t.custom_class,
  };
});
```

După (folosește timpii reali fără ajustare vizuală):
```tsx
// Use real times — no visual inflation, so dependency arrows render correctly (FS).
// Short ops (< 1h) get a minimum of 1h so bars remain clickable.
const ganttTasks = tasks.map(t => {
  const startMs = new Date(t.start.replace(' ', 'T')).getTime();
  const endMs   = new Date((t.end || t.start).replace(' ', 'T')).getTime();
  const minEndMs = startMs + 1 * 3600 * 1000; // 1h minimum so bar is clickable
  const realEnd = endMs < minEndMs ? new Date(minEndMs) : new Date(endMs);
  const fmt = (d: Date) => d.toISOString().slice(0, 16).replace('T', ' ');
  return {
    id: t.id, name: t.name, start: t.start,
    end: fmt(realEnd), progress: t.progress,
    dependencies: t.dependencies || '',
    custom_class: t.custom_class,
  };
});
```

- [ ] **Step 2: Verificare vizuală**

Rebuild și verifică în browser că:
1. Săgețile merg de la dreapta barei operației spre stânga barei succesorului
2. Nu mai există săgeți care merg înapoi (dreapta → stânga pe același rând temporal)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/GanttView.tsx
git commit -m "fix: Gantt arrows STOP→START — use real end times, not inflated visual

MIN_VISUAL_HOURS=4 caused predecessor bars to visually extend past
successor start, making frappe-gantt draw arrows backwards (right→left).
Replaced with 1h minimum (keeps bars clickable) while preserving FS arrows."
```

---

## Task 3: Fix Board Mașini — Prima parte goală la filtrare

**Problema:** La filtrare după CL, grupurile parent (CL headers) au `nestedGroups: [res_id_1, res_id_2, ...]` cu TOATE resursele acelui CL. Când unele resurse sunt filtrate out (nu au items vizibile), vis-timeline încearcă să randeze rânduri pentru groupuri care nu mai există în DataSet → apare spațiu gol în partea de sus.

**Soluție:** Când construim `filteredGroups`, actualizăm și `nestedGroups` pe fiecare parent să conțină DOAR resursele active (cu items vizibile).

**Files:**
- Modify: `frontend/src/components/BoardView.tsx:92-101`

- [ ] **Step 1: Actualizează `filteredGroups` useMemo**

Înlocuiește blocul existent (liniile ~92-101):

```tsx
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
      // Restrict nestedGroups to only active resource IDs → eliminates empty rows
      const activeNested = (g.nestedGroups || []).filter((id: string) => activeResIds.has(id));
      return { ...g, nestedGroups: activeNested };
    });
}, [allGroups, filteredItems]);
```

- [ ] **Step 2: Verificare vizuală**

1. Deschide Board Mașini
2. Selectează un CL cu mai puțin de 5 resurse
3. Verifică că nu există rânduri goale în partea de sus a timeline-ului

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BoardView.tsx
git commit -m "fix: Board filter — remove empty rows by trimming nestedGroups

When filtering by CL, parent group nestedGroups referenced resource IDs
no longer in the DataSet, causing vis-timeline to render blank rows.
Now filteredGroups trims nestedGroups to only active resource IDs."
```

---

## Task 4: Fix PlanningList — Contoarele nu se modifică la filtrare

**Problema:** `stats` este calculat din `filteredResults` (linia 144: `useMemo(() => {...}, [filteredResults])`). Când utilizatorul dă click pe un card (ex: "Planificate"), `selectedStatus` se setează, `filteredResults` se reduce, și toate contoarele se resetează la 0 sau valori parțiale. Aceasta e confuzant.

**Soluție:** Calculează `stats` din `allResults` (toate op. pentru CL-ul curent), nu din `filteredResults`. Contoarele rămân stabile la filtrare status/resursă/search.

**Files:**
- Modify: `frontend/src/components/PlanningList.tsx:144-155`

- [ ] **Step 1: Schimbă dependența useMemo pentru stats**

Înlocuiește (liniile ~144-155):
```tsx
// ── Stats computed from filtered results (2.5) ─────────────────────────────
const stats = useMemo(() => {
  const planned     = filteredResults.filter(r => r.status === 'planned').length;
  const previzionat = filteredResults.filter(r => PREVIZIONAT_SET.has(r.status)).length;
  const no_material = filteredResults.filter(r => r.status === 'no_material').length;
  const no_bt       = filteredResults.filter(r => r.status === 'no_bt').length;
  const blocked     = filteredResults.filter(r => r.status === 'blocked_by_rank').length;
  const no_resource = filteredResults.filter(r => r.status === 'no_resource').length;
  const ore         = filteredResults
    .filter(r => PLACED_SET.has(r.status))
    .reduce((s, r) => s + (r.durata_ore || 0), 0);
  return { total: filteredResults.length, planned, previzionat, no_material, no_bt, blocked, no_resource, ore };
}, [filteredResults]);
```

Cu:
```tsx
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
}, [allResults]);  // ← allResults, not filteredResults
```

- [ ] **Step 2: Fix overflow tabel (durata trunchiată dreapta)**

La linia ~303, înlocuiește:
```tsx
<div className="bg-white rounded-lg shadow-sm overflow-hidden">
  <div className="overflow-x-auto">
```

Cu:
```tsx
<div className="bg-white rounded-lg shadow-sm">
  <div className="overflow-x-auto rounded-lg">
```

`overflow-hidden` pe container exterior bloca scroll-ul orizontal al tabelului, trunchiind coloanele din dreapta (Stop, Durata).

- [ ] **Step 3: Verificare**

1. Deschide tabul Planificare
2. Verifică că cifrele din carduri nu se schimbă când aplici filtre de status/resursă
3. Verifică că tabelul e scrollabil orizontal și coloana "Durata (h)" e vizibilă

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PlanningList.tsx
git commit -m "fix: PlanningList — stable counters + fix table overflow clipping

Stats cards now compute from allResults (CL-filtered) not filteredResults,
so counters stay stable when user filters by status/resource/search.
Removed overflow-hidden from table container — was clipping horizontal scroll
and hiding the Stop/Durata columns on narrow screens."
```

---

## Task 5: Gantt — 3 Nivele de Filtrare

**Cerință:** Adaugă 3 seturi de filtre în Gantt:
1. **Stadiu planificare**: PLANIFICAT / PREVIZIONAT (din câmpul `status`)
2. **Stadiu livrare**: LA TIMP / ÎNTÂRZIAT (din `custom_class` care conține `"late"`)
3. **Stadiu Freeze** (skip — pending Î5)

Filtrele sunt client-side pe `tasks` array-ul deja încărcat.

**Files:**
- Modify: `frontend/src/components/GanttView.tsx`

- [ ] **Step 1: Adaugă state pentru filtrele noi**

La secțiunea de `useState` (după `viewMode`), adaugă:
```tsx
const [planFilter,  setPlanFilter]  = useState<'all' | 'planificat' | 'previzionat'>('all');
const [lateFilter,  setLateFilter]  = useState<'all' | 'late' | 'ontime'>('all');
```

- [ ] **Step 2: Adaugă helper pentru derivarea stadiului din task**

Imediat după definirea `STATUS_LABEL` (linia ~39), adaugă:
```tsx
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
```

- [ ] **Step 3: Adaugă `filteredTasks` derivat din `tasks`**

Adaugă după `const [tasks, setTasks] = useState...` blocul:
```tsx
const filteredTasks = useMemo(() => {
  return tasks.filter(t => {
    if (planFilter === 'planificat'  && taskPlanStadiu(t) !== 'planificat')  return false;
    if (planFilter === 'previzionat' && taskPlanStadiu(t) !== 'previzionat') return false;
    if (lateFilter === 'late'   && !taskIsLate(t))  return false;
    if (lateFilter === 'ontime' &&  taskIsLate(t))  return false;
    return true;
  });
}, [tasks, planFilter, lateFilter]);
```

- [ ] **Step 4: Înlocuiește `tasks` cu `filteredTasks` în efectul Gantt**

La linia ~130:
```tsx
if (!containerRef.current || !wrapperRef.current || filteredTasks.length === 0) return;
```

La linia ~136 (ganttTasks.map):
```tsx
const ganttTasks = filteredTasks.map(t => {
```

La `on_click` (linia ~159):
```tsx
const t = filteredTasks.find(x => x.id === task.id);
```

- [ ] **Step 5: Adaugă UI pentru filtrele noi — înaintea butonului ↺**

Găsește în JSX blocul de filtre (după butonul "Azi", înainte de `loadGantt`). Adaugă înainte de `<button onClick={loadGantt}`:

```tsx
{/* ── Filtre 3 nivele ── */}
<div className="flex flex-wrap gap-2 items-center">
  {/* Stadiu planificare */}
  <div className="flex items-center gap-1 text-xs text-slate-500 font-medium mr-1">Plan:</div>
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

  <span className="text-slate-300">|</span>

  {/* Stadiu livrare */}
  <div className="flex items-center gap-1 text-xs text-slate-500 font-medium mr-1">Livrare:</div>
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
</div>
```

- [ ] **Step 6: Adaugă counter de task-uri filtrate**

Imediat după blocul de filtre, adaugă:
```tsx
{(planFilter !== 'all' || lateFilter !== 'all') && (
  <span className="text-xs text-slate-400">
    {filteredTasks.length} / {tasks.length} operații afișate
  </span>
)}
```

- [ ] **Step 7: Rebuild și verificare**

```bash
cd frontend
VITE_API_BASE=https://arta-grafica.fly.dev/api npx vite build
```

Verifică:
1. Chipurile de filtru apar în toolbar-ul Gantt
2. Selectând "Planificat" ascunde barele previzionate și vice versa
3. Selectând "Întârziat" afișează doar ops cu `custom_class` ce conține `"late"`
4. "Toate" resetează filtrul

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/GanttView.tsx
git commit -m "feat: Gantt — 3-level filters (plan status + delivery status)

Added client-side filter chips for:
- Stadiu planificare: Toate / Planificat / Previzionat
- Stadiu livrare: Toate / La timp / Întârziat
Derived from task.status and task.custom_class respectively.
(Freeze filter pending client answer on Î5 logic)"
```

---

## Task 6: Board Mașini — 3 Nivele de Filtrare

**Cerință:** Extinde filtrarea din Board de la 1 dimensiune (late/ontime) la 3 dimensiuni:
1. **Stadiu planificare**: ALL / PLANIFICAT / PREVIZIONAT
2. **Stadiu livrare**: ALL / LA TIMP / ÎNTÂRZIAT
3. **Stadiu Freeze**: ALL / FROZEN / UNFROZEN

Filtrele sunt client-side, pe `allItems`.

**Files:**
- Modify: `frontend/src/components/BoardView.tsx`

- [ ] **Step 1: Înlocuiește state-ul de filtrare**

Linia ~42:
```tsx
const [statusFilter, setStatusFilter] = useState<'all' | 'late' | 'ontime'>('all');
```

Cu:
```tsx
const [planFilter,   setPlanFilter]   = useState<'all' | 'planificat' | 'previzionat'>('all');
const [lateFilter,   setLateFilter]   = useState<'all' | 'late' | 'ontime'>('all');
const [freezeFilter, setFreezeFilter] = useState<'all' | 'frozen' | 'unfrozen'>('all');
```

- [ ] **Step 2: Actualizează `filteredItems` useMemo**

Înlocuiește blocul existent (liniile ~76-90):

```tsx
const PREV_BOARD_STATUSES = new Set([
  'previzionat', 'previzionat_bt', 'previzionat_material', 'previzionat_semifabricat',
]);

const filteredItems = useMemo(() => {
  const s = search.toLowerCase().trim();
  return allItems.filter(item => {
    // CL filter
    if (selectedCL && item.cl !== selectedCL) return false;

    // Stadiu planificare
    if (planFilter === 'planificat'  && item.status !== 'planned')              return false;
    if (planFilter === 'previzionat' && !PREV_BOARD_STATUSES.has(item.status))  return false;

    // Stadiu livrare
    if (lateFilter === 'late'   && !item.late) return false;
    if (lateFilter === 'ontime' &&  item.late) return false;

    // Stadiu Freeze
    if (freezeFilter === 'frozen'   && !item.frozen) return false;
    if (freezeFilter === 'unfrozen' &&  item.frozen) return false;

    // Text search
    if (s) {
      const woMatch     = String(item.wo).includes(s);
      const clientMatch = (item.client  || '').toLowerCase().includes(s);
      const artMatch    = (item.articol || '').toLowerCase().includes(s);
      if (!woMatch && !clientMatch && !artMatch) return false;
    }
    return true;
  });
}, [allItems, selectedCL, planFilter, lateFilter, freezeFilter, search]);
```

- [ ] **Step 3: Înlocuiește UI-ul de filtrare**

Găsește în JSX secțiunea cu filtre (după select-ul CL). Înlocuiește blocul cu `statusFilter` cu:

```tsx
{/* ── Filtre 3 nivele ── */}
<div className="flex flex-wrap gap-3 items-center">
  {/* Stadiu planificare */}
  <div className="flex items-center gap-1">
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
  </div>

  {/* Stadiu livrare */}
  <div className="flex items-center gap-1">
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
  </div>

  {/* Stadiu Freeze */}
  <div className="flex items-center gap-1">
    <span className="text-xs text-slate-500 font-medium">Freeze:</span>
    {(['all', 'unfrozen', 'frozen'] as const).map(v => (
      <button key={v} onClick={() => setFreezeFilter(v)}
        className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
          freezeFilter === v
            ? v === 'frozen'   ? 'bg-purple-100 border-purple-400 text-purple-700 font-medium'
            : v === 'unfrozen' ? 'bg-slate-200 border-slate-400 text-slate-700 font-medium'
            : 'bg-slate-200 border-slate-400 text-slate-700 font-medium'
            : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'
        }`}>
        {v === 'all' ? 'Toate' : v === 'frozen' ? '❄ Frozen' : 'Unfrozen'}
      </button>
    ))}
  </div>
</div>
```

- [ ] **Step 4: Verificare**

1. Deschide Board Mașini
2. Testează fiecare filtru independent
3. Combină filtre (ex: Planificat + Întârziat) — trebuie să funcționeze cumulat
4. Verifică că bug-ul "prima parte goală" nu reapare cu Task 3 livrat

- [ ] **Step 5: Rebuild și commit**

```bash
cd frontend
VITE_API_BASE=https://arta-grafica.fly.dev/api npx vite build
git add frontend/src/components/BoardView.tsx
git commit -m "feat: Board — 3-level filters (plan status, delivery, freeze)

Replaced single late/ontime toggle with three independent filter dimensions:
- Stadiu planificare: Toate / Planificat / Previzionat
- Stadiu livrare: Toate / La timp / Întârziat
- Stadiu Freeze: Toate / Frozen / Unfrozen
All filters are client-side on loaded items."
```

---

## Task 7: Deploy și verificare finală

- [ ] **Step 1: Push și deploy**

```bash
git push origin main
fly deploy --app arta-grafica
```

- [ ] **Step 2: Verifică timezone pe server**

```bash
fly ssh console -C "date" --app arta-grafica
```

Expected output: ora Bucuresti (ex: `Tue May 20 10:30:00 EEST 2026`)

- [ ] **Step 3: Declanșează replanificare**

- Deschide aplicația
- Dashboard → „Planifică acum"
- Verifică că datele start din Planificare/Gantt/Board au ora corectă (Bucuresti)

- [ ] **Step 4: Verificare checklist complet**

| Test | Expected |
|---|---|
| Timezone în planificare | Oră corectă Bucuresti, nu UTC |
| Gantt săgeți | Merg din coada op. A → capul op. B (stânga→dreapta) |
| Board filtru CL | Nu mai există rânduri goale în partea de sus |
| Planning contoare | Nu se schimbă la filtrare status/resursă |
| Planning tabel | Coloanele Stop și Durata sunt vizibile fără scroll |
| Gantt filtre chips | Planificat/Previzionat/Livrare funcționează |
| Board filtre chips | 3 dimensiuni funcționează cumulat |

---

## Ce rămâne după Î3 și Î5

**Î3 (consum per unitate):** `planner.py` — înlocuiește verificarea `cantitate <= 0.01` cu `cantitate / cant_comanda <= 0.01` (cant_comanda = cant_vnz sau q_plan, pending răspuns).

**Î5 (Frozen-posibil/imposibil):** `BoardView.tsx` + `main.py` — board endpoint adaugă câmp `frozen_possible: bool`, calculat ca "frozen AND (are BT valid AND are material acum)".
