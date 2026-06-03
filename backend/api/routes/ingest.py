"""
Couche d'ingestion temps réel — connecteur de données VENDOR-AGNOSTIC.

N'importe quelle source (passerelle edge, pont OPC-UA, client MQTT, capteur
sans fil, script de test) pousse une forme d'onde d'accélération réelle ici.
Le signal traverse le pipeline complet :

  features standard → ISO 10816 → anomalie vs baseline machine →
  diagnostic spectral → Health Index → persistance + flotte.

C'est ce qui transforme PrognoSense d'un « rejoueur de datasets » en une
plateforme connectable à de vraies machines.
"""

from datetime import datetime
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ml.realtime import compute_features, baseline_store
from backend.ml.health_tracker import fleet_manager
from backend.api.routes.spectral import (
    diagnose_signal, DiagnoseRequest, BearingParams
)

router = APIRouter(tags=["Ingestion temps réel"])

# Health Index ancré sur la zone ISO (langage fiabiliste)
ISO_ZONE_HI = {"A": 95.0, "B": 80.0, "C": 45.0, "D": 15.0}


class IngestSignal(BaseModel):
    machine_id     : str
    signal         : List[float]               # forme d'onde d'accélération brute
    fs             : float = 12800.0
    input_unit     : str   = "g"               # 'g' ou 'm/s2'
    rpm            : Optional[float] = None
    machine_class  : str   = "II"              # classe ISO 10816 (I–IV)
    bearing_params : Optional[BearingParams] = None
    learn_baseline : bool  = False             # True = alimenter le baseline


def _ingest_health(iso_zone: str, anomaly_score: Optional[float]) -> float:
    base = ISO_ZONE_HI.get(iso_zone, 70.0)
    if anomaly_score is not None:
        return round(base * 0.6 + (100.0 - anomaly_score) * 0.4, 2)
    return base


@router.post("/ingest/signal")
def ingest_signal(req: IngestSignal):
    """Ingère un signal réel et retourne l'évaluation complète."""
    if len(req.signal) < 64:
        raise HTTPException(400, "Signal trop court (min 64 points)")

    x = np.asarray(req.signal, dtype=np.float64)

    # 1) Features standard (indépendantes de tout modèle)
    feats = compute_features(x, req.fs, req.rpm, req.input_unit)

    # 2) Baseline propre à la machine
    baseline = baseline_store.get(req.machine_id)

    if req.learn_baseline:
        baseline.collect(feats)
        return {
            "machine_id"      : req.machine_id,
            "mode"            : "learning_baseline",
            "samples_collected": len(baseline._buffer),
            "message"         : "Échantillon ajouté au baseline (appeler "
                                "/ingest/baseline/finalize pour entraîner).",
            "iso_velocity_mm_s": round(feats["iso_velocity_mm_s"], 3),
        }

    anomaly = baseline.score(feats)            # {available, anomaly_score, ...}
    anomaly_score = anomaly.get("anomaly_score") if anomaly.get("available") else None

    # 3) Diagnostic spectral complet (réutilise le pipeline existant + ISO)
    diag = diagnose_signal(DiagnoseRequest(
        signal         = req.signal,
        sampling_rate  = req.fs,
        health_index   = 80.0,
        bearing_params = req.bearing_params,
        input_unit     = req.input_unit,
        machine_class  = req.machine_class,
    ))
    iso = diag["iso_severity"]

    # 4) Health Index ancré ISO + anomalie baseline
    hi = _ingest_health(iso["zone"], anomaly_score)

    # 5) Persistance + flotte
    machine = fleet_manager.get_machine(req.machine_id) \
        or fleet_manager.add_machine(req.machine_id, "INGEST")
    machine.update_signal(x, req.fs)
    update = machine.update(
        health_index  = hi,
        anomaly_score = anomaly_score if anomaly_score is not None else 0.0,
        rul           = None,
    )

    try:
        from backend.db.models import SessionLocal
        from backend.db.repository import MachineRepository
        _db = SessionLocal()
        try:
            repo = MachineRepository(_db)
            repo.save_state(
                machine_id    = req.machine_id,
                dataset       = "INGEST",
                health_index  = hi,
                anomaly_score = anomaly_score,
                fault_label   = diag["diagnosis"]["fault"],
                confidence    = diag["diagnosis"].get("confidence"),
            )
            for alert in update.get("new_alerts", []):
                repo.save_alert(
                    machine_id   = req.machine_id,
                    alert_type   = alert.get("type", "unknown"),
                    message      = alert.get("message", ""),
                    health_index = hi,
                )
        finally:
            _db.close()
    except Exception:
        pass

    # 6) Ordre de travail automatique si critique (boucle GMAO)
    work_order = None
    try:
        from backend.api.routes.workorders import maybe_auto_workorder
        work_order = maybe_auto_workorder(
            machine_id = req.machine_id,
            health_index = hi,
            iso_zone   = iso["zone"],
            fault      = diag["diagnosis"]["fault"],
            recommendation = diag.get("recommendation", {}),
        )
    except Exception:
        pass

    return {
        "machine_id"   : req.machine_id,
        "timestamp"    : datetime.now().isoformat(),
        "health_index" : hi,
        "iso_severity" : iso,
        "anomaly"      : anomaly,
        "diagnosis"    : diag["diagnosis"],
        "recommendation": diag.get("recommendation"),
        "annotations"  : diag.get("annotations", []),
        "features"     : {k: round(v, 5) for k, v in feats.items()},
        "trend"        : update.get("trend"),
        "new_alerts"   : update.get("new_alerts", []),
        "work_order"   : work_order,
        "baseline_used": anomaly.get("available", False),
    }


@router.post("/ingest/baseline/finalize")
def finalize_baseline(machine_id: str):
    """Entraîne le baseline d'une machine à partir des signaux collectés."""
    baseline = baseline_store.get(machine_id)
    result = baseline.finalize()
    if result.get("fitted"):
        baseline.save()
    return {"machine_id": machine_id, **result}


@router.post("/ingest/baseline/reset")
def reset_baseline(machine_id: str):
    """Réinitialise le baseline d'une machine."""
    baseline_store.reset(machine_id)
    return {"machine_id": machine_id, "message": "Baseline réinitialisé"}


@router.get("/ingest/baseline/status")
def baseline_status():
    """État des baselines appris par machine."""
    return {"baselines": baseline_store.status()}
