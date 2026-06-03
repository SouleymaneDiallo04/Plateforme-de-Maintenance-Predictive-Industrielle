"""
SignalReplayer — génère des signaux vibratoires calibrés sur les vraies
features extraites des datasets, au lieu d'une sinusoïde générique.

Apport :
  - amplitude calibrée sur le RMS réel de la fenêtre,
  - harmoniques proportionnelles à la dégradation (Health Index),
  - impulsions injectées quand le Kurtosis réel est élevé
    (signature physique d'un défaut de roulement).

Utilisé par la simulation WebSocket pour un rendu plus réaliste, et
exposé via un endpoint de replay des signaux d'un dataset.
"""

import pickle
from pathlib import Path

import numpy as np

TARGET_FS = 12_800
N_POINTS  = 2_048


class SignalReplayer:

    def __init__(self):
        self._datasets = {}   # {dataset: {"X","y","meta"}}

    # ── Chargement (pour le replay par index) ─────────────────────────────────

    def load_dataset(self, dataset: str, base_path: str = "data/processed") -> bool:
        base = Path(base_path)
        key  = dataset.lower()
        try:
            X = np.load(base / f"X_{key}.npy")
            with open(base / f"y_{key}.pkl", "rb") as f:
                y = pickle.load(f)
            with open(base / f"meta_{key}.pkl", "rb") as f:
                meta = pickle.load(f)
            self._datasets[dataset.upper()] = {"X": X, "y": y, "meta": meta}
            print(f"  SignalReplayer : {dataset.upper()} chargé ({len(X)} fenêtres)")
            return True
        except Exception as e:
            print(f"  SignalReplayer : {dataset} indisponible — {e}")
            return False

    # ── Cœur : génération calibrée sur features réelles ───────────────────────

    def signal_from_features(self, features, health_index: float,
                             shaft_freq: float = 20.6,
                             n_points: int = N_POINTS,
                             fs: float = TARGET_FS) -> np.ndarray:
        """
        Génère un signal calibré sur les features réelles.
        `features[0]` = RMS, `features[1]` = Kurtosis (convention d'extraction).
        """
        t   = np.linspace(0, n_points / fs, n_points)
        rms = max(0.05, abs(float(features[0]))) if len(features) > 0 else 1.0
        amp = rms * np.sqrt(2)
        kurt = float(features[1]) if len(features) > 1 else 3.0

        degradation = max(0.0, 1.0 - health_index / 100.0)

        # Fondamentale + harmoniques proportionnelles à la dégradation
        sig  = amp * np.sin(2 * np.pi * shaft_freq * t)
        sig += degradation * amp * 0.4 * np.sin(2 * np.pi * shaft_freq * 2 * t)
        sig += degradation * amp * 0.2 * np.sin(2 * np.pi * shaft_freq * 3 * t)
        sig += degradation * amp * 0.1 * np.sin(2 * np.pi * shaft_freq * 4 * t)

        # Bruit gaussien de fond
        noise_lvl = 0.05 + degradation * 0.25
        noise = np.random.normal(0, noise_lvl * amp, n_points)

        # Impulsions si Kurtosis élevé (signature défaut roulement)
        if kurt > 4:
            n_impulses = int(min(40, max(1, kurt * 2)))
            idx = np.random.choice(n_points, n_impulses, replace=False)
            noise[idx] += np.random.exponential(rms * min(kurt, 20) * 0.3, n_impulses)

        return (sig + noise).astype(np.float32)

    # ── Replay par index (endpoint) ───────────────────────────────────────────

    def replay_index(self, dataset: str, idx: int,
                     shaft_freq: float = 20.6) -> dict:
        ds = self._datasets.get(dataset.upper())
        if ds is None or idx < 0 or idx >= len(ds["X"]):
            return {"error": f"Index {idx} invalide pour {dataset}"}

        features = ds["X"][idx]
        meta     = ds["meta"][idx] if idx < len(ds["meta"]) else {}
        label    = ds["y"][idx] if idx < len(ds["y"]) else "unknown"
        rul      = meta.get("rul")
        hi       = max(0.0, 1.0 - (rul / 125.0)) * 100 if rul is not None else 60.0

        sig = self.signal_from_features(features, hi, shaft_freq)
        return {
            "dataset"      : dataset.upper(),
            "idx"          : idx,
            "label"        : label,
            "rul"          : rul,
            "sampling_rate": TARGET_FS,
            "length"       : len(sig),
            "signal"       : sig.tolist(),
        }

    @property
    def datasets_loaded(self) -> list:
        return list(self._datasets.keys())


# Instance globale
replayer = SignalReplayer()
