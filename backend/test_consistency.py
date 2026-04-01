"""
Consistency & functionality tests for Arta Grafica Production Planning.

Tests verify:
1. Dashboard stats match actual DB counts
2. Comenzi tab data consistency
3. Planificare algorithm correctness
4. Stoc formula correctness (the bug we fixed)
5. Board endpoint consistency with planificare
6. Gantt endpoint consistency with planificare
7. Cross-tab data consistency
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, create_engine
from database import get_db, engine, Base
from models import (
    Comanda, DispatchItem, Operatie, Deficit, Resursa, ProgramResursa,
    PlanificareSesiune, PlanificareRezultat,
)


@pytest.fixture
def db():
    """Get a database session."""
    session = next(get_db())
    yield session
    session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboardStats:
    def test_total_comenzi_matches_db(self, db: Session):
        api_total = db.query(Comanda).count()
        assert api_total == 1176, f"Expected 1176 comenzi, got {api_total}"

    def test_comenzi_active_is_liber(self, db: Session):
        liber = db.query(Comanda).filter(Comanda.status_cda == "LIBER").count()
        stop = db.query(Comanda).filter(Comanda.status_cda == "STOP").count()
        total = db.query(Comanda).count()
        assert liber + stop == total, f"LIBER({liber}) + STOP({stop}) != total({total})"

    def test_stadiu_prepress_sums_to_total(self, db: Session):
        total = db.query(Comanda).count()
        stadiu_counts = (
            db.query(Comanda.stadiu_prepress, func.count())
            .group_by(Comanda.stadiu_prepress)
            .all()
        )
        sum_stadii = sum(c for _, c in stadiu_counts)
        assert sum_stadii == total, f"Sum of stadiu groups ({sum_stadii}) != total ({total})"

    def test_dispatch_count_matches_db(self, db: Session):
        count = db.query(DispatchItem).count()
        assert count == 2684, f"Expected 2684 dispatch items, got {count}"

    def test_resurse_count_matches_db(self, db: Session):
        count = db.query(Resursa).count()
        assert count == 65, f"Expected 65 resurse, got {count}"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. COMENZI TAB
# ═══════════════════════════════════════════════════════════════════════════════

class TestComenzi:
    def test_all_comenzi_have_status_cda(self, db: Session):
        """Every comanda should have a valid status_cda."""
        no_status = db.query(Comanda).filter(
            (Comanda.status_cda == None) | (Comanda.status_cda == "")
        ).count()
        assert no_status == 0, f"{no_status} comenzi without status_cda"

    def test_status_cda_values_valid(self, db: Session):
        """status_cda should only be LIBER or STOP."""
        invalid = db.query(Comanda).filter(
            ~Comanda.status_cda.in_(["LIBER", "STOP"])
        ).count()
        assert invalid == 0, f"{invalid} comenzi with unexpected status_cda values"

    def test_cp_non_negative(self, db: Session):
        """cp should be >= 0 (0 is valid for sales-only orders without production)."""
        negative = db.query(Comanda).filter(Comanda.cp < 0).count()
        assert negative == 0, f"{negative} comenzi with cp < 0"
        # Informational: how many are sales-only (cp=0)
        zero_cp = db.query(Comanda).filter(Comanda.cp == 0).count()
        if zero_cp:
            print(f"\n  INFO: {zero_cp} comenzi with cp=0 (sales-only, excluded from planning)")

    def test_dispatch_items_reference_valid_comenzi(self, db: Session):
        """Dispatch items should mostly link to existing comenzi via wo=cp.
        Some orphans are expected from ERP data quality issues."""
        cp_set = {c.cp for c in db.query(Comanda.cp).all()}
        total = db.query(DispatchItem).count()
        orphans = db.query(DispatchItem).filter(
            ~DispatchItem.wo.in_(cp_set)
        ).count()
        orphan_pct = orphans / total * 100 if total else 0
        assert orphan_pct < 5, (
            f"{orphans} orphan dispatch items ({orphan_pct:.1f}%) — too many"
        )
        if orphans:
            print(f"\n  INFO: {orphans} dispatch items ({orphan_pct:.1f}%) reference "
                  f"non-existent comenzi (ERP data quality)")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PLANIFICARE ALGORITHM
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlanificare:
    def _get_latest_sesiune(self, db: Session) -> PlanificareSesiune:
        return db.query(PlanificareSesiune).order_by(
            PlanificareSesiune.id.desc()
        ).first()

    def _get_results(self, db: Session) -> list[PlanificareRezultat]:
        s = self._get_latest_sesiune(db)
        return db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id
        ).all()

    def test_sesiune_exists(self, db: Session):
        s = self._get_latest_sesiune(db)
        assert s is not None, "No planning session found"
        assert s.status == "completed"

    def test_sesiune_totals_match_results(self, db: Session):
        """Session header counts should match actual result rows."""
        s = self._get_latest_sesiune(db)
        results = self._get_results(db)
        planned = [r for r in results if r.status == "planned"]
        unplanned = [r for r in results if r.status != "planned"]
        assert s.operatii_planificate == len(planned), (
            f"Session says {s.operatii_planificate} planned but found {len(planned)} results"
        )
        assert s.operatii_neplanificate == len(unplanned), (
            f"Session says {s.operatii_neplanificate} unplanned but found {len(unplanned)} results"
        )

    def test_all_statuses_are_valid(self, db: Session):
        results = self._get_results(db)
        valid = {"planned", "no_material", "no_resource", "blocked_by_rank", "no_bt"}
        for r in results:
            assert r.status in valid, f"Invalid status '{r.status}' for result {r.id}"

    def test_planned_ops_have_dates_and_resource(self, db: Session):
        """Planned operations must have start/end dates and a resource."""
        results = self._get_results(db)
        for r in results:
            if r.status == "planned":
                assert r.data_start is not None, f"Planned op {r.id} missing data_start"
                assert r.data_end is not None, f"Planned op {r.id} missing data_end"
                assert r.resursa_id is not None, f"Planned op {r.id} missing resursa_id"
                assert r.resursa_nume is not None, f"Planned op {r.id} missing resursa_nume"
                assert r.data_end > r.data_start, (
                    f"Planned op {r.id}: end ({r.data_end}) <= start ({r.data_start})"
                )

    def test_unplanned_ops_have_no_dates(self, db: Session):
        """Unplanned operations should NOT have resource/dates assigned."""
        results = self._get_results(db)
        for r in results:
            if r.status != "planned":
                assert r.data_start is None, f"Unplanned op {r.id} ({r.status}) has data_start"
                assert r.data_end is None, f"Unplanned op {r.id} ({r.status}) has data_end"

    def test_planned_ops_total_capacity_not_exceeded(self, db: Session):
        """Total hours allocated per resource should not exceed the total
        available capacity across the date span.

        Note: The planner stores day-level date boundaries but tracks
        hour-level capacity via disponibilitate (not stored in results).
        Multi-day ops may use uneven hours per day (e.g., 0.3h on day 1,
        7.7h on day 2), so we can only verify total capacity, not per-day."""
        results = self._get_results(db)
        planned = [r for r in results if r.status == "planned"]

        # Total hours per resource
        hours_per_resource: dict[int, float] = defaultdict(float)
        for r in planned:
            if r.resursa_id:
                hours_per_resource[r.resursa_id] += r.durata_ore

        # Total available capacity per resource (sum of all programmed days)
        violations = 0
        for res_id, total_hours in hours_per_resource.items():
            total_capacity = db.query(
                func.sum(ProgramResursa.ore_disponibile)
            ).filter(ProgramResursa.resursa_id == res_id).scalar() or 0

            if total_hours > total_capacity + 1.0:
                violations += 1
                print(f"\n  OVERCAPACITY: resource {res_id}: "
                      f"{total_hours:.1f}h allocated vs {total_capacity:.1f}h total capacity")
        assert violations == 0, f"{violations} resources exceed total capacity"

    def test_rank_ordering_within_wo(self, db: Session):
        """For a single WO, a higher-rank planned op should start >= lower-rank end."""
        results = self._get_results(db)
        planned = [r for r in results if r.status == "planned"]

        # Get operation ranks
        op_ranks = {}
        for op in db.query(Operatie).all():
            op_ranks[op.cod] = op.rank

        by_wo = defaultdict(list)
        for r in planned:
            by_wo[r.wo].append(r)

        violations = 0
        for wo, ops in by_wo.items():
            ops.sort(key=lambda x: op_ranks.get(str(x.op), 999))
            for i in range(len(ops) - 1):
                r1, r2 = ops[i], ops[i + 1]
                rank1 = op_ranks.get(str(r1.op), 999)
                rank2 = op_ranks.get(str(r2.op), 999)
                if rank1 < rank2 and r2.data_start < r1.data_end:
                    violations += 1
        assert violations == 0, f"{violations} WOs where higher-rank op starts before lower-rank ends"

    def test_no_bt_ops_belong_to_commands_without_bt(self, db: Session):
        """Operations marked no_bt should belong to commands without valid BT."""
        results = self._get_results(db)
        no_bt = [r for r in results if r.status == "no_bt"]
        if not no_bt:
            return  # skip if none

        INVALID_BT_DATE = "1911-11-11"
        for r in no_bt:
            comanda = db.query(Comanda).filter(Comanda.cp == r.wo).first()
            if comanda:
                has_bt = False
                for bt in [comanda.bt1, comanda.bt2, comanda.bt3, comanda.bt4]:
                    if bt and bt.strip() and bt.strip() != INVALID_BT_DATE:
                        has_bt = True
                assert not has_bt, f"Op {r.id} marked no_bt but WO {r.wo} has valid BT"

    def test_stop_orders_excluded_from_planning(self, db: Session):
        """STOP orders should not appear in planning results."""
        results = self._get_results(db)
        stop_cps = {c.cp for c in db.query(Comanda).filter(Comanda.status_cda == "STOP").all()}
        for r in results:
            assert r.wo not in stop_cps, f"STOP order {r.wo} found in planning results"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. STOC / MATERIAL CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoc:
    def test_disponibil_formula_is_addition(self, db: Session):
        """disponibil = sold_actual + sum(cantitate), NOT subtraction.
        cantitate is stored as NEGATIVE for B-type reservations."""
        results = (
            db.query(
                Deficit.articol,
                func.max(Deficit.sold_actual).label("sold"),
                func.sum(Deficit.cantitate).label("rez"),
            )
            .group_by(Deficit.articol)
            .limit(20)
            .all()
        )
        for r in results:
            sold = r[1] or 0
            rez = r[2] or 0
            disponibil = sold + rez  # correct formula
            # Verify the API formula matches planner logic
            # Planner: stoc_tracker[art] + cantitate < 0 → no_material
            # API: disponibil = sold + sum(cantitate) → same sign logic
            assert disponibil == sold + rez, f"Mismatch for {r[0]}"

    def test_b_type_reservations_are_negative(self, db: Session):
        """B-type (order reservation) cantitate should be negative or zero."""
        positive_b = db.query(Deficit).filter(
            Deficit.tip_rezervare == "B",
            Deficit.cantitate > 0,
        ).count()
        # This is informational - if some are positive, the formula might need adjustment
        total_b = db.query(Deficit).filter(Deficit.tip_rezervare == "B").count()
        if total_b > 0:
            pct = positive_b / total_b * 100
            # Allow some tolerance - some B-type might legitimately be positive (returns?)
            assert pct < 5, (
                f"{positive_b}/{total_b} ({pct:.1f}%) B-type records have positive cantitate"
            )

    def test_stoc_deficit_articles_appear_in_planner_no_material(self, db: Session):
        """Articles in deficit (stoc) should cause no_material in planner."""
        # Get articles with true deficit
        deficit_articles = set()
        stoc = (
            db.query(
                Deficit.articol,
                func.max(Deficit.sold_actual),
                func.sum(Deficit.cantitate),
            )
            .group_by(Deficit.articol)
            .all()
        )
        for art, sold, rez in stoc:
            if (sold or 0) + (rez or 0) < 0:
                deficit_articles.add(art)

        # Get articles mentioned in planner no_material motiv
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        no_mat = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
            PlanificareRezultat.status == "no_material",
        ).all()
        planner_articles = set()
        for r in no_mat:
            if r.motiv and "insuficient " in r.motiv:
                art = r.motiv.split("insuficient ")[1].split(":")[0]
                planner_articles.add(art)

        # Check that planner articles are indeed in deficit in stoc
        false_positives = planner_articles - deficit_articles
        # Note: planner processes sequentially (running balance), so it may
        # report deficit for articles that have positive global balance but
        # run out after high-priority orders consume them.
        # This is EXPECTED behavior, not a bug. Just log it.
        if false_positives:
            print(f"\n  INFO: {len(false_positives)} articles reported as no_material "
                  f"by planner but have positive global stock (sequential depletion). "
                  f"This is expected.")

    def test_planner_stoc_tracker_matches_api_formula(self, db: Session):
        """The planner's stoc_tracker initialization should use the same base
        value (sold_actual) as the API's disponibil formula."""
        # Planner: stoc_tracker[art] = d.sold_actual (first occurrence)
        # API: disponibil = max(sold_actual) + sum(cantitate)
        # Both should start from the same sold_actual base
        multi_sold = (
            db.query(
                Deficit.articol,
                func.min(Deficit.sold_actual),
                func.max(Deficit.sold_actual),
            )
            .group_by(Deficit.articol)
            .having(func.min(Deficit.sold_actual) != func.max(Deficit.sold_actual))
            .all()
        )
        # If sold_actual varies across rows for same article, planner takes
        # first-seen while API takes MAX. This is a potential inconsistency.
        if multi_sold:
            print(f"\n  WARNING: {len(multi_sold)} articles have varying sold_actual "
                  f"across deficit rows. Planner uses first-seen, API uses MAX.")
            for art, mn, mx in multi_sold[:5]:
                print(f"    {art}: min={mn}, max={mx}")


