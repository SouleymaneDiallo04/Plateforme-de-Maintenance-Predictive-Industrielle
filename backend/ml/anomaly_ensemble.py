"""
AnomalyEnsemble — détection d'anomalie par consensus de 3 algorithmes.

Complète l'Autoencoder : là où l'AE donne un score continu, l'ensemble
fournit une décision robuste par vote majoritaire de méthodes aux biais
différents (moins de faux positifs).

  - Isolation Forest : isole les points rares, robuste en haute dimension
  - Local Outlier Factor : densité locale (anomalies de voisinage)
  - Elliptic Envelope : hypothèse gaussienne (déviation de covariance)

Chaque détecteur est entraîné uniquement sur des données saines. Un
détecteur qui échoue à s'ajuster (ex. covariance singulière) est ignoré
sans casser l'ensemble.
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.covariance import EllipticEnvelope
from sklearn.preprocessing import StandardScaler


class AnomalyEnsemble:

    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.scaler = StandardScaler()
        self.detectors = {
            "isolation_forest": IsolationForest(
                contamination=contamination, n_estimators=100,
                random_state=42, n_jobs=-1,
            ),
            "lof": LocalOutlierFactor(
                n_neighbors=20, contamination=contamination,
                novelty=True, n_jobs=-1,
            ),
            "elliptic": EllipticEnvelope(
                contamination=contamination, support_fraction=0.9,
            ),
        }
        self._ok  = []       # détecteurs effectivement entraînés
        self._ref = {}       # {name: (lo, hi)} plage decision_function sur données saines
        self.fitted = False

    def fit(self, X_normal: np.ndarray) -> dict:
        X_scaled = self.scaler.fit_transform(X_normal)
        self._ok, self._ref = [], {}
        for name, det in self.detectors.items():
            try:
                det.fit(X_scaled)
                self._ok.append(name)
                # Référence de normalité : plage robuste de decision_function
                # sur les données saines → scores stables même sur 1 échantillon.
                if hasattr(det, "decision_function"):
                    s = det.decision_function(X_scaled)
                    self._ref[name] = (float(np.percentile(s, 1)),
                                       float(np.percentile(s, 99)))
            except Exception:
                pass
        self.fitted = len(self._ok) > 0
        return {"fitted_detectors": self._ok, "n_samples": int(len(X_normal))}

    def predict(self, X: np.ndarray) -> dict:
        if not self.fitted:
            return {"error": "Ensemble non entraîné"}

        X_scaled = self.scaler.transform(X)
        votes, scores = [], {}

        for name in self._ok:
            det = self.detectors[name]
            try:
                pred = det.predict(X_scaled)            # -1 = anomalie, +1 = normal
                is_anomaly = (pred == -1).astype(float)
                votes.append(is_anomaly)

                # Score normalisé contre la référence de normalité (pas le lot),
                # ce qui le rend exploitable même sur un seul échantillon.
                if name in self._ref:
                    s = det.decision_function(X_scaled)  # + = normal, - = anomalie
                    lo, hi = self._ref[name]
                    sc = np.clip((hi - s) / (hi - lo + 1e-10) * 50.0, 0, 100)
                    scores[name] = float(sc.mean())
                else:
                    scores[name] = float(is_anomaly.mean() * 100)
            except Exception:
                pass

        if votes:
            vote_matrix = np.stack(votes, axis=1)
            needed = max(1, (len(votes) // 2) + 1)       # majorité absolue
            majority = (vote_matrix.sum(axis=1) >= needed).astype(float)
            consensus = float(majority.mean() * 100)
        else:
            consensus = 0.0

        final_score = float(np.mean(list(scores.values()))) if scores else 0.0

        return {
            "anomaly_score"    : round(final_score, 2),
            "consensus_score"  : round(consensus, 2),
            "is_anomaly"       : consensus > 50,
            "votes"            : {
                name: bool(v.mean() > 0.5)
                for name, v in zip(self._ok, votes)
            },
            "individual_scores": {k: round(v, 2) for k, v in scores.items()},
            "n_detectors"      : len(self._ok),
            "method"           : "ensemble_vote",
            "confidence"       : round(abs(consensus - 50) / 50 * 100, 1),
        }
