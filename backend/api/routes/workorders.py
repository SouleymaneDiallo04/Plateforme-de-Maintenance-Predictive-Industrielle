"""
Ordres de travail — boucle fermée maintenance (closed-loop GMAO).

L'alerte ne reste pas un voyant : elle devient une ACTION. Un ordre de
travail est créé automatiquement sur état critique, et peut être poussé
vers une GMAO externe (SAP PM / IBM Maximo / Infor EAM) via un webhook
REST configurable (`CMMS_WEBHOOK_URL`). Sans webhook, l'OT reste interne.

C'est la fonctionnalité qui rend le ROI démontrable pour un acheteur.
"""

import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.models import get_db, SessionLocal, WorkOrder, SparePart
from backend.competency import required_competency, certif_label
from backend.assets import resolve_fault

router = APIRouter(tags=["Ordres de travail / GMAO"])

# Libellés du cycle de vie (partagés)
WO_STATUS_LABELS = {
    "open"       : "Créé",
    "assigned"   : "Assigné",
    "in_progress": "En cours",
    "on_hold"    : "En attente",
    "done"       : "Terminé",
    "closed"     : "Clôturé",
}


def _push_to_cmms(wo: WorkOrder) -> Optional[str]:
    """Pousse l'OT vers une GMAO externe via webhook REST. Retourne l'id externe."""
    url = os.getenv("CMMS_WEBHOOK_URL", "").strip()
    if not url:
        return None
    payload = {
        "asset"      : wo.machine_id,
        "priority"   : wo.priority,
        "title"      : wo.title,
        "description": wo.description,
        "fault"      : wo.fault,
        "iso_zone"   : wo.iso_zone,
        "health_index": wo.health_index,
        "source"     : "PrognoSense",
        "created_at" : wo.created_at.isoformat() if wo.created_at else None,
    }
    try:
        r = httpx.post(url, json=payload, timeout=10.0)
        if r.status_code < 300:
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            return str(data.get("id") or data.get("wonum") or data.get("ref") or "ext-ok")
    except Exception:
        pass
    return None


def _iso(dt):
    return dt.isoformat() if dt else None


def _part_stock(db, reference: Optional[str]) -> dict:
    """Cherche une pièce au magasin. Retourne dispo/qté/emplacement/désignation."""
    if not reference:
        return {"part_designation": None, "part_in_stock": None,
                "part_stock_qty": None, "part_location": None}
    sp = db.query(SparePart).filter(SparePart.reference == reference).first()
    if not sp:
        # Pièce identifiée mais inconnue du magasin → à commander
        return {"part_designation": None, "part_in_stock": False,
                "part_stock_qty": 0, "part_location": None}
    return {
        "part_designation": sp.designation,
        "part_in_stock"   : (sp.stock_qty or 0) > 0,
        "part_stock_qty"  : sp.stock_qty or 0,
        "part_location"   : sp.location,
    }


def _stock_phrase(enr: dict) -> str:
    """Phrase lisible sur la disponibilité de la pièce (pour la description)."""
    ref = enr.get("part_reference")
    if not ref:
        return "Aucune pièce de stock requise."
    if enr.get("part_in_stock"):
        loc = enr.get("part_location") or "magasin"
        return (f"Pièce requise : {ref} — EN STOCK "
                f"({enr.get('part_stock_qty')} dispo, {loc}).")
    return f"Pièce requise : {ref} — RUPTURE de stock, À COMMANDER."


def _enrich(db, machine_id: str, fault: str) -> dict:
    """Élément défaillant explicite (catalogue) + disponibilité de la pièce."""
    info = resolve_fault(machine_id, fault)
    stock = _part_stock(db, info["part_reference"])
    return {
        "equipment"      : info["equipment"],
        "location"       : info["location"],
        "failing_element": info["failing_element"],
        "action"         : info["action"],
        "part_reference" : info["part_reference"],
        **stock,
    }


def _serialize(wo: WorkOrder) -> dict:
    return {
        "id"           : wo.id,
        "machine_id"   : wo.machine_id,
        "created_at"   : _iso(wo.created_at),
        "priority"     : wo.priority,
        "status"       : wo.status,
        "status_label" : WO_STATUS_LABELS.get(wo.status, wo.status),
        "title"        : wo.title,
        "description"  : wo.description,
        "fault"        : wo.fault,
        "iso_zone"     : wo.iso_zone,
        "health_index" : wo.health_index,
        "source"       : wo.source,
        "cmms_ref"     : wo.cmms_ref,
        "pushed_to_cmms": wo.pushed_to_cmms,
        "closed_at"    : _iso(wo.closed_at),
        # Affectation / compétence
        "assigned_to"       : wo.assigned_to,
        "assigned_to_name"  : wo.assigned_to_name,
        "competence_requise": wo.competence_requise,
        "certif_requise"    : wo.certif_requise,
        "certif_requise_label": certif_label(wo.certif_requise),
        "assigned_at"       : _iso(wo.assigned_at),
        "started_at"        : _iso(wo.started_at),
        "completed_at"      : _iso(wo.completed_at),
        "verified_at"       : _iso(wo.verified_at),
        # Élément défaillant explicite + pièce / stock
        "failing_element"   : wo.failing_element,
        "part_reference"    : wo.part_reference,
        "part_designation"  : wo.part_designation,
        "part_in_stock"     : wo.part_in_stock,
        "part_stock_qty"    : wo.part_stock_qty,
        "part_location"     : wo.part_location,
    }


