"""
Unit tests for the production planning algorithm (planner.py).

Tests cover:
  1. Material shortage detection (the suspected bug area)
  2. BT (Bun de Tipar) validation
  3. Rank dependency blocking
  4. Resource allocation and slot finding
  5. Full integration flow with mixed statuses
"""
from __future__ import annotations
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import (
    Comanda, DispatchItem, Operatie, Deficit, Resursa, ProgramResursa,
    PlanificareSesiune, PlanificareRezultat,
)
from planner import (
    has_valid_bt, get_delivery_date, calc_remaining_time,
    find_slot, get_stadiu_priority, run_planning, INVALID_BT_DATE,
)
from collections import defaultdict


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Create a fresh in-memory SQLite DB for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def make_comanda(cp, stadiu="06 - In productie", status_cda="LIBER",
                 bt1="2026-01-15", bt2=None, bt3=None, bt4=None,
                 tip_comanda="V", data_actualizata_livrare=None,
                 dt_livr_prod=None, data_estimata_livrare=None):
    """Helper to create a Comanda."""
    return Comanda(
        cp=cp, cv=cp, client="Test", client_final="Test",
        tip_produs="Produs", articol="ART001", tip_comanda=tip_comanda,
        cant_vnz=1000, livrat=0,
        stadiu_prepress=stadiu, stadiu_sf=None, status_cda=status_cda,
        data_estimata_livrare=data_estimata_livrare or date(2026, 4, 15),
        data_actualizata_livrare=data_actualizata_livrare or date(2026, 4, 10),
        dt_livr_prod=dt_livr_prod or date(2026, 4, 12),
        data_comanda=date(2026, 1, 1), data_limita_bt=date(2026, 2, 1),
        bt1=bt1, bt2=bt2, bt3=bt3, bt4=bt4,
    )


def make_dispatch(wo, op, cl, p_setup=1.0, p_runtime=4.0, r_runtime=0.0):
    """Helper to create a DispatchItem."""
    return DispatchItem(
        cl=cl, wo=wo, op=op, descr_op=f"Op {op}",
        stock_code="SC001", grupa="G1",
        comandat=1000, q_plan=1000.0, setup=1, flagsetup=0,
        unitati=1000.0,
        p_setup=p_setup, p_runtime=p_runtime,
        r_setup=0.0, r_runtime=r_runtime,
        q_raportat=0, q_rest=1000.0,
    )


def make_operatie(cod, rank):
    """Helper to create an Operatie (operation catalog entry)."""
    return Operatie(
        cod=str(cod), descriere=f"Operatie {cod}",
        cod_unic=f"U{cod}", sectie="S1", rank=rank,
    )


def make_resursa(cl, resursa_name, operatii=None):
    """Helper to create a Resursa."""
    return Resursa(
        cl=cl, denumire_cl=f"CL {cl}",
        resursa=resursa_name, operatii=operatii,
    )


def make_program(resursa, data, ore):
    """Helper to create a ProgramResursa."""
    return ProgramResursa(
        resursa_id=resursa.id, data=data,
        schimburi="6-14", ore_disponibile=ore,
    )


