"""FastAPI backend for Arta Grafica Production Planning."""
from __future__ import annotations
import os
from typing import List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib as _hashlib
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
import json as _json
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import engine, get_db, Base
from models import (
    Comanda, DispatchItem, Operatie, Deficit, Resursa, ProgramResursa,
    PlanificareSesiune, PlanificareRezultat,
)
from schemas import (
    ComandaOut, DispatchOut, PlanificareOut, GanttTask,
    ResursaOut, ImportResult, PlanningResult, StocArticol,
)
from importer import import_all
from planner import run_planning

Base.metadata.create_all(bind=engine)

# ── Auth ───────────────────────────────────────────────────────────────────────
_AUTH_USER = "andrei"
_AUTH_PASS = "sarbu1234"
_AUTH_SALT = "arta-grafica-2026"
_VALID_TOKEN: str = _hashlib.sha256(
    f"{_AUTH_USER}:{_AUTH_PASS}:{_AUTH_SALT}".encode()
).hexdigest()

app = FastAPI(title="Arta Grafica - Production Planning", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Public: login endpoint + all static/SPA assets
    if path == "/api/auth/login" or not path.startswith("/api/"):
        return await call_next(request)
    # Protected: all other /api/* routes
    token = request.headers.get("Authorization", "")
    if token == f"Bearer {_VALID_TOKEN}":
        return await call_next(request)
    return JSONResponse({"detail": "Unauthorized"}, status_code=401)


@app.post("/api/auth/login")
def login(body: dict):
    if body.get("username") == _AUTH_USER and body.get("password") == _AUTH_PASS:
        return {"token": _VALID_TOKEN}
    raise HTTPException(status_code=401, detail="Credentiale incorecte")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "")


# --- Import ---
@app.post("/api/import", response_model=ImportResult)
def do_import(db: Session = Depends(get_db)):
    results = import_all(db, DATA_DIR)
    return ImportResult(**results)


# --- Planning ---
@app.post("/api/plan", response_model=PlanningResult)
def do_plan(db: Session = Depends(get_db)):
    result = run_planning(db)
    return PlanningResult(**result)


# --- Comenzi ---
@app.get("/api/comenzi", response_model=List[ComandaOut])
def list_comenzi(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    stadiu: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Comanda)
    if status:
        q = q.filter(Comanda.status_cda == status)
    if stadiu:
        q = q.filter(Comanda.stadiu_prepress == stadiu)
    if search:
        search_term = f"%{search}%"
        q = q.filter(
            (Comanda.client.ilike(search_term)) |
            (Comanda.articol.ilike(search_term)) |
            (Comanda.ref_client.ilike(search_term))
        )
    return q.order_by(Comanda.data_actualizata_livrare).offset(offset).limit(limit).all()


@app.get("/api/comenzi/{cp}", response_model=ComandaOut)
def get_comanda(cp: int, db: Session = Depends(get_db)):
    c = db.query(Comanda).filter(Comanda.cp == cp).first()
    if not c:
        raise HTTPException(status_code=404, detail="Comanda not found")
    return c


@app.get("/api/comenzi/{cp}/operatii", response_model=List[DispatchOut])
def get_comanda_operatii(cp: int, db: Session = Depends(get_db)):
    return db.query(DispatchItem).filter(DispatchItem.wo == cp).all()


