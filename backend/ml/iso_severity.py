"""
Sévérité vibratoire ISO 10816 / 20816.

Le standard que tout ingénieur fiabilité utilise au quotidien : on évalue
l'état d'une machine tournante par la **vitesse vibratoire RMS en mm/s**
dans la bande 10–1000 Hz, classée en zones :

  A = neuf / mise en service       B = acceptable long terme
  C = insatisfaisant (à surveiller) D = dangereux (risque de dommage)

Les limites dépendent de la classe de machine (I à IV selon puissance /
type de fondation). Valeurs ISO 10816-1.

Entrée attendue : signal d'**accélération** (g ou m/s²). On intègre en
vitesse, on filtre, et on calcule le RMS large bande.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt
from scipy.integrate import cumulative_trapezoid

# Limites de zones (mm/s RMS) par classe machine — ISO 10816-1
ISO_ZONES = {
    "I":   {"A/B": 0.71, "B/C": 1.8,  "C/D": 4.5},   # petites machines < 15 kW
    "II":  {"A/B": 1.12, "B/C": 2.8,  "C/D": 7.1},   # moyennes 15–75 kW
    "III": {"A/B": 1.8,  "B/C": 4.5,  "C/D": 11.2},  # grandes, fondation rigide
    "IV":  {"A/B": 2.8,  "B/C": 7.1,  "C/D": 18.0},  # grandes, fondation souple
}

ZONE_INFO = {
    "A": ("green",  "Neuf / mise en service — état excellent"),
    "B": ("cyan",   "Acceptable pour exploitation longue durée sans restriction"),
    "C": ("amber",  "Insatisfaisant — exploitation limitée, planifier intervention"),
    "D": ("red",    "Dangereux — risque de dommage, arrêt à envisager"),
}

CLASS_LABELS = {
    "I":   "Classe I — petite machine (< 15 kW)",
    "II":  "Classe II — machine moyenne (15–75 kW)",
    "III": "Classe III — grande machine, fondation rigide",
    "IV":  "Classe IV — grande machine, fondation souple",
}


def acceleration_to_velocity_rms(signal: np.ndarray, fs: float,
                                 input_unit: str = "g",
                                 f_low: float = 10.0,
                                 f_high: float = 1000.0) -> float:
    """
    Intègre une accélération en vitesse et retourne le RMS en mm/s
    dans la bande [f_low, f_high] (ISO : 10–1000 Hz).
    """
    x = np.asarray(signal, dtype=np.float64)
    if x.size < 16:
        return 0.0

    # Conversion en m/s²
    if input_unit.lower() in ("g", "g-force", "gravity"):
        x = x * 9.80665

    x = x - np.mean(x)

    # Bornes valides vs Nyquist
    nyq    = fs / 2.0
    f_high = min(f_high, nyq * 0.95)
    f_low  = max(0.5, min(f_low, f_high * 0.5))

    # Passe-bande sur l'accélération (limite la dérive d'intégration)
    sos = butter(2, [f_low, f_high], btype="band", fs=fs, output="sos")
    x_bp = sosfiltfilt(sos, x)

    # Intégration accélération → vitesse (m/s)
    v = cumulative_trapezoid(x_bp, dx=1.0 / fs, initial=0.0)

    # Passe-haut sur la vitesse pour retirer la dérive résiduelle
    sos_hp = butter(2, f_low, btype="high", fs=fs, output="sos")
    v = sosfiltfilt(sos_hp, v)

    v_mm_s = v * 1000.0
    return float(np.sqrt(np.mean(v_mm_s ** 2)))


def classify_zone(v_rms: float, machine_class: str = "II") -> dict:
    """Classe une vitesse RMS (mm/s) en zone ISO A/B/C/D."""
    machine_class = machine_class if machine_class in ISO_ZONES else "II"
    z = ISO_ZONES[machine_class]

    if v_rms <= z["A/B"]:
        zone = "A"
    elif v_rms <= z["B/C"]:
        zone = "B"
    elif v_rms <= z["C/D"]:
        zone = "C"
    else:
        zone = "D"

    color, desc = ZONE_INFO[zone]
    return {
        "v_rms_mm_s"   : round(v_rms, 3),
        "zone"         : zone,
        "machine_class": machine_class,
        "class_label"  : CLASS_LABELS[machine_class],
        "color"        : color,
        "description"  : desc,
        "limits_mm_s"  : z,
        "standard"     : "ISO 10816-1 / 20816",
    }


def iso_assessment(signal, fs: float, input_unit: str = "g",
                   machine_class: str = "II") -> dict:
    """Évaluation ISO complète depuis un signal d'accélération brut."""
    v = acceleration_to_velocity_rms(signal, fs, input_unit)
    return classify_zone(v, machine_class)