def make_deficit(articol, sold_actual, cantitate, pe_comanda, tip_rezervare="B"):
    """Helper to create a Deficit record."""
    return Deficit(
        articol=articol, sold_actual=sold_actual,
        cantitate=cantitate, la_data=date(2026, 4, 1),
        pentru="WO", pe_comanda=pe_comanda,
        tiraj_comandat=1000, tiraj_realizat=0,
        rezervat_in="MAG1", tip_rezervare=tip_rezervare,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. UNIT TESTS — pure function tests (no DB)
# ═══════════════════════════════════════════════════════════════════════════

class TestHasValidBT:
    """Test BT (Bun de Tipar) validation."""

    def test_bt1_valid(self):
        c = make_comanda(1, bt1="2026-01-15")
        assert has_valid_bt(c) is True

    def test_all_bt_none(self):
        c = make_comanda(1, bt1=None, bt2=None, bt3=None, bt4=None)
        assert has_valid_bt(c) is False

    def test_all_bt_empty_string(self):
        c = make_comanda(1, bt1="", bt2="", bt3="", bt4="")
        assert has_valid_bt(c) is False

    def test_bt_invalid_date(self):
        c = make_comanda(1, bt1=INVALID_BT_DATE, bt2=None)
        assert has_valid_bt(c) is False

    def test_bt2_valid_bt1_invalid(self):
        c = make_comanda(1, bt1=INVALID_BT_DATE, bt2="2026-02-01")
        assert has_valid_bt(c) is True

    def test_bt_whitespace_only(self):
        c = make_comanda(1, bt1="   ", bt2=None)
        assert has_valid_bt(c) is False


class TestCalcRemainingTime:

    def test_normal(self):
        d = make_dispatch(1, 10, "CL1", p_setup=1.0, p_runtime=4.0, r_runtime=2.0)
        assert calc_remaining_time(d) == 3.0

    def test_completed(self):
        d = make_dispatch(1, 10, "CL1", p_setup=1.0, p_runtime=4.0, r_runtime=5.0)
        assert calc_remaining_time(d) == 0.0

    def test_zero_setup(self):
        d = make_dispatch(1, 10, "CL1", p_setup=0.0, p_runtime=3.0, r_runtime=0.0)
        assert calc_remaining_time(d) == 3.0


class TestGetStadiuPriority:

    def test_in_productie(self):
        assert get_stadiu_priority("06 - In productie") == 100

    def test_none(self):
        assert get_stadiu_priority(None) == 0

    def test_unknown(self):
        assert get_stadiu_priority("99 - Unknown") == 0


class TestFindSlot:

    def test_single_day_enough(self):
        disp = defaultdict(lambda: defaultdict(float))
        disp[1][date(2026, 4, 1)] = 8.0
        start, end, hours = find_slot(1, disp, 5.0, date(2026, 4, 1))
        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 1)
        assert disp[1][date(2026, 4, 1)] == 3.0  # 8 - 5

    def test_multi_day_slot(self):
        disp = defaultdict(lambda: defaultdict(float))
        disp[1][date(2026, 4, 1)] = 4.0
        disp[1][date(2026, 4, 2)] = 4.0
        start, end, hours = find_slot(1, disp, 6.0, date(2026, 4, 1))
        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 2)
        assert disp[1][date(2026, 4, 1)] == 0.0  # fully used
        assert disp[1][date(2026, 4, 2)] == 2.0   # 4 - 2

    def test_no_availability(self):
        disp = defaultdict(lambda: defaultdict(float))
        start, end, hours = find_slot(1, disp, 5.0, date(2026, 4, 1))
        assert start is None
        assert end is None

    def test_skip_zero_days(self):
        disp = defaultdict(lambda: defaultdict(float))
        disp[1][date(2026, 4, 1)] = 0.0
        disp[1][date(2026, 4, 2)] = 0.0
        disp[1][date(2026, 4, 3)] = 8.0
        start, end, _ = find_slot(1, disp, 3.0, date(2026, 4, 1))
        assert start == date(2026, 4, 3)

    def test_earliest_start_respected(self):
        disp = defaultdict(lambda: defaultdict(float))
        disp[1][date(2026, 4, 1)] = 8.0
        disp[1][date(2026, 4, 5)] = 8.0
        start, end, _ = find_slot(1, disp, 3.0, date(2026, 4, 3))
        assert start == date(2026, 4, 5)  # skips April 1 (before earliest)


# ═══════════════════════════════════════════════════════════════════════════
# 2. INTEGRATION TESTS — full planning runs with DB
# ═══════════════════════════════════════════════════════════════════════════