# --- Dispatch ---
@app.get("/api/dispatch", response_model=List[DispatchOut])
def list_dispatch(
    cl: Optional[str] = Query(None),
    wo: Optional[int] = Query(None),
    limit: int = Query(200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(DispatchItem)
    if cl:
        q = q.filter(DispatchItem.cl == cl)
    if wo:
        q = q.filter(DispatchItem.wo == wo)
    return q.offset(offset).limit(limit).all()


# --- Resurse ---
@app.get("/api/resurse", response_model=List[ResursaOut])
def list_resurse(cl: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Resursa)
    if cl:
        q = q.filter(Resursa.cl == cl)
    return q.all()


@app.get("/api/resurse/centre-lucru")
def list_centre_lucru(db: Session = Depends(get_db)):
    results = db.query(Resursa.cl, Resursa.denumire_cl).distinct().all()
    return [{"cl": r[0], "denumire": r[1]} for r in results]


# --- Planificare results ---
@app.get("/api/planificare/latest")
def get_latest_planning(db: Session = Depends(get_db)):
    sesiune = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
    if not sesiune:
        return {"error": "No planning session found. Run POST /api/plan first."}

    results = (
        db.query(PlanificareRezultat)
        .filter(PlanificareRezultat.sesiune_id == sesiune.id)
        .all()
    )

    stats = {}
    for r in results:
        stats[r.status] = stats.get(r.status, 0) + 1

    return {
        "sesiune_id": sesiune.id,
        "created_at": sesiune.created_at.isoformat() if sesiune.created_at else None,
        "status": sesiune.status,
        "total_operatii": sesiune.total_operatii,
        "operatii_planificate": sesiune.operatii_planificate,
        "operatii_neplanificate": sesiune.operatii_neplanificate,
        "breakdown": stats,
    }


@app.get("/api/planificare/gantt", response_model=List[GanttTask])
def get_gantt_data(
    cl: Optional[str] = Query(None),
    wo: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    sesiune = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
    if not sesiune:
        return []

    q = (
        db.query(PlanificareRezultat)
        .filter(PlanificareRezultat.sesiune_id == sesiune.id)
        .filter(PlanificareRezultat.status == "planned")
    )
    if cl:
        q = q.filter(PlanificareRezultat.cl == cl)
    if wo:
        q = q.filter(PlanificareRezultat.wo == wo)

    results = q.all()
    tasks = []
    for r in results:
        if not r.data_start or not r.data_end:
            continue

        comanda = db.query(Comanda).filter(Comanda.cp == r.wo).first()
        custom_class = "bar-planned"
        if comanda:
            delivery = comanda.data_actualizata_livrare or comanda.dt_livr_prod
            if delivery and r.data_end.date() > delivery:
                custom_class = "bar-late"
            elif r.frozen:
                custom_class = "bar-frozen"

        deps = []
        if r.dispatch:
            op_catalog = db.query(Operatie).filter(Operatie.cod == str(r.op)).first()
            if op_catalog and op_catalog.rank > 1:
                prev_ops = (
                    db.query(PlanificareRezultat)
                    .filter(PlanificareRezultat.sesiune_id == sesiune.id)
                    .filter(PlanificareRezultat.wo == r.wo)
                    .filter(PlanificareRezultat.status == "planned")
                    .all()
                )
                for p in prev_ops:
                    p_cat = db.query(Operatie).filter(Operatie.cod == str(p.op)).first()
                    if p_cat and p_cat.rank < op_catalog.rank:
                        deps.append(f"{p.wo}-{p.op}")

        tasks.append(GanttTask(
            id=f"{r.wo}-{r.op}",
            name=f"WO:{r.wo} OP:{r.op} ({r.cl})",
            start=r.data_start.strftime("%Y-%m-%d"),
            end=r.data_end.strftime("%Y-%m-%d"),
            progress=0,
            dependencies=",".join(deps),
            custom_class=custom_class,
            wo=r.wo,
            op=r.op,
            cl=r.cl,
            resursa=r.resursa_nume,
            status=r.status,
        ))

    # Sort by WO then by planned start date so rank order is visible in Gantt rows
    tasks.sort(key=lambda t: (t.wo, t.start))
    return tasks


@app.get("/api/planificare/board")
def get_board_data(db: Session = Depends(get_db)):
    """Resource-centric board view (rows=machines, columns=hours).
    Returns vis-timeline compatible groups + items with hour-level precision."""
    sesiune = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
    if not sesiune:
        return {"groups": [], "items": []}

    results = (
        db.query(PlanificareRezultat)
        .filter(PlanificareRezultat.sesiune_id == sesiune.id)
        .filter(PlanificareRezultat.status == "planned")
        .all()
    )

    # Shift schedules per resource per day
    program_map: dict = defaultdict(dict)  # {resursa_id: {date: schimburi_str}}
    for p in db.query(ProgramResursa).all():
        program_map[p.resursa_id][p.data] = p.schimburi or ""

    # Cache comenzi
    comanda_cache: dict = {}
    for r in results:
        if r.wo not in comanda_cache:
            comanda_cache[r.wo] = db.query(Comanda).filter(Comanda.cp == r.wo).first()

    # Groups: only resources that have planned operations
    resurse_ids = {r.resursa_id for r in results if r.resursa_id}
    resurse_map = {r.id: r for r in db.query(Resursa).filter(Resursa.id.in_(resurse_ids)).all()}

    groups = []
    for r in sorted(resurse_map.values(), key=lambda x: (x.cl, x.resursa)):
        groups.append({"id": str(r.id), "content": r.resursa, "cl": r.cl})

    # Group planned ops by (resursa_id, day) to assign sequential hour-level times
    ops_by_res_day: dict = defaultdict(list)
    for r in results:
        if r.resursa_id and r.data_start:
            ops_by_res_day[(r.resursa_id, r.data_start.date())].append(r)

    # Color palette by CL (center of work)
    cl_colors = [
        "#3b82f6","#06b6d4","#8b5cf6","#f59e0b","#10b981",
        "#f97316","#ec4899","#6366f1","#14b8a6","#84cc16",
    ]
    cl_color_map: dict = {}

    def get_cl_color(cl: str) -> str:
        if cl not in cl_color_map:
            cl_color_map[cl] = cl_colors[len(cl_color_map) % len(cl_colors)]
        return cl_color_map[cl]

    items = []
    item_id = 1

    for (res_id, day), ops in sorted(ops_by_res_day.items()):
        # Determine shift start for this resource on this day
        schimburi = program_map.get(res_id, {}).get(day, "")
        shift_start_hour = 6  # default
        if schimburi:
            try:
                shift_start_hour = int(schimburi.split(";")[0].split("-")[0])
            except Exception:
                pass

        current_dt = datetime.combine(day, datetime.min.time()) + timedelta(hours=shift_start_hour)
        ops.sort(key=lambda o: o.id)  # preserve planner insertion order

        for op in ops:
            comanda = comanda_cache.get(op.wo)
            delivery = None
            if comanda:
                delivery = comanda.data_actualizata_livrare or comanda.dt_livr_prod

            start_dt = current_dt
            end_dt = current_dt + timedelta(hours=max(op.durata_ore, 0.25))  # min 15min bar
            current_dt = end_dt

            is_late = bool(delivery and start_dt.date() > delivery)
            color = "#dc2626" if is_late else get_cl_color(op.cl or "")

            tooltip = (
                f"<b>WO: {op.wo}</b><br>"
                f"OP: {op.op} &nbsp;|&nbsp; CL: {op.cl}<br>"
                f"Resursa: {op.resursa_nume or '-'}<br>"
                f"Durata: {op.durata_ore:.1f} h<br>"
                f"Client: {comanda.client if comanda else '-'}<br>"
                f"Articol: {(comanda.articol or '')[:60] if comanda else '-'}<br>"
                f"Data livrare: {delivery or '-'}"
                + ("<br><span style='color:#dc2626;font-weight:bold'>⚠ ÎNTÂRZIAT</span>" if is_late else "")
            )

            items.append({
                "id": item_id,
                "group": str(res_id),
                "start": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "end": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "content": f"WO:{op.wo} OP:{op.op}",
                "title": tooltip,
                "style": f"background-color:{color};border-color:{color};color:#fff;",
                "wo": op.wo,
                "op": op.op,
                "cl": op.cl,
                "durata_ore": op.durata_ore,
                "late": is_late,
            })
            item_id += 1

    return {"groups": groups, "items": items}


@app.get("/api/planificare/operatii", response_model=List[PlanificareOut])
def get_planning_results(
    cl: Optional[str] = Query(None),
    wo: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    sesiune = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
    if not sesiune:
        return []

    q = db.query(PlanificareRezultat).filter(PlanificareRezultat.sesiune_id == sesiune.id)
    if cl:
        q = q.filter(PlanificareRezultat.cl == cl)
    if wo:
        q = q.filter(PlanificareRezultat.wo == wo)
    if status:
        q = q.filter(PlanificareRezultat.status == status)
    return q.offset(offset).limit(limit).all()


# --- Stoc ---
@app.get("/api/stoc", response_model=List[StocArticol])
def get_stoc(
    search: Optional[str] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    # cantitate in Deficit table is stored as negative for B-type reservations.
    # disponibil = sold_actual + sum(cantitate)  ← correct (adding negatives = subtracting)
    # NOT sold_actual - sum(cantitate)           ← wrong (double negation inflates stock)
    q = db.query(
        Deficit.articol,
        func.max(Deficit.sold_actual).label("sold_actual"),
        func.sum(Deficit.cantitate).label("total_rezervat"),
    ).group_by(Deficit.articol)

    if search:
        q = q.filter(Deficit.articol.ilike(f"%{search}%"))

    results = q.limit(limit).all()
    return [
        StocArticol(
            articol=r[0],
            sold_actual=r[1] or 0,
            total_rezervat=r[2] or 0,
            disponibil=(r[1] or 0) + (r[2] or 0),
        )
        for r in results
    ]


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_comenzi = db.query(Comanda).count()
    comenzi_active = db.query(Comanda).filter(Comanda.status_cda == "LIBER").count()
    comenzi_stop = db.query(Comanda).filter(Comanda.status_cda == "STOP").count()
    total_dispatch = db.query(DispatchItem).count()
    total_resurse = db.query(Resursa).count()

    stadiu_counts = (
        db.query(Comanda.stadiu_prepress, func.count(Comanda.id))
        .group_by(Comanda.stadiu_prepress)
        .all()
    )

    return {
        "total_comenzi": total_comenzi,
        "comenzi_active": comenzi_active,
        "comenzi_stop": comenzi_stop,
        "total_dispatch": total_dispatch,
        "total_resurse": total_resurse,
        "stadiu_prepress": {s[0]: s[1] for s in stadiu_counts},
    }


# ── AI Assistant ──────────────────────────────────────────────────────────────
try:
    import anthropic as _anthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

_AI_SYSTEM_PROMPT = """Ești un asistent specializat EXCLUSIV în planificarea producției pentru o tipografie.

REGULI STRICTE — respectă-le întotdeauna:
1. Analizezi DOAR datele furnizate în secțiunea CONTEXT. Nu inventa, nu extrapola, nu presupune.
2. Dacă datele sunt insuficiente pentru o concluzie, spune explicit: "Date insuficiente pentru această concluzie."
3. Răspunsuri în română, structurate, max 300 cuvinte.
4. Folosește bullet points (•) pentru liste.
5. Numerele din răspuns trebuie să corespundă EXACT cu datele din context — niciun număr inventat.
6. Nu oferi sfaturi generice de management — doar analiză specifică pe datele prezente.
7. Dacă o problemă are multiple cauze posibile din date, menționează-le pe TOATE."""


def _build_ai_context(question_id: str, db: Session) -> tuple[str, str]:
    """Returns (question_text, context_text) for the AI endpoint."""
    from datetime import date
    today = date.today()

    # ── Shared: stats + latest planning session ───────────────────────────────
    total_comenzi = db.query(Comanda).count()
    comenzi_active = db.query(Comanda).filter(Comanda.status_cda == "LIBER").count()
    comenzi_stop   = db.query(Comanda).filter(Comanda.status_cda == "STOP").count()

    sesiune = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
    plan_stats: dict = {}
    if sesiune:
        for r in db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == sesiune.id
        ).all():
            plan_stats[r.status] = plan_stats.get(r.status, 0) + 1

    plan_line = (
        f"Planificate:{plan_stats.get('planned',0)} | "
        f"FaraMaterial:{plan_stats.get('no_material',0)} | "
        f"BlocateRank:{plan_stats.get('blocked_by_rank',0)} | "
        f"FaraResursa:{plan_stats.get('no_resource',0)} | "
        f"FaraBT:{plan_stats.get('no_bt',0)}"
    ) if sesiune else "Nicio sesiune de planificare disponibila"
    ses_label = (
        f"Sesiunea #{sesiune.id} din "
        f"{sesiune.created_at.strftime('%d.%m.%Y %H:%M')}"
    ) if sesiune else "N/A"

    # ── DASHBOARD: Rezumă situația ────────────────────────────────────────────
    if question_id == "dashboard_summary":
        question = "Rezumă situația curentă de producție și principalele puncte de atenție."
        stadiu_counts = (
            db.query(Comanda.stadiu_prepress, func.count(Comanda.id))
            .group_by(Comanda.stadiu_prepress)
            .all()
        )
        stadiu_str = " | ".join(
            f"{s or 'N/A'}:{c}" for s, c in stadiu_counts
        )
        context = (
            f"DATA: {today}\n"
            f"PLANIFICARE: {ses_label}\n\n"
            f"COMENZI:\n"
            f"- Total: {total_comenzi}\n"
            f"- Active (LIBER): {comenzi_active}\n"
            f"- STOP: {comenzi_stop}\n\n"
            f"REZULTATE PLANIFICARE: {plan_line}\n\n"
            f"STADIU PREPRESS: {stadiu_str}"
        )
        return question, context

    # ── DASHBOARD: Comenzi urgente ────────────────────────────────────────────
    elif question_id == "dashboard_urgent":
        question = "Care sunt comenzile urgente sau cu termenul de livrare depășit?"
        comenzi = (
            db.query(Comanda)
            .filter(Comanda.status_cda == "LIBER")
            .order_by(Comanda.data_actualizata_livrare)
            .limit(40)
            .all()
        )
        overdue, next7, next30 = [], [], []
        for c in comenzi:
            d = c.data_actualizata_livrare or c.dt_livr_prod
            if not d:
                continue
            delta = (d - today).days
            line = (
                f"WO:{c.cp} | {(c.client or 'N/A')[:22]} | "
                f"{(c.articol or '')[:32]} | Livr:{d}"
            )
            if delta < 0:
                overdue.append(f"{line} | DEPASIT {abs(delta)}z")
            elif delta <= 7:
                next7.append(f"{line} | {delta}z")
            elif delta <= 30:
                next30.append(f"{line} | {delta}z")

        context = (
            f"DATA: {today}\n"
            f"COMENZI ACTIVE: {comenzi_active}\n\n"
            f"DEPASIT TERMENUL ({len(overdue)}):\n"
            + ("\n".join(overdue[:10]) or "Niciuna") + "\n\n"
            f"LIVRARE IN 1-7 ZILE ({len(next7)}):\n"
            + ("\n".join(next7[:10]) or "Niciuna") + "\n\n"
            f"LIVRARE IN 8-30 ZILE ({len(next30)}):\n"
            + ("\n".join(next30[:10]) or "Niciuna") + "\n\n"
            f"PLANIFICARE: {plan_line}"
        )
        return question, context

    # ── DASHBOARD: Blocaje ────────────────────────────────────────────────────
    elif question_id == "dashboard_blocaje":
        question = "Unde sunt principalele blocaje în producție și ce le cauzează?"
        no_mat, blocked, no_bt_list = [], [], []
        if sesiune:
            for status_filter, target in [
                ("no_material", no_mat),
                ("blocked_by_rank", blocked),
                ("no_bt", no_bt_list),
            ]:
                rows = (
                    db.query(PlanificareRezultat.wo, func.count(PlanificareRezultat.id))
                    .filter(PlanificareRezultat.sesiune_id == sesiune.id)
                    .filter(PlanificareRezultat.status == status_filter)
                    .group_by(PlanificareRezultat.wo)
                    .order_by(func.count(PlanificareRezultat.id).desc())
                    .limit(8)
                    .all()
                )
                for wo_id, cnt in rows:
                    c = db.query(Comanda).filter(Comanda.cp == wo_id).first()
                    cl = (c.client or "N/A")[:20] if c else "N/A"
                    target.append(f"WO:{wo_id} ({cnt} op) | {cl}")

        context = (
            f"DATA: {today}\n"
            f"PLANIFICARE: {plan_line}\n\n"
            f"BLOCAJ FARA MATERIAL ({plan_stats.get('no_material',0)} op):\n"
            + ("\n".join(no_mat) or "Nicio operatie") + "\n\n"
            f"BLOCAJ RANK ({plan_stats.get('blocked_by_rank',0)} op - asteapta operatii precedente):\n"
            + ("\n".join(blocked) or "Nicio operatie") + "\n\n"
            f"FARA BUN DE TIPAR ({plan_stats.get('no_bt',0)} op):\n"
            + ("\n".join(no_bt_list) or "Nicio operatie") + "\n\n"
            f"FARA RESURSA: {plan_stats.get('no_resource',0)} op"
        )
        return question, context

    # ── PLANIFICARE: De ce sunt blocate ───────────────────────────────────────
    elif question_id == "plan_blocate":
        question = "De ce sunt comenzi blocate și care este cauza principală?"
        if not sesiune:
            return question, "Nicio sesiune de planificare. Ruleaza din Dashboard."

        blocked_ops = (
            db.query(PlanificareRezultat)
            .filter(PlanificareRezultat.sesiune_id == sesiune.id)
            .filter(PlanificareRezultat.status.in_(
                ["no_material", "blocked_by_rank", "no_resource", "no_bt"]
            ))
            .order_by(PlanificareRezultat.wo)
            .limit(60)
            .all()
        )
        wo_map: dict = {}
        for r in blocked_ops:
            if r.wo not in wo_map:
                wo_map[r.wo] = {"s": set(), "ops": [], "motiv": r.motiv}
            wo_map[r.wo]["s"].add(r.status)
            wo_map[r.wo]["ops"].append(r.op)

        lines = []
        for wo_id, info in list(wo_map.items())[:18]:
            c = db.query(Comanda).filter(Comanda.cp == wo_id).first()
            cl = (c.client or "N/A")[:20] if c else "N/A"
            d = (c.data_actualizata_livrare or c.dt_livr_prod) if c else None
            causes = "+".join(sorted(info["s"]))
            motiv = (info["motiv"] or "")[:55]
            lines.append(
                f"WO:{wo_id} | {cl} | Livr:{d} | "
                f"Cauze:{causes} | Ops:{info['ops'][:4]} | {motiv}"
            )

        total_blocked = sum(v for k, v in plan_stats.items() if k != "planned")
        context = (
            f"DATA: {today}\n"
            f"PLANIFICARE: {plan_line}\n"
            f"Total blocate: {total_blocked} din {sum(plan_stats.values())} operatii\n\n"
            f"DETALIU WO BLOCATE:\n" + "\n".join(lines)
        )
        return question, context

    # ── PLANIFICARE: Aprovizionare materiale ──────────────────────────────────
    elif question_id == "plan_aprovizionare":
        question = "Ce materiale trebuie aprovizionate urgent pentru a debloca comenzile?"
        deficits = (
            db.query(
                Deficit.articol,
                func.max(Deficit.sold_actual).label("sold"),
                func.sum(Deficit.cantitate).label("rezervat"),
            )
            .group_by(Deficit.articol)
            .all()
        )
        critical, low = [], []
        for d in deficits:
            avail = (d.sold or 0) + (d.rezervat or 0)
            art = (d.articol or "N/A")[:48]
            if avail < 0:
                critical.append(
                    f"{art} | Stoc:{d.sold:.0f} | Rez:{d.rezervat:.0f} | Deficit:{avail:.0f}"
                )
            elif avail < 10:
                low.append(
                    f"{art} | Stoc:{d.sold:.0f} | Rez:{d.rezervat:.0f} | Disp:{avail:.0f}"
                )

        context = (
            f"DATA: {today}\n"
            f"Op blocate din lipsa material: {plan_stats.get('no_material',0)}\n\n"
            f"MATERIALE IN DEFICIT NEGATIV ({len(critical)} art) — aprovizionare URGENTA:\n"
            + ("\n".join(critical[:15]) or "Niciun material") + "\n\n"
            f"MATERIALE CU STOC SCAZUT 0-10 ({len(low)} art):\n"
            + ("\n".join(low[:10]) or "Niciun material")
        )
        return question, context

    # ── PLANIFICARE: Quick wins ────────────────────────────────────────────────
    elif question_id == "plan_quickwins":
        question = "Care sunt operațiile care pot fi deblocate cel mai rapid (quick wins)?"
        if not sesiune:
            return question, "Nicio sesiune de planificare. Ruleaza din Dashboard."

        # 1. blocked_by_rank with near delivery — predecessor may already be done
        rank_blocked = (
            db.query(PlanificareRezultat)
            .filter(PlanificareRezultat.sesiune_id == sesiune.id)
            .filter(PlanificareRezultat.status == "blocked_by_rank")
            .limit(50)
            .all()
        )
        rank_lines = []
        for r in rank_blocked:
            c = db.query(Comanda).filter(Comanda.cp == r.wo).first()
            d = (c.data_actualizata_livrare or c.dt_livr_prod) if c else None
            delta = (d - today).days if d else 999
            motiv = (r.motiv or "")[:70]
            rank_lines.append(
                (delta, f"WO:{r.wo} OP:{r.op} CL:{r.cl} | Livr:{d} ({delta}z) | {motiv}")
            )
        rank_lines.sort(key=lambda x: x[0])

        # 2. small material deficits — cheap to fix
        deficits = (
            db.query(
                Deficit.articol,
                func.max(Deficit.sold_actual).label("sold"),
                func.sum(Deficit.cantitate).label("rezervat"),
            )
            .group_by(Deficit.articol)
            .all()
        )
        small_def = []
        for d in deficits:
            avail = (d.sold or 0) + (d.rezervat or 0)
            if -100 < avail < 0:
                small_def.append(
                    f"{(d.articol or '')[:48]} | Deficit mic: {avail:.0f} unitati"
                )

        context = (
            f"DATA: {today}\n"
            f"PLANIFICARE: {plan_line}\n\n"
            f"OPERATII BLOCATE-RANK CU LIVRARE APROPIATA (verifica daca predecesorul e finalizat):\n"
            + ("\n".join([x[1] for x in rank_lines[:12]]) or "Nicio operatie") + "\n\n"
            f"MATERIALE CU DEFICIT MIC (<100 unitati) — comanda rapida poate debloca:\n"
            + ("\n".join(small_def[:10]) or "Niciun material cu deficit mic")
        )
        return question, context

    return "Întrebare necunoscută.", "Nu există context disponibil."


@app.get("/api/ai/analyze")
async def ai_analyze(
    question_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Stream an AI analysis via SSE. Each chunk: data: {"text": "..."}\n\n"""

    async def _error_stream(msg: str):
        yield f"data: {_json.dumps({'text': msg})}\n\n"
        yield "data: [DONE]\n\n"

    if not _ANTHROPIC_OK:
        return StreamingResponse(
            _error_stream("Pachetul 'anthropic' nu este instalat pe server. Rulati: pip install anthropic"),
            media_type="text/event-stream",
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return StreamingResponse(
            _error_stream(
                "ANTHROPIC_API_KEY nu este configurat pe server.\n"
                "Adaugati-l in /etc/systemd/system/arta-grafica.service:\n"
                "Environment=ANTHROPIC_API_KEY=sk-ant-..."
            ),
            media_type="text/event-stream",
        )

    try:
        question, context = _build_ai_context(question_id, db)
    except Exception as exc:
        return StreamingResponse(
            _error_stream(f"Eroare la construirea contextului: {exc}"),
            media_type="text/event-stream",
        )

    async def _stream():
        try:
            client = _anthropic.AsyncAnthropic(api_key=api_key)
            async with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=1200,
                thinking={"type": "adaptive"},
                system=_AI_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"CONTEXT:\n{context}\n\nÎNTREBARE: {question}",
                }],
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {_json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'text': f'[Eroare API: {exc}]'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Serve React frontend (production build) ───────────────────────────────────
_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        """Catch-all: return index.html for SPA routing."""
        file_path = os.path.join(_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(
            os.path.join(_DIST, "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