def maybe_auto_workorder(machine_id: str, health_index: float, iso_zone: str,
                         fault: str, recommendation: dict) -> Optional[dict]:
    """
    Crée un OT automatiquement si l'état est critique (zone D / HI bas),
    en évitant les doublons (un seul OT ouvert par machine).
    Appelé par la couche d'ingestion. Gère sa propre session DB.
    """
    # Critères de déclenchement + priorité
    if iso_zone == "D" or health_index < 20:
        priority = "P1"
    elif iso_zone == "C" or health_index < 40:
        priority = "P2"
    else:
        return None

    db = SessionLocal()
    try:
        # Dédoublonnage : pas de nouvel OT si un est déjà ouvert
        existing = (
            db.query(WorkOrder)
            .filter(WorkOrder.machine_id == machine_id,
                    WorkOrder.status != "closed")
            .first()
        )
        if existing:
            return None

        delay  = recommendation.get("delay", "") if recommendation else ""

        req = required_competency(fault, priority=priority, iso_zone=iso_zone)
        enr = _enrich(db, machine_id, fault)
        action = enr["action"]
        stock_txt = _stock_phrase(enr)

        wo = WorkOrder(
            machine_id   = machine_id,
            priority     = priority,
            status       = "open",
            title        = f"[{priority}] {enr['equipment']} ({machine_id}) — {enr['failing_element']}",
            description  = f"Action : {action}. {stock_txt} Délai : {delay or 'au plus tôt'}. "
                           f"Health Index {health_index}% — déclenchement automatique PrognoSense.",
            fault        = fault,
            iso_zone     = iso_zone,
            health_index = health_index,
            source       = "auto",
            competence_requise = req["competence"],
            certif_requise     = req["certif_requise"],
            failing_element  = enr["failing_element"],
            part_reference   = enr["part_reference"],
            part_designation = enr["part_designation"],
            part_in_stock    = enr["part_in_stock"],
            part_stock_qty   = enr["part_stock_qty"],
            part_location    = enr["part_location"],
        )
        db.add(wo)
        db.commit()
        db.refresh(wo)

        ext = _push_to_cmms(wo)
        if ext:
            wo.cmms_ref = ext
            wo.pushed_to_cmms = True
            db.commit()
            db.refresh(wo)

        return _serialize(wo)
    finally:
        db.close()


# ── API ────────────────────────────────────────────────────────────────────

class WorkOrderCreate(BaseModel):
    machine_id  : str
    title       : str
    description : Optional[str] = ""
    priority    : str = "P2"
    fault       : Optional[str] = None
    iso_zone    : Optional[str] = None
    health_index: Optional[float] = None


class WorkOrderUpdate(BaseModel):
    status : str   # open | in_progress | closed


@router.post("/workorder")
def create_workorder(req: WorkOrderCreate, db: Session = Depends(get_db)):
    """Création manuelle d'un ordre de travail (+ push GMAO si configuré)."""
    comp = required_competency(req.fault, priority=req.priority, iso_zone=req.iso_zone)
    enr  = _enrich(db, req.machine_id, req.fault)
    desc = req.description or (
        f"Action : {enr['action']}. {_stock_phrase(enr)}")
    wo = WorkOrder(
        machine_id   = req.machine_id,
        priority     = req.priority,
        status       = "open",
        title        = req.title or f"[{req.priority}] {enr['equipment']} ({req.machine_id}) — {enr['failing_element']}",
        description  = desc,
        fault        = req.fault,
        iso_zone     = req.iso_zone,
        health_index = req.health_index,
        source       = "manual",
        competence_requise = comp["competence"],
        certif_requise     = comp["certif_requise"],
        failing_element  = enr["failing_element"],
        part_reference   = enr["part_reference"],
        part_designation = enr["part_designation"],
        part_in_stock    = enr["part_in_stock"],
        part_stock_qty   = enr["part_stock_qty"],
        part_location    = enr["part_location"],
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)

    ext = _push_to_cmms(wo)
    if ext:
        wo.cmms_ref = ext
        wo.pushed_to_cmms = True
        db.commit()
        db.refresh(wo)

    return _serialize(wo)


@router.get("/workorders")
def list_workorders(status: Optional[str] = None,
                    machine_id: Optional[str] = None,
                    limit: int = 100, db: Session = Depends(get_db)):
    """Liste des ordres de travail (filtrable)."""
    q = db.query(WorkOrder)
    if status:
        q = q.filter(WorkOrder.status == status)
    if machine_id:
        q = q.filter(WorkOrder.machine_id == machine_id)
    rows = q.order_by(WorkOrder.created_at.desc()).limit(limit).all()
    open_count = db.query(WorkOrder).filter(WorkOrder.status != "closed").count()
    return {"work_orders": [_serialize(w) for w in rows], "open_count": open_count}


@router.patch("/workorder/{wo_id}")
def update_workorder(wo_id: int, req: WorkOrderUpdate, db: Session = Depends(get_db)):
    """Met à jour le statut d'un OT (in_progress / closed)."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Ordre de travail introuvable")
    wo.status = req.status
    if req.status == "closed":
        wo.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(wo)
    return _serialize(wo)


@router.get("/workorders/config")
def workorders_config():
    """Diagnostic : la GMAO externe est-elle configurée ?"""
    url = os.getenv("CMMS_WEBHOOK_URL", "").strip()
    return {
        "cmms_webhook_configured": bool(url),
        "mode": "push vers GMAO externe" if url else "interne seulement (table work_orders)",
    }
