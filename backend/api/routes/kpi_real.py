"""
KPIs industriels réels — calculés depuis les événements de maintenance saisis.

Contrairement à /api/kpi/* (dérivé de l'état temps réel en RAM), ces KPIs
reposent sur les vrais événements enregistrés en base : MTBF, MTTR,
disponibilité, coûts et ROI deviennent démontrables, pas simulés.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import get_db, MaintenanceEvent
from backend.db.repository import MachineRepository
from backend.api.auth import get_current_user, require_admin

router = APIRouter(tags=["KPIs Réels"])


class MaintenanceEventCreate(BaseModel):
    machine_id     : str
    event_type     : str                      # failure | corrective | planned
    started_at     : str                      # ISO 8601
    ended_at       : Optional[str]   = None
    fault_type     : Optional[str]   = None
    technician     : Optional[str]   = None
    parts_replaced : Optional[List]  = []
    cost_euros     : Optional[float] = None
    notes          : Optional[str]   = None


@router.post("/maintenance/event", dependencies=[Depends(get_current_user)])
def create_maintenance_event(event: MaintenanceEventCreate,
                             db: Session = Depends(get_db)):
    """Enregistre un événement de maintenance réel (authentifié)."""
    started = datetime.fromisoformat(event.started_at)
    ended   = datetime.fromisoformat(event.ended_at) if event.ended_at else None
    duration = ((ended - started).total_seconds() / 3600.0) if ended else None

    db_event = MaintenanceEvent(
        machine_id     = event.machine_id,
        event_type     = event.event_type,
        started_at     = started,
        ended_at       = ended,
        duration_hours = duration,
        fault_type     = event.fault_type,
        technician     = event.technician,
        parts_replaced = event.parts_replaced,
        cost_euros     = event.cost_euros,
        notes          = event.notes,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return {
        "message"   : "Événement enregistré",
        "event_id"  : db_event.id,
        "duration_h": round(duration, 2) if duration else None,
    }


@router.get("/maintenance/events/{machine_id}")
def list_maintenance_events(machine_id: str, limit: int = 100,
                            db: Session = Depends(get_db)):
    """Liste les événements de maintenance d'une machine."""
    rows = (
        db.query(MaintenanceEvent)
        .filter(MaintenanceEvent.machine_id == machine_id)
        .order_by(MaintenanceEvent.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "machine_id": machine_id,
        "events": [
            {
                "id"            : r.id,
                "event_type"    : r.event_type,
                "started_at"    : r.started_at.isoformat() if r.started_at else None,
                "ended_at"      : r.ended_at.isoformat() if r.ended_at else None,
                "duration_hours": r.duration_hours,
                "fault_type"    : r.fault_type,
                "technician"    : r.technician,
                "cost_euros"    : r.cost_euros,
                "notes"         : r.notes,
            }
            for r in rows
        ],
    }


@router.get("/machine/{machine_id}/history/db")
def machine_history_db(machine_id: str, hours: int = 168,
                       db: Session = Depends(get_db)):
    """
    Historique PERSISTÉ (base de données) d'une machine — survit aux
    redémarrages, contrairement à /machine/{id}/history (tracker en RAM).
    """
    rows = MachineRepository(db).get_history(machine_id, hours=hours, limit=1000)
    return {
        "machine_id": machine_id,
        "source"    : "database",
        "n_points"  : len(rows),
        "history"   : rows,
    }


@router.get("/machine/{machine_id}/history/rollup")
def machine_history_rollup(machine_id: str, hours: int = 168,
                           bucket: str = "hour", db: Session = Depends(get_db)):
    """
    Historique AGRÉGÉ (downsamplé) — lecture qui passe à l'échelle.
    bucket = minute | hour | day.
    """
    return {
        "machine_id": machine_id,
        "bucket"    : bucket,
        "source"    : "database (agrégé)",
        "points"    : MachineRepository(db).get_history_rollup(machine_id, hours, bucket),
    }


@router.post("/admin/retention/purge", dependencies=[Depends(require_admin)])
def retention_purge(keep_days: int = 90, db: Session = Depends(get_db)):
    """Rétention (admin) : purge les états bruts plus anciens que keep_days."""
    n = MachineRepository(db).purge_old_states(keep_days)
    return {"purged": n, "keep_days": keep_days}


@router.get("/kpi/real/{machine_id}")
def get_real_kpis(machine_id: str, days: int = 30,
                  db: Session = Depends(get_db)):
    """KPIs (MTBF/MTTR/disponibilité/coûts) depuis les vrais événements."""
    return MachineRepository(db).compute_real_kpis(machine_id, days)


@router.get("/kpi/roi/{machine_id}")
def get_roi_estimate(machine_id: str,
                     production_cost_per_hour: float = 500.0,
                     avg_failure_duration: float = 8.0,
                     db: Session = Depends(get_db)):
    """
    Estimation du ROI de la maintenance prédictive : coût des arrêts évités
    (pannes anticipées via maintenance corrective) vs coût des interventions.
    """
    cost_failures = (
        db.query(func.sum(MaintenanceEvent.cost_euros))
        .filter(MaintenanceEvent.machine_id == machine_id,
                MaintenanceEvent.event_type == "failure")
        .scalar() or 0.0
    )
    cost_planned = (
        db.query(func.sum(MaintenanceEvent.cost_euros))
        .filter(MaintenanceEvent.machine_id == machine_id,
                MaintenanceEvent.event_type.in_(["planned", "corrective"]))
        .scalar() or 0.0
    )
    n_corrective = (
        db.query(MaintenanceEvent)
        .filter(MaintenanceEvent.machine_id == machine_id,
                MaintenanceEvent.event_type == "corrective")
        .count()
    )

    # Hypothèse : une intervention corrective évite ~70 % d'un arrêt subi
    downtime_avoided = n_corrective * avg_failure_duration * 0.7
    cost_avoided     = downtime_avoided * production_cost_per_hour

    return {
        "machine_id"             : machine_id,
        "total_cost_failures_eur": round(cost_failures, 2),
        "total_cost_planned_eur" : round(cost_planned, 2),
        "downtime_avoided_hours" : round(downtime_avoided, 1),
        "estimated_cost_avoided" : round(cost_avoided, 2),
        "roi_ratio"              : round(cost_avoided / max(cost_planned, 1.0), 2),
        "assumptions"            : {
            "production_cost_per_hour": production_cost_per_hour,
            "avg_failure_duration_h"  : avg_failure_duration,
        },
        "note": "Estimation basée sur les événements enregistrés",
    }
