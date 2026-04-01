# Arta Grafica — Planificare Productie

Aplicatie web pentru planificarea productiei intr-o tipografie. Import date din Excel, algoritm de planificare, vizualizare Gantt, asistent AI.

---

## Stack

| Layer | Tehnologie |
|---|---|
| Backend | FastAPI + uvicorn, Python 3.11+ |
| ORM / DB | SQLAlchemy + SQLite (`data/planning.db`) |
| Frontend | React + TypeScript + TailwindCSS + Vite |
| Gantt | frappe-gantt (open source) |
| Board mașini | vis-timeline |
| AI | Anthropic Claude API (claude-opus-4-6), streaming SSE |
| Deploy | Raspberry Pi 4 (ARM64, Raspbian), systemd service |

---

## Structura proiect

```
arta grafica/
├── backend/
│   ├── main.py          # FastAPI app, toate endpoint-urile, auth, AI
│   ├── planner.py       # Algoritmul de planificare
│   ├── importer.py      # Import Excel → DB
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   ├── database.py      # Engine + session
│   ├── requirements.txt
│   └── .env             # ANTHROPIC_API_KEY (gitignored!)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx      # Statistici generale + AI
│   │   │   ├── PlanningList.tsx   # Rezultate planificare + AI
│   │   │   ├── AIAssistant.tsx    # Componentă AI refolosibilă
│   │   │   ├── GanttView.tsx      # Vizualizare Gantt
│   │   │   ├── BoardView.tsx      # Board mașini (vis-timeline)
│   │   │   ├── ComenziList.tsx    # Lista comenzi
│   │   │   ├── StocView.tsx       # Stoc materiale
│   │   │   └── LoginPage.tsx      # Autentificare
│   │   └── api/                   # Fetch client cu Authorization header
│   └── dist/                      # Build produs (gitignored)
├── data/
│   └── planning.db                # SQLite (gitignored)
├── docs/
│   ├── Ghid_Utilizare_Arta_Grafica.docx
│   └── create_guide_docx.js
├── arta-grafica.service            # systemd unit pentru Pi
├── deploy_pi.sh                    # Script deploy Pi (ruleaza o singura data)
└── CLAUDE.md                       # Acest fisier
```

---

## Date de autentificare

- **User aplicatie**: `andrei` / `sarbu1234`
- **Raspberry Pi SSH**: `raspberry@192.168.0.13` (user este `raspberry`, nu `pi`)
- **Raspberry Pi IP local**: `192.168.0.13`
- **Port aplicatie**: `8000`
- **ANTHROPIC_API_KEY**: vezi `backend/.env` (gitignored — trebuie adaugat manual pe fiecare masina)

---

## Setup local (dev)

```bash
# Backend
cd backend
pip3 install -r requirements.txt
# Asigura-te ca backend/.env contine ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload --port 8000

# Frontend (alt terminal)
cd frontend
npm install
npm run dev   # proxy → http://localhost:8000
```

Frontend dev server ruleaza pe portul `5173` si proxiaza `/api` catre backend.

---

## Deploy Raspberry Pi

### Prima instalare (o singura data)

```bash
ssh raspberry@192.168.0.13
cd ~
git clone https://github.com/<user>/arta-grafica.git
cd arta-grafica

# OBLIGATORIU: adauga API key (nu e in git!)
echo "ANTHROPIC_API_KEY=sk-ant-..." > backend/.env

chmod +x deploy_pi.sh
./deploy_pi.sh
```

> **Atentie**: `deploy_pi.sh` foloseste `/home/raspberry/` nu `/home/pi/`.

### Environment Variables (optional)

You can optionally override default credentials by setting environment variables in the systemd service file. Edit `/etc/systemd/system/arta-grafica.service`:

```ini
[Service]
# Optional: override default credentials (recommended in production)
# Environment=AG_USER=andrei
# Environment=AG_PASS=<strong-password>
# Environment=AG_SALT=<random-string>
```

Then reload the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart arta-grafica
```

- `AG_USER`: Application login username (default: `andrei`)
- `AG_PASS`: Application login password (default: `sarbu1234`)
- `AG_SALT`: Salt for token generation (default: `arta-grafica-2026`)

### Update aplicatie (dupa modificari in git)

```bash
ssh raspberry@192.168.0.13
cd ~/arta-grafica
git pull origin main

# Daca s-au adaugat pachete Python noi:
~/arta-grafica/venv/bin/pip install -r backend/requirements.txt

# Rebuild frontend:
cd frontend && npx vite build

# Restart serviciu:
sudo systemctl restart arta-grafica
sudo systemctl status arta-grafica --no-pager
```

### Cron job auto-update (instalat pe Pi)

```bash
# Verifica cu:
crontab -l
# Ar trebui sa existe o linie pentru update orar
```

### Comenzi utile pe Pi

```bash
# Logs live
sudo journalctl -u arta-grafica -f

