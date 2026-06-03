"""
Calibration des probabilités — PrognoSense.

Sans calibration, un Random Forest qui prédit "confiance 94 %" peut
n'être correct que dans 75 % des cas. La calibration isotonique corrige
ce biais pour que la confiance affichée soit fiable industriellement.

Usage :
    calibrated = calibrate_classifier(model, X_cal, y_cal)
    diagram    = reliability_diagram_data(calibrated, X_test, y_test)
"""

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from typing import Any


def calibrate_classifier(
    model,
    X_cal: np.ndarray,
    y_cal: list,
    method: str = "isotonic",
) -> Any:
    """
    Calibre un classifieur pré-entraîné.

    Args:
        model   : Estimateur sklearn déjà entraîné (prefit=True).
        X_cal   : Features de calibration (jeu séparé, jamais vu à l'entraînement).
        y_cal   : Labels de calibration.
        method  : 'isotonic' (recommandé pour RF/XGBoost) ou 'sigmoid' (Platt).

    Returns:
        Classifieur calibré avec la même interface que le modèle d'entrée.
    """
    calibrated = CalibratedClassifierCV(
        estimator=model,
        method=method,
        cv="prefit",
    )
    calibrated.fit(X_cal, y_cal)
    return calibrated


def reliability_diagram_data(
    model,
    X_test: np.ndarray,
    y_test: list,
    n_bins: int = 10,
) -> dict:
    """
    Calcule les données pour le diagramme de fiabilité (reliability diagram).

    Un modèle bien calibré montre une droite diagonale :
    confidence = accuracy dans chaque bin.

    Returns:
        {
            "bins": [{"confidence_mean": 0.75, "accuracy": 0.72, "n_samples": 42, "calibrated": True}],
            "well_calibrated": True,
            "ece": 0.03,   # Expected Calibration Error
        }
    """
    try:
        proba  = model.predict_proba(X_test)
        max_p  = proba.max(axis=1)
        y_pred = model.predict(X_test)
        y_arr  = np.array(y_test)

        bins    = np.linspace(0, 1, n_bins + 1)
        results = []
        ece_num = 0.0
        n_total = len(y_test)

        for i in range(n_bins):
            mask = (max_p >= bins[i]) & (max_p < bins[i + 1])
            if mask.sum() == 0:
                continue
            conf    = float(max_p[mask].mean())
            acc     = float((np.array(y_pred)[mask] == y_arr[mask]).mean())
            n       = int(mask.sum())
            ece_num += n * abs(conf - acc)
            results.append({
                "confidence_mean": round(conf, 3),
                "accuracy"       : round(acc, 3),
                "n_samples"      : n,
                "calibrated"     : abs(conf - acc) < 0.1,
            })

        ece             = ece_num / n_total if n_total > 0 else 0.0
        well_calibrated = ece < 0.05

        return {
            "bins"           : results,
            "well_calibrated": well_calibrated,
            "ece"            : round(ece, 4),
        }

    except Exception as e:
        return {"bins": [], "well_calibrated": False, "error": str(e)}


def compute_confidence_stats(model, X: np.ndarray) -> dict:
    """Statistiques rapides sur la confiance des prédictions."""
    try:
        proba = model.predict_proba(X)
        max_p = proba.max(axis=1)
        return {
            "mean_confidence": round(float(max_p.mean()), 3),
            "min_confidence" : round(float(max_p.min()), 3),
            "max_confidence" : round(float(max_p.max()), 3),
            "std_confidence" : round(float(max_p.std()), 3),
            "pct_high_conf"  : round(float((max_p > 0.9).mean() * 100), 1),
            "pct_low_conf"   : round(float((max_p < 0.6).mean() * 100), 1),
        }
    except Exception:
        return {}
