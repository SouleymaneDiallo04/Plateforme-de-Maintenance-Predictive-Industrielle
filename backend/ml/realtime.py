"""
Couche temps réel — ingestion de signaux RÉELS (vendor-agnostic).

Deux briques qui répondent aux critiques industrielles majeures :

  1. compute_features() : extrait un jeu d'indicateurs **indépendant du
     modèle** depuis une forme d'onde d'accélération brute (temporel +
     fréquentiel + ISO vitesse). Marche pour n'importe quelle machine,
     sans modèle pré-entraîné.

  2. MachineBaseline : apprend l'état SAIN propre à CHAQUE machine du
     client (non supervisé, sans label, sans run-to-failure). L'anomalie
     est mesurée par rapport à ce baseline — pas par rapport à un dataset
     public. C'est le modèle d'Augury / AspenTech Mtell.

Les baselines sont persistés sur disque → survivent aux redémarrages.
"""

import pickle
from pathlib import Path

import numpy as np
from scipy.stats import kurtosis, skew
from scipy.fft import rfft, rfftfreq

from backend.ml.iso_severity import acceleration_to_velocity_rms

BASELINE_DIR = Path("models/baselines")
BASELINE_DIR.mkdir(parents=True, exist_ok=True)

# Ordre canonique des features (vecteur stable)
FEATURE_NAMES = [
    "rms", "peak", "peak_to_peak", "crest_factor", "kurtosis", "skewness",
    "std", "spectral_entropy", "dom_freq",
    "band_0_1k", "band_1_3k", "band_3_5k", "band_5_nyq",
    "iso_velocity_mm_s", "harm_1x", "harm_2x", "harm_3x",
]


def compute_features(signal, fs: float, rpm: float = None,
                     input_unit: str = "g") -> dict:
    """Indicateurs standard depuis une forme d'onde d'accélération brute."""
    x = np.asarray(signal, dtype=np.float64)
    x = x - np.mean(x)
    N = len(x)

    rms   = float(np.sqrt(np.mean(x ** 2)))
    peak  = float(np.max(np.abs(x)))
    p2p   = float(np.max(x) - np.min(x))
    crest = float(peak / (rms + 1e-12))
    kurt  = float(kurtosis(x, fisher=True))
    skw   = float(skew(x))
    std   = float(np.std(x))

    spec  = np.abs(rfft(x)) / N
    freqs = rfftfreq(N, d=1.0 / fs)
    ps    = spec ** 2
    ps_n  = ps / (ps.sum() + 1e-12)
    spec_ent = float(-np.sum(ps_n * np.log(ps_n + 1e-12)))
    dom_freq = float(freqs[int(np.argmax(spec))])

    nyq   = fs / 2.0
    edges = [0, 1000, 3000, 5000, nyq]
    bands = []
    for i in range(len(edges) - 1):
        m = (freqs >= edges[i]) & (freqs < edges[i + 1])
        bands.append(float(np.sum(ps[m])))

    iso_v = acceleration_to_velocity_rms(x, fs, input_unit)

    # Harmoniques de rotation si RPM fourni
    harm = [0.0, 0.0, 0.0]
    if rpm:
        shaft = rpm / 60.0
        for k in range(1, 4):
            fc = shaft * k
            m  = (freqs >= fc * 0.9) & (freqs <= fc * 1.1)
            harm[k - 1] = float(np.sum(ps[m]))

    feats = {
        "rms": rms, "peak": peak, "peak_to_peak": p2p, "crest_factor": crest,
        "kurtosis": kurt, "skewness": skw, "std": std,
        "spectral_entropy": spec_ent, "dom_freq": dom_freq,
        "band_0_1k": bands[0], "band_1_3k": bands[1],
        "band_3_5k": bands[2], "band_5_nyq": bands[3],
        "iso_velocity_mm_s": iso_v,
        "harm_1x": harm[0], "harm_2x": harm[1], "harm_3x": harm[2],
    }
    return feats


def features_vector(feats: dict) -> np.ndarray:
    return np.array([feats.get(n, 0.0) for n in FEATURE_NAMES], dtype=np.float64)