# Status serviciu
sudo systemctl status arta-grafica

# Restart
sudo systemctl restart arta-grafica
```

### Particularitati ARM64 (Raspberry Pi)

- **pandas** nu se instaleaza din pip pe ARM — se instaleaza via apt:
  ```bash
  sudo apt-get install -y python3-pandas python3-numpy
  python3 -m venv venv --system-site-packages
  ```
- **TypeScript errors** blocheaza `npm run build` — foloseste `npx vite build` (skip type-check)
- **Port 8000** era ocupat de `manufacturing-adviser.service` (vechi) — dezactivat

---

## Algoritmul de planificare (`backend/planner.py`)

### Flux general

1. **Sortare comenzi**: "06 - In productie" primul, apoi descrescator dupa `StadiuPrepress`, apoi dupa `DataActualizataLivrare` (daca tip_comanda="V") sau `DtLivrProd`
2. **Excludere**: `Status_cda = STOP`
3. **Pentru fiecare comanda**, operatii sortate dupa `Rank`
4. **Conditii planificare operatie**:
   a. **BT valid** — cel putin un camp `bt1..bt4` nevid si != `"1911-11-11"`
   b. **Rank** — operatiile cu rank inferior trebuie sa fie inchise sau deja planificate (nu "open"). Daca precedentul e "planned", operatia curenta incepe dupa `data_end` a precedentului
   c. **Materiale** — `SoldActual - sum(cantitati deja rezervate) > 0`
   d. **Resursa disponibila** — prima resursa din CL cu ore disponibile in `ProgramResursa`
5. **Timp** = `P_Setup + P_Runtime - R_Runtime` (minim 0)
6. Operatii fara rank → rank implicit `999`

### Prioritati StadiuPrepress

```python
STADIU_PRIORITY = {
    "06 - In productie": 100,
    "05 - BT existent":  50,
    "04 - Trimis la BT": 40,
    "03 - Fisiere existente": 30,
    "02 - Job creat": 20,
    "01 - Fara Fisiere": 10,
    "00 - N/A": 0,
}
```

### Status posibile pentru o operatie planificata

| Status | Descriere |
|---|---|
| `Planificat` | Operatia a primit slot |
| `Fara Material` | `SoldActual - rezervat <= 0` |
| `Fara BT` | BT lipsa sau invalid |
| `Blocat Rank` | Operatie cu rank inferior inca deschisa |
| `Fara Resursa` | Nicio resursa CL disponibila |

### Relatii intre fisierele Excel

| Fisier | Coloana | Se leaga cu |
|---|---|---|
| Stari comenzi | `CP` | Dispatch `WO` (98% match) |
| Dispatch List | `Stock_code` | Lista Deficite `Articol` |
| Dispatch List | `OP` | Operatii `cod` (100%) |
| Dispatch List | `CL` | Resurse `CL` (95%) |

---

## Asistentul AI

Foloseste Claude API (model `claude-opus-4-6`) cu streaming SSE.

### Endpoint

```
POST /api/ai/analyze   (SSE streaming)
Body: { "tab": "dashboard"|"planificare", "question": "..." }
```

### Butoane predefinite

**Dashboard**: "Rezumă situația de azi" · "Care sunt comenzile urgente?" · "Unde sunt principalele blocaje?"

**Planificare**: "De ce sunt comenzi blocate?" · "Ce materiale să aprovizionez?" · "Care sunt quick wins?"

### Principii de design AI

- Utilizatorul NU scrie liber — doar butoane predefinite
- Backend-ul construieste contextul din DB (nu date brute din UI)
- Raspunsuri strict bazate pe date, in romana
- Streaming obligatoriu (Pi e lent fara streaming)

---

## Auth aplicatie

- Implementat ca middleware HTTP in `main.py`
- Token SHA256 din `andrei:sarbu1234:arta-grafica-2026`
- Stocat in `localStorage` (cu checkbox "tine-ma minte")
- Toate rutele `/api/*` protejate, exceptie `/api/auth/login`

---

## Note importante

- `.env` este **gitignored** — trebuie creat manual pe fiecare masina cu `ANTHROPIC_API_KEY`
- `data/planning.db` este **gitignored** — se creeaza la primul pornire, dar directorul `data/` trebuie sa existe
- Cand faci deploy pe Pi nou: `mkdir -p ~/arta-grafica/data`
- Frontend-ul buildat (`dist/`) este servit de FastAPI ca SPA static
- Vite proxy in dev: `vite.config.ts` proxiaza `/api` → `http://localhost:8000`
