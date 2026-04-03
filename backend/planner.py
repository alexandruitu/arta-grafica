from __future__ import annotations
"""
Production Planning Algorithm.

Flow:
1. Sort orders: "06 - In productie" first, then descending by StadiuPrepress,
   then by delivery date (DataActualizataLivrare or DtLivrProd)
2. Exclude Status_cda = STOP
3. For each order, get dispatch operations sorted by rank
4. For each operation, check:
   a. BT (Bun de Tipar) exists on the order
   b. Lower-rank operations are not "open" (completed or planned is OK)
      - If predecessor is "planned", this op starts after predecessor's planned end
   c. Materials are available (SoldActual - already reserved > 0)
   d. Resource is available (CL match + hours available on date)
5. Allocate to first available slot starting from earliest_start
6. Time = P_Setup + P_Runtime - R_Runtime
"""
from datetime import date, datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from models import (
    Comanda, DispatchItem, Operatie, Deficit, Resursa, ProgramResursa,
    PlanificareSesiune, PlanificareRezultat,
)

# StadiuPrepress priority (higher number = higher priority in planning)
STADIU_PRIORITY = {
    "06 - In productie": 100,
    "05 - BT existent": 50,
    "04 - Trimis la BT": 40,
    "03 - Fisiere existente": 30,
    "02 - Job creat": 20,
    "01 - Fara Fisiere": 10,
    "00 - N/A": 0,
}

INVALID_BT_DATE = "1911-11-11"

SHIFT_START_H = 6   # 06:00 shift start
SHIFT_END_H = 22    # 22:00 shift end


def get_stadiu_priority(stadiu: str | None) -> int:
    if not stadiu:
        return 0
    return STADIU_PRIORITY.get(stadiu, 0)


def has_valid_bt(comanda: Comanda) -> bool:
    """Check if Bun de Tipar exists (at least one BT field is not empty/invalid)."""
    for bt in [comanda.bt1, comanda.bt2, comanda.bt3, comanda.bt4]:
        if bt and bt.strip() and bt.strip() != INVALID_BT_DATE:
            return True
    return False


def get_delivery_date(comanda: Comanda) -> date:
    """Get the relevant delivery date for sorting."""
    if comanda.tip_comanda == "V" and comanda.data_actualizata_livrare:
        return comanda.data_actualizata_livrare
    if comanda.dt_livr_prod:
        return comanda.dt_livr_prod
    if comanda.data_actualizata_livrare:
        return comanda.data_actualizata_livrare
    if comanda.data_estimata_livrare:
        return comanda.data_estimata_livrare
    return date(2099, 12, 31)  # fallback: end of queue


def calc_remaining_time(disp: DispatchItem) -> float:
    """Calculate remaining time in hours: P_Setup + P_Runtime - R_Runtime."""
    return max(0.0, disp.p_setup + disp.p_runtime - disp.r_runtime)


def find_slot_precise(
    resursa_id: int,
    disponibilitate: dict,
    next_free_time: dict,
    hours_needed: float,
    earliest_start: datetime,
) -> tuple[datetime | None, datetime | None]:
    """
    Find when a resource can fit hours_needed, respecting shift bounds (6-22).

    Uses next_free_time[resursa_id] to know when the resource is next free
    (hour-level precision). disponibilitate is used read-only to check
    whether a date is a working day.

    Returns (slot_start, slot_end) as datetimes, or (None, None) if no slot
    found within 730 days.

    Updates next_free_time[resursa_id] = slot_end on success.
    """
    candidate = max(earliest_start, next_free_time.get(resursa_id, earliest_start))

    slot_start: datetime | None = None
    slot_end: datetime | None = None
    hours_remaining = hours_needed

    for day_offset in range(730):
        check_date = candidate.date() + timedelta(days=day_offset)

        # Check if this is a working day for this resource
        if disponibilitate[resursa_id].get(check_date, 0.0) <= 0:
            continue

        # Determine start time on this day (in fractional hours)
        if day_offset == 0:
            start_h = candidate.hour + candidate.minute / 60.0
            start_h = max(start_h, float(SHIFT_START_H))
        else:
            start_h = float(SHIFT_START_H)

        hours_available = float(SHIFT_END_H) - start_h
        if hours_available <= 0:
            # Past shift end on candidate's date; next day will use SHIFT_START_H
            continue

        if slot_start is None:
            start_hour = int(start_h)
            start_minute = round((start_h - start_hour) * 60)
            slot_start = datetime(
                check_date.year, check_date.month, check_date.day,
                start_hour, start_minute,
            )

        if hours_available >= hours_remaining:
            end_h = start_h + hours_remaining
            end_hour = int(end_h)
            end_minute = round((end_h - end_hour) * 60)
            if end_minute >= 60:
                end_hour += 1
                end_minute = 0
            slot_end = datetime(
                check_date.year, check_date.month, check_date.day,
                end_hour, end_minute,
            )
            hours_remaining = 0.0
            break
        else:
            hours_remaining -= hours_available
            slot_end = datetime(
                check_date.year, check_date.month, check_date.day,
                SHIFT_END_H, 0,
            )

    if hours_remaining <= 0.0 and slot_start is not None and slot_end is not None:
        next_free_time[resursa_id] = slot_end
        return slot_start, slot_end
    return None, None


