"""Import data from Excel files into the database."""
from __future__ import annotations
import pandas as pd
from datetime import date, datetime
from sqlalchemy.orm import Session
from models import Comanda, DispatchItem, Operatie, Deficit, Resursa, ProgramResursa


def safe_date(val) -> date | None:
    if pd.isna(val):
        return None
    if isinstance(val, str):
        if val.strip() == "" or val.startswith("1911"):
            return None
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    if isinstance(val, pd.Timestamp):
        return val.date()
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return None


def safe_str(val) -> str | None:
    if pd.isna(val):
        return None
    return str(val).strip()


def safe_int(val) -> int:
    if pd.isna(val):
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def safe_float(val) -> float:
    if pd.isna(val):
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def parse_ore_disponibile(schimburi: str | None) -> float:
    """Parse shift string like '6-14;14-22' into total hours."""
    if not schimburi or pd.isna(schimburi):
        return 0.0
    total = 0.0
    for schimb in str(schimburi).split(";"):
        parts = schimb.strip().split("-")
        if len(parts) == 2:
            try:
                start_h = int(parts[0])
                end_h = int(parts[1])
                total += end_h - start_h
            except ValueError:
                pass
    return total


def import_comenzi(db: Session, filepath: str):
    df = pd.read_excel(filepath, sheet_name="SC")
    db.query(Comanda).delete()

    for _, row in df.iterrows():
        comanda = Comanda(
            id=safe_int(row.get("id")),
            cp=safe_int(row.get("CP")),
            cv=safe_int(row.get("CV") or row.get("Comanda")),  # Excel: "Comanda" = CV
            client=safe_str(row.get("Dealer")),        # Excel: "Dealer" = clientul tipografiei
            client_final=safe_str(row.get("ClientFinal")),
            tip_produs=safe_str(row.get("TipProdus")),
            articol=safe_str(row.get("Articol")),
            tip_comanda=safe_str(row.get("TipComanda")),
            cant_vnz=safe_int(row.get("CantVnz")),
            livrat=safe_int(row.get("Livrat")),
            stadiu_prepress=safe_str(row.get("StadiuPrepress")),
            stadiu_sf=safe_str(row.get("StadiuSf")),
            status_cda=safe_str(row.get("Status_cda")),
            data_estimata_livrare=safe_date(row.get("DataEstimataLivrare")),
            data_actualizata_livrare=safe_date(row.get("DataActualizataLivrare")),
            dt_livr_prod=safe_date(row.get("DtLivrProd")),
            data_comanda=safe_date(row.get("DataComenzii")),
            data_limita_bt=safe_date(row.get("DataLimitaBT")),
            bt1=safe_str(row.get("BT1")),
            bt2=safe_str(row.get("BT2")),
            bt3=safe_str(row.get("BT3")),
            bt4=safe_str(row.get("BT4")),
            data_reala_bt=safe_str(row.get("DataRealaBT")),
            val_platita=safe_float(row.get("ValPlatita")),
            val_de_platit=safe_float(row.get("ValDePlatit")),
            cant_plan_cp=safe_float(row.get("CantPlanCP")) if not pd.isna(row.get("CantPlanCP", None)) else None,
            cant_real_cp=safe_float(row.get("CantRealCP")) if not pd.isna(row.get("CantRealCP", None)) else None,
            observatii=safe_str(row.get("Observatii")),
            ref_client=safe_str(row.get("RefClient")),
        )
        db.add(comanda)
    db.flush()
    return len(df)


def import_dispatch(db: Session, filepath: str):
    df = pd.read_excel(filepath, sheet_name="Dispatch")
    db.query(DispatchItem).delete()

    for _, row in df.iterrows():
        item = DispatchItem(
            cl=safe_str(row.get("CL")),
            start=safe_date(row.get("Start")),
            data_fin_plan=safe_date(row.get("DataFinPlan")),
            data_livr_com=safe_date(row.get("DataLivrCom")),
            wo=safe_int(row.get("WO")),
            op=safe_int(row.get("OP")),
            descr_op=safe_str(row.get("Descr_OP")),
            stock_code=safe_str(row.get("Stock_code")),
            grupa=safe_str(row.get("Grupa")),
            comandat=safe_int(row.get("Comandat")),
            q_plan=safe_float(row.get("Q_Plan")),
            setup=safe_int(row.get("Setup")),
            flagsetup=safe_int(row.get("flagsetup")),
            unitati=safe_float(row.get("Unitati")),
            p_setup=safe_float(row.get("P_Setup")),
            p_runtime=safe_float(row.get("P_Runtime")),
            r_setup=safe_float(row.get("R_Setup")),
            r_runtime=safe_float(row.get("R_Runtime")),
            q_raportat=safe_int(row.get("Q_Raportat")),
            q_rest=safe_float(row.get("Q_Rest")),
            bt_data_limita=safe_date(row.get("BTDataLimita")),
            data_actualizare_livrare=safe_date(row.get("DataActualizareLivrare")),
        )
        db.add(item)
    db.flush()
    return len(df)


