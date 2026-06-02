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
from zoneinfo import ZoneInfo
from collections import defaultdict

TZ_RO = ZoneInfo("Europe/Bucharest")

def _localize(dt: datetime | None) -> datetime | None:
    """Attach TZ_RO to naive datetimes read back from SQLite."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=TZ_RO)

from sqlalchemy.orm import Session
from models import (
    Comanda, DispatchItem, Operatie, Deficit, Resursa, ProgramResursa,
    PlanificareSesiune, PlanificareRezultat,
)

# StadiuPrepress priority (higher number = higher priority in planning)
# "00 - N/A" = treated same as "In productie": already in production, no BT needed.
STADIU_PRIORITY = {
    "06 - In productie": 100,
    "05 - BT existent": 50,
    "04 - Trimis la BT": 40,
    "03 - Fisiere existente": 30,
    "02 - Job creat": 20,
    "01 - Fara Fisiere": 10,
    "00 - N/A": 100,  # Treated as "in production" — top priority, no BT required
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
    dry_run: bool = False,
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
                tzinfo=TZ_RO,
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
                tzinfo=TZ_RO,
            )
            hours_remaining = 0.0
            break
        else:
            hours_remaining -= hours_available
            slot_end = datetime(
                check_date.year, check_date.month, check_date.day,
                SHIFT_END_H, 0,
                tzinfo=TZ_RO,
            )

    if hours_remaining <= 0.0 and slot_start is not None and slot_end is not None:
        if not dry_run:
            next_free_time[resursa_id] = slot_end
        return slot_start, slot_end
    return None, None


def run_planning(
    db: Session,
    ignore_material: bool = False,
    ignore_rank: bool = False,
) -> dict:
    """Execute the planning algorithm.

    ignore_material: skip material availability checks (plan even if stock is insufficient)
    ignore_rank:     skip rank dependency checks (plan operations out of rank order)
    """
    sesiune = PlanificareSesiune(
        created_at=datetime.now(TZ_RO),
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

    # ── Step 1: Load orders ───────────────────────────────────────────────────
    comenzi = (
        db.query(Comanda)
        .filter(Comanda.status_cda != "STOP")
        .filter(Comanda.cp > 0)
        .all()
    )

    # ── Step 1b: Pre-scan material availability per WO for sort priority ──────
    # Quick stock snapshot (sold_actual) without modifying stoc_tracker yet.
    # wo_has_material[cp] = True if SOLD - REZ > 0 for all needed articles.
    _stoc_snap: dict[str, float] = {}
    _wo_mat_snap: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for d in db.query(Deficit).all():
        art = d.articol
        if art and art not in _stoc_snap:
            _stoc_snap[art] = d.sold_actual if d.sold_actual else 0.0
        if d.tip_rezervare == "B" and d.pe_comanda and d.articol:
            cantitate = abs(d.cantitate) if d.cantitate else 0.0
            _wo_mat_snap[str(d.pe_comanda)].append((d.articol, cantitate))

    def wo_has_material(cp: int) -> bool:
        """True if current stock covers ALL non-trivial reservations for this WO."""
        for art, needed in _wo_mat_snap.get(str(cp), []):
            if needed <= 0.01:
                continue  # negligible consumption — ignore
            if art and art.startswith("MS"):
                continue  # MS-prefixed materials are excluded from planning checks
            if _stoc_snap.get(art, 0.0) < needed:
                return False
        return True

    # Sort: higher stadiu → earlier delivery → WITH material first (Planificată > Previzionată)
    comenzi.sort(key=lambda c: (
        -get_stadiu_priority(c.stadiu_prepress),  # Higher priority first
        get_delivery_date(c),                      # Earlier delivery first
        0 if wo_has_material(c.cp) else 1,         # With material before without
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

    # wo_last_end[wo] = latest data_end among all planned ops for this WO.
    # Ensures that operations within the same WO are always sequential —
    # a product can only be in ONE place at a time, even if two ops share
    # the same rank and end up on different resources within the same CL.
    wo_last_end: dict[int, datetime] = {}

    # Pre-populate next_free_time and wo_last_end from frozen operations
    for fr in frozen_ops.values():
        if fr.resursa_id and fr.data_end:
            end = _localize(fr.data_end)
            existing = next_free_time.get(fr.resursa_id)
            if existing is None or end > existing:
                next_free_time[fr.resursa_id] = end
        if fr.data_end:
            end = _localize(fr.data_end)
            wo_existing = wo_last_end.get(fr.wo)
            if wo_existing is None or end > wo_existing:
                wo_last_end[fr.wo] = end

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
    # Also add undated external aprovizionari (no la_data, not from internal WO)
    # directly to stoc_tracker — these are confirmed purchase orders without ETA.
    artikel_arrivals: dict[str, list] = defaultdict(list)
    for d in db.query(Deficit).filter(
        Deficit.tip_rezervare == "A",
        Deficit.cantitate > 0,
    ).all():
        if not d.articol:
            continue
        # Skip internal WO-production records (prefabricate) — handled separately
        is_prefabricat = d.rezervat_in and (
            "COMAND" in d.rezervat_in.upper() and "LUCRU" in d.rezervat_in.upper()
        )
        if is_prefabricat:
            continue
        if d.la_data is not None:
            artikel_arrivals[d.articol].append((d.la_data, d.cantitate))
        else:
            # No arrival date → treat as available in current stock
            # (confirmed purchase order without ETA — e.g., +272.000 supply orders)
            stoc_tracker[d.articol] = stoc_tracker.get(d.articol, 0.0) + d.cantitate
    for art in artikel_arrivals:
        artikel_arrivals[art].sort(key=lambda x: x[0])

    # ── Step 4c: Build prefabricat map ────────────────────────────────────────
    # prefabricat_map[articol] = [wo_producator, ...]
    # Prefabricatele sunt articole produse de WO-uri interne (A-type cu
    # rezervat_in continand "COMAND" si "LUCRU"), nu cumparate de la furnizori.
    prefabricat_map: dict[str, list[int]] = {}
    for d in db.query(Deficit).filter(
        Deficit.tip_rezervare == "A",
        Deficit.rezervat_in.ilike("%COMAND%LUCRU%"),
        Deficit.pe_comanda.isnot(None),
    ).all():
        if d.articol:
            wos = prefabricat_map.setdefault(d.articol, [])
            if d.pe_comanda not in wos:
                wos.append(d.pe_comanda)

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
        "previzionat_bt": 0,            # previzionat: fara BT dar cu data_limita_bt
        "previzionat_material": 0,      # previzionat: fara material dar cu aprovizionare
        "previzionat_semifabricat": 0,  # previzionat: material e produs de un WO intern planificat
        "no_material": 0,
        "blocat_semifabricat": 0,       # material lipsa, produs de un WO intern NEPLANIFICAT
        "no_resource": 0,
        "blocked_by_rank": 0,
        "no_bt": 0,
        "completed": 0,
    }
    # Use current datetime as planning start — operations won't be scheduled in the past.
    # Clamp to shift hours: before shift → use shift start; after shift → next day shift start.
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
            if cantitate <= 0.01:
                continue  # negligible consumption — skip material check
            if art and art.startswith("MS"):
                continue  # MS-prefixed materials excluded from planning checks
            available = stoc_tracker.get(art, 0.0)
            if available < cantitate:
                material_lipsit = (art, available, cantitate)
                break

        # ── Determine WO-level planning mode ─────────────────────────────────
        wo_block: tuple[str, str] | None = None
        wo_previzionat_start: date | None = None
        # Tracks WHY this WO is previzionat — used for status sub-type
        wo_previzionat_reason: str = ""   # "bt" | "material" | "bt+material"

        stadiu_priority_val = get_stadiu_priority(comanda.stadiu_prepress)

        # BT check: skip for high-stadiu orders (≥ 50) — BT already exists or not needed.
        # "05 - BT existent" (50), "06 - In productie" (100), "00 - N/A" (100) are all exempt.
        if stadiu_priority_val < 50 and not has_valid_bt(comanda):
            if comanda.data_limita_bt:
                wo_previzionat_start = comanda.data_limita_bt
                wo_previzionat_reason = "bt"
            else:
                wo_block = ("no_bt", "Comanda nu are Bun de Tipar valid si nu are data limita BT")

        if wo_block is None and material_lipsit and not ignore_material:
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
                # Check if the missing article is a prefabricat (produced by another WO)
                producer_wos = prefabricat_map.get(art, [])
                if producer_wos:
                    wos_str = ",".join(str(w) for w in producer_wos)
                    # Check if any producer WO has a planned end date in this session
                    producer_end_dates = [_localize(wo_last_end[pwo]) for pwo in producer_wos if pwo in wo_last_end]
                    for (fw, _fp), fr in frozen_ops.items():
                        if fw in producer_wos and fr.data_end:
                            producer_end_dates.append(_localize(fr.data_end))
                    if producer_end_dates:
                        # Producer is planned → this WO is previzionat (starts after producer finishes)
                        semi_end_date = max(producer_end_dates).date()
                        wo_previzionat_start = max(wo_previzionat_start, semi_end_date) if wo_previzionat_start else semi_end_date
                        wo_previzionat_reason = (
                            wo_previzionat_reason + "+semifabricat" if wo_previzionat_reason else "semifabricat"
                        )
                    else:
                        # Producer not yet planned → hard block
                        wo_block = (
                            "blocat_semifabricat",
                            f"prefabricat:{wos_str}:{art}",
                        )
                else:
                    wo_block = (
                        "no_material",
                        f"Stoc insuficient {art}: disponibil={available:.0f}, necesar={cantitate_needed:.0f}, aprovizionare insuficienta",
                    )
            else:
                new_start = mat_date
                wo_previzionat_start = max(wo_previzionat_start, new_start) if wo_previzionat_start else new_start
                # Mark material as previzionat reason (may combine with BT reason)
                wo_previzionat_reason = (
                    "bt+material" if wo_previzionat_reason == "bt" else "material"
                )

        # Reserve materials if WO is not hard-blocked.
        # Previzionat WOs (material arriving later / semifabricat in production) are
        # still committed — deduct their stock to prevent double-allocation downstream.
        if wo_block is None:
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

        # Priority: open=2, placed(planned/previzionat*)=1, completed=0  (higher = more restrictive)
        _STATUS_PRIO = {
            "completed": 0,
            "planned": 1, "previzionat_bt": 1, "previzionat_material": 1, "previzionat_semifabricat": 1,
            "open": 2,
        }

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
                # Auto-unfreeze: if the operation is now completed in ERP, don't carry the frozen slot
                if calc_remaining_time(disp) <= 0:
                    update_rank(rank, "completed")
                    stats["completed"] += 1
                    continue
                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id,
                    dispatch_id=disp.id,
                    wo=fr.wo, op=fr.op, cl=fr.cl,
                    resursa_id=fr.resursa_id, resursa_nume=fr.resursa_nume,
                    data_start=_localize(fr.data_start), data_end=_localize(fr.data_end),
                    durata_ore=fr.durata_ore,
                    frozen=True, status=fr.status, motiv=None,
                ))
                # Migrate legacy "previzionat" status from older sessions
                frozen_status = fr.status
                if frozen_status == "previzionat":
                    frozen_status = "previzionat_bt"
                stats[frozen_status] = stats.get(frozen_status, 0) + 1
                frozen_rank = get_rank(disp)
                update_rank(frozen_rank, frozen_status, _localize(fr.data_end) if fr.data_end else None)
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
                    tzinfo=TZ_RO,
                )
                earliest_start = max(earliest_start, previz_dt)
            for prev_rank, prev_status in rank_status.items():
                if prev_rank >= rank:
                    continue
                if prev_status == "open":
                    blocked = True
                    break
                if prev_status in ("planned", "previzionat_bt", "previzionat_material", "previzionat_semifabricat") and prev_rank in rank_end_date:
                    # Must start after predecessor finishes (hour precision)
                    earliest_start = max(
                        earliest_start,
                        rank_end_date[prev_rank],
                    )

            if blocked and not ignore_rank:
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

            # A product can only be in ONE place at a time: enforce that this
            # operation starts after ALL previously placed operations for the
            # same WO finish, regardless of resource or CL.
            if disp.wo in wo_last_end:
                earliest_start = max(earliest_start, wo_last_end[disp.wo])

            # Load balancing — "earliest slot first":
            # Try ALL valid resources in dry_run mode (no side effects),
            # pick the one offering the earliest slot_start, then commit only
            # that allocation. A busy machine has a later next_free_time, so a
            # free machine naturally wins → work spreads across all resources.
            best_start: datetime | None = None
            best_end: datetime | None = None
            best_r = None
            for r in valid_resurse:
                s_start, s_end = find_slot_precise(
                    r.id, disponibilitate, next_free_time, remaining, earliest_start,
                    dry_run=True,
                )
                if s_start is None:
                    continue
                if best_start is None or s_start < best_start:
                    best_start = s_start
                    best_end = s_end
                    best_r = r

            allocated = False
            if best_r is not None:
                slot_start, slot_end = best_start, best_end
                # Commit: update next_free_time for the chosen resource
                next_free_time[best_r.id] = slot_end

                if wo_previzionat_start is None:
                    final_status = "planned"
                elif "bt" in wo_previzionat_reason:
                    final_status = "previzionat_bt"      # BT is the primary constraint
                elif wo_previzionat_reason == "material":
                    final_status = "previzionat_material"
                elif wo_previzionat_reason == "semifabricat":
                    final_status = "previzionat_semifabricat"
                else:
                    final_status = "previzionat_bt"      # fallback

                db.add(PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=best_r.id, resursa_nume=best_r.resursa,
                    data_start=slot_start, data_end=slot_end,
                    durata_ore=remaining,
                    status=final_status, motiv=None,
                ))
                stats[final_status] += 1
                update_rank(rank, final_status, slot_end)
                # Update WO-level last end time to prevent parallel ops within same WO
                wo_existing = wo_last_end.get(disp.wo)
                if wo_existing is None or slot_end > wo_existing:
                    wo_last_end[disp.wo] = slot_end
                allocated = True

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
    previzionat_total = stats["previzionat_bt"] + stats["previzionat_material"] + stats.get("previzionat_semifabricat", 0)
    sesiune.operatii_planificate = stats["planned"] + previzionat_total
    sesiune.operatii_neplanificate = total - stats["planned"] - previzionat_total
    db.commit()

    return {
        "sesiune_id": sesiune.id,
        "stats": stats,
        "total_comenzi": len(comenzi),
    }
