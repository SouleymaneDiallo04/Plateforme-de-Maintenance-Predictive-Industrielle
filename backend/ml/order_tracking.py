"""
Analyse d'ordre — PrognoSense.

L'analyse spectrale classique (FFT) donne des fréquences fixes (Hz).
Sur une machine à vitesse variable, la BPFO d'un roulement se déplace
avec la vitesse : difficile à suivre.

L'analyse d'ordre rééchantillonne le signal dans le domaine angulaire
(tours de l'arbre) plutôt que temporel. Les défauts apparaissent toujours
au même ordre cinématique (ex. BPFO ≈ ordre 3.5) quelle que soit la vitesse.

Usage :
    result = compute_order_spectrum(signal, rpm_signal, fs=12800)
    bpfo_energy = extract_order_energy(result, order=3.5, bandwidth=0.2)
"""

import numpy as np
from scipy.interpolate import interp1d
from typing import Optional


def compute_order_spectrum(
    signal    : np.ndarray,
    rpm_signal: Optional[np.ndarray] = None,
    fs        : float = 12800.0,
    rpm_mean  : float = 1750.0,
    max_order : float = 20.0,
    n_orders  : int   = 1024,
) -> dict:
    """
    Calcule le spectre d'ordre d'un signal vibratoire.

    Args:
        signal     : Signal temporel (1D).
        rpm_signal : Vitesse de rotation en rpm (même longueur que signal).
                     Si None, on utilise rpm_mean comme vitesse constante.
        fs         : Fréquence d'échantillonnage (Hz).
        rpm_mean   : Vitesse moyenne si rpm_signal non disponible.
        max_order  : Ordre maximum à afficher.
        n_orders   : Résolution angulaire (nombre de points).

    Returns:
        {
            "orders"  : [0.0, 0.02, ...],   # abscisses (ordres)
            "spectrum": [0.0, 0.001, ...],  # amplitudes
            "method"  : "order_tracking" | "constant_rpm",
            "rpm_mean": 1750.0,
            "note"    : "...",
        }
    """
    n = len(signal)
    t = np.arange(n) / fs

    if rpm_signal is not None and len(rpm_signal) == n:
        # Rééchantillonnage angulaire réel
        rpm_interp = interp1d(t, rpm_signal, kind="linear",
                              fill_value="extrapolate")
        omega = rpm_interp(t) / 60.0           # tours/seconde
        method = "order_tracking"
        actual_rpm = float(np.mean(rpm_signal))
    else:
        # Vitesse constante — simule l'analyse d'ordre
        omega  = np.full(n, rpm_mean / 60.0)
        method = "constant_rpm"
        actual_rpm = rpm_mean

    # Angle accumulé (en tours)
    theta = np.cumsum(omega) / fs

    # Rééchantillonnage uniforme en angle
    if theta[-1] <= theta[0]:
        return {"orders": [], "spectrum": [], "method": method,
                "rpm_mean": actual_rpm, "error": "Signal trop court"}

    theta_uniform  = np.linspace(theta[0], theta[-1], n_orders)
    interp_fn      = interp1d(theta, signal, kind="linear",
                              fill_value="extrapolate")
    signal_angular = interp_fn(theta_uniform)

    # FFT dans le domaine angulaire
    spectrum = np.abs(np.fft.rfft(signal_angular)) / n_orders
    orders   = np.fft.rfftfreq(n_orders) * n_orders

    # Filtrer aux ordres utiles
    mask = orders <= max_order
    return {
        "orders"  : orders[mask].tolist(),
        "spectrum": spectrum[mask].tolist(),
        "method"  : method,
        "rpm_mean": round(actual_rpm, 1),
        "note"    : "Indépendant de la vitesse de rotation — défauts à ordre fixe",
    }


def extract_order_energy(
    order_result: dict,
    order       : float,
    bandwidth   : float = 0.2,
) -> float:
    """
    Extrait l'énergie autour d'un ordre cinématique spécifique.

    Args:
        order_result : Résultat de compute_order_spectrum.
        order        : Ordre cinématique cible (ex. 3.5 pour BPFO).
        bandwidth    : ±bandwidth autour de l'ordre cible.

    Returns:
        Énergie RMS dans la bande d'ordre.
    """
    orders   = np.array(order_result.get("orders", []))
    spectrum = np.array(order_result.get("spectrum", []))

    if len(orders) == 0:
        return 0.0

    mask   = (orders >= order - bandwidth) & (orders <= order + bandwidth)
    energy = float(np.sqrt(np.mean(spectrum[mask] ** 2))) if mask.any() else 0.0
    return round(energy, 6)


def compute_kinematic_orders(
    shaft_freq    : float = 20.6,
    n_balls       : int   = 9,
    ball_diam     : float = 7.94,
    pitch_diam    : float = 38.5,
    contact_angle : float = 0.0,
) -> dict:
    """
    Calcule les ordres cinématiques des défauts de roulement.
    Les ordres sont normalisés par la fréquence de rotation de l'arbre.

    Returns:
        {
            "BPFO": 3.585,   # Ball Pass Frequency Outer race
            "BPFI": 5.415,   # Ball Pass Frequency Inner race
            "BSF" : 2.357,   # Ball Spin Frequency
            "FTF" : 0.398,   # Fundamental Train Frequency
        }
    """
    import math
    cos_a = math.cos(math.radians(contact_angle))
    d_D   = ball_diam / pitch_diam

    bpfo_order = (n_balls / 2) * (1 - d_D * cos_a)
    bpfi_order = (n_balls / 2) * (1 + d_D * cos_a)
    bsf_order  = (pitch_diam / (2 * ball_diam)) * (1 - (d_D * cos_a) ** 2)
    ftf_order  = 0.5 * (1 - d_D * cos_a)

    return {
        "BPFO": round(bpfo_order, 3),
        "BPFI": round(bpfi_order, 3),
        "BSF" : round(bsf_order, 3),
        "FTF" : round(ftf_order, 3),
    }