def run_planning(db: Session) -> dict:
    """Execute the planning algorithm."""
    sesiune = PlanificareSesiune(
        created_at=datetime.now(),
        status="running",
    )
    db.add(sesiune)
    db.flush()

    # ── Step 0: Load frozen operations from the last completed session ─────────
    prev_sesiune = (
        db.query(PlanificareSesiune)
        .filter(PlanificareSesiune.status == "completed")
        .order_by(PlanificareSesiune.id.desc())
        .first()
    )
    frozen_ops: dict[tuple[int, int], PlanificareRezultat] = {}
    if prev_sesiune:
        for fr in db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == prev_sesiune.id,
            PlanificareRezultat.frozen == True,
        ).all():
            frozen_ops[(fr.wo, fr.op)] = fr

    # ── Step 1: Load and sort orders ──────────────────────────────────────────
    comenzi = (
        db.query(Comanda)
        .filter(Comanda.status_cda != "STOP")
        .filter(Comanda.cp > 0)
        .all()
    )

    comenzi.sort(key=lambda c: (
        -get_stadiu_priority(c.stadiu_prepress),  # Higher priority first
        get_delivery_date(c),                      # Earlier delivery first
    ))

    # ── Step 2: Load operations catalog (for rank lookup) ────────────────────
    operatii_catalog: dict[str, Operatie] = {}
    for op in db.query(Operatie).all():
        operatii_catalog[op.cod] = op

    # ── Step 3: Load resources and their schedules ───────────────────────────
    resurse = db.query(Resursa).all()
    resurse_by_cl: dict[str, list[Resursa]] = defaultdict(list)
    for r in resurse:
        resurse_by_cl[r.cl].append(r)

    # disponibilitate[resursa_id][date] = ore_disponibile
    # Used read-only to check whether a date is a working day for a resource.
    disponibilitate: dict[int, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for prog in db.query(ProgramResursa).all():
        disponibilitate[prog.resursa_id][prog.data] = prog.ore_disponibile

    # next_free_time[resursa_id] = datetime when resource next becomes free
    next_free_time: dict[int, datetime] = {}

    # Pre-populate next_free_time from frozen operations
    for fr in frozen_ops.values():
        if fr.resursa_id and fr.data_end:
            existing = next_free_time.get(fr.resursa_id)
            if existing is None or fr.data_end > existing:
                next_free_time[fr.resursa_id] = fr.data_end

    # ── Step 4: Build material stock tracker ─────────────────────────────────
    # stoc_tracker[articol] = available quantity (updated as WOs are reserved)
    # wo_materiale[wo_str]  = [(articol, cantitate), ...]  (cantitate < 0 = B-type reservation)
    stoc_tracker: dict[str, float] = {}
    wo_materiale: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for d in db.query(Deficit).all():
        art = d.articol
        if art not in stoc_tracker:
            stoc_tracker[art] = d.sold_actual if d.sold_actual else 0.0
        if d.tip_rezervare == "B" and d.pe_comanda:
            # Store the absolute value of cantitate as the amount NEEDED.
            # ERP may export positive or negative values for reservations.
            cantitate = abs(d.cantitate) if d.cantitate else 0.0
            wo_materiale[str(d.pe_comanda)].append((art, cantitate))

    # ── Step 4b: Build A-type arrival timeline per article ────────────────────
    # artikel_arrivals[articol] = sorted [(date, qty)] from aprovizionare records
    artikel_arrivals: dict[str, list] = defaultdict(list)
    for d in db.query(Deficit).filter(
        Deficit.tip_rezervare == "A",
        Deficit.la_data.isnot(None),
    ).all():
        if d.articol and d.cantitate and d.cantitate > 0:
            artikel_arrivals[d.articol].append((d.la_data, d.cantitate))
    for art in artikel_arrivals:
        artikel_arrivals[art].sort(key=lambda x: x[0])

    # ── Step 5: Operation capability map per resource ────────────────────────
    resursa_operatii: dict[int, set[str]] = {}
    for r in resurse:
        if r.operatii:
            resursa_operatii[r.id] = {c.strip() for c in r.operatii.split(";")}
        else:
            resursa_operatii[r.id] = set()

    # ── Step 6: Plan operations ───────────────────────────────────────────────
    stats = {
        "planned": 0,
        "previzionat": 0,
        "no_material": 0,
        "no_resource": 0,
        "blocked_by_rank": 0,
        "no_bt": 0,
        "completed": 0,
    }
    today = date.today()
    today_dt = datetime(today.year, today.month, today.day, SHIFT_START_H)

    for comanda in comenzi:
        dispatch_items = (
            db.query(DispatchItem)
            .filter(DispatchItem.wo == comanda.cp)
            .all()
        )
        if not dispatch_items:
            continue

        def get_rank(d: DispatchItem) -> int:
            op_code = str(d.op)
            if op_code in operatii_catalog:
                return operatii_catalog[op_code].rank
            return 999

        dispatch_items.sort(key=get_rank)

        # ── Material check at WO level ────────────────────────────────────────
        wo_str = str(comanda.cp)
        materiale = wo_materiale.get(wo_str, [])
        material_lipsit = None
        for art, cantitate in materiale:
            available = stoc_tracker.get(art, 0.0)
            if available < cantitate:
                material_lipsit = (art, available, cantitate)
                break

        # ── Determine WO-level planning mode ─────────────────────────────────
        wo_block: tuple[str, str] | None = None
        wo_previzionat_start: date | None = None

        if not has_valid_bt(comanda):
            if comanda.data_limita_bt:
                wo_previzionat_start = comanda.data_limita_bt
            else:
                wo_block = ("no_bt", "Comanda nu are Bun de Tipar valid si nu are data limita BT")

        if wo_block is None and material_lipsit:
            art, available, cantitate_needed = material_lipsit
            deficit_qty = cantitate_needed - available
            mat_date = None
            cumulative = 0.0
            for arr_date, arr_qty in artikel_arrivals.get(art, []):
                cumulative += arr_qty
                if cumulative >= deficit_qty:
                    mat_date = arr_date
                    break
            if mat_date is None:
                wo_block = (
                    "no_material",
                    f"Stoc insuficient {art}: disponibil={available:.0f}, necesar={cantitate_needed:.0f}, aprovizionare insuficienta",
                )
            else:
                new_start = mat_date
                wo_previzionat_start = max(wo_previzionat_start, new_start) if wo_previzionat_start else new_start

        # Reserve materials only if WO is not hard-blocked.
        # Previzionat WOs are considered committed (material will arrive), so
        # we still deduct their stock to avoid double-counting.
        if wo_block is None and not material_lipsit:
            for art, cantitate in materiale:
                stoc_tracker[art] = stoc_tracker.get(art, 0.0) - cantitate

        # ── Per-WO rank tracking ──────────────────────────────────────────────
        # rank_status[rank] = "completed" | "planned" | "previzionat" | "open"
        # rank_end_date[rank] = datetime when this rank's operation is expected to finish
        #                        (used to set earliest_start for successor ranks)
        #
        # IMPORTANT: Multiple ops can share the same rank.  We must keep the
        # MOST RESTRICTIVE status: open > planned/previzionat > completed.  And we must
        # keep the LATEST end-date among all planned ops at a rank so that
        # successor ranks start after ALL predecessors finish.
        rank_status: dict[int, str] = {}
        rank_end_date: dict[int, datetime] = {}

        # Priority: open=2, planned/previzionat=1, completed=0  (higher = more restrictive)
        _STATUS_PRIO = {"completed": 0, "planned": 1, "previzionat": 1, "open": 2}

        def update_rank(rank: int, new_status: str, end_dt: datetime | None = None):
            """Update rank tracking, keeping the most restrictive status."""
            old_prio = _STATUS_PRIO.get(rank_status.get(rank, ""), -1)
            new_prio = _STATUS_PRIO[new_status]
            if new_prio >= old_prio:
                rank_status[rank] = new_status
            if end_dt is not None:
                # Keep latest end-datetime among planned ops at this rank
                if rank not in rank_end_date or end_dt > rank_end_date[rank]:
                    rank_end_date[rank] = end_dt

        for disp in dispatch_items:
            # ── Frozen: carry from previous session unchanged ─────────────────
            key = (disp.wo, disp.op)
            if key in frozen_ops:
                fr = frozen_ops[key]
                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id,
                    dispatch_id=disp.id,
                    wo=fr.wo, op=fr.op, cl=fr.cl,
                    resursa_id=fr.resursa_id, resursa_nume=fr.resursa_nume,
                    data_start=fr.data_start, data_end=fr.data_end,
                    durata_ore=fr.durata_ore,
                    frozen=True, status=fr.status, motiv=None,
                ))
                stats[fr.status] += 1
                frozen_rank = get_rank(disp)
                update_rank(frozen_rank, fr.status, fr.data_end if fr.data_end else None)
                continue

            remaining = calc_remaining_time(disp)
            op_code = str(disp.op)
            rank = get_rank(disp)

            # ── Already completed ─────────────────────────────────────────────
            if remaining <= 0:
                update_rank(rank, "completed")
                stats["completed"] += 1
                continue

            # ── WO-level hard block ───────────────────────────────────────────
            if wo_block:
                block_status, block_motiv = wo_block
                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=None, resursa_nume=None,
                    data_start=None, data_end=None, durata_ore=remaining,
                    status=block_status, motiv=block_motiv,
                ))
                stats[block_status] += 1
                update_rank(rank, "open")
                continue

            # ── Check 2: Rank dependency ──────────────────────────────────────
            # - predecessor "open"    → blocked (can't plan until it's placed/done)
            # - predecessor "planned"/"previzionat" → OK, but start AFTER predecessor ends
            # - predecessor "completed" → no constraint
            blocked = False
            earliest_start = today_dt
            if wo_previzionat_start:
                previz_dt = datetime(
                    wo_previzionat_start.year, wo_previzionat_start.month,
                    wo_previzionat_start.day, SHIFT_START_H,
                )
                earliest_start = max(earliest_start, previz_dt)
            for prev_rank, prev_status in rank_status.items():
                if prev_rank >= rank:
                    continue
                if prev_status == "open":
                    blocked = True
                    break
                if prev_status in ("planned", "previzionat") and prev_rank in rank_end_date:
                    # Must start after predecessor finishes (hour precision)
                    earliest_start = max(
                        earliest_start,
                        rank_end_date[prev_rank],
                    )

            if blocked:
                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=None, resursa_nume=None,
                    data_start=None, data_end=None, durata_ore=remaining,
                    status="blocked_by_rank",
                    motiv=f"Operatie cu rank inferior inca deschisa/neplanificata",
                ))
                stats["blocked_by_rank"] += 1
                update_rank(rank, "open")
                continue

            # ── Check 4: Find available resource ─────────────────────────────
            cl = disp.cl
            candidate_resurse = resurse_by_cl.get(cl, [])

            # Filter to resources that support this operation code
            valid_resurse = [
                r for r in candidate_resurse
                if not resursa_operatii.get(r.id) or op_code in resursa_operatii[r.id]
            ]

            # Pick first valid resource with an available slot starting from earliest_start.
            # find_slot_precise updates next_free_time in-place on success.
            allocated = False
            for r in valid_resurse:
                slot_start, slot_end = find_slot_precise(
                    r.id, disponibilitate, next_free_time, remaining, earliest_start
                )
                if slot_start is None:
                    continue  # no room on this resource, try next

                final_status = "previzionat" if wo_previzionat_start is not None else "planned"
                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=r.id, resursa_nume=r.resursa,
                    data_start=slot_start, data_end=slot_end,
                    durata_ore=remaining,
                    status=final_status, motiv=None,
                ))
                stats[final_status] += 1
                update_rank(rank, final_status, slot_end)
                allocated = True
                break

            if not allocated:
                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=None, resursa_nume=None,
                    data_start=None, data_end=None, durata_ore=remaining,
                    status="no_resource",
                    motiv=f"Nu exista resursa disponibila in CL={cl} (earliest={earliest_start})",
                ))
                stats["no_resource"] += 1
                update_rank(rank, "open")

    # ── Finalize session ──────────────────────────────────────────────────────
    total = sum(v for k, v in stats.items() if k != "completed")
    sesiune.status = "completed"
    sesiune.total_operatii = total + stats["completed"]
    sesiune.operatii_planificate = stats["planned"] + stats["previzionat"]
    sesiune.operatii_neplanificate = total - stats["planned"] - stats["previzionat"]
    db.commit()

    return {
        "sesiune_id": sesiune.id,
        "stats": stats,
        "total_comenzi": len(comenzi),
    }
