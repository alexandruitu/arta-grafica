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


def find_slot(
    resursa_id: int,
    disponibilitate: dict,
    hours_needed: float,
    earliest_start: date,
) -> tuple[date | None, date | None, float]:
    """
    Find the first contiguous (calendar) block of availability starting from
    earliest_start that can accommodate hours_needed.

    Returns (slot_start, slot_end, hours_used_on_last_day).
    slot_start / slot_end are dates.
    hours_used_on_last_day is needed to compute the exact end time.
    """
    hours_remaining = hours_needed
    slot_start = None
    slot_end = None
    hours_used_on_last_day = 0.0

    for day_offset in range(730):  # Search up to 2 years
        check_date = earliest_start + timedelta(days=day_offset)
        avail = disponibilitate[resursa_id].get(check_date, 0.0)

        if avail <= 0:
            continue

        if slot_start is None:
            slot_start = check_date

        if avail >= hours_remaining:
            disponibilitate[resursa_id][check_date] -= hours_remaining
            hours_used_on_last_day = hours_remaining
            slot_end = check_date
            hours_remaining = 0.0
            break
        else:
            hours_remaining -= avail
            hours_used_on_last_day = avail
            disponibilitate[resursa_id][check_date] = 0.0
            slot_end = check_date

    if hours_remaining <= 0.0 and slot_start and slot_end:
        return slot_start, slot_end, hours_used_on_last_day
    return None, None, 0.0


def run_planning(db: Session) -> dict:
    """Execute the planning algorithm."""
    sesiune = PlanificareSesiune(
        created_at=datetime.now(),
        status="running",
    )
    db.add(sesiune)
    db.flush()

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

    # disponibilitate[resursa_id][date] = ore_ramase  (decremented as ops are placed)
    disponibilitate: dict[int, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for prog in db.query(ProgramResursa).all():
        disponibilitate[prog.resursa_id][prog.data] = prog.ore_disponibile

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
        # Reserve materials (subtract from stock) if all available
        if not material_lipsit:
            for art, cantitate in materiale:
                stoc_tracker[art] = stoc_tracker.get(art, 0.0) - cantitate

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

        # ── Per-WO rank tracking ──────────────────────────────────────────────
        # rank_status[rank] = "completed" | "planned" | "previzionat" | "open"
        # rank_end_date[rank] = date when this rank's operation is expected to finish
        #                        (used to set earliest_start for successor ranks)
        #
        # IMPORTANT: Multiple ops can share the same rank.  We must keep the
        # MOST RESTRICTIVE status: open > planned/previzionat > completed.  And we must
        # keep the LATEST end-date among all planned ops at a rank so that
        # successor ranks start after ALL predecessors finish.
        rank_status: dict[int, str] = {}
        rank_end_date: dict[int, date] = {}

        # Priority: open=2, planned/previzionat=1, completed=0  (higher = more restrictive)
        _STATUS_PRIO = {"completed": 0, "planned": 1, "previzionat": 1, "open": 2}

        def update_rank(rank: int, new_status: str, end_date: date | None = None):
            """Update rank tracking, keeping the most restrictive status."""
            old_prio = _STATUS_PRIO.get(rank_status.get(rank, ""), -1)
            new_prio = _STATUS_PRIO[new_status]
            if new_prio >= old_prio:
                rank_status[rank] = new_status
            if end_date is not None:
                # Keep latest end-date among planned ops at this rank
                if rank not in rank_end_date or end_date > rank_end_date[rank]:
                    rank_end_date[rank] = end_date

        for disp in dispatch_items:
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
            earliest_start = today
            if wo_previzionat_start:
                earliest_start = max(earliest_start, wo_previzionat_start)
            for prev_rank, prev_status in rank_status.items():
                if prev_rank >= rank:
                    continue
                if prev_status == "open":
                    blocked = True
                    break
                if prev_status in ("planned", "previzionat") and prev_rank in rank_end_date:
                    # Must start the day after predecessor finishes
                    earliest_start = max(
                        earliest_start,
                        rank_end_date[prev_rank] + timedelta(days=1),
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

            # Pick first valid resource with an available slot starting from earliest_start
            # find_slot modifies disponibilitate in-place, so we stop at first success
            allocated = False
            for r in valid_resurse:
                slot_start, slot_end, hours_last_day = find_slot(
                    r.id, disponibilitate, remaining, earliest_start
                )
                if slot_start is None:
                    continue  # no room on this resource, try next

                # Use date-only boundaries (exclusive end = next day after last working day).
                # This ensures frappe-gantt Day-view bars are at least 1 column wide
                # and that chained operations on consecutive days are visually separated.
                data_start = datetime.combine(slot_start, datetime.min.time())
                data_end   = datetime.combine(slot_end + timedelta(days=1), datetime.min.time())

                final_status = "previzionat" if wo_previzionat_start is not None else "planned"
                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=r.id, resursa_nume=r.resursa,
                    data_start=data_start, data_end=data_end,
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
