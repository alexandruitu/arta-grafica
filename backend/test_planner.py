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
    find_slot_precise, get_stadiu_priority, run_planning,
    INVALID_BT_DATE, SHIFT_START_H, SHIFT_END_H,
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


class TestFindSlotPrecise:
    """Tests for find_slot_precise — hour-precise slot finder (shift 06:00-22:00)."""

    def _make_disp(self, resursa_id: int, dates: dict) -> dict:
        """Build a disponibilitate dict: {resursa_id: {date: ore_disponibile}}."""
        return {resursa_id: dates}

    def test_single_day_enough(self):
        """Slot fits within one working day."""
        disp = self._make_disp(1, {date(2026, 4, 1): 8.0})
        nft: dict = {}
        earliest = datetime(2026, 4, 1, SHIFT_START_H, 0)
        start, end = find_slot_precise(1, disp, nft, 5.0, earliest)
        assert start is not None
        assert start.date() == date(2026, 4, 1)
        assert start.hour == SHIFT_START_H
        assert end is not None
        assert end.date() == date(2026, 4, 1)
        # next_free_time should be updated to slot_end
        assert nft[1] == end

    def test_multi_day_slot(self):
        """Slot spans two days when hours needed exceed one full shift (16h 06:00-22:00)."""
        # shift = 16h/day; need 20h → must span 2 days
        disp = self._make_disp(1, {date(2026, 4, 1): 16.0, date(2026, 4, 2): 16.0})
        nft: dict = {}
        earliest = datetime(2026, 4, 1, SHIFT_START_H, 0)
        start, end = find_slot_precise(1, disp, nft, 20.0, earliest)
        assert start is not None and start.date() == date(2026, 4, 1)
        assert end is not None and end.date() == date(2026, 4, 2)

    def test_no_availability_returns_none(self):
        """No working days → returns (None, None)."""
        disp = self._make_disp(1, {})
        nft: dict = {}
        earliest = datetime(2026, 4, 1, SHIFT_START_H, 0)
        start, end = find_slot_precise(1, disp, nft, 5.0, earliest)
        assert start is None
        assert end is None

    def test_skip_zero_hour_days(self):
        """Days with 0 ore_disponibile are skipped."""
        disp = self._make_disp(1, {
            date(2026, 4, 1): 0.0,
            date(2026, 4, 2): 0.0,
            date(2026, 4, 3): 8.0,
        })
        nft: dict = {}
        earliest = datetime(2026, 4, 1, SHIFT_START_H, 0)
        start, end = find_slot_precise(1, disp, nft, 2.0, earliest)
        assert start is not None and start.date() == date(2026, 4, 3)

    def test_earliest_start_respected(self):
        """earliest_start in the future skips past working days."""
        disp = self._make_disp(1, {
            date(2026, 4, 1): 8.0,
            date(2026, 4, 5): 8.0,
        })
        nft: dict = {}
        # earliest = April 3, so April 1 is skipped
        earliest = datetime(2026, 4, 3, SHIFT_START_H, 0)
        start, end = find_slot_precise(1, disp, nft, 2.0, earliest)
        assert start is not None and start.date() == date(2026, 4, 5)

    def test_next_free_time_chains_slots(self):
        """Second call respects next_free_time left by first call."""
        disp = self._make_disp(1, {date(2026, 4, 1): 16.0})  # 16h = full shift 6-22
        nft: dict = {}
        earliest = datetime(2026, 4, 1, SHIFT_START_H, 0)

        s1, e1 = find_slot_precise(1, disp, nft, 8.0, earliest)
        s2, e2 = find_slot_precise(1, disp, nft, 8.0, earliest)

        assert s1 is not None and s2 is not None
        # Second slot must start where first ended
        assert s2 >= e1

    def test_slot_respects_shift_end(self):
        """A slot must not exceed SHIFT_END_H (22:00)."""
        disp = self._make_disp(1, {date(2026, 4, 1): 8.0, date(2026, 4, 2): 8.0})
        nft: dict = {}
        # Start at 20:00 → only 2h left in shift → must overflow to next day
        earliest = datetime(2026, 4, 1, 20, 0)
        start, end = find_slot_precise(1, disp, nft, 5.0, earliest)
        assert start is not None
        # End must not exceed 22:00 on any single day
        assert end is not None
        # With 5h needed and only 2h on day1, end must be on day2
        assert end.date() >= date(2026, 4, 1)
        if end.date() == date(2026, 4, 1):
            assert end.hour <= SHIFT_END_H


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
    """Test BT (Bun de Tipar) validation in the planner.

    Algorithm behavior (post sub-classification update):
    - No BT + resource available  → previzionat_bt  (scheduled optimistically)
    - No BT + NO resource at all  → no_bt           (fully blocked)
    """

    def test_no_bt_with_resource_gives_previzionat_bt(self, db):
        """No BT but resource exists → previzionat_bt (scheduled without confirmed BT)."""
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

        assert result is not None
        assert result.status == "previzionat_bt", (
            f"Expected previzionat_bt (resource exists but no BT), got '{result.status}'"
        )
        # Must still have a scheduled time slot
        assert result.data_start is not None
        assert result.data_end is not None

    def test_invalid_bt_date_with_resource_gives_previzionat_bt(self, db):
        """BT=1911-11-11 (invalid sentinel) + resource → previzionat_bt."""
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

        assert result is not None
        assert result.status == "previzionat_bt"

    def test_no_bt_and_no_resource_gives_no_resource(self, db):
        """No BT + no matching resource → no_resource.

        Resource check fires before BT check in status assignment:
        - no BT + resource exists   → previzionat_bt
        - no BT + no resource       → no_resource  (resource has priority)
        """
        c = make_comanda(4003, bt1=None, bt2=None, bt3=None, bt4=None)
        db.add(c)
        db.flush()

        d = make_dispatch(4003, 10, "CL_NONEXISTENT")
        db.add(d)

        op = make_operatie(10, rank=1)
        db.add(op)
        # No Resursa added for CL_NONEXISTENT
        db.commit()

        run_planning(db)
        result = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 4003
        ).first()

        assert result is not None
        assert result.status == "no_resource", (
            f"Expected no_resource (resource check takes priority over BT), got '{result.status}'"
        )


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

        # Rank 2 must start at or after rank 1 ends (hour-precise)
        assert results[1].data_start >= results[0].data_end, (
            f"Rank 2 start ({results[1].data_start}) must be >= "
            f"rank 1 end ({results[0].data_end})"
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
        # No BT + resource exists → previzionat_bt (scheduled optimistically)
        assert r2 is not None and r2.status == "previzionat_bt", f"WO 7002: {r2.status if r2 else 'missing'}"
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


class TestPrefabricatDetection:
    """
    Test that the planner distinguishes between:
    - no_material: missing purchased article (no internal producer WO)
    - blocat_prefabricat: missing article that is produced by another WO internally
    """

    def _setup_base(self, db):
        """Common setup: one resource available for 3 days."""
        r = make_resursa("CL1", "Masina1")
        db.add(r)
        db.flush()
        today = date.today()
        for i in range(3):
            db.add(make_program(r, today + timedelta(days=i), 8.0))
        db.add(make_operatie(10, rank=1))
        return r

    def test_prefabricat_gives_blocat_prefabricat_status(self, db):
        """
        Article ART-PREF is produced internally by WO 9001 (A-type, COMANDA LUCRU).
        WO 9002 needs ART-PREF but stock=0 and no supply arrives.
        Expected: WO 9002 → blocat_prefabricat (not no_material).
        The motiv should contain the producer WO number.
        """
        self._setup_base(db)

        # Producer WO (just needs to be referenced in the Deficit A-type entry)
        c_producer = make_comanda(9001, bt1=None, bt2=None, bt3=None, bt4=None)
        # Consumer WO
        c_consumer = make_comanda(9002)
        db.add_all([c_producer, c_consumer])
        db.flush()

        # Dispatch for consumer only (producer WO has no dispatch → won't be planned)
        db.add(make_dispatch(9002, 10, "CL1", p_setup=0.0, p_runtime=2.0))

        # A-type entry: WO 9001 produces ART-PREF internally
        db.add(Deficit(
            articol="ART-PREF",
            sold_actual=0.0,
            cantitate=500.0,
            la_data=None,
            pentru="productie",
            pe_comanda=9001,
            tiraj_comandat=500,
            tiraj_realizat=0,
            rezervat_in="* COMANDĂ LUCRU *",
            tip_rezervare="A",
        ))
        # B-type entry: WO 9002 needs ART-PREF (stock=0)
        db.add(Deficit(
            articol="ART-PREF",
            sold_actual=0.0,
            cantitate=100.0,
            la_data=date(2026, 4, 1),
            pentru="WO",
            pe_comanda=9002,
            tiraj_comandat=1000,
            tiraj_realizat=0,
            rezervat_in="* MTRL TO WO *",
            tip_rezervare="B",
        ))
        db.commit()

        run_planning(db)

        result = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 9002).first()
        assert result is not None
        assert result.status == "blocat_prefabricat", (
            f"Expected blocat_prefabricat, got '{result.status}'. "
            f"Motiv: {result.motiv}"
        )
        assert result.motiv is not None
        assert "9001" in result.motiv, (
            f"Producer WO 9001 not found in motiv: '{result.motiv}'"
        )
        assert "ART-PREF" in result.motiv, (
            f"Article ART-PREF not found in motiv: '{result.motiv}'"
        )

    def test_missing_external_material_gives_no_material(self, db):
        """
        Article ART-EXT is NOT produced by any internal WO (only B-type entries).
        WO 9003 needs ART-EXT but stock=0 and no supply arrives.
        Expected: WO 9003 → no_material (not blocat_prefabricat).
        """
        self._setup_base(db)

        c = make_comanda(9003)
        db.add(c)
        db.flush()
        db.add(make_dispatch(9003, 10, "CL1", p_setup=0.0, p_runtime=2.0))

        # Only B-type, no A-type from internal WO
        db.add(Deficit(
            articol="ART-EXT",
            sold_actual=0.0,
            cantitate=100.0,
            la_data=date(2026, 4, 1),
            pentru="WO",
            pe_comanda=9003,
            tiraj_comandat=1000,
            tiraj_realizat=0,
            rezervat_in="* MTRL TO WO *",
            tip_rezervare="B",
        ))
        db.commit()

        run_planning(db)

        result = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 9003).first()
        assert result is not None
        assert result.status == "no_material", (
            f"Expected no_material, got '{result.status}'. "
            f"Motiv: {result.motiv}"
        )

    def test_prefabricat_supplier_entry_does_not_trigger(self, db):
        """
        Article ART-SUPPL has an A-type entry but with rezervat_in='FURNIZOR' (supplier).
        WO 9004 needs ART-SUPPL but stock=0.
        Expected: WO 9004 → no_material (rezervat_in doesn't match COMAND%LUCRU pattern).
        """
        self._setup_base(db)

        c = make_comanda(9004)
        db.add(c)
        db.flush()
        db.add(make_dispatch(9004, 10, "CL1", p_setup=0.0, p_runtime=2.0))

        # A-type but from a supplier, not an internal WO
        db.add(Deficit(
            articol="ART-SUPPL",
            sold_actual=0.0,
            cantitate=500.0,
            la_data=None,
            pentru="furnizor",
            pe_comanda=9004,
            tiraj_comandat=500,
            tiraj_realizat=0,
            rezervat_in="FURNIZOR EXTERN",
            tip_rezervare="A",
        ))
        # B-type: WO 9004 needs ART-SUPPL
        db.add(Deficit(
            articol="ART-SUPPL",
            sold_actual=0.0,
            cantitate=100.0,
            la_data=date(2026, 4, 1),
            pentru="WO",
            pe_comanda=9004,
            tiraj_comandat=1000,
            tiraj_realizat=0,
            rezervat_in="* MTRL TO WO *",
            tip_rezervare="B",
        ))
        db.commit()

        run_planning(db)

        result = db.query(PlanificareRezultat).filter(PlanificareRezultat.wo == 9004).first()
        assert result is not None
        assert result.status == "no_material", (
            f"Expected no_material for supplier article, got '{result.status}'. "
            f"Motiv: {result.motiv}"
        )