def import_operatii(db: Session, filepath: str):
    df = pd.read_excel(filepath, sheet_name="Operatii")
    db.query(Operatie).delete()

    seen_codes = set()
    count = 0
    for _, row in df.iterrows():
        cod = safe_str(row.get("cod"))
        if not cod or cod in seen_codes:
            continue
        seen_codes.add(cod)
        rank_val = row.get("Rank")
        rank = int(rank_val) if not pd.isna(rank_val) else 999

        op = Operatie(
            cod=cod,
            descriere=safe_str(row.get("Descriere")),
            cod_unic=safe_str(row.get("codunic")),
            sectie=safe_str(row.get("sectie")),
            flagsetup=safe_str(row.get("flagsetup")),
            flagcaiete=safe_str(row.get("flagcaiete")),
            rank=rank,
        )
        db.add(op)
        count += 1
    db.flush()
    return count


def import_deficite(db: Session, filepath: str):
    df = pd.read_excel(filepath, sheet_name="Deficite")
    db.query(Deficit).delete()

    for _, row in df.iterrows():
        d = Deficit(
            articol=safe_str(row.get("Articol")),
            sold_actual=safe_float(row.get("SoldActual")),
            cantitate=safe_float(row.get("CantitateRezervata") if "CantitateRezervata" in row.index else row.get("Cantitate")),
            la_data=safe_date(row.get("LaData")),
            pentru=safe_str(row.get("Pentru")),
            pe_comanda=safe_int(row.get("PeComanda")),
            tiraj_comandat=safe_int(row.get("TirajComandat")),
            tiraj_realizat=safe_int(row.get("TirajRealizatPeComanda")),
            rezervat_in=safe_str(row.get("RezervatIn")),
            tip_rezervare=safe_str(row.get("TipRezervare")),
        )
        db.add(d)
    db.flush()
    return len(df)


def import_resurse(db: Session, filepath: str):
    df = pd.read_excel(filepath, sheet_name="WC")
    db.query(ProgramResursa).delete()
    db.query(Resursa).delete()

    # Columns after 'Operatii' are date columns (DD.MM format)
    date_cols = [c for c in df.columns if c not in ("CL", "Denumire CL", "Resursa", "Operatii")]
    current_year = datetime.now().year

    for _, row in df.iterrows():
        resursa = Resursa(
            cl=safe_str(row.get("CL")),
            denumire_cl=safe_str(row.get("Denumire CL")),
            resursa=safe_str(row.get("Resursa")),
            operatii=safe_str(row.get("Operatii")),
        )
        db.add(resursa)
        db.flush()

        for col in date_cols:
            schimburi = row.get(col)
            ore = parse_ore_disponibile(schimburi)
            if ore <= 0:
                continue

            # Parse DD.MM column name to date
            try:
                parts = str(col).split(".")
                day = int(parts[0])
                month = int(parts[1])
                data = date(current_year, month, day)
            except (ValueError, IndexError):
                continue

            prog = ProgramResursa(
                resursa_id=resursa.id,
                data=data,
                schimburi=safe_str(schimburi),
                ore_disponibile=ore,
            )
            db.add(prog)

    db.flush()
    return len(df)


def import_all(db: Session, data_dir: str):
    import os
    results = {}
    try:
        results["comenzi"]  = import_comenzi(db, os.path.join(data_dir, "Stari comenzi_AS.xlsx"))
        results["dispatch"] = import_dispatch(db, os.path.join(data_dir, "Dispatch List_AS.xlsx"))
        results["operatii"] = import_operatii(db, os.path.join(data_dir, "OperatiiWO_AS.xlsx"))
        results["deficite"] = import_deficite(db, os.path.join(data_dir, "Lista Deficite_AS.xlsx"))
        results["resurse"]  = import_resurse(db, os.path.join(data_dir, "Resurse_AS.xlsx"))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return results
