"""
Route ensemble d'anomalie — consensus IsolationForest + LOF + EllipticEnvelope.

L'ensemble est entraîné paresseusement (lazy) à la première requête, sur les
échantillons sains du dataset (sous-échantillonnés), puis mis en cache.
"""

import pickle
from pathlib import Path
from typing import List

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["Anomalie Ensemble"])

# Datasets de classification supportés (CMAPSS = régression, exclu)
_DS_FILES = {"VBL": "vbl", "CWRU": "cwru", "MF": "mf"}
_MAX_NORMAL = 2000


class EnsembleRequest(BaseModel):
    features: List[List[float]]


def _load_normal_samples(dataset: str):
    """Charge les échantillons sains d'un dataset (sous-échantillonnés)."""
    fname = _DS_FILES.get(dataset)
    if not fname:
        return None

    base = Path("data/processed")
    try:
        X = np.load(base / f"X_{fname}.npy")
        with open(base / f"y_{fname}.pkl", "rb") as f:
            y = pickle.load(f)
    except Exception:
        return None

    y_low = np.array([str(v).lower() for v in y])
    mask  = np.array(["sain" in v or "normal" in v for v in y_low])
    X_norm = X[mask] if mask.any() else X

    if len(X_norm) > _MAX_NORMAL:
        rng = np.random.default_rng(42)
        X_norm = X_norm[rng.choice(len(X_norm), _MAX_NORMAL, replace=False)]
    return X_norm


def _get_ensemble(dataset: str):
    # Cache unique partagé avec le scoring temps réel (registry)
    from backend.ml.model_registry import registry
    return registry.get_anomaly_ensemble(dataset)


@router.post("/anomaly/ensemble/{dataset}")
def anomaly_ensemble(dataset: str, req: EnsembleRequest):
    """Score d'anomalie par consensus de 3 algorithmes."""
    dataset = dataset.upper()
    ens = _get_ensemble(dataset)
    if ens is None:
        raise HTTPException(
            404,
            f"Ensemble indisponible pour {dataset} "
            f"(datasets supportés : {list(_DS_FILES)})"
        )

    X = np.array(req.features, dtype=np.float32)
    if X.ndim == 1:
        X = X.reshape(1, -1)
    return {"dataset": dataset, **ens.predict(X)}


@router.get("/anomaly/ensemble/demo/{dataset}")
def ensemble_demo(dataset: str, n: int = 60):
    """
    Démo : exécute l'ensemble sur un lot réel du dataset dans lequel on
    injecte des anomalies (fort bruit) sur ~1/3 des échantillons, pour
    rendre le vote des 3 détecteurs visible.
    """
    dataset = dataset.upper()
    ens = _get_ensemble(dataset)
    if ens is None:
        raise HTTPException(404, f"Ensemble indisponible pour {dataset}")

    X = _load_normal_samples(dataset)
    if X is None or len(X) < 20:
        raise HTTPException(404, f"Échantillons sains insuffisants pour {dataset}")

    rng = np.random.default_rng()
    k   = int(min(max(n, 20), len(X)))
    idx = rng.choice(len(X), k, replace=False)
    batch = X[idx].astype(np.float32).copy()

    # Injecter des anomalies (fort bruit) sur ~1/3 du lot
    n_anom = k // 3
    if n_anom > 0:
        anom_idx = rng.choice(k, n_anom, replace=False)
        scale = 6.0 * (float(np.abs(batch).std()) + 1e-6)
        batch[anom_idx] += rng.normal(0, scale, batch[anom_idx].shape).astype(np.float32)

    result = ens.predict(batch)
    result["batch_size"]           = k
    result["n_injected_anomalies"] = int(n_anom)
    return {"dataset": dataset, **result}


@router.get("/anomaly/ensemble/status")
def ensemble_status():
    """État des ensembles entraînés en cache (partagé avec le temps réel)."""
    from backend.ml.model_registry import registry
    return {
        "trained": {
            ds: {"detectors": ens._ok, "fitted": ens.fitted}
            for ds, ens in registry._anomaly_ensembles.items()
            if ens is not None
        },
        "supported_datasets": list(_DS_FILES),
    }