class TestMaterialShortageDetection:
    """
    THE SUSPECTED BUG AREA.

    In real ERP data, Deficit records with tip_rezervare="B" (reservation)
    typically have POSITIVE cantitate values representing how much material
    the WO *needs* (consumes).

    The planner checks:  stoc_tracker[art] + cantitate < 0
    If cantitate is positive (e.g. 500), then:  stoc(100) + 500 = 600 > 0
    → Material is NEVER flagged as missing.

    The check should be:  stoc_tracker[art] - cantitate < 0
    (or cantitate should be stored as negative in wo_materiale)
    """

    def test_material_shortage_with_positive_cantitate(self, db):
        """
        WO needs 500 units of material, only 100 in stock.
        Cantitate is POSITIVE (typical ERP format).
        Expected: operation should be flagged as no_material.
        """
        # Setup: comanda, dispatch, operatie, resursa, program
        c = make_comanda(1001)
        db.add(c)
        db.flush()

        d = make_dispatch(1001, 10, "CL1", p_setup=1.0, p_runtime=4.0)
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)

        # Material: stock=100, reservation needs 500 (positive in ERP)
        deficit = make_deficit("HARTIE_A4", sold_actual=100.0,
                               cantitate=500.0, pe_comanda=1001)
        db.add(deficit)
        db.commit()

        result = run_planning(db)

        # Get planning results
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 1001
        ).all()

        assert len(results) == 1
        # This SHOULD be no_material because 100 < 500
        assert results[0].status == "no_material", (
            f"Expected no_material but got '{results[0].status}'. "
            f"Bug: material shortage not detected when cantitate is positive!"
        )

    def test_material_sufficient_with_positive_cantitate(self, db):
        """
        WO needs 50 units, stock is 100. Should be planned successfully.
        """
        c = make_comanda(1002)
        db.add(c)
        db.flush()

        d = make_dispatch(1002, 10, "CL1", p_setup=0.5, p_runtime=2.0)
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)

        deficit = make_deficit("HARTIE_A4", sold_actual=100.0,
                               cantitate=50.0, pe_comanda=1002)
        db.add(deficit)
        db.commit()

        result = run_planning(db)
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 1002
        ).all()

        assert len(results) == 1
        assert results[0].status == "planned", (
            f"Expected planned but got '{results[0].status}'. "
            f"Stock (100) >= needed (50) should be sufficient."
        )

    def test_material_shortage_with_negative_cantitate(self, db):
        """
        Test with NEGATIVE cantitate (some ERP formats).
        After abs(), cantitate=500, stock=100 → 100 < 500 → no_material.
        The planner should handle both positive and negative cantitate.
        """
        c = make_comanda(1003)
        db.add(c)
        db.flush()

        d = make_dispatch(1003, 10, "CL1", p_setup=1.0, p_runtime=3.0)
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)

        # Negative cantitate — planner should use abs() and still detect shortage
        deficit = make_deficit("HARTIE_A4", sold_actual=100.0,
                               cantitate=-500.0, pe_comanda=1003)
        db.add(deficit)
        db.commit()

        result = run_planning(db)
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 1003
        ).all()

        assert len(results) == 1
        assert results[0].status == "no_material", (
            f"Expected no_material but got '{results[0].status}'."
        )

    def test_material_depletion_across_wos(self, db):
        """
        Two WOs share the same material. Stock=150.
        WO1 needs 100, WO2 needs 100. After WO1 takes 100, only 50 left.
        WO2 should get no_material.
        """
        for cp in [2001, 2002]:
            c = make_comanda(cp)
            db.add(c)
        db.flush()

        for cp in [2001, 2002]:
            d = make_dispatch(cp, 10, "CL1", p_setup=0.5, p_runtime=2.0)
            db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        # Enough hours for both WOs
        prog1 = make_program(r, date.today(), 8.0)
        prog2 = make_program(r, date.today() + timedelta(days=1), 8.0)
        db.add_all([prog1, prog2])

        # Stock = 150, each WO needs 100
        # WO1: stock entry
        db.add(make_deficit("HARTIE", sold_actual=150.0,
                            cantitate=100.0, pe_comanda=2001))
        # WO2: same article, same stock (sold_actual should be same)
        db.add(make_deficit("HARTIE", sold_actual=150.0,
                            cantitate=100.0, pe_comanda=2002))
        db.commit()

        result = run_planning(db)
        r1 = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 2001
        ).first()
        r2 = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 2002
        ).first()

        assert r1 is not None
        assert r2 is not None

        # First WO should be planned (100 <= 150)
        assert r1.status == "planned", (
            f"WO 2001: expected planned, got '{r1.status}'"
        )
        # Second WO should fail: only 50 left after first WO reserved 100
        assert r2.status == "no_material", (
            f"WO 2002: expected no_material, got '{r2.status}'. "
            f"Stock depletion across WOs may not be working."
        )

    def test_no_deficit_records_means_no_material_check(self, db):
        """
        WO has no Deficit records at all → material check should pass
        (no material constraint), and it should get planned if resources exist.
        """
        c = make_comanda(3001)
        db.add(c)
        db.flush()

        d = make_dispatch(3001, 10, "CL1", p_setup=0.5, p_runtime=1.5)
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)
        db.commit()

        run_planning(db)
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 3001
        ).all()

        assert len(results) == 1
        assert results[0].status == "planned"


