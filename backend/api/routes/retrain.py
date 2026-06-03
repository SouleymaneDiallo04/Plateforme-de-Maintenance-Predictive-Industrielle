"""Routes de réentraînement."""

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import List
import numpy as np
import asyncio

from backend.ml.model_registry import registry
from backend.api.auth import require_admin

router = APIRouter(tags=["Réentraînement"])


class RetrainRequest(BaseModel):
    dataset   : str
    new_label : str
    features  : List[List[float]]


class RetrainDemoRequest(BaseModel):
    dataset   : str
    new_label : str
    n_samples : int = 40


@router.post("/retrain/start", dependencies=[Depends(require_admin)])
async def start_retrain(req: RetrainRequest,
                         background_tasks: BackgroundTasks):
    """Lance le réentraînement en arrière-plan."""
    if registry._retrain_status['running']:
        return {"error": "Réentraînement déjà en cours"}

    X_new = np.array(req.features, dtype=np.float32)
    y_new = [req.new_label] * len(X_new)

    background_tasks.add_task(
        asyncio.run,
        registry.retrain_async(req.dataset, X_new, y_new, req.new_label)
    )

    return {
        "message" : f"Réentraînement lancé pour {req.dataset}",
        "label"   : req.new_label,
        "n_samples": len(X_new)
    }


@router.post("/retrain/demo", dependencies=[Depends(require_admin)])
async def start_retrain_demo(req: RetrainDemoRequest,
                             background_tasks: BackgroundTasks):
    """
    Réentraînement démo pilotable depuis l'UI : échantillonne des features
    réelles du dataset (légèrement bruitées) comme exemples du nouveau défaut,
    puis lance le réentraînement (qui les combine avec les données existantes).
    """
    if registry._retrain_status['running']:
        return {"error": "Réentraînement déjà en cours"}

    from pathlib import Path
    ds_key = {"VBL": "vbl", "CWRU": "cwru", "MF": "mf"}.get(req.dataset)
    if not ds_key:
        raise HTTPException(400,
            f"Dataset '{req.dataset}' non supporté pour la démo (VBL, CWRU, MF)")
    if not req.new_label.strip():
        raise HTTPException(400, "Label du nouveau défaut requis")

    try:
        X = np.load(Path("data/processed") / f"X_{ds_key}.npy")
    except Exception:
        raise HTTPException(404, f"Données {req.dataset} indisponibles")

    n   = max(10, min(req.n_samples, 200))
    rng = np.random.default_rng()
    idx = rng.choice(len(X), min(n, len(X)), replace=False)
    X_sample = X[idx].astype(np.float32)

    # Légère perturbation → simule un nouveau régime de défaut
    scale = 0.05 * (float(np.abs(X_sample).mean()) + 1e-6)
    X_new = (X_sample + rng.normal(0, scale, X_sample.shape)).astype(np.float32)
    y_new = [req.new_label.strip()] * len(X_new)

    background_tasks.add_task(
        asyncio.run,
        registry.retrain_async(req.dataset, X_new, y_new, req.new_label.strip())
    )
    return {
        "message"  : f"Réentraînement démo lancé pour {req.dataset}",
        "label"    : req.new_label.strip(),
        "n_samples": len(X_new),
    }


@router.get("/retrain/status")
def get_retrain_status():
    """Polling de l'avancement du réentraînement."""
    return registry.get_retrain_status()