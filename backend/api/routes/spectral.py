"""
Analyse spectrale — 3 routes avec niveaux de complexité distincts.

/signal/indicators  → léger, temps réel
/signal/spectrum    → FFT + annotations, semi-temps réel
/machine/{id}/diagnose → diagnostic complet, à la demande
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from typing import Optional, List
import numpy as np
from datetime import datetime

from backend.ml.iso_severity import iso_assessment

router = APIRouter(tags=["Analyse Spectrale"])

MIN_SIGNAL_LENGTH = 64   # minimum absolu pour FFT


# ── Modèles Pydantic avec validation ──────────────────────────────────────

class BearingParams(BaseModel):
    shaft_freq    : float
    n_balls       : int
    ball_diam     : float
    pitch_diam    : float
    contact_angle : float = 0.0

    @validator('shaft_freq')
    def shaft_freq_positive(cls, v):
        if v <= 0:
            raise ValueError('shaft_freq doit être positif')
        return v

    @validator('ball_diam', 'pitch_diam')
    def dims_positive(cls, v):
        if v <= 0:
            raise ValueError('Les dimensions doivent être positives')
        return v

    @validator('n_balls')
    def balls_positive(cls, v):
        if v < 3:
            raise ValueError('n_balls doit être >= 3')
        return v


class SignalBase(BaseModel):
    signal        : List[float]
    sampling_rate : float = 12800.0

    @validator('signal')
    def signal_not_empty(cls, v):
        if len(v) < MIN_SIGNAL_LENGTH:
            raise ValueError(
                f'Signal trop court ({len(v)} pts). '
                f'Minimum : {MIN_SIGNAL_LENGTH} pts'
            )
        return v

    @validator('sampling_rate')
    def fs_positive(cls, v):
        if v <= 0:
            raise ValueError('sampling_rate doit être positif')
        return v


class SpectrumRequest(SignalBase):
    bearing_params : Optional[BearingParams] = None


class DiagnoseRequest(SignalBase):
    health_index   : float = 100.0
    bearing_params : Optional[BearingParams] = None
    hilbert_band_low  : float = 500.0    # Hz — configurable
    hilbert_band_high : float = 5000.0   # Hz — configurable
    input_unit     : str = "g"           # 'g' ou 'm/s2' (pour ISO)
    machine_class  : str = "II"          # classe ISO 10816 (I–IV)


class ISORequest(SignalBase):
    input_unit    : str = "g"            # 'g' ou 'm/s2'
    machine_class : str = "II"           # classe ISO 10816 (I–IV)


# ── Fonctions utilitaires ──────────────────────────────────────────────────

def compute_bearing_frequencies(p: BearingParams) -> dict:
    f0    = p.shaft_freq
    n     = p.n_balls
    bd    = p.ball_diam
    pd    = p.pitch_diam
    phi   = np.radians(p.contact_angle)
    ratio = (bd / pd) * np.cos(phi)

    return {
        "f0"  : round(f0, 3),
        "BPFO": round((n/2) * f0 * (1 - ratio), 3),
        "BPFI": round((n/2) * f0 * (1 + ratio), 3),
        "BSF" : round((pd/(2*bd)) * f0 * (1 - ratio**2), 3),
        "FTF" : round((f0/2) * (1 - ratio), 3),
        "2xf0": round(f0*2, 3),
        "3xf0": round(f0*3, 3),
        "4xf0": round(f0*4, 3),
    }


def detect_fault_peaks(spectrum, freqs, char_freqs,
                        tolerance_pct=0.08) -> tuple:
    spec_db     = 20 * np.log10(spectrum + 1e-10)
    noise_floor = float(np.percentile(spec_db, 50))

    fault_signatures = {
        "desequilibre"    : ["f0", "2xf0"],
        "desalignement"   : ["2xf0", "3xf0", "f0"],
        "roulement_externe": ["BPFO"],
        "roulement_interne": ["BPFI"],
        "roulement_bille" : ["BSF"],
        "cage"            : ["FTF"],
        "jeu_mecanique"   : ["f0", "2xf0", "3xf0", "4xf0"],
    }

    fault_scores, peak_details = {}, {}
    for fault, sig_freqs in fault_signatures.items():
        score, peaks = 0.0, []
        for fname in sig_freqs:
            if fname not in char_freqs:
                continue
            fc = char_freqs[fname]
            if fc <= 0 or fc >= freqs[-1]:
                continue
            mask = (freqs >= fc*(1-tolerance_pct)) & \
                   (freqs <= fc*(1+tolerance_pct))
            if not mask.any():
                continue
            peak_db    = float(spec_db[mask].max())
            peak_freq  = float(freqs[mask][spec_db[mask].argmax()])
            prominence = max(0.0, peak_db - noise_floor)
            score     += prominence
            peaks.append({
                "freq_name"    : fname,
                "target_hz"    : fc,
                "found_hz"     : round(peak_freq, 2),
                "amplitude_db" : round(peak_db, 2),
                "prominence_db": round(prominence, 2),
                "detected"     : prominence > 3.0
            })
        fault_scores[fault] = round(score, 2)
        peak_details[fault] = peaks

    return fault_scores, peak_details


def diagnose_from_scores(fault_scores, health_index) -> dict:
    if not fault_scores or max(fault_scores.values()) < 1.0:
        return {
            "fault"     : "sain",
            "confidence": 0.95,
            "severity"  : "normal",
            "message"   : "Aucun défaut spectral détecté",
            "all_scores": fault_scores
        }
    best  = max(fault_scores, key=fault_scores.get)
    score = fault_scores[best]
    conf  = score / (sum(fault_scores.values()) + 1e-10)

    if health_index < 20 or score > 20:
        severity = "critique"
    elif health_index < 40 or score > 10:
        severity = "elevee"
    elif health_index < 70 or score > 5:
        severity = "moderee"
    else:
        severity = "faible"

    messages = {
        "desequilibre"    : "Déséquilibre rotor — pic dominant à f0",
        "desalignement"   : "Désalignement — pics à 2×f0 et 3×f0",
        "roulement_externe": "Défaut bague externe — pic à BPFO",
        "roulement_interne": "Défaut bague interne — pic à BPFI",
        "roulement_bille" : "Défaut bille — pic à BSF",
        "cage"            : "Défaut cage — pic à FTF",
        "jeu_mecanique"   : "Jeu mécanique — harmoniques multiples",
    }
    return {
        "fault"     : best,
        "confidence": round(conf, 3),
        "score"     : round(score, 2),
        "severity"  : severity,
        "message"   : messages.get(best, "Défaut détecté"),
        "all_scores": fault_scores
    }


def get_recommendation(fault: str, severity: str) -> dict:
    recs = {
        "sain"            : ("Aucune action", "normal",  "Inspection planifiée"),
        "desequilibre"    : ("Rééquilibrage rotor", "modérée", "Sous 2 semaines"),
        "desalignement"   : ("Réalignement accouplement", "modérée", "Sous 1 semaine"),
        "roulement_externe": ("Remplacement roulement", "haute", "Sous 48h"),
        "roulement_interne": ("Remplacement roulement", "haute", "Sous 48h"),
        "roulement_bille" : ("Remplacement roulement", "haute", "Sous 72h"),
        "jeu_mecanique"   : ("Serrage fixations", "modérée", "Sous 1 semaine"),
    }
    action, urgency, delay = recs.get(fault, recs["sain"])
    return {"action": action, "urgency": urgency, "delay": delay}


# ── Route 1 : Indicateurs temporels (temps réel) ─────────────────────────

@router.post("/signal/indicators")
def compute_indicators(req: SignalBase):
    """
    Léger — appelé toutes les secondes en temps réel.
    Calcule uniquement les indicateurs statistiques temporels.
    """
    from scipy.stats import kurtosis, skew
    x   = np.array(req.signal, dtype=np.float64)
    rms = float(np.sqrt(np.mean(x**2)))
    k   = float(kurtosis(x, fisher=True))

    return {
        "RMS"         : round(rms, 6),
        "Kurtosis"    : round(k, 4),
        "Skewness"    : round(float(skew(x)), 4),
        "Peak"        : round(float(np.max(np.abs(x))), 6),
        "Peak_to_Peak": round(float(np.max(x) - np.min(x)), 6),
        "Crest_Factor": round(float(np.max(np.abs(x)) / (rms + 1e-10)), 4),
        "Std"         : round(float(np.std(x)), 6),
        "Kurtosis_flag": "anomalie" if k > 4 else "normal",
        "timestamp"   : datetime.now().isoformat()
    }


# ── Route 2 : Spectre FFT + annotations (semi-temps réel) ─────────────────

@router.post("/signal/spectrum")
def compute_spectrum(req: SpectrumRequest):
    """
    Semi-temps réel — appelé toutes les 5 secondes.
    Calcule le spectre FFT et annote les fréquences caractéristiques.
    """
    from scipy.fft import rfft, rfftfreq
    x    = np.array(req.signal, dtype=np.float64)
    N    = len(x)
    fs   = req.sampling_rate

    # FFT avec fenêtre de Hanning
    win      = np.hanning(N)
    spectrum = np.abs(rfft(x * win)) / (N / 2)
    freqs    = rfftfreq(N, d=1.0/fs)
    spec_db  = 20 * np.log10(spectrum + 1e-10)

    # Sous-échantillonner pour le frontend (max 512 points)
    step    = max(1, len(freqs) // 512)
    fft_out = {
        "freqs"       : freqs[::step].tolist(),
        "spectrum_db" : spec_db[::step].tolist(),
        "spectrum_lin": spectrum[::step].tolist(),
        "resolution_hz": round(fs / N, 3),
        "nyquist_hz"  : round(fs / 2, 1),
    }

    # Fréquences caractéristiques si paramètres fournis
    char_freqs  = {}
    annotations = []
    if req.bearing_params:
        char_freqs = compute_bearing_frequencies(req.bearing_params)
        for fname, fval in char_freqs.items():
            idx = np.argmin(np.abs(freqs - fval))
            if idx < len(spec_db):
                annotations.append({
                    "name"        : fname,
                    "frequency_hz": round(fval, 2),
                    "amplitude_db": round(float(spec_db[idx]), 2),
                    "color"       : "orange" if fname in
                                    ["f0","2xf0","3xf0","4xf0"] else "blue"
                })

    return {
        "fft"            : fft_out,
        "char_frequencies": char_freqs,
        "annotations"    : annotations,
        "timestamp"      : datetime.now().isoformat()
    }


# ── Route 3 : Diagnostic complet (à la demande) ───────────────────────────

@router.post("/signal/diagnose")
def diagnose_signal(req: DiagnoseRequest):
    """
    Diagnostic complet — déclenché manuellement ou quand HI < 70%.
    Combine FFT + détection pics + enveloppe Hilbert.
    """
    from scipy.fft import rfft, rfftfreq
    from scipy.signal import hilbert, butter, filtfilt
    x  = np.array(req.signal, dtype=np.float64)
    N  = len(x)
    fs = req.sampling_rate
    hi = req.health_index

    # FFT
    win      = np.hanning(N)
    spectrum = np.abs(rfft(x * win)) / (N / 2)
    freqs    = rfftfreq(N, d=1.0/fs)

    # Fréquences caractéristiques
    if req.bearing_params:
        char_freqs    = compute_bearing_frequencies(req.bearing_params)
        analysis_mode = "bearing"
    else:
        # Estimation générique f0 depuis le spectre
        top_idx    = np.argmax(spectrum[1:int(len(spectrum)*0.1)]) + 1
        f0_est     = float(freqs[top_idx])
        char_freqs = {
            "f0"  : f0_est,
            "2xf0": f0_est * 2,
            "3xf0": f0_est * 3,
            "4xf0": f0_est * 4,
        }
        analysis_mode = "generic"

    # Détection des pics
    fault_scores, peak_details = detect_fault_peaks(
        spectrum, freqs, char_freqs
    )

    # Diagnostic
    diagnosis = diagnose_from_scores(fault_scores, hi)

    # Enveloppe Hilbert (confirmation défauts roulements)
    envelope_analysis = {}
    if (analysis_mode == "bearing" and
            "roulement" in diagnosis['fault']):
        try:
            # Bande configurable depuis la requête
            bl = req.hilbert_band_low  / (fs/2)
            bh = req.hilbert_band_high / (fs/2)

            # Vérifier que les fréquences sont dans [0, 1]
            if 0 < bl < bh < 1:
                b, a     = butter(4, [bl, bh], btype='band')
                x_bp     = filtfilt(b, a, x)
                envelope = np.abs(hilbert(x_bp))

                env_spec  = np.abs(rfft(envelope * np.hanning(len(envelope))))
                env_spec  = env_spec / (env_spec.max() + 1e-10)
                env_freqs = rfftfreq(len(envelope), d=1.0/fs)

                fault_freq_map = {
                    "roulement_externe": "BPFO",
                    "roulement_interne": "BPFI",
                    "roulement_bille"  : "BSF",
                }
                fkey      = fault_freq_map.get(diagnosis['fault'], "BPFO")
                fault_f   = char_freqs.get(fkey, 0)

                if fault_f > 0:
                    mask      = ((env_freqs >= fault_f*0.9) &
                                 (env_freqs <= fault_f*1.1))
                    env_peak  = float(env_spec[mask].max()) \
                                if mask.any() else 0.0
                    envelope_analysis = {
                        "fault_freq_hz": fault_f,
                        "envelope_peak": round(env_peak, 4),
                        "confirmed"    : env_peak > 0.1,
                        "band_hz"      : [req.hilbert_band_low,
                                          req.hilbert_band_high],
                        "message"      : "Confirmé par enveloppe"
                                         if env_peak > 0.1
                                         else "Non confirmé"
                    }
        except Exception as e:
            envelope_analysis = {"error": str(e)}

    # Annotations pour le frontend
    annotations = []
    primary_fault_freq = {
        "roulement_externe": "BPFO",
        "roulement_interne": "BPFI",
        "roulement_bille"  : "BSF",
        "cage"             : "FTF",
        "desequilibre"     : "f0",
        "desalignement"    : "2xf0",
    }.get(diagnosis['fault'], "")

    for fname, fval in char_freqs.items():
        idx = np.argmin(np.abs(freqs - fval))
        if idx < len(spectrum):
            spec_db = 20 * np.log10(spectrum[idx] + 1e-10)
            annotations.append({
                "name"        : fname,
                "frequency_hz": round(fval, 2),
                "amplitude_db": round(float(spec_db), 2),
                "color"       : "red"    if fname == primary_fault_freq
                                else "orange" if fname in
                                     ["f0","2xf0","3xf0","4xf0"]
                                else "blue",
                "is_primary"  : fname == primary_fault_freq
            })

    return {
        "analysis_mode"    : analysis_mode,
        "health_index"     : hi,
        "diagnosis"        : diagnosis,
        "peak_details"     : peak_details,
        "envelope_analysis": envelope_analysis,
        "annotations"      : annotations,
        "char_frequencies" : char_freqs,
        "iso_severity"     : iso_assessment(x, fs, req.input_unit, req.machine_class),
        "recommendation"   : get_recommendation(
            diagnosis['fault'], diagnosis['severity']
        ),
        "timestamp"        : datetime.now().isoformat()
    }


# ── Route 4 : Diagnostic lié à une machine (avec sauvegarde) ─────────────

@router.post("/machine/{machine_id}/diagnose")
def diagnose_machine(machine_id: str, req: DiagnoseRequest):
    """
    Diagnostic complet lié à une machine spécifique.
    Sauvegarde le résultat dans le HealthTracker.
    """
    from backend.ml.health_tracker import fleet_manager

    machine = fleet_manager.get_machine(machine_id)
    if machine is None:
        raise HTTPException(404, f"Machine {machine_id} introuvable")

    # Lancer le diagnostic
    result = diagnose_signal(req)

    # Sauvegarder dans le tracker
    machine._last_diagnosis = {
        "fault"         : result['diagnosis']['fault'],
        "confidence"    : result['diagnosis']['confidence'],
        "severity"      : result['diagnosis']['severity'],
        "message"       : result['diagnosis']['message'],
        "recommendation": result['recommendation'],
        "timestamp"     : result['timestamp']
    }

    result["machine_id"] = machine_id
    return result


@router.post("/signal/iso-severity")
def signal_iso_severity(req: ISORequest):
    """
    Sévérité vibratoire ISO 10816/20816 — vitesse RMS (mm/s) + zone A/B/C/D.
    Attend un signal d'ACCÉLÉRATION (g ou m/s²).
    """
    x = np.array(req.signal, dtype=np.float64)
    return {
        **iso_assessment(x, req.sampling_rate, req.input_unit, req.machine_class),
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/bearing/frequencies")
def bearing_frequencies(params: BearingParams):
    """Calcule les fréquences caractéristiques d'un roulement."""
    return {
        "frequencies"  : compute_bearing_frequencies(params),
        "shaft_freq_hz": params.shaft_freq,
        "shaft_rpm"    : round(params.shaft_freq * 60, 1),
        "interpretation": {
            "BPFO": "Fréquence de passage sur bague externe",
            "BPFI": "Fréquence de passage sur bague interne",
            "BSF" : "Fréquence de rotation des billes",
            "FTF" : "Fréquence fondamentale de la cage",
        }
    }