class TestBTValidation:
    """Test that operations are blocked when BT is missing."""

    def test_no_bt_blocks_planning(self, db):
        c = make_comanda(4001, bt1=None, bt2=None, bt3=None, bt4=None)
        db.add(c)
        db.flush()

        d = make_dispatch(4001, 10, "CL1")
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)
        db.commit()

        run_planning(db)
        result = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 4001
        ).first()

        assert result.status == "no_bt"

    def test_invalid_bt_date_blocks(self, db):
        c = make_comanda(4002, bt1=INVALID_BT_DATE)
        db.add(c)
        db.flush()

        d = make_dispatch(4002, 10, "CL1")
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)
        db.commit()

        run_planning(db)
        result = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 4002
        ).first()

        assert result.status == "no_bt"


class TestRankBlocking:
    """Test rank dependency logic."""

    def test_lower_rank_completed_allows_higher(self, db):
        """
        Op rank=1 is completed (r_runtime >= p_setup+p_runtime).
        Op rank=2 should be planned.
        """
        c = make_comanda(5001)
        db.add(c)
        db.flush()

        # Rank 1: completed (remaining time = 0)
        d1 = make_dispatch(5001, 10, "CL1", p_setup=1.0, p_runtime=4.0, r_runtime=5.0)
        # Rank 2: needs planning
        d2 = make_dispatch(5001, 20, "CL1", p_setup=0.5, p_runtime=2.0, r_runtime=0.0)
        db.add_all([d1, d2])

        op1 = make_operatie(10, rank=1)
        op2 = make_operatie(20, rank=2)
        db.add_all([op1, op2])

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)
        db.commit()

        run_planning(db)
        result = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 5001
        ).first()

        # Only rank=2 produces a result (rank=1 is "completed", skipped)
        assert result.status == "planned"

    def test_lower_rank_open_blocks_higher(self, db):
        """
        Rank=1 is open (has remaining time, but no resource).
        Rank=2 should be blocked_by_rank.
        """
        c = make_comanda(5002)
        db.add(c)
        db.flush()

        # Rank 1: needs CL_MISSING (no resource will match)
        d1 = make_dispatch(5002, 10, "CL_MISSING", p_setup=1.0, p_runtime=4.0)
        # Rank 2: has matching resource
        d2 = make_dispatch(5002, 20, "CL1", p_setup=0.5, p_runtime=2.0)
        db.add_all([d1, d2])

        op1 = make_operatie(10, rank=1)
        op2 = make_operatie(20, rank=2)
        db.add_all([op1, op2])

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)
        db.commit()

        run_planning(db)
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 5002
        ).order_by(PlanificareRezultat.op).all()

        assert len(results) == 2
        assert results[0].op == 10
        assert results[0].status == "no_resource"
        assert results[1].op == 20
        assert results[1].status == "blocked_by_rank"

    def test_lower_rank_planned_chains_start_date(self, db):
        """
        Rank=1 is planned (e.g., ends on day X).
        Rank=2 should start the day after X.
        """
        c = make_comanda(5003)
        db.add(c)
        db.flush()

        d1 = make_dispatch(5003, 10, "CL1", p_setup=0.0, p_runtime=8.0)  # takes 1 full day
        d2 = make_dispatch(5003, 20, "CL1", p_setup=0.0, p_runtime=4.0)
        db.add_all([d1, d2])

        op1 = make_operatie(10, rank=1)
        op2 = make_operatie(20, rank=2)
        db.add_all([op1, op2])

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        today = date.today()
        prog1 = make_program(r, today, 8.0)
        prog2 = make_program(r, today + timedelta(days=1), 8.0)
        db.add_all([prog1, prog2])
        db.commit()

        run_planning(db)
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 5003
        ).order_by(PlanificareRezultat.op).all()

        assert len(results) == 2
        assert results[0].status == "planned"
        assert results[1].status == "planned"

        # Rank 2 should start AFTER rank 1 ends
        assert results[1].data_start.date() > results[0].data_start.date(), (
            f"Rank 2 start ({results[1].data_start.date()}) should be after "
            f"rank 1 start ({results[0].data_start.date()})"
        )