class MachineBaseline:
    """État sain appris pour UNE machine (z-score multivarié robuste)."""

    def __init__(self, machine_id: str):
        self.machine_id = machine_id
        self._buffer = []          # vecteurs de features (mode apprentissage)
        self.mean    = None
        self.std     = None
        self.iso_baseline = None   # vitesse RMS saine (mm/s)
        self.n_samples = 0
        self.fitted   = False

    def collect(self, feats: dict):
        self._buffer.append(features_vector(feats))

    def finalize(self, min_samples: int = 10) -> dict:
        if len(self._buffer) < min_samples:
            return {"fitted": False,
                    "reason": f"Besoin de ≥{min_samples} échantillons "
                              f"(actuel : {len(self._buffer)})"}
        X = np.vstack(self._buffer)
        self.mean = X.mean(axis=0)
        self.std  = X.std(axis=0)
        self.std  = np.where(self.std < 1e-9, 1e-9, self.std)
        self.n_samples = len(self._buffer)
        # vitesse ISO saine = moyenne du baseline
        iso_idx = FEATURE_NAMES.index("iso_velocity_mm_s")
        self.iso_baseline = float(self.mean[iso_idx])
        self.fitted = True
        self._buffer = []
        return {"fitted": True, "n_samples": self.n_samples,
                "iso_baseline_mm_s": round(self.iso_baseline, 3)}

    def score(self, feats: dict) -> dict:
        """Anomalie 0-100 % relative à l'état sain de CETTE machine."""
        if not self.fitted:
            return {"available": False}
        v = features_vector(feats)
        z = np.abs((v - self.mean) / self.std)
        z = np.clip(z, 0.0, 50.0)                       # borne les écarts-types ~0
        frac_3sigma = float(np.mean(z > 3.0))           # part de features déviantes
        mean_z      = float(np.mean(z))
        score = float(np.clip(frac_3sigma * 60.0 + min(1.0, mean_z / 5.0) * 40.0,
                              0.0, 100.0))
        # features les plus déviantes (explicabilité)
        top = np.argsort(z)[::-1][:3]
        contributors = [
            {"feature": FEATURE_NAMES[i], "z_score": round(float(z[i]), 2)}
            for i in top
        ]
        return {
            "available"     : True,
            "anomaly_score" : round(score, 2),
            "is_anomaly"    : score > 50.0,
            "mean_z"        : round(mean_z, 2),
            "contributors"  : contributors,
        }

    # ── Persistance ────────────────────────────────────────────────────────
    def save(self):
        with open(BASELINE_DIR / f"{self.machine_id}.pkl", "wb") as f:
            pickle.dump({
                "machine_id": self.machine_id, "mean": self.mean,
                "std": self.std, "iso_baseline": self.iso_baseline,
                "n_samples": self.n_samples, "fitted": self.fitted,
            }, f)

    @classmethod
    def load(cls, machine_id: str):
        path = BASELINE_DIR / f"{machine_id}.pkl"
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                d = pickle.load(f)
            b = cls(machine_id)
            b.mean = d["mean"]; b.std = d["std"]
            b.iso_baseline = d["iso_baseline"]
            b.n_samples = d["n_samples"]; b.fitted = d["fitted"]
            return b
        except Exception:
            return None


class BaselineStore:
    """Registre des baselines par machine (mémoire + disque)."""

    def __init__(self):
        self._baselines = {}

    def get(self, machine_id: str) -> MachineBaseline:
        if machine_id not in self._baselines:
            loaded = MachineBaseline.load(machine_id)
            self._baselines[machine_id] = loaded or MachineBaseline(machine_id)
        return self._baselines[machine_id]

    def reset(self, machine_id: str) -> MachineBaseline:
        b = MachineBaseline(machine_id)
        self._baselines[machine_id] = b
        return b

    def status(self) -> dict:
        return {
            mid: {"fitted": b.fitted, "n_samples": b.n_samples,
                  "iso_baseline_mm_s": b.iso_baseline}
            for mid, b in self._baselines.items()
        }


baseline_store = BaselineStore()
