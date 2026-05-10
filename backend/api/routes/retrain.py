"""Routes de réentraînement."""

from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import List
import numpy as np
import asyncio

from backend.ml.model_registry import registry

router = APIRouter(tags=["Réentraînement"])


class RetrainRequest(BaseModel):
    dataset   : str
    new_label : str
    features  : List[List[float]]


@router.post("/retrain/start")
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


@router.get("/retrain/status")
def get_retrain_status():
    """Polling de l'avancement du réentraînement."""
    return registry.get_retrain_status()