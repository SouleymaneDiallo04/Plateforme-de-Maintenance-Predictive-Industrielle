"""
HealthTracker — suit l'évolution du Health Index dans le temps.
Maintient un historique par machine pour la courbe de dégradation.
"""

import numpy as np
from collections import deque
from datetime import datetime
from typing import Optional
import json
from pathlib import Path


class MachineHealthTracker:
    """
    Suit l'état de santé d'une machine au fil du temps.
    Stocke l'historique pour la courbe de dégradation.
    """

    def __init__(self, machine_id: str,
                 dataset: str,
                 history_size: int = 200):
        self.machine_id   = machine_id
        self.dataset      = dataset
        self.history_size = history_size

        # Buffer du dernier signal reçu (pour diagnostic sans renvoyer le signal)
        self._last_signal = None     # np.ndarray (N,) dernier signal brut
        self._last_signal_fs = 12800.0  # fréquence d'échantillonnage

# Historique des diagnostics (liste, pas juste le dernier)
        self._diagnosis_history  = []       # [{fault, confidence, timestamp, ...}]
        self._last_diagnosis = None     # raccourci vers le plus récent

        # Historique circulaire (les N dernières valeurs)
        self._hi_history      = deque(maxlen=history_size)
        self._rul_history     = deque(maxlen=history_size)
        self._anomaly_history = deque(maxlen=history_size)
        self._rms_history     = deque(maxlen=history_size)
        self._timestamps      = deque(maxlen=history_size)
        self._cycle_history   = deque(maxlen=history_size)

        # Baseline (état sain initial)
        self._rms_baseline    = None
        self._hi_baseline     = 100.0
        self._cycle_counter   = 0

        # Alertes déclenchées
        self._alerts          = []
        self._last_diagnosis = None   # dernier diagnostic spectral

    def update(self, health_index: float,
               anomaly_score: float,
               rul: Optional[float] = None,
               rms: Optional[float] = None,
               cycle: Optional[int] = None) -> dict:
        """
        Met à jour l'état de la machine avec une nouvelle mesure.
        Retourne un dict avec les changements importants.
        """
        self._cycle_counter += 1
        now = datetime.now().isoformat()

        # Baseline RMS sur les 10 premières mesures (état supposé sain)
        if rms is not None:
            if len(self._rms_history) < 10:
                self._rms_baseline = rms
            elif self._rms_baseline is None:
                self._rms_baseline = rms

        # Stocker dans l'historique
        self._hi_history.append(health_index)
        self._anomaly_history.append(anomaly_score)
        self._timestamps.append(now)
        self._cycle_history.append(
            cycle if cycle is not None else self._cycle_counter
        )
        if rul is not None:
            self._rul_history.append(rul)
        if rms is not None:
            self._rms_history.append(rms)

        # ── Calcul de la tendance ─────────────────────────────────────────
        trend = self._compute_trend()

        # ── Détection de franchissement de seuils ────────────────────────
        alerts = self._check_alerts(health_index, rul)

        return {
            'health_index'    : health_index,
            'trend'           : trend,
            'new_alerts'      : alerts,
            'cycle'           : cycle or self._cycle_counter,
        }

    def _compute_trend(self) -> dict:
        """
        Calcule la tendance du Health Index.
        Utilise une régression linéaire sur les 20 dernières valeurs.
        """
        if len(self._hi_history) < 5:
            return {
                'slope'      : 0.0,
                'direction'  : 'stable',
                'description': 'Données insuffisantes'
            }

        # Régression linéaire sur les N dernières valeurs
        n    = min(20, len(self._hi_history))
        hi   = list(self._hi_history)[-n:]
        x    = np.arange(n)
        slope = float(np.polyfit(x, hi, 1)[0])

        if slope < -0.5:
            direction   = 'degradation_rapide'
            description = f'↓↓ Dégradation rapide ({slope:.2f}%/cycle)'
        elif slope < -0.1:
            direction   = 'degradation'
            description = f'↓ Dégradation active ({slope:.2f}%/cycle)'
        elif slope < 0.1:
            direction   = 'stable'
            description = f'→ Stable ({slope:.2f}%/cycle)'
        else:
            direction   = 'amelioration'
            description = f'↑ Amélioration ({slope:.2f}%/cycle)'

        return {
            'slope'      : round(slope, 3),
            'direction'  : direction,
            'description': description
        }

    def _check_alerts(self, hi: float,
                       rul: Optional[float]) -> list:
        """Vérifie si des seuils critiques ont été franchis."""
        alerts = []
        prev   = list(self._hi_history)[-2] \
                 if len(self._hi_history) >= 2 else 100.0

        # Franchissement de seuils (une seule fois par seuil)
        thresholds = [
            (70, "alerte_jaune",  "État de surveillance"),
            (40, "alerte_orange", "Intervention recommandée"),
            (20, "alerte_rouge",  "CRITIQUE — Intervention immédiate"),
        ]
        for threshold, alert_type, message in thresholds:
            if prev > threshold >= hi:
                alert = {
                    'type'      : alert_type,
                    'message'   : message,
                    'hi'        : hi,
                    'rul'       : rul,
                    'timestamp' : datetime.now().isoformat(),
                    'machine_id': self.machine_id
                }
                alerts.append(alert)
                self._alerts.append(alert)

        # Alerte RUL critique
        if rul is not None and rul < 15:
            if not any(a['type'] == 'rul_critique'
                       for a in self._alerts[-5:]):
                alert = {
                    'type'      : 'rul_critique',
                    'message'   : f'RUL critique : {rul:.0f} cycles restants',
                    'hi'        : hi,
                    'rul'       : rul,
                    'timestamp' : datetime.now().isoformat(),
                    'machine_id': self.machine_id
                }
                alerts.append(alert)
                self._alerts.append(alert)

        return alerts

    def get_history(self) -> dict:
        """Retourne l'historique complet pour la courbe frontend."""
        return {
            'machine_id'  : self.machine_id,
            'dataset'     : self.dataset,
            'cycles'      : list(self._cycle_history),
            'health_index': list(self._hi_history),
            'rul'         : list(self._rul_history),
            'anomaly'     : list(self._anomaly_history),
            'rms'         : list(self._rms_history),
            'timestamps'  : list(self._timestamps),
            'trend'       : self._compute_trend(),
            'alerts'      : self._alerts[-20:],  # 20 dernières alertes
        }

    def get_current_state(self) -> dict:
        """Retourne l'état actuel résumé."""
        hi  = list(self._hi_history)[-1] \
              if self._hi_history else 100.0
        rul = list(self._rul_history)[-1] \
              if self._rul_history else None

        if hi >= 70:
            status, color = "sain",        "green"
        elif hi >= 40:
            status, color = "surveillance", "yellow"
        elif hi >= 20:
            status, color = "alerte",       "orange"
        else:
            status, color = "critique",     "red"

        state = {
            'machine_id'   : self.machine_id,
            'health_index' : hi,
            'status'       : status,
            'color'        : color,
            'rul'          : rul,
            'trend'        : self._compute_trend(),
            'n_alerts'     : len(self._alerts),
            'last_update'  : list(self._timestamps)[-1]
                             if self._timestamps else None,
            'last_diagnosis' : self._last_diagnosis,  # ← ajout
            'n_diagnoses'     : len(self._diagnosis_history),  # ← ajout
        }
        return state
    def update_signal(self, signal: np.ndarray,
                   sampling_rate: float = 12800.0):
        """
        Stocke le dernier signal reçu.
        Appelé par le WebSocket à chaque cycle.
        """
        self._last_signal    = signal.copy()
        self._last_signal_fs = sampling_rate

    def add_diagnosis(self, diagnosis: dict):
        """
          Ajoute un diagnostic à l'historique.
          Garde les 50 derniers diagnostics.
        """
        entry = {**diagnosis, "timestamp": datetime.now().isoformat()}
        self._diagnosis_history.append(entry)
        if len(self._diagnosis_history) > 50:
            self._diagnosis_history.pop(0)
        self._last_diagnosis = entry

    def get_diagnosis_history(self) -> list:
        return self._diagnosis_history

    def get_last_signal(self) -> dict:
        if self._last_signal is None:
            return {"available": False}
        return {
            "available"    : True,
            "signal"       : self._last_signal.tolist(),
            "sampling_rate": self._last_signal_fs,
            "length"       : len(self._last_signal)
        }


