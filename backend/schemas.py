from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime


class ComandaOut(BaseModel):
    id: int
    cp: int
    cv: int
    client: Optional[str] = None
    client_final: Optional[str] = None
    articol: Optional[str] = None
    tip_comanda: Optional[str] = None
    cant_vnz: int
    livrat: int
    stadiu_prepress: Optional[str] = None
    stadiu_sf: Optional[str] = None
    status_cda: Optional[str] = None
    data_actualizata_livrare: Optional[date] = None
    dt_livr_prod: Optional[date] = None
    val_platita: float
    val_de_platit: float
    ref_client: Optional[str] = None

    class Config:
        from_attributes = True


class DispatchOut(BaseModel):
    id: int
    cl: Optional[str] = None
    wo: int
    op: int
    descr_op: Optional[str] = None
    stock_code: Optional[str] = None
    grupa: Optional[str] = None
    comandat: int
    q_plan: float
    p_setup: float
    p_runtime: float
    r_setup: float
    r_runtime: float
    q_raportat: int
    q_rest: float

    class Config:
        from_attributes = True


class PlanificareOut(BaseModel):
    id: int
    sesiune_id: int
    dispatch_id: Optional[int] = None
    wo: int
    op: int
    cl: Optional[str] = None
    resursa_id: Optional[int] = None
    resursa_nume: Optional[str] = None
    data_start: Optional[datetime] = None
    data_end: Optional[datetime] = None
    durata_ore: float
    frozen: bool
    status: str
    motiv: Optional[str] = None

    class Config:
        from_attributes = True


class GanttTask(BaseModel):
    id: str
    name: str
    start: str
    end: str
    progress: float
    dependencies: str
    custom_class: str
    wo: int
    op: int
    cl: Optional[str] = None
    resursa: Optional[str] = None
    status: str


class ResursaOut(BaseModel):
    id: int
    cl: Optional[str] = None
    denumire_cl: Optional[str] = None
    resursa: Optional[str] = None
    operatii: Optional[str] = None

    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    comenzi: int
    dispatch: int
    operatii: int
    deficite: int
    resurse: int


class PlanningResult(BaseModel):
    sesiune_id: int
    stats: dict
    total_comenzi: int


class StocArticol(BaseModel):
    articol: str
    sold_actual: float
    total_rezervat: float
    total_aprovizionare: float
    disponibil: float
    disponibil_final: float


class ComandaSummary(BaseModel):
    data_planificare: Optional[str] = None   # ISO date string or None
    intarziere_zile: Optional[int] = None    # positive=late, negative=early, None=unknown
    status_planificare: str                  # "Planificat" | "Previzionat" | "Partial" | "Blocat"
    status_material: str                     # "Disponibil" | "In aprovizionare" | "Lipsa"
