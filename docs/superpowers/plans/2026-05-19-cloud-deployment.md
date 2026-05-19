# Cloud Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrează aplicația Arta Grafica de pe Raspberry Pi pe Cloudflare Pages (frontend) + Fly.io (backend + SQLite).

**Architecture:** Frontend-ul React compilat e servit de Cloudflare Pages (CDN global). Backend-ul FastAPI rulează pe Fly.io cu SQLite pe un volum persistent de 3GB. Frontend-ul apelează backend-ul prin URL absolut injectat la build time (`VITE_API_BASE`).

**Tech Stack:** FastAPI, SQLite, uvicorn, Docker, Fly.io CLI (`flyctl`), Cloudflare Pages (dashboard), Vite

---

## Fișiere atinse

| Fișier | Acțiune | Schimbare |
|---|---|---|
| `backend/database.py` | Modificat | PATH SQLite citit din `DATA_DIR` env var |
| `frontend/src/api/client.ts` | Modificat | `BASE` citit din `VITE_API_BASE` env var |
| `Dockerfile` | Creat | Imagine Docker pentru Fly.io |
| `fly.toml` | Creat | Configurare app Fly.io |
| `.dockerignore` | Creat | Exclude frontend/, data/, xlsx-uri |

---

## Task 1: Actualizează `database.py` — path SQLite din env var

**Files:**
- Modify: `backend/database.py`

