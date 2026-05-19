# Cloud Deployment Design — Arta Grafica
**Data:** 2026-05-19  
**Status:** Aprobat

---

## Obiectiv

Migrarea aplicației de pe Raspberry Pi (192.168.0.13) în cloud, folosind:
- **Cloudflare Pages** pentru frontend (React SPA)
- **Fly.io** pentru backend (FastAPI + SQLite pe volum persistent)

Pi-ul rămâne activ temporar ca backup; se dezactivează după validare.

---

## Arhitectură

```
Browser
  → Cloudflare Pages  (React SPA, CDN global, HTTPS automat)
       ↓ fetch https://arta-grafica.fly.dev/api/...
  → Fly.io Machine    (FastAPI + uvicorn, port 8080, lhr)
       ↓ SQLite read/write
  → Fly Volume /data  (planning.db, 3GB persistent)
```

---

## Modificări de cod

### 1. `frontend/src/api/client.ts`
```ts
// Înainte:
const BASE = '/api';
// După:
const BASE = (import.meta.env.VITE_API_BASE as string) ?? '/api';
```
- În dev: proxy Vite continuă să funcționeze (fără `VITE_API_BASE`, fallback la `/api`)
- Pe Cloudflare Pages: `VITE_API_BASE=https://arta-grafica.fly.dev/api` injectat la build time

### 2. `backend/database.py`
```python
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH  = os.path.join(DATA_DIR, "planning.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"
```
- Local dev: continuă să folosească `data/planning.db` (fără env var)
- Fly.io: `DATA_DIR=/data` (volum montat)

---

## Fișiere noi

### `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### `fly.toml`
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

### `.dockerignore`
```
frontend/
data/
*.xlsx
~$*.xlsx
__pycache__/
*.pyc
.env
```

---

## Secrets Fly.io (CLI, nu în git)
```bash
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly secrets set AG_USER=andrei
fly secrets set AG_PASS=sarbu1234
```

---

## Cloudflare Pages — setări dashboard

| Câmp | Valoare |
|---|---|
| Root directory | `frontend` |
| Build command | `npx vite build` |
| Build output | `dist` |
| Env var | `VITE_API_BASE = https://arta-grafica.fly.dev/api` |

---

## Migrarea datelor (`planning.db`)

```bash
# 1. Descarcă de pe Pi
scp raspberry@192.168.0.13:~/arta-grafica/data/planning.db ./planning.db

# 2. Copiază pe volumul Fly.io (după primul deploy reușit)
fly ssh sftp shell -a arta-grafica
# în sftp shell:
put planning.db /data/planning.db
```

Se execută **o singură dată**, după ce backend-ul pe Fly.io a pornit cu succes.

---

## Ordinea de deploy

1. Modifică `client.ts` și `database.py`
2. Adaugă `Dockerfile`, `fly.toml`, `.dockerignore`
3. Commit + push pe `main`
4. `fly launch --no-deploy` (import fly.toml existent)
5. `fly volumes create arta_grafica_data --size 3`
6. `fly secrets set ...` (cele 3 variabile)
7. `fly deploy` → testează `https://arta-grafica.fly.dev/api/stats`
8. Migrează `planning.db` de pe Pi
9. Conectează Cloudflare Pages la repo GitHub, setează env var, trigger build
10. Testează login + planificare pe URL-ul Cloudflare
11. Pi rămâne activ câteva zile ca backup
12. Când totul e ok: `sudo systemctl stop arta-grafica` pe Pi

---

## Ce NU se schimbă

- Logica aplicației (planner.py, modele, algoritm) — nicio modificare
- CORS rămâne `allow_origins=["*"]`  
- Auth (SHA256 token) — funcționează identic
- Dev local (`uvicorn` + `npm run dev`) — funcționează identic, fără env vars

---

## Costuri estimate

| Serviciu | Plan | Cost |
|---|---|---|
| Cloudflare Pages | Free | $0/lună |
| Fly.io (1 VM shared, 512MB) | Free allowance | $0/lună |
| Fly.io Volume (3GB) | Free allowance | $0/lună |
| **Total** | | **$0/lună** |