class FleetHealthManager:
    """
    Gestionnaire de flotte — supervise N machines simultanément.
    C'est ce que la page Accueil du dashboard affiche.
    """

    def __init__(self):
        self._machines = {}   # {machine_id: MachineHealthTracker}

    def add_machine(self, machine_id: str,
                    dataset: str) -> MachineHealthTracker:
        tracker = MachineHealthTracker(machine_id, dataset)
        self._machines[machine_id] = tracker
        return tracker

    def get_machine(self, machine_id: str) -> Optional[MachineHealthTracker]:
        return self._machines.get(machine_id)

    def get_fleet_overview(self) -> dict:
        """
        Vue globale de la flotte pour la page Accueil.
        Retourne l'état de toutes les machines triées par criticité.
        """
        states = [
            m.get_current_state()
            for m in self._machines.values()
        ]

        # Trier par Health Index croissant (les plus critiques en premier)
        states.sort(key=lambda x: x['health_index'])

        # KPIs globaux
        hi_values  = [s['health_index'] for s in states]
        rul_values = [s['rul'] for s in states if s['rul'] is not None]

        return {
            'machines'          : states,
            'n_machines'        : len(states),
            'n_critical'        : sum(1 for s in states
                                      if s['color'] == 'red'),
            'n_alert'           : sum(1 for s in states
                                      if s['color'] == 'orange'),
            'n_surveillance'    : sum(1 for s in states
                                      if s['color'] == 'yellow'),
            'n_healthy'         : sum(1 for s in states
                                      if s['color'] == 'green'),
            'avg_health_index'  : round(float(np.mean(hi_values)), 1)
                                   if hi_values else 100.0,
            'min_rul'           : round(float(min(rul_values)), 1)
                                   if rul_values else None,
            'total_alerts'      : sum(s['n_alerts'] for s in states),
        }

    def get_all_alerts(self, severity: str = None) -> list:
        """Retourne toutes les alertes de la flotte, triées par date."""
        all_alerts = []
        for machine in self._machines.values():
            all_alerts.extend(machine._alerts)

        all_alerts.sort(key=lambda x: x['timestamp'], reverse=True)

        if severity:
            all_alerts = [a for a in all_alerts
                          if a['type'] == severity]

        return all_alerts[:100]   # 100 dernières alertes max


# Instance globale
fleet_manager = FleetHealthManager()