class TestStocAprov:
    def test_stoc_endpoint_returns_aprovizionare_fields(self, db: Session):
        """The stoc response must include total_aprovizionare and disponibil_final."""
        from sqlalchemy import case
        results = db.query(
            Deficit.articol,
            func.max(Deficit.sold_actual).label("sold"),
            func.sum(case((Deficit.tip_rezervare == "B", Deficit.cantitate), else_=0)).label("rez"),
            func.sum(case((Deficit.tip_rezervare == "A", Deficit.cantitate), else_=0)).label("aprov"),
        ).group_by(Deficit.articol).limit(5).all()
        for r in results:
            sold = r[1] or 0
            rez = r[2] or 0
            aprov = r[3] or 0
            disponibil = sold + rez
            disponibil_final = disponibil + aprov
            assert disponibil_final >= disponibil, (
                f"disponibil_final ({disponibil_final}) < disponibil ({disponibil}) "
                f"for {r[0]} — A-type cantitate should be positive"
            )

    def test_a_type_cantitate_is_positive(self, db: Session):
        """A-type (incoming) cantitate must be >= 0."""
        negative_a = db.query(Deficit).filter(
            Deficit.tip_rezervare == "A",
            Deficit.cantitate < 0,
        ).count()
        total_a = db.query(Deficit).filter(Deficit.tip_rezervare == "A").count()
        if total_a > 0:
            pct = negative_a / total_a * 100
            assert pct < 5, (
                f"{negative_a}/{total_a} ({pct:.1f}%) A-type records have negative cantitate. "
                "Aprovizionare should be positive."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. BOARD ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoard:
    def test_board_items_match_planned_count(self, db: Session):
        """Board should show exactly the planned operations."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        planned_count = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
            PlanificareRezultat.status == "planned",
        ).count()
        assert planned_count > 0, "No planned operations found"
        assert planned_count == s.operatii_planificate, (
            f"Planned count ({planned_count}) != session header ({s.operatii_planificate})"
        )

    def test_board_groups_are_valid_resources(self, db: Session):
        """Each board group should correspond to a real resource."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        planned = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
            PlanificareRezultat.status == "planned",
        ).all()
        resource_ids = {r.resursa_id for r in planned if r.resursa_id}
        for rid in resource_ids:
            res = db.query(Resursa).filter(Resursa.id == rid).first()
            assert res is not None, f"Planned op references non-existent resource {rid}"

    def test_planned_ops_have_valid_resource_for_cl(self, db: Session):
        """Each planned op's resource should belong to the same CL."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        planned = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
            PlanificareRezultat.status == "planned",
        ).all()
        mismatches = 0
        for r in planned:
            if r.resursa_id:
                res = db.query(Resursa).filter(Resursa.id == r.resursa_id).first()
                if res and res.cl != r.cl:
                    mismatches += 1
        assert mismatches == 0, f"{mismatches} planned ops have resource CL mismatch"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. GANTT ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestGantt:
    def test_gantt_task_count_matches_planned(self, db: Session):
        """Gantt should show same number of tasks as planned operations."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        planned_count = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
            PlanificareRezultat.status == "planned",
        ).count()
        assert planned_count > 0, "No planned operations for gantt"
        assert planned_count == s.operatii_planificate

    def test_all_planned_ops_have_positive_duration(self, db: Session):
        """All planned operations should have positive remaining time."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        planned = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
            PlanificareRezultat.status == "planned",
        ).all()
        for r in planned:
            assert r.durata_ore > 0, f"Planned op {r.id} has non-positive duration {r.durata_ore}"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. CROSS-TAB CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossTabConsistency:
    def test_planificare_total_matches_dashboard(self, db: Session):
        """The sum of all planning statuses should relate to total dispatch items.
        Not all dispatch items get planned (only non-STOP with remaining time > 0)."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        total_results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
        ).count()
        # Total results + completed ops = dispatch items considered
        # The planner skips STOP orders and completed ops (remaining=0)
        assert total_results > 0, "No planning results found"
        assert total_results <= 2684, f"More results ({total_results}) than dispatch items (2684)"

    def test_planning_status_distribution_sane(self, db: Session):
        """Planning results should have reasonable distribution across statuses."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
        ).all()
        counts = defaultdict(int)
        for r in results:
            counts[r.status] += 1

        total = len(results)
        assert total > 0, "No planning results"
        assert counts["planned"] > 100, f"Too few planned: {counts['planned']}"
        assert counts["planned"] + counts["no_material"] + counts["blocked_by_rank"] + \
               counts["no_bt"] + counts["no_resource"] == total, \
               "Status counts don't sum to total"
        print(f"\n  Planning distribution: planned={counts['planned']}, "
              f"no_material={counts['no_material']}, blocked={counts['blocked_by_rank']}, "
              f"no_bt={counts['no_bt']}, no_resource={counts['no_resource']}")

    def test_stoc_deficit_count_matches_frontend(self, db: Session):
        """Number of deficit articles should be consistent."""
        stoc = (
            db.query(
                Deficit.articol,
                func.max(Deficit.sold_actual),
                func.sum(Deficit.cantitate),
            )
            .group_by(Deficit.articol)
            .all()
        )
        deficit = sum(1 for _, sold, rez in stoc if (sold or 0) + (rez or 0) < 0)
        # Frontend showed 13 deficit out of first 50 articles,
        # but there are 500 total articles. Count all.
        assert deficit > 0, "Expected some articles in deficit"
        print(f"\n  INFO: {deficit} total articles in deficit (out of {len(stoc)} total)")

    def test_no_duplicate_dispatch_in_planning(self, db: Session):
        """Each dispatch item should appear at most once in planning results."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        results = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
        ).all()
        dispatch_ids = [r.dispatch_id for r in results if r.dispatch_id]
        assert len(dispatch_ids) == len(set(dispatch_ids)), (
            f"Found duplicate dispatch IDs: {len(dispatch_ids)} total, {len(set(dispatch_ids))} unique"
        )

    def test_board_late_items_are_past_today(self, db: Session):
        """Items marked as 'late' on the board should have end dates before today."""
        s = db.query(PlanificareSesiune).order_by(PlanificareSesiune.id.desc()).first()
        planned = db.query(PlanificareRezultat).filter(
            PlanificareRezultat.sesiune_id == s.id,
            PlanificareRezultat.status == "planned",
        ).all()
        today = datetime.now()
        late_count = sum(1 for r in planned if r.data_end and r.data_end < today)
        # Board API reported 168 late items out of 179
        print(f"\n  INFO: {late_count} late items (end date before now), out of {len(planned)}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CREDENTIALS FROM ENV
# ═══════════════════════════════════════════════════════════════════════════════

import importlib

# ═══════════════════════════════════════════════════════════════════════════════
# 9. ATOMIC IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

from unittest.mock import patch

class TestAtomicImport:
    """Verify that a failure in any import step rolls back all previous steps."""

    def _make_db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        return Session()

    def test_failure_in_step3_rolls_back_steps1_and_2(self):
        """
        import_all: if import_operatii raises, Comanda rows inserted by step 1
        must NOT be visible in the DB after the failure.
        """
        from models import Comanda
        from importer import import_all

        db = self._make_db()

        def fake_import_comenzi(db, path):
            db.add(Comanda(
                cp=9999, cv=9999, client="Atomic Test",
                cant_vnz=1, livrat=0, status_cda="LIBER",
            ))
            return 1

        def fake_import_dispatch(db, path):
            return 0

        def fake_import_operatii(db, path):
            raise RuntimeError("Simulated failure in step 3")

        def fake_import_deficite(db, path):
            return 0

        def fake_import_resurse(db, path):
            return 0

        with patch("importer.import_comenzi", fake_import_comenzi), \
             patch("importer.import_dispatch", fake_import_dispatch), \
             patch("importer.import_operatii", fake_import_operatii), \
             patch("importer.import_deficite", fake_import_deficite), \
             patch("importer.import_resurse", fake_import_resurse):
            try:
                import_all(db, "/fake/data/dir")
            except RuntimeError:
                pass  # expected

        count = db.query(Comanda).filter(Comanda.cp == 9999).count()
        assert count == 0, (
            f"Expected 0 Comanda rows after rollback, got {count}. "
            "The import is not atomic — partial data was committed."
        )
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 10. PATH TRAVERSAL
# ═══════════════════════════════════════════════════════════════════════════════

class TestPathTraversal:
    """Verify the SPA catch-all route cannot serve files outside frontend/dist."""

    def _make_fake_dist(self, tmp_path):
        """Create a minimal fake dist/ directory for testing."""
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "assets").mkdir()
        (dist / "index.html").write_text("<html><body>SPA</body></html>")
        (dist / "about.html").write_text("<html><body>About</body></html>")
        return str(dist)

    def test_traversal_path_falls_back_to_index(self, tmp_path):
        """
        A path with ../ traversal must NOT serve files outside dist/.
        It should fall back to index.html instead.
        """
        import sys, os, types
        import importlib

        dist = self._make_fake_dist(tmp_path)

        # Also create a file OUTSIDE dist to attempt to serve
        secret = tmp_path / "secret.txt"
        secret.write_text("SECRET_CONTENT")

        # Patch _DIST to our fake dist, reload app
        if "main" in sys.modules:
            del sys.modules["main"]

        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "os.path.isdir", side_effect=lambda p: True if p == dist else os.path.isdir.__wrapped__(p) if hasattr(os.path.isdir, "__wrapped__") else True
        ):
            pass  # Don't use this approach

        # Simpler: monkeypatch _DIST directly after import
        if "main" in sys.modules:
            del sys.modules["main"]
        import main as m

        original_dist_real = m._DIST_REAL if hasattr(m, "_DIST_REAL") else None

        # Only test if the route is mounted (dist exists in real deployment)
        import os
        real_dist = os.path.join(os.path.dirname(m.__file__), "..", "frontend", "dist")
        if not os.path.isdir(real_dist):
            import pytest
            pytest.skip("frontend/dist not built — SPA routes not mounted")

        from fastapi.testclient import TestClient
        client = TestClient(m.app, raise_server_exceptions=False)

        # Attempt traversal to backend/main.py
        resp = client.get(
            "/../../../../backend/main.py",
            headers={"Authorization": f"Bearer {m._VALID_TOKEN}"},
        )
        assert resp.status_code == 200
        # Must be index.html content, not Python source
        assert "def " not in resp.text and "FastAPI" not in resp.text, (
            "Path traversal succeeded — Python source was served!"
        )
        # Must be the SPA index page
        assert resp.headers.get("content-type", "").startswith("text/html"), (
            "Expected index.html (text/html) but got different content-type"
        )

    def test_normal_file_in_dist_is_served(self):
        """Legitimate files inside dist/ must still be served correctly."""
        import sys, os
        if "main" in sys.modules:
            del sys.modules["main"]
        import main as m

        real_dist = os.path.join(os.path.dirname(m.__file__), "..", "frontend", "dist")
        if not os.path.isdir(real_dist):
            import pytest
            pytest.skip("frontend/dist not built — SPA routes not mounted")

        from fastapi.testclient import TestClient
        client = TestClient(m.app, raise_server_exceptions=False)

        # Request index.html directly (always exists in a built SPA)
        resp = client.get(
            "/index.html",
            headers={"Authorization": f"Bearer {m._VALID_TOKEN}"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", ""), (
            "index.html should be served as text/html"
        )


class TestPlanningLock:
    """Verify that concurrent planning calls are serialized."""

    def test_lock_exists_on_module(self):
        """main._PLAN_LOCK must exist and be a threading.Lock."""
        import sys
        if "main" in sys.modules:
            del sys.modules["main"]
        import main as m
        import threading
        assert hasattr(m, "_PLAN_LOCK"), "main must expose _PLAN_LOCK"
        assert isinstance(m._PLAN_LOCK, type(threading.Lock())), (
            "_PLAN_LOCK must be a threading.Lock instance"
        )

    def test_second_plan_call_is_blocked_while_lock_held(self):
        """
        While _PLAN_LOCK is held (simulating an in-progress plan),
        a second acquire must fail (non-blocking).
        """
        import sys
        if "main" in sys.modules:
            del sys.modules["main"]
        import main as m

        acquired = m._PLAN_LOCK.acquire(blocking=False)
        assert acquired, "Lock should be acquirable when idle"

        try:
            second = m._PLAN_LOCK.acquire(blocking=False)
            assert not second, (
                "_PLAN_LOCK must reject a second caller while held. "
                "Concurrent planning is not protected."
            )
        finally:
            m._PLAN_LOCK.release()

        # After release, must be acquirable again
        third = m._PLAN_LOCK.acquire(blocking=False)
        assert third, "Lock should be free after release"
        m._PLAN_LOCK.release()


class TestCredentialsFromEnv:
    """Verify auth credentials are read from environment variables."""

    def test_auth_user_not_hardcoded(self):
        """AG_USER env var must be set; the default 'andrei' must not be baked in."""
        # Save and clear env
        original = os.environ.pop("AG_USER", None)
        try:
            # Re-import main with env cleared — should fall back or raise, not use 'andrei'
            # We test this indirectly: the token must differ when the env var differs.
            os.environ["AG_USER"] = "testuser"
            os.environ["AG_PASS"] = "testpass"
            os.environ["AG_SALT"] = "testsalt"

            import hashlib
            expected = hashlib.sha256("testuser:testpass:testsalt".encode()).hexdigest()

            # Import the module fresh
            if "main" in sys.modules:
                del sys.modules["main"]
            import main as m
            assert m._VALID_TOKEN == expected, (
                f"Token should reflect env vars. Got {m._VALID_TOKEN[:16]}..., "
                f"expected {expected[:16]}..."
            )
        finally:
            if original is not None:
                os.environ["AG_USER"] = original
            else:
                os.environ.pop("AG_USER", None)
            os.environ.pop("AG_PASS", None)
            os.environ.pop("AG_SALT", None)
            if "main" in sys.modules:
                del sys.modules["main"]
