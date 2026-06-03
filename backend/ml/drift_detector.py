"""
DriftDetector — détection de concept drift par test de Kolmogorov-Smirnov.

Principe :
    Compare la distribution des données de production récentes à la
    distribution d'entraînement (référence). Un drift est détecté quand
    plus de 30 % des features ont une p-value KS < 0.05.

Utilisation :
    detector = DriftDetector('CWRU', window_size=500)
    detector.set_reference(X_train)

    # Dans la boucle de prédiction :
    report = detector.add_production_sample(X)
    if report['drift_detected']:
        print("Réentraînement recommandé !")
"""

import numpy as np
from scipy.stats import ks_2samp
from datetime import datetime
from collections import deque


class DriftDetector:

    def __init__(self, dataset: str, window_size: int = 500):
        self.dataset     = dataset
        self.window_size = window_size
        self.ref_data    = None          # features d'entraînement (référence)
        self._prod_buffer: deque = deque(maxlen=window_size)
        self.drift_log: list     = []    # historique des drifts détectés

    # ── Référence ─────────────────────────────────────────────────────────────

    def set_reference(self, X_train: np.ndarray):
        """Enregistre les données d'entraînement comme distribution de référence."""
        self.ref_data = X_train.copy()

    # ── Monitoring ───────────────────────────────────────────────────────────

    def add_production_sample(self, X: np.ndarray) -> dict:
        """
        Ajoute un échantillon de production et teste le drift.
        Retourne un rapport minimal si pas encore assez de données,
        ou un rapport complet avec drift_detected=True/False.
        """
        self._prod_buffer.append(X.flatten())

        n = len(self._prod_buffer)
        if n < min(50, self.window_size // 10):
            return {"drift_detected": False, "n_samples": n, "dataset": self.dataset}

        if self.ref_data is None:
            return {"drift_detected": False, "n_samples": n, "dataset": self.dataset,
                    "note": "Référence non définie"}

        X_prod   = np.array(self._prod_buffer)
        n_feat   = min(10, self.ref_data.shape[1], X_prod.shape[1])
        p_values = []

        for i in range(n_feat):
            try:
                _, p = ks_2samp(self.ref_data[:, i], X_prod[:, i])
                p_values.append(p)
            except Exception:
                p_values.append(1.0)

        if not p_values:
            return {"drift_detected": False, "n_samples": n}

        min_p            = min(p_values)
        drifted_features = [i for i, p in enumerate(p_values) if p < 0.05]
        drift_detected   = len(drifted_features) > n_feat * 0.3

        if drift_detected:
            report = {
                "drift_detected"   : True,
                "dataset"          : self.dataset,
                "min_p_value"      : round(min_p, 4),
                "drifted_features" : drifted_features,
                "n_drifted"        : len(drifted_features),
                "n_features_tested": n_feat,
                "severity"         : "critique" if min_p < 0.001 else "modéré",
                "recommendation"   : "Réentraînement recommandé",
                "timestamp"        : datetime.now().isoformat(),
            }
            self.drift_log.append(report)
            return report

        return {
            "drift_detected": False,
            "dataset"       : self.dataset,
            "min_p_value"   : round(min_p, 4),
            "n_samples"     : n,
        }

    # ── Score global ──────────────────────────────────────────────────────────

    def get_drift_score(self) -> float:
        """
        Score de drift 0–100 % (0 = stable, 100 = drift maximal).
        Calculé sur la fenêtre de production courante.
        """
        if self.ref_data is None or len(self._prod_buffer) < 10:
            return 0.0

        X_prod = np.array(self._prod_buffer)
        n_feat = min(10, self.ref_data.shape[1], X_prod.shape[1])
        p_vals = []

        for i in range(n_feat):
            try:
                _, p = ks_2samp(self.ref_data[:, i], X_prod[:, i])
                p_vals.append(p)
            except Exception:
                p_vals.append(1.0)

        if not p_vals:
            return 0.0

        score = sum(1 for p in p_vals if p < 0.05) / n_feat * 100
        return round(score, 1)

    # ── Résumé ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "dataset"       : self.dataset,
            "score"         : self.get_drift_score(),
            "n_drifts"      : len(self.drift_log),
            "n_samples_prod": len(self._prod_buffer),
            "has_reference" : self.ref_data is not None,
            "last_drift"    : self.drift_log[-1] if self.drift_log else None,
        }

    def reset(self):
        """Remet le buffer de production à zéro (après réentraînement)."""
        self._prod_buffer.clear()
        self.drift_log.clear()
