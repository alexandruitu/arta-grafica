# AGENTS.md

## Fast orientation (what matters first)
- Backend entrypoint is `backend/main.py` (FastAPI app, auth middleware, import/plan endpoints, AI SSE, SPA serving).
- Planner logic is centralized in `backend/planner.py` (`run_planning`); treat this file as source of truth for statuses and sequencing.
- Import pipeline is `backend/importer.py`; uploaded Excel files are persisted into `data/` and then imported into SQLite.
- Frontend is a single Vite app in `frontend/` (`frontend/src/App.tsx` top-level tabs + auth gate).

## Verified local commands
- Backend dev server (run from `backend/`): `uvicorn main:app --reload --port 8000`.
- Frontend dev server (run from `frontend/`): `npm run dev` (proxies `/api` to `http://localhost:8000` via `frontend/vite.config.ts`).
- Frontend build (run from `frontend/`): `npm run build` (currently works).
- Backend targeted tests (run from repo root): `pytest -q backend/test_consistency.py` (currently passes).

## Validation pitfalls (current repo state)
- `pytest -q backend` fails during collection because `backend/test_planner.py` imports `find_slot` which no longer exists in `backend/planner.py`.
- `npm run lint` currently fails with many existing violations (`no-explicit-any`, React hooks rules). Do not assume lint is a clean gate right now.

## API and behavior gotchas
- All `/api/*` routes require bearer token except `/api/auth/login`; middleware is in `backend/main.py`.
- Default login is controlled by env vars `AG_USER` / `AG_PASS` / `AG_SALT` (defaults are in `backend/main.py`), token is deterministic SHA256 of those values.
- AI endpoint is **GET** `/api/ai/analyze?question_id=...` with SSE streaming; if docs mention POST body (`tab`/`question`), treat code as canonical.
- Planner statuses include `planned`, `previzionat_bt`, `previzionat_material`, `no_material`, `no_resource`, `blocked_by_rank`, `no_bt` (plus `completed` internal accounting).

## Data/import constraints agents usually miss
- `/api/import` requires exactly these filenames: `Stari comenzi_AS.xlsx`, `Dispatch List_AS.xlsx`, `OperatiiWO_AS.xlsx`, `Lista Deficite_AS.xlsx`, `Resurse_AS.xlsx`.
- Database path is fixed to `data/planning.db` from `backend/database.py`.
- `Base.metadata.create_all(...)` runs at app startup; schema is created automatically if DB file is missing.

## Deploy reality on Raspberry Pi
- Deployment script is `deploy_pi.sh`; it installs pandas/numpy from apt and builds frontend with `npx vite build`.
- systemd service file is `arta-grafica.service` and runs uvicorn from `/home/raspberry/arta-grafica/backend`.
