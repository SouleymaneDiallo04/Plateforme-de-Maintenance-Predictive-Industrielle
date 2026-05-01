import numpy as np

def compute_health_index(
    anomaly_score: float,
    rul: float = None,
    rul_max: float = 125.0,
    vibration_rms: float = None,
    rms_baseline: float = None,
) -> dict:
    """
    Calcule le Health Index (0-100%) à partir de plusieurs indicateurs.
    Retourne également les composantes et l'action recommandée.
    """
    components = {}
    weights = []
    scores = []

    # Composante 1 : score d'anomalie (autoencoder)
    hi_anomaly = max(0, 100 - anomaly_score)
    components['anomaly'] = hi_anomaly
    scores.append(hi_anomaly)
    weights.append(0.4 if rul is not None else 0.8)

    # Composante 2 : RUL normalisée
    if rul is not None:
        hi_rul = min(100, (rul / rul_max) * 100)
        components['rul'] = hi_rul
        scores.append(hi_rul)
        weights.append(0.4)
    else:
        # Si pas de RUL, le poids de l'anomalie est déjà augmenté
        pass

    # Composante 3 : RMS vibration
    if vibration_rms is not None and rms_baseline is not None:
        ratio = rms_baseline / (vibration_rms + 1e-10)
        hi_vib = min(100, max(0, ratio * 100))
        components['vibration'] = hi_vib
        scores.append(hi_vib)
        weights.append(0.2)
    else:
        # Redistribuer le poids manquant sur les autres composantes
        remaining = 0.2 / len(weights) if weights else 0.0
        weights = [w + remaining for w in weights]

    # Score final pondéré
    if not weights:
        return {
            'health_index': 100.0,
            'status': 'sain',
            'color': 'green',
            'action': 'Surveillance standard',
            'components': {}
        }

    weights_norm = [w / sum(weights) for w in weights]
    hi_final = sum(s * w for s, w in zip(scores, weights_norm))
    hi_final = round(float(np.clip(hi_final, 0, 100)), 2)

    # Statut et couleur
    if hi_final >= 70:
        status = "sain"
        color = "green"
        action = "Surveillance standard"
    elif hi_final >= 40:
        status = "surveillance"
        color = "yellow"
        action = "Planifier inspection préventive"
    elif hi_final >= 20:
        status = "alerte"
        color = "orange"
        action = "Intervention sous 48h recommandée"
    else:
        status = "critique"
        color = "red"
        action = "Arrêt et intervention immédiate"

    return {
        'health_index': hi_final,
        'status': status,
        'color': color,
        'action': action,
        'components': components,
    }