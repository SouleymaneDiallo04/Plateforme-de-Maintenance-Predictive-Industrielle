"""Routes de prédiction."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import numpy as np
from sqlalchemy.orm import Session

from backend.ml.model_registry import registry
from backend.ml.health_tracker import fleet_manager
from backend.ml.health_index import compute_health_index
from backend.ml.model_versioning import version_manager
from backend.api.auth import require_admin
from backend.db.models import get_db

router = APIRouter(tags=["Prédiction"])


class PredictRequest(BaseModel):
    dataset    : str              # 'VBL', 'CWRU', 'MF', 'CMAPSS'
    machine_id : str              # identifiant machine
    features   : List[List[float]] # features extraites (n_windows, n_features)
    model_name : Optional[str] = None   # None = modèle actif
    rul        : Optional[float] = None
    cycle      : Optional[int]  = None


@router.post("/predict")
def predict(req: PredictRequest):
    """
    Prédiction complète pour une machine :
    - Classification du défaut (modèle supervisé)
    - Score d'anomalie (Autoencoder)
    - Health Index calculé
    - Mise à jour de l'historique
    """
    X = np.array(req.features, dtype=np.float32)

    if len(X) == 0:
        raise HTTPException(400, "Features vides")

    # ── Prédiction supervisée ─────────────────────────────────────────────
    pred_result = registry.predict(req.dataset, X, req.model_name)

    # ── Score d'anomalie ──────────────────────────────────────────────────
    anomaly_result = registry.predict_anomaly(req.dataset, X)

    # ── Health Index ──────────────────────────────────────────────────────
    hi_result = compute_health_index(
        anomaly_score = anomaly_result.get('anomaly_score', 50.0),
        rul           = req.rul,
        rul_max       = 125.0
    )

    # ── Mise à jour HealthTracker ─────────────────────────────────────────
    machine = fleet_manager.get_machine(req.machine_id)
    if machine is None:
        machine = fleet_manager.add_machine(req.machine_id, req.dataset)

    update = machine.update(
        health_index  = hi_result['health_index'],
        anomaly_score = anomaly_result.get('anomaly_score', 50.0),
        rul           = req.rul,
        cycle         = req.cycle
    )

    return {
        "machine_id"    : req.machine_id,
        "prediction"    : pred_result,
        "anomaly"       : anomaly_result,
        "health_index"  : hi_result,
        "trend"         : update['trend'],
        "new_alerts"    : update['new_alerts'],
        "model_used"    : registry.get_active_model(req.dataset),
    }


@router.post("/model/select")
def select_model(dataset: str, model_name: str):
    """Sélectionne le modèle actif pour un dataset."""
    success = registry.set_active_model(dataset, model_name)
    if not success:
        available = registry.get_available_models(dataset)
        raise HTTPException(
            400,
            f"Modèle '{model_name}' non disponible. "
            f"Disponibles : {available}"
        )
    return {
        "dataset"     : dataset,
        "active_model": model_name,
        "message"     : f"Modèle {model_name} activé pour {dataset}"
    }


@router.get("/model/active/{dataset}")
def get_active_model(dataset: str):
    """Retourne le modèle actif pour un dataset."""
    return {
        "dataset"    : dataset,
        "active"     : registry.get_active_model(dataset),
        "available"  : registry.get_available_models(dataset),
    }


@router.get("/model/versions/{dataset}/{model_name}")
def list_model_versions(dataset: str, model_name: str,
                        db: Session = Depends(get_db)):
    """Historique des versions d'un modèle."""
    return {
        "dataset"   : dataset,
        "model_name": model_name,
        "versions"  : version_manager.list_versions(db, dataset, model_name),
    }


@router.post("/model/rollback", dependencies=[Depends(require_admin)])
def rollback_model(dataset: str, model_name: str, version: int,
                   db: Session = Depends(get_db)):
    """Revient à une version antérieure du modèle (admin)."""
    result = version_manager.rollback(db, dataset, model_name, version)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result