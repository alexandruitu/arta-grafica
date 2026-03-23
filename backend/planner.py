from __future__ import annotations
"""
Production Planning Algorithm.

Flow:
1. Sort orders: "06 - In productie" first, then descending by StadiuPrepress,
   then by delivery date (DataActualizataLivrare or DtLivrProd)
2. Exclude Status_cda = STOP
3. For each order, get dispatch operations sorted by rank
4. For each operation, check:
   a. BT exists on the order
   b. Lower-rank operations are completed
   c. Materials are available (SoldActual - already planned > 0)
   d. Resource is available (CL match + hours available on date)
5. If all checks pass, allocate to first available resource slot
6. Time = P_Setup + P_Runtime - R_Runtime
"""
from datetime import date, datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func
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
    """Check if BT exists (at least one BT field is not empty/invalid)."""
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
    return disp.p_setup + disp.p_runtime - disp.r_runtime


def run_planning(db: Session) -> dict:
    """Execute the planning algorithm."""
    # Create session
    sesiune = PlanificareSesiune(
        created_at=datetime.now(),
        status="running",
    )
    db.add(sesiune)
    db.flush()

    # Clear previous results for this session
    # (keep frozen items from last session if any)

    # --- Step 1: Load and sort orders ---
    comenzi = (
        db.query(Comanda)
        .filter(Comanda.status_cda != "STOP")
        .filter(Comanda.cp > 0)  # Must have production order
        .all()
    )

    comenzi.sort(key=lambda c: (
        -get_stadiu_priority(c.stadiu_prepress),  # Higher priority first
        get_delivery_date(c),                      # Earlier delivery first
    ))

    # --- Step 2: Load operations catalog (for rank lookup) ---
    operatii_catalog = {}
    for op in db.query(Operatie).all():
        operatii_catalog[op.cod] = op

    # --- Step 3: Load resources and their schedules ---
    resurse = db.query(Resursa).all()
    resurse_by_cl = defaultdict(list)
    for r in resurse:
        resurse_by_cl[r.cl].append(r)

    # Build resource availability: {resursa_id: {date: ore_ramase}}
    disponibilitate = defaultdict(lambda: defaultdict(float))
    for prog in db.query(ProgramResursa).all():
        disponibilitate[prog.resursa_id][prog.data] = prog.ore_disponibile

    # --- Step 4: Build material stock tracker ---
    # Group deficite by articol, compute available stock
    # SoldActual is the same per articol (current stock), Cantitate is reserved
    stoc_tracker = {}  # {articol: available_qty}
    deficite_rows = db.query(Deficit).all()
    articol_sold = {}
    for d in deficite_rows:
        art = d.articol
        if art not in articol_sold:
            articol_sold[art] = d.sold_actual
    stoc_tracker = dict(articol_sold)  # Start with current stock

    # --- Step 5: Check which resources can do which operations ---
    resursa_operatii = {}  # {resursa_id: set of op codes}
    for r in resurse:
        if r.operatii:
            codes = {c.strip() for c in r.operatii.split(";")}
            resursa_operatii[r.id] = codes
        else:
            resursa_operatii[r.id] = set()

    # --- Step 6: Plan operations ---
    stats = {"planned": 0, "no_material": 0, "no_resource": 0, "blocked_by_rank": 0, "no_bt": 0, "completed": 0}
    planned_items = []
    today = date.today()

    for comanda in comenzi:
        # Get all dispatch items for this WO, sorted by operation rank
        dispatch_items = (
            db.query(DispatchItem)
            .filter(DispatchItem.wo == comanda.cp)
            .all()
        )
        if not dispatch_items:
            continue

        # Sort by rank (from operatii catalog)
        def get_rank(d: DispatchItem) -> int:
            op_code = str(d.op)
            if op_code in operatii_catalog:
                return operatii_catalog[op_code].rank
            return 999

        dispatch_items.sort(key=get_rank)

        # Track which ranks are completed/planned for this WO
        rank_status = {}  # {rank: "completed" | "planned" | "open"}

        for disp in dispatch_items:
            remaining = calc_remaining_time(disp)
            op_code = str(disp.op)
            rank = get_rank(disp)

            # Skip if already completed
            if remaining <= 0:
                rank_status[rank] = "completed"
                stats["completed"] += 1
                continue

            # Check 1: BT must exist
            if not has_valid_bt(comanda):
                result = PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=None, resursa_nume=None,
                    data_start=None, data_end=None, durata_ore=remaining,
                    status="no_bt", motiv="Comanda nu are BT valid",
                )
                db.add(result)
                stats["no_bt"] += 1
                continue

            # Check 2: Lower-rank operations must be completed
            blocked = False
            for prev_rank, prev_status in rank_status.items():
                if prev_rank < rank and prev_status != "completed":
                    blocked = True
                    break
            if blocked:
                result = PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=None, resursa_nume=None,
                    data_start=None, data_end=None, durata_ore=remaining,
                    status="blocked_by_rank",
                    motiv=f"Operatie cu rank inferior ({prev_rank}) inca deschisa",
                )
                db.add(result)
                stats["blocked_by_rank"] += 1
                rank_status[rank] = "open"
                continue

            # Check 3: Materials available
            stock_code = disp.stock_code
            if stock_code and stock_code in stoc_tracker:
                available = stoc_tracker[stock_code]
                needed = disp.q_plan if disp.q_plan else disp.comandat
                if available <= 0:
                    result = PlanificareRezultat(
                        sesiune_id=sesiune.id, dispatch_id=disp.id,
                        wo=disp.wo, op=disp.op, cl=disp.cl,
                        resursa_id=None, resursa_nume=None,
                        data_start=None, data_end=None, durata_ore=remaining,
                        status="no_material",
                        motiv=f"Stoc insuficient pentru {stock_code}: disponibil={available:.0f}",
                    )
                    db.add(result)
                    stats["no_material"] += 1
                    rank_status[rank] = "open"
                    continue

            # Check 4: Find available resource
            cl = disp.cl
            candidate_resurse = resurse_by_cl.get(cl, [])

            # Filter resources that can do this operation
            valid_resurse = []
            for r in candidate_resurse:
                ops = resursa_operatii.get(r.id, set())
                if not ops or op_code in ops:
                    valid_resurse.append(r)

            # Find first available slot
            allocated = False
            for r in valid_resurse:
                # Search from today forward for available hours
                search_date = today
                hours_remaining = remaining
                slot_start = None
                slot_end = None

                for day_offset in range(365):  # Search up to 1 year
                    check_date = today + timedelta(days=day_offset)
                    avail_hours = disponibilitate[r.id].get(check_date, 0)

                    if avail_hours <= 0:
                        continue

                    if slot_start is None:
                        slot_start = check_date

                    if avail_hours >= hours_remaining:
                        # Fits in this day
                        disponibilitate[r.id][check_date] -= hours_remaining
                        slot_end = check_date
                        hours_remaining = 0
                        break
                    else:
                        # Partial fit, continue to next day
                        hours_remaining -= avail_hours
                        disponibilitate[r.id][check_date] = 0
                        slot_end = check_date

                if hours_remaining <= 0 and slot_start:
                    # Deduct material stock
                    if stock_code and stock_code in stoc_tracker:
                        needed = disp.q_plan if disp.q_plan else disp.comandat
                        stoc_tracker[stock_code] -= needed

                    result = PlanificareRezultat(
                        sesiune_id=sesiune.id, dispatch_id=disp.id,
                        wo=disp.wo, op=disp.op, cl=disp.cl,
                        resursa_id=r.id, resursa_nume=r.resursa,
                        data_start=datetime.combine(slot_start, datetime.min.time()),
                        data_end=datetime.combine(slot_end, datetime.min.time()) + timedelta(hours=remaining + calc_remaining_time(disp)),
                        durata_ore=calc_remaining_time(disp),
                        status="planned", motiv=None,
                    )
                    db.add(result)
                    stats["planned"] += 1
                    rank_status[rank] = "planned"
                    allocated = True
                    break

            if not allocated:
                result = PlanificareRezultat(
                    sesiune_id=sesiune.id, dispatch_id=disp.id,
                    wo=disp.wo, op=disp.op, cl=disp.cl,
                    resursa_id=None, resursa_nume=None,
                    data_start=None, data_end=None, durata_ore=remaining,
                    status="no_resource",
                    motiv=f"Nu exista resursa disponibila in CL={cl}",
                )
                db.add(result)
                stats["no_resource"] += 1
                rank_status[rank] = "open"

    # Update session
    total = stats["planned"] + stats["no_material"] + stats["no_resource"] + stats["blocked_by_rank"] + stats["no_bt"]
    sesiune.status = "completed"
    sesiune.total_operatii = total + stats["completed"]
    sesiune.operatii_planificate = stats["planned"]
    sesiune.operatii_neplanificate = total - stats["planned"]
    db.commit()

    return {
        "sesiune_id": sesiune.id,
        "stats": stats,
        "total_comenzi": len(comenzi),
    }