- [ ] **Step 1: Deschide fișierul și înlocuiește conținutul complet**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# DATA_DIR poate fi suprascris prin env var (ex: Fly.io setează DATA_DIR=/data)
# Fallback: directorul `data/` din rădăcina proiectului (dev local)
DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data")
)
DB_PATH = os.path.join(DATA_DIR, "planning.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Verifică că dev local funcționează în continuare**

```bash
cd backend
uvicorn main:app --port 8000 --reload
```

Așteptat: `Application startup complete.` fără erori. Dacă apare `no such table`, DB-ul local e gol — normal, nu e o problemă.

- [ ] **Step 3: Commit**

```bash
git add backend/database.py
git commit -m "feat: read SQLite path from DATA_DIR env var for Fly.io"
```

---

## Task 2: Actualizează `client.ts` — URL API din env var

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Înlocuiește prima linie din fișier**

```typescript
// Înainte:
const BASE = '/api';

// După:
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api';
```

Linia completă înlocuită e linia 1 din fișier. Restul fișierului rămâne neschimbat.

- [ ] **Step 2: Verifică că dev local funcționează**

```bash
cd frontend
npm run dev
```

Așteptat: aplicația pornește pe `http://localhost:5173`, apelurile `/api` sunt proxiate spre `http://localhost:8000` (fără `VITE_API_BASE` setat, fallback-ul `/api` e activ).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: read API base URL from VITE_API_BASE env var for Cloudflare Pages"
```

---

## Task 3: Creează `Dockerfile`

**Files:**
- Create: `Dockerfile` (în rădăcina proiectului)

- [ ] **Step 1: Creează fișierul**

```dockerfile
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Verifică build-ul Docker local**

```bash
docker build -t arta-grafica-test .
```

Așteptat: `Successfully built <id>` sau `naming to docker.io/library/arta-grafica-test`. Durează ~60 secunde la prima rulare (descarcă python:3.11-slim + pachete).

- [ ] **Step 3: Verifică că containerul pornește**

```bash
docker run --rm -p 8080:8080 -e DATA_DIR=/tmp arta-grafica-test
```

Așteptat: `Application startup complete.` pe portul 8080. Oprește cu `Ctrl+C`.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile for Fly.io deployment"
```

---

## Task 4: Creează `fly.toml` și `.dockerignore`

**Files:**
- Create: `fly.toml` (rădăcina proiectului)
- Create: `.dockerignore` (rădăcina proiectului)

- [ ] **Step 1: Creează `fly.toml`**

```toml
app            = "arta-grafica"
primary_region = "lhr"

[env]
  DATA_DIR = "/data"
  PORT     = "8080"

[http_service]
  auto_start_machines  = true
  auto_stop_machines   = true
  force_https          = true
  internal_port        = 8_080
  min_machines_running = 0

  [http_service.concurrency]
  type       = "requests"
  soft_limit = 20
  hard_limit = 25

[[mounts]]
  source       = "arta_grafica_data"
  destination  = "/data"
  initial_size = "3gb"

[[vm]]
  cpu_kind = "shared"
  cpus     = 1
  memory   = "512mb"
```

- [ ] **Step 2: Creează `.dockerignore`**

```
frontend/
data/
*.xlsx
~$*.xlsx
__pycache__/
*.pyc
.env
docs/
```

- [ ] **Step 3: Commit**

```bash
git add fly.toml .dockerignore
git commit -m "feat: add fly.toml and .dockerignore for Fly.io"
```

- [ ] **Step 4: Push pe GitHub**

```bash
git push origin main
```

Așteptat: push reușit. Acesta e ultimul commit de cod — tot ce urmează sunt pași de infrastructure/CLI.

---

## Task 5: Creează și configurează app-ul pe Fly.io

**Prerequisite:** `flyctl` instalat (`brew install flyctl`) și autentificat (`fly auth login`).

- [ ] **Step 1: Creează app-ul (fără deploy)**

```bash
fly apps create arta-grafica
```

Așteptat:
```
New app created: arta-grafica
```

Dacă numele `arta-grafica` e ocupat, alege `arta-grafica-prod` și actualizează `fly.toml` (câmpul `app`).

- [ ] **Step 2: Creează volumul persistent**

```bash
fly volumes create arta_grafica_data --region lhr --size 3 --app arta-grafica
```

Așteptat output similar cu:
```
ID: vol_xxxxxxxxxx
Name: arta_grafica_data
App: arta-grafica
Region: lhr
Size GB: 3
```

- [ ] **Step 3: Setează secretele (înlocuiește valorile reale)**

```bash
fly secrets set \
  ANTHROPIC_API_KEY="sk-ant-..." \
  AG_USER="andrei" \
  AG_PASS="sarbu1234" \
  --app arta-grafica
```

Așteptat:
```
Secrets are staged for the first deployment
```

`ANTHROPIC_API_KEY` se găsește în `backend/.env` pe Pi:
```bash
ssh raspberry@192.168.0.13 cat ~/arta-grafica/backend/.env
```

- [ ] **Step 4: Deploy**

```bash
fly deploy --app arta-grafica
```

Prima rulare durează 3-5 minute (build Docker + push imagine). Așteptat la final:
```
Visit your newly deployed app at https://arta-grafica.fly.dev/
```

- [ ] **Step 5: Verifică că backend-ul răspunde**

```bash
curl https://arta-grafica.fly.dev/api/stats
```

Așteptat: răspuns JSON (poate fi `{"error": "..."}` dacă DB e gol — e normal). Dacă primești `401 Unauthorized`, înseamnă că endpoint-ul `/api/stats` e protejat — încearcă:

```bash
curl -X POST https://arta-grafica.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"andrei","password":"sarbu1234"}'
```

Așteptat: `{"token": "..."}` — backend-ul funcționează.

---

## Task 6: Migrează `planning.db` de pe Pi

- [ ] **Step 1: Descarcă DB-ul de pe Pi**

```bash
scp raspberry@192.168.0.13:~/arta-grafica/data/planning.db ./planning.db
```

Așteptat: fișierul `planning.db` apare în directorul curent. Verifică dimensiunea:
```bash
ls -lh planning.db
```

- [ ] **Step 2: Copiază pe volumul Fly.io**

```bash
fly ssh sftp shell --app arta-grafica
```

În shell-ul sftp interactiv care se deschide:
```
sftp> put planning.db /data/planning.db
sftp> ls /data/
sftp> exit
```

Așteptat: `planning.db` apare în `/data/` cu dimensiunea corectă.

- [ ] **Step 3: Restartează app-ul ca să preia noul DB**

```bash
fly machine restart --app arta-grafica
```

- [ ] **Step 4: Verifică că datele sunt prezente**

```bash
# Obține token
TOKEN=$(curl -s -X POST https://arta-grafica.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"andrei","password":"sarbu1234"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Verifică stats
curl -H "Authorization: Bearer $TOKEN" https://arta-grafica.fly.dev/api/stats
```

Așteptat: JSON cu date reale (comenzi, operatii) — nu zero.

- [ ] **Step 5: Șterge fișierul local temporar**

```bash
rm ./planning.db
```

---

## Task 7: Configurează Cloudflare Pages

Toți pașii se fac în **Cloudflare Dashboard** (browser).

- [ ] **Step 1: Creează un nou Pages project**

1. Mergi la [dash.cloudflare.com](https://dash.cloudflare.com) → **Pages** → **Create a project**
2. Alege **Connect to Git** → selectează repo-ul `arta-grafica` de pe GitHub
3. Autorizează accesul dacă e prima dată

- [ ] **Step 2: Configurează build settings**

| Câmp | Valoare |
|---|---|
| Project name | `arta-grafica` |
| Production branch | `main` |
| Root directory | `frontend` |
| Build command | `npx vite build` |
| Build output directory | `dist` |

- [ ] **Step 3: Adaugă environment variable**

În secțiunea **Environment variables (advanced)** înainte de Save:

| Variable name | Value | Environment |
|---|---|---|
| `VITE_API_BASE` | `https://arta-grafica.fly.dev/api` | Production |
| `VITE_API_BASE` | `https://arta-grafica.fly.dev/api` | Preview |

- [ ] **Step 4: Salvează și pornește primul build**

Click **Save and Deploy**. Build-ul durează 1-2 minute.

Așteptat în log:
```
✓ Build completed
✓ Deployment complete
```

URL-ul va fi `https://arta-grafica.pages.dev`.

- [ ] **Step 5: Testează aplicația completă**

1. Deschide `https://arta-grafica.pages.dev` în browser
2. Login cu `andrei` / `sarbu1234`
3. Verifică: Dashboard → are date
4. Verifică: Planificare → lista operații se încarcă
5. Verifică: Gantt → diagrama se afișează
6. Verifică: Export Excel → descarcă un fișier `.xlsx` valid

---

## Task 8: Validare finală și dezactivare Pi (după câteva zile)

- [ ] **Step 1: Monitorizează logs Fly.io câteva zile**

```bash
fly logs --app arta-grafica
```

Urmărește erori neașteptate (5xx, crash-uri, probleme SQLite).

- [ ] **Step 2: Când ești mulțumit, oprește serviciul de pe Pi**

```bash
ssh raspberry@192.168.0.13
sudo systemctl stop arta-grafica
sudo systemctl disable arta-grafica
```

Așteptat:
```
Removed /etc/systemd/system/multi-user.target.wants/arta-grafica.service.
```

- [ ] **Step 3: Verifică că aplicația cloud funcționează în continuare**

Accesează din nou `https://arta-grafica.pages.dev` și confirmă că totul merge fără Pi.

---

## Referință rapidă — comenzi utile post-deploy

```bash
# Logs live
fly logs --app arta-grafica

# Status mașini
fly status --app arta-grafica

# SSH în container
fly ssh console --app arta-grafica

# Verifică DB direct
fly ssh console --app arta-grafica -C "ls -lh /data/"

# Redeploy după modificări de cod
git push origin main && fly deploy --app arta-grafica

# Secrets (listare fără valori)
fly secrets list --app arta-grafica
```