class SpectrumDiagnoseRequest(BaseModel):
    """
    Diagnostic depuis un spectre externe (FFT déjà calculée).
    Utile pour les analyseurs vibratoires externes.
    """
    freqs          : List[float]   # fréquences en Hz
    amplitudes     : List[float]   # amplitudes (dB ou linéaire)
    is_db          : bool  = True  # True si amplitudes en dB
    bearing_params : Optional[BearingParams] = None
    health_index   : float = 80.0


@router.post("/diagnose/spectrum")
def diagnose_from_spectrum(req: SpectrumDiagnoseRequest):
    try:
        if len(req.freqs) != len(req.amplitudes):
            raise HTTPException(400,
                f"Longueurs différentes : {len(req.freqs)} fréquences, "
                f"{len(req.amplitudes)} amplitudes")

        if len(req.freqs) < 5:
            raise HTTPException(400,
                f"Trop peu de points : {len(req.freqs)} (minimum 5)")

        freqs    = np.array(req.freqs,      dtype=np.float64)
        amps_raw = np.array(req.amplitudes, dtype=np.float64)

        # Nettoyage
        amps_raw = np.nan_to_num(amps_raw, nan=-80.0,
                                  posinf=0.0, neginf=-120.0)
        freqs    = np.nan_to_num(freqs, nan=0.0)
        freqs    = np.abs(freqs)  # fréquences positives

        # Conversion linéaire
        if req.is_db:
            spectrum = 10.0 ** (np.clip(amps_raw, -200.0, 100.0) / 20.0)
        else:
            spectrum = np.abs(amps_raw) + 1e-12

        spectrum = np.where(np.isfinite(spectrum), spectrum, 1e-12)

        # Fréquences caractéristiques
        if req.bearing_params:
            char_freqs    = compute_bearing_frequencies(req.bearing_params)
            analysis_mode = "bearing"
        else:
            # Estimer f0 depuis le spectre basse fréquence
            nyquist     = freqs[-1] if len(freqs) > 0 else 6400.0
            low_mask    = (freqs > 0) & (freqs < nyquist * 0.15)

            if low_mask.sum() >= 2:
                low_spec = spectrum[low_mask]
                low_f    = freqs[low_mask]
                f0_est   = float(low_f[np.argmax(low_spec)])
            else:
                f0_est   = float(freqs[min(1, len(freqs)-1)])

            f0_est = max(f0_est, 0.5)
            char_freqs = {
                "f0"  : round(f0_est,   2),
                "2xf0": round(f0_est*2, 2),
                "3xf0": round(f0_est*3, 2),
                "4xf0": round(f0_est*4, 2),
            }
            analysis_mode = "generic"

        # Détection pics avec tolérance plus large
        fault_scores, peak_details = detect_fault_peaks(
            spectrum, freqs, char_freqs, tolerance_pct=0.12
        )

        diagnosis = diagnose_from_scores(fault_scores, req.health_index)

        # Annotations
        primary_map = {
            "roulement_externe": "BPFO",
            "roulement_interne": "BPFI",
            "roulement_bille"  : "BSF",
            "cage"             : "FTF",
            "desequilibre"     : "f0",
            "desalignement"    : "2xf0",
            "jeu_mecanique"    : "f0",
        }
        primary  = primary_map.get(diagnosis.get("fault", ""), "")
        spec_db  = 20 * np.log10(spectrum + 1e-10)
        annotations = []

        for fname, fval in char_freqs.items():
            if fval <= 0 or fval > freqs[-1]:
                continue
            idx = int(np.argmin(np.abs(freqs - fval)))
            if idx < len(spec_db):
                annotations.append({
                    "name"        : fname,
                    "frequency_hz": round(float(fval), 2),
                    "amplitude_db": round(float(spec_db[idx]), 2),
                    "color"       : "red"    if fname == primary
                                    else "orange" if "xf0" in fname
                                    else "blue",
                    "is_primary"  : fname == primary,
                })

        return {
            "analysis_mode"   : analysis_mode,
            "health_index"    : req.health_index,
            "n_freq_points"   : len(req.freqs),
            "freq_range_hz"   : [
                round(float(freqs.min()), 2),
                round(float(freqs.max()), 2)
            ],
            "char_frequencies": char_freqs,
            "diagnosis"       : diagnosis,
            "peak_details"    : peak_details,
            "annotations"     : annotations,
            "recommendation"  : get_recommendation(
                diagnosis.get("fault", "sain"),
                diagnosis.get("severity", "normal")
            ),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(500, f"Erreur interne : {str(e)}\n{traceback.format_exc()}")