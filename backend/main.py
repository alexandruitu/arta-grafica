"""FastAPI backend for Arta Grafica Production Planning."""
from __future__ import annotations
import os
from typing import List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

app = FastAPI(title="Arta Grafica - Production Planning", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        return FileResponse(os.path.join(_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
