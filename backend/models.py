from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class Comanda(Base):
    __tablename__ = "comenzi"

    id = Column(Integer, primary_key=True, index=True)
    cp = Column(Integer, index=True)  # Comanda productie
    cv = Column(Integer, index=True)  # Comanda vanzare
    client = Column(String)
    client_final = Column(String)
    tip_produs = Column(String)
    articol = Column(String)
    tip_comanda = Column(String)  # V=vanzare, P=productie
    cant_vnz = Column(Integer)
    livrat = Column(Integer, default=0)
    stadiu_prepress = Column(String)
    stadiu_sf = Column(String)
    status_cda = Column(String)  # LIBER / STOP
    data_estimata_livrare = Column(Date, nullable=True)
    data_actualizata_livrare = Column(Date, nullable=True)
    dt_livr_prod = Column(Date, nullable=True)
    data_comanda = Column(Date, nullable=True)
    data_limita_bt = Column(Date, nullable=True)
    bt1 = Column(String, nullable=True)
    bt2 = Column(String, nullable=True)
    bt3 = Column(String, nullable=True)
    bt4 = Column(String, nullable=True)
    data_reala_bt = Column(String, nullable=True)
    cant_plan_cp = Column(Float, nullable=True)
    cant_real_cp = Column(Float, nullable=True)
    observatii = Column(Text, nullable=True)
    ref_client = Column(String, nullable=True)

    operatii = relationship("DispatchItem", back_populates="comanda", foreign_keys="DispatchItem.wo")


class DispatchItem(Base):
    __tablename__ = "dispatch"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cl = Column(String, index=True)  # Centru de lucru/cost
    start = Column(Date, nullable=True)
    data_fin_plan = Column(Date, nullable=True)
    data_livr_com = Column(Date, nullable=True)
    wo = Column(Integer, ForeignKey("comenzi.cp"), index=True)  # Work Order = CP
    op = Column(Integer, index=True)  # Cod operatie
    descr_op = Column(String)
    stock_code = Column(String, index=True)
    grupa = Column(String)
    comandat = Column(Integer)
    q_plan = Column(Float)
    setup = Column(Integer)
    flagsetup = Column(Integer)
    unitati = Column(Float)
    p_setup = Column(Float, default=0)  # Planificat setup (ore)
    p_runtime = Column(Float, default=0)  # Planificat runtime (ore)
    r_setup = Column(Float, default=0)  # Raportat setup (ore)
    r_runtime = Column(Float, default=0)  # Raportat runtime (ore)
    q_raportat = Column(Integer, default=0)
    q_rest = Column(Float)
    bt_data_limita = Column(Date, nullable=True)
    data_actualizare_livrare = Column(Date, nullable=True)

    comanda = relationship("Comanda", back_populates="operatii", foreign_keys=[wo])


class Operatie(Base):
    __tablename__ = "operatii"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cod = Column(String, unique=True, index=True)
    descriere = Column(String)
    cod_unic = Column(String)
    sectie = Column(String)
    flagsetup = Column(String, nullable=True)
    flagcaiete = Column(String, nullable=True)
    rank = Column(Integer, default=999)


class Deficit(Base):
    __tablename__ = "deficite"

    id = Column(Integer, primary_key=True, autoincrement=True)
    articol = Column(String, index=True)
    sold_actual = Column(Float)
    cantitate = Column(Float)
    la_data = Column(Date, nullable=True)
    pentru = Column(String)
    pe_comanda = Column(Integer, index=True)
    tiraj_comandat = Column(Integer)
    tiraj_realizat = Column(Integer)
    rezervat_in = Column(String)
    tip_rezervare = Column(String)  # B=rezervare, A=aprovizionare, 0=altele


class Resursa(Base):
    __tablename__ = "resurse"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cl = Column(String, index=True)  # Centru de lucru
    denumire_cl = Column(String)
    resursa = Column(String)  # Nume masina/om
    operatii = Column(String, nullable=True)  # Coduri operatii separate prin ;


class ProgramResursa(Base):
    __tablename__ = "program_resurse"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resursa_id = Column(Integer, ForeignKey("resurse.id"), index=True)
    data = Column(Date, index=True)
    schimburi = Column(String, nullable=True)  # e.g. "6-14;14-22"
    ore_disponibile = Column(Float, default=0)

    resursa = relationship("Resursa")


class PlanificareSesiune(Base):
    """Rezultatul unei sesiuni de planificare."""
    __tablename__ = "planificare_sesiuni"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime)
    status = Column(String)  # running, completed, failed
    total_operatii = Column(Integer, default=0)
    operatii_planificate = Column(Integer, default=0)
    operatii_neplanificate = Column(Integer, default=0)


class PlanificareRezultat(Base):
    """O operatie planificata pe o resursa, la o data/ora."""
    __tablename__ = "planificare_rezultate"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sesiune_id = Column(Integer, ForeignKey("planificare_sesiuni.id"), index=True)
    dispatch_id = Column(Integer, ForeignKey("dispatch.id"), index=True)
    wo = Column(Integer, index=True)
    op = Column(Integer)
    cl = Column(String)
    resursa_id = Column(Integer, ForeignKey("resurse.id"))
    resursa_nume = Column(String)
    data_start = Column(DateTime)
    data_end = Column(DateTime)
    durata_ore = Column(Float)
    frozen = Column(Boolean, default=False)  # Operatie blocata (nu se replanifica)

    # Motiv daca nu s-a putut planifica
    status = Column(String)  # planned, no_material, no_resource, blocked_by_rank, no_bt
    motiv = Column(String, nullable=True)

    sesiune = relationship("PlanificareSesiune")
    dispatch = relationship("DispatchItem")
    resursa_rel = relationship("Resursa")


class Setari(Base):
    """Key-value application settings."""
    __tablename__ = "setari"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    cheie   = Column(String, unique=True, index=True, nullable=False)
    valoare = Column(String, nullable=True)
