"""
Analyse d'efficacité prédictive — PrognoSense.

Mesure si la plateforme a réellement anticipé les pannes :
croise les alertes persistées (Alert) avec les pannes réelles
(MaintenanceEvent type "failure") dans une fenêtre d'anticipation.

Métriques : precision, recall, F1, lead-time (heures d'anticipation).
C'est LE différenciateur : prouver chiffres à l'appui que les alertes
arrivent avant les pannes.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import get_db, Alert, MaintenanceEvent, AlertVerdict

router = APIRouter(tags=["Analytics"])


class VerdictRequest(BaseModel):
    verdict : str               # true_positive | false_positive
    analyst : str = "analyste"
    comment : str = ""

WINDOW_HOURS = 48   # fenêtre d'anticipation alerte → panne


@router.get("/analytics/prediction-accuracy/{machine_id}")
def prediction_accuracy(machine_id: str, window_hours: int = WINDOW_HOURS,
                        db: Session = Depends(get_db)):
    """
    TP : alerte suivie d'une panne dans la fenêtre.
    FP : alerte sans panne dans la fenêtre.
    FN : panne sans alerte préalable dans la fenêtre.
    """
    alerts = (
        db.query(Alert)
        .filter(Alert.machine_id == machine_id)
        .all()
    )
    failures = (
        db.query(MaintenanceEvent)
        .filter(MaintenanceEvent.machine_id == machine_id,
                MaintenanceEvent.event_type == "failure")
        .all()
    )

    def hours_between(later, earlier):
        return (later - earlier).total_seconds() / 3600.0

    tp = fp = fn = 0

    for a in alerts:
        matched = any(
            0 <= hours_between(f.started_at, a.timestamp) <= window_hours
            for f in failures
        )
        if matched:
            tp += 1
        else:
            fp += 1

    lead_times = []
    for f in failures:
        prior = [a for a in alerts
                 if 0 <= hours_between(f.started_at, a.timestamp) <= window_hours]
        if prior:
            first = min(prior, key=lambda a: a.timestamp)
            lead_times.append(hours_between(f.started_at, first.timestamp))
        else:
            fn += 1

    precision = tp / max(tp + fp, 1)
    recall    = tp / max(tp + fn, 1)
    f1        = 2 * precision * recall / max(precision + recall, 1e-10)
    avg_lead  = sum(lead_times) / len(lead_times) if lead_times else None

    return {
        "machine_id"         : machine_id,
        "window_hours"       : window_hours,
        "true_positives"     : tp,
        "false_positives"    : fp,
        "false_negatives"    : fn,
        "precision"          : round(precision, 3),
        "recall"             : round(recall, 3),
        "f1_score"           : round(f1, 3),
        "avg_lead_time_hours": round(avg_lead, 1) if avg_lead else None,
        "max_lead_time_hours": round(max(lead_times), 1) if lead_times else None,
        "interpretation"     : {
            "precision": f"{precision*100:.0f}% des alertes étaient justifiées",
            "recall"   : f"{recall*100:.0f}% des pannes ont été anticipées",
            "lead_time": (f"Anticipation moyenne : {avg_lead:.1f}h avant panne"
                          if avg_lead else "Données insuffisantes"),
        },
    }


@router.get("/alerts/persisted")
def list_persisted_alerts(machine_id: str = None, limit: int = 100,
                          db: Session = Depends(get_db)):
    """Alertes persistées (avec id) + leur verdict analyste s'il existe."""
    q = db.query(Alert)
    if machine_id:
        q = q.filter(Alert.machine_id == machine_id)
    rows = q.order_by(Alert.timestamp.desc()).limit(limit).all()

    verdicts = {
        v.alert_id: v.verdict
        for v in db.query(AlertVerdict).all()
    }
    return {
        "alerts": [
            {
                "id"          : a.id,
                "machine_id"  : a.machine_id,
                "timestamp"   : a.timestamp.isoformat() if a.timestamp else None,
                "alert_type"  : a.alert_type,
                "message"     : a.message,
                "health_index": a.health_index,
                "verdict"     : verdicts.get(a.id),
            }
            for a in rows
        ]
    }


@router.post("/alerts/{alert_id}/verdict")
def set_alert_verdict(alert_id: int, req: VerdictRequest,
                      db: Session = Depends(get_db)):
    """Enregistre le verdict analyste (TP/FP) sur une alerte."""
    if req.verdict not in ("true_positive", "false_positive"):
        raise HTTPException(400, "verdict doit être true_positive ou false_positive")

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alerte introuvable")

    existing = db.query(AlertVerdict).filter(AlertVerdict.alert_id == alert_id).first()
    if existing:
        existing.verdict = req.verdict
        existing.analyst = req.analyst
        existing.comment = req.comment
    else:
        db.add(AlertVerdict(
            alert_id=alert_id, machine_id=alert.machine_id,
            verdict=req.verdict, analyst=req.analyst, comment=req.comment,
        ))
    if alert.acknowledged is not None:
        alert.acknowledged = 1
    db.commit()
    return {"alert_id": alert_id, "verdict": req.verdict, "recorded": True}


@router.get("/analytics/false-alarm-rate")
def false_alarm_rate(machine_id: str = None, db: Session = Depends(get_db)):
    """
    VRAI taux de fausses alarmes depuis les verdicts analystes.
    FP-rate = FP / (TP + FP). Le KPI de confiance exigé par tout acheteur PdM.
    """
    q = db.query(AlertVerdict)
    if machine_id:
        q = q.filter(AlertVerdict.machine_id == machine_id)
    verdicts = q.all()

    tp = sum(1 for v in verdicts if v.verdict == "true_positive")
    fp = sum(1 for v in verdicts if v.verdict == "false_positive")
    total = tp + fp

    return {
        "machine_id"        : machine_id or "all",
        "true_positives"    : tp,
        "false_positives"   : fp,
        "n_reviewed"        : total,
        "false_alarm_rate"  : round(fp / total, 3) if total else None,
        "precision"         : round(tp / total, 3) if total else None,
        "interpretation"    : (f"{fp}/{total} alertes étaient de fausses alarmes "
                               f"({round(fp/total*100)}%)") if total
                              else "Aucune alerte évaluée — marquez des verdicts TP/FP",
    }


@router.get("/analytics/fleet-report")
def fleet_report(db: Session = Depends(get_db)):
    """Synthèse flotte depuis les vraies données (export direction)."""
    machine_ids = [m[0] for m in
                   db.query(MaintenanceEvent.machine_id).distinct().all()]

    total_failures = (
        db.query(MaintenanceEvent)
        .filter(MaintenanceEvent.event_type == "failure")
        .count()
    )
    total_cost = db.query(func.sum(MaintenanceEvent.cost_euros)).scalar() or 0.0

    return {
        "n_machines_with_events": len(machine_ids),
        "machines"              : machine_ids,
        "total_failures"        : total_failures,
        "total_maintenance_cost": round(total_cost, 2),
        "generated_at"          : datetime.utcnow().isoformat(),
        "source"                : "real_data",
    }
