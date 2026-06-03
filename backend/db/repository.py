"""
Couche d'accès aux données (repository) — PrognoSense.

Encapsule toutes les requêtes SQLAlchemy pour :
  - l'historique des états machines (MachineState)
  - les alertes persistées (Alert)
  - les événements de maintenance réels (MaintenanceEvent)
  - les KPIs industriels calculés depuis les vraies données (MTBF/MTTR/dispo/ROI)

Utilise les modèles déjà définis dans backend.db.models (un seul Base, SQLite
par défaut, Postgres-ready via DATABASE_URL).
"""

from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import MachineState, Alert, MaintenanceEvent


class MachineRepository:
    """Accès persistant aux états/alertes/événements d'une machine."""

    def __init__(self, db: Session):
        self.db = db

    # ── Écriture états ────────────────────────────────────────────────────────

    def save_state(self, machine_id: str, dataset: str,
                   health_index: float, rul_pred: float = None,
                   anomaly_score: float = None, fault_label: str = None,
                   confidence: float = None, cycle: int = None) -> MachineState:
        """Persiste un état machine (snapshot d'un cycle)."""
        state = MachineState(
            machine_id    = machine_id,
            dataset       = dataset,
            health_index  = health_index,
            rul_pred      = rul_pred,
            anomaly_score = anomaly_score,
            fault_label   = fault_label,
            confidence    = confidence,
            cycle         = cycle,
        )
        self.db.add(state)
        self.db.commit()
        return state

    def save_alert(self, machine_id: str, alert_type: str, message: str,
                   health_index: float = None, rul: float = None) -> Alert:
        """Persiste une alerte."""
        alert = Alert(
            machine_id   = machine_id,
            alert_type   = alert_type,
            message      = message,
            health_index = health_index,
            rul          = rul,
        )
        self.db.add(alert)
        self.db.commit()
        return alert

    # ── Lecture historique ────────────────────────────────────────────────────

    def get_history(self, machine_id: str, hours: int = 24,
                    limit: int = 500) -> list:
        since = datetime.utcnow() - timedelta(hours=hours)
        rows = (
            self.db.query(MachineState)
            .filter(MachineState.machine_id == machine_id,
                    MachineState.timestamp >= since)
            .order_by(MachineState.timestamp.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "timestamp"    : r.timestamp.isoformat() if r.timestamp else None,
                "health_index" : r.health_index,
                "rul_pred"     : r.rul_pred,
                "anomaly_score": r.anomaly_score,
                "fault_label"  : r.fault_label,
                "cycle"        : r.cycle,
            }
            for r in rows
        ]

    # ── Lecture agrégée (scalabilité time-series) ──────────────────────────────

    def get_history_rollup(self, machine_id: str, hours: int = 168,
                           bucket: str = "hour") -> list:
        """
        Historique AGRÉGÉ par tranche de temps (downsampling) : au lieu de
        renvoyer des milliers de points bruts, on renvoie des moyennes par heure
        ou par jour. C'est la lecture qui passe à l'échelle (500 machines × 50 kHz).

        SQLite : agrégation via strftime. Sur TimescaleDB : remplacer par
        time_bucket('1 hour', timestamp) (hypertable) — voir docs/SCALING.md.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        fmt = {"minute": "%Y-%m-%d %H:%M",
               "hour":   "%Y-%m-%d %H:00",
               "day":    "%Y-%m-%d"}.get(bucket, "%Y-%m-%d %H:00")
        b = func.strftime(fmt, MachineState.timestamp).label("bucket")

        rows = (
            self.db.query(
                b,
                func.avg(MachineState.health_index),
                func.min(MachineState.health_index),
                func.max(MachineState.health_index),
                func.avg(MachineState.anomaly_score),
                func.count(MachineState.id),
            )
            .filter(MachineState.machine_id == machine_id,
                    MachineState.timestamp >= since)
            .group_by(b).order_by(b).all()
        )
        return [
            {
                "bucket"      : r[0],
                "hi_avg"      : round(r[1], 2) if r[1] is not None else None,
                "hi_min"      : round(r[2], 2) if r[2] is not None else None,
                "hi_max"      : round(r[3], 2) if r[3] is not None else None,
                "anomaly_avg" : round(r[4], 2) if r[4] is not None else None,
                "n_points"    : r[5],
            }
            for r in rows
        ]

    def purge_old_states(self, keep_days: int = 90) -> int:
        """Rétention : supprime les états bruts plus anciens que keep_days."""
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        n = (self.db.query(MachineState)
             .filter(MachineState.timestamp < cutoff)
             .delete(synchronize_session=False))
        self.db.commit()
        return int(n or 0)

    # ── KPIs réels ────────────────────────────────────────────────────────────

    def compute_real_kpis(self, machine_id: str, days: int = 30) -> dict:
        """
        MTBF / MTTR / MTTF / disponibilité calculés depuis les vrais
        événements de maintenance enregistrés (pas de valeurs simulées).
        """
        since = datetime.utcnow() - timedelta(days=days)

        failures = (
            self.db.query(MaintenanceEvent)
            .filter(MaintenanceEvent.machine_id == machine_id,
                    MaintenanceEvent.event_type == "failure",
                    MaintenanceEvent.started_at >= since)
            .all()
        )
        repairs = (
            self.db.query(MaintenanceEvent)
            .filter(MaintenanceEvent.machine_id == machine_id,
                    MaintenanceEvent.event_type.in_(["corrective", "planned"]),
                    MaintenanceEvent.started_at >= since)
            .all()
        )

        total_hours  = days * 24
        n_failures   = len(failures)
        repair_times = [r.duration_hours for r in repairs
                        if r.duration_hours is not None]

        # Si aucune panne, MTBF non défini → on renvoie la fenêtre complète
        mtbf = total_hours / n_failures if n_failures > 0 else None
        mttr = float(np.mean(repair_times)) if repair_times else None
        avail = (mtbf / (mtbf + mttr) * 100) if (mtbf and mttr) else None

        total_cost = sum(
            e.cost_euros for e in (failures + repairs)
            if e.cost_euros is not None
        )

        return {
            "machine_id"    : machine_id,
            "period_days"   : days,
            "MTBF"          : round(mtbf, 2) if mtbf else None,
            "MTTR"          : round(mttr, 2) if mttr else None,
            "availability"  : round(avail, 2) if avail else None,
            "n_failures"    : n_failures,
            "n_repairs"     : len(repairs),
            "total_cost_eur": round(total_cost, 2),
            "source"        : "real_data",
        }