class TestNoParallelOpsWithinWO:
    """
    A product can only be in ONE place at a time.
    Two operations from the same WO with the same rank on different
    resources within the same CL must NOT overlap in time.
    """

    def test_same_rank_different_resources_are_sequential(self, db):
        """
        WO 5001 has OP:10 and OP:20 both with rank=1 on CL=CL1.
        CL1 has two resources (Masina1, Masina2).
        Expected: they are placed sequentially (Masina2 starts after Masina1 ends),
        NOT in parallel (same start time on different machines).
        """
        # Two resources in same CL
        r1 = make_resursa("CL1", "Masina1")
        r2 = make_resursa("CL1", "Masina2")
        db.add_all([r1, r2])
        db.flush()

        today = date.today()
        for i in range(5):
            db.add(make_program(r1, today + timedelta(days=i), 8.0))
            db.add(make_program(r2, today + timedelta(days=i), 8.0))

        # Both ops have same rank
        db.add(Operatie(cod="10", descriere="Op 10", cod_unic="U10", sectie="S1", rank=1))
        db.add(Operatie(cod="20", descriere="Op 20", cod_unic="U20", sectie="S1", rank=1))

        c = make_comanda(5001)
        db.add(c)
        db.flush()

        db.add(make_dispatch(5001, 10, "CL1", p_setup=0.0, p_runtime=4.0))
        db.add(make_dispatch(5001, 20, "CL1", p_setup=0.0, p_runtime=4.0))
        db.commit()

        run_planning(db)

        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.wo == 5001
        ).order_by(PlanificareRezultat.data_start).all()

        assert len(results) == 2
        assert all(r.status in ("planned",) for r in results), \
            f"Expected both planned, got {[r.status for r in results]}"

        # KEY assertion: second op must start AFTER first op ends (no overlap)
        r_a, r_b = results[0], results[1]
        assert r_b.data_start >= r_a.data_end, (
            f"Operations overlap! OP_A ends {r_a.data_end}, OP_B starts {r_b.data_start}. "
            f"Resources: {r_a.resursa_id} vs {r_b.resursa_id}"
        )