class TestResourceAllocation:
    """Test resource matching and availability."""

    def test_no_resource_for_cl(self, db):
        """No resource exists for the CL → no_resource."""
        c = make_comanda(6001)
        db.add(c)
        db.flush()

        d = make_dispatch(6001, 10, "CL_NONEXISTENT")
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)
        db.commit()

        run_planning(db)
        result = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 6001
        ).first()

        assert result.status == "no_resource"

    def test_resource_exists_but_no_schedule(self, db):
        """Resource exists for CL but has no ProgramResursa (no hours)."""
        c = make_comanda(6002)
        db.add(c)
        db.flush()

        d = make_dispatch(6002, 10, "CL1")
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.commit()

        run_planning(db)
        result = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 6002
        ).first()

        assert result.status == "no_resource"

    def test_stop_comanda_excluded(self, db):
        """Comenzi with status_cda=STOP should be excluded entirely."""
        c = make_comanda(6003, status_cda="STOP")
        db.add(c)
        db.flush()

        d = make_dispatch(6003, 10, "CL1")
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        prog = make_program(r, date.today(), 8.0)
        db.add(prog)
        db.commit()

        run_planning(db)
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 6003
        ).all()

        assert len(results) == 0, "STOP orders should not produce planning results"


class TestFullIntegration:
    """Full end-to-end planning with multiple WOs and mixed statuses."""

    def test_mixed_scenario(self, db):
        """
        WO 7001: has BT, has material, has resource → planned
        WO 7002: no BT → no_bt
        WO 7003: has BT, material shortage → no_material
        """
        # WO 7001 — should be planned
        c1 = make_comanda(7001, bt1="2026-01-15")
        db.add(c1)

        # WO 7002 — no BT
        c2 = make_comanda(7002, bt1=None, bt2=None, bt3=None, bt4=None)
        db.add(c2)

        # WO 7003 — has BT, but material shortage
        c3 = make_comanda(7003, bt1="2026-01-15")
        db.add(c3)

        db.flush()

        # Dispatch items
        for cp in [7001, 7002, 7003]:
            db.add(make_dispatch(cp, 10, "CL1", p_setup=0.5, p_runtime=2.0))

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        today = date.today()
        for i in range(5):
            db.add(make_program(r, today + timedelta(days=i), 8.0))

        # WO 7001: enough material
        db.add(make_deficit("MAT_A", sold_actual=1000.0,
                            cantitate=200.0, pe_comanda=7001))

        # WO 7003: NOT enough material (stock=50, needs=500)
        db.add(make_deficit("MAT_B", sold_actual=50.0,
                            cantitate=500.0, pe_comanda=7003))

        db.commit()

        run_planning(db)

        r1 = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 7001).first()
        r2 = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 7002).first()
        r3 = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 7003).first()

        assert r1 is not None and r1.status == "planned", f"WO 7001: {r1.status if r1 else 'missing'}"
        assert r2 is not None and r2.status == "no_bt", f"WO 7002: {r2.status if r2 else 'missing'}"
        assert r3 is not None and r3.status == "no_material", (
            f"WO 7003: expected no_material, got '{r3.status if r3 else 'missing'}'. "
            f"Material check may be broken!"
        )


class TestStockTrackerInitialization:
    """
    Test that stock tracker properly handles multiple Deficit records
    for the same article — sold_actual should only be taken once.
    """

    def test_same_article_multiple_wos(self, db):
        """
        Article PAPER has sold_actual=200 across both deficit records.
        WO 8001 needs 150, WO 8002 needs 150.
        Total need = 300 > 200 → second WO should fail.
        """
        c1 = make_comanda(8001)
        c2 = make_comanda(8002)
        db.add_all([c1, c2])
        db.flush()

        for cp in [8001, 8002]:
            db.add(make_dispatch(cp, 10, "CL1", p_setup=0.0, p_runtime=2.0))

        op = make_operatie(10, rank=1)
        db.add(op)

        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()

        today = date.today()
        for i in range(3):
            db.add(make_program(r, today + timedelta(days=i), 8.0))

        # Both deficits reference the same article with same sold_actual
        db.add(make_deficit("PAPER", sold_actual=200.0, cantitate=150.0, pe_comanda=8001))
        db.add(make_deficit("PAPER", sold_actual=200.0, cantitate=150.0, pe_comanda=8002))
        db.commit()

        run_planning(db)

        r1 = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 8001).first()
        r2 = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 8002).first()

        # First should succeed (200 >= 150)
        assert r1.status == "planned", f"WO 8001: expected planned, got {r1.status}"
        # Second should fail (200 - 150 = 50 < 150)
        assert r2.status == "no_material", (
            f"WO 8002: expected no_material, got {r2.status}. "
            f"Cross-WO stock depletion is broken."
        )
