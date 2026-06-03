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

from backend.db.models import get_db, SessionLocal, WorkOrder

router = APIRouter(tags=["Ordres de travail / GMAO"])


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


def _serialize(wo: WorkOrder) -> dict:
    return {
        "id"           : wo.id,
        "machine_id"   : wo.machine_id,
        "created_at"   : wo.created_at.isoformat() if wo.created_at else None,
        "priority"     : wo.priority,
        "status"       : wo.status,
        "title"        : wo.title,
        "description"  : wo.description,
        "fault"        : wo.fault,
        "iso_zone"     : wo.iso_zone,
        "health_index" : wo.health_index,
        "source"       : wo.source,
        "cmms_ref"     : wo.cmms_ref,
        "pushed_to_cmms": wo.pushed_to_cmms,
        "closed_at"    : wo.closed_at.isoformat() if wo.closed_at else None,
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

        action = recommendation.get("action", "Inspection requise") if recommendation else "Inspection requise"
        delay  = recommendation.get("delay", "") if recommendation else ""

        wo = WorkOrder(
            machine_id   = machine_id,
            priority     = priority,
            status       = "open",
            title        = f"[{priority}] {machine_id} — {fault} (ISO zone {iso_zone})",
            description  = f"Action recommandée : {action}. Délai : {delay}. "
                           f"Health Index {health_index}% — déclenchement automatique PrognoSense.",
            fault        = fault,
            iso_zone     = iso_zone,
            health_index = health_index,
            source       = "auto",
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
    wo = WorkOrder(
        machine_id   = req.machine_id,
        priority     = req.priority,
        status       = "open",
        title        = req.title,
        description  = req.description,
        fault        = req.fault,
        iso_zone     = req.iso_zone,
        health_index = req.health_index,
        source       = "manual",
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
