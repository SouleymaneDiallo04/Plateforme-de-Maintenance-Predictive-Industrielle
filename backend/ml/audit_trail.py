"""
AuditTrail — journal de toutes les décisions IA de PrognoSense.

Répond aux questions industrielles :
  - Qui a prédit quoi, quand, avec quelle confiance ?
  - Quelles alertes ont été émises et ont-elles été acquittées ?
  - Quand et pourquoi les modèles ont-ils été réentraînés ?

Conforme aux exigences de traçabilité ISO 13373 (surveillance vibratoire).

Usage :
    from backend.ml.audit_trail import audit_trail
    audit_trail.log_prediction(machine_id="M01", ...)
    audit_trail.log_alert(machine_id="M01", ...)
"""

import json
from datetime import datetime
from pathlib import Path
from collections import deque


class AuditTrail:

    def __init__(self, max_memory: int = 10_000):
        self._log     = deque(maxlen=max_memory)
        self._log_dir = Path("data/audit")
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Recharge le journal du jour depuis le disque pour survivre
        # à un redémarrage du serveur (le deque est sinon vide au boot).
        for entry in self.load_from_disk():
            self._log.append(entry)

    # ── Enregistrement ────────────────────────────────────────────────────────

    def log_prediction(
        self,
        machine_id      : str,
        dataset         : str,
        model_name      : str,
        prediction      : str,
        confidence      : float,
        health_index    : float,
        rul             : float = None,
        features_summary: dict  = None,
    ) -> dict:
        entry = {
            "type"            : "prediction",
            "timestamp"       : datetime.now().isoformat(),
            "machine_id"      : machine_id,
            "dataset"         : dataset,
            "model_name"      : model_name,
            "prediction"      : prediction,
            "confidence"      : round(confidence, 4) if confidence else None,
            "health_index"    : round(health_index, 2) if health_index else None,
            "rul"             : round(rul, 1) if rul is not None else None,
            "features_summary": features_summary or {},
        }
        self._log.append(entry)
        self._persist(entry)
        return entry

    def log_alert(
        self,
        machine_id  : str,
        alert_type  : str,
        message     : str,
        health_index: float,
        severity    : str = "warning",
    ) -> dict:
        entry = {
            "type"        : "alert",
            "timestamp"   : datetime.now().isoformat(),
            "machine_id"  : machine_id,
            "alert_type"  : alert_type,
            "message"     : message,
            "health_index": round(health_index, 2) if health_index else None,
            "severity"    : severity,
            "acknowledged": False,
        }
        self._log.append(entry)
        self._persist(entry)
        return entry

    def log_retrain(
        self,
        dataset      : str,
        model_name   : str,
        n_samples    : int,
        new_accuracy : float,
        triggered_by : str = "user",
        drift_score  : float = None,
    ) -> dict:
        entry = {
            "type"        : "retrain",
            "timestamp"   : datetime.now().isoformat(),
            "dataset"     : dataset,
            "model_name"  : model_name,
            "n_samples"   : n_samples,
            "new_accuracy": round(new_accuracy, 4) if new_accuracy else None,
            "triggered_by": triggered_by,
            "drift_score" : drift_score,
        }
        self._log.append(entry)
        self._persist(entry)
        return entry

    def log_drift(
        self,
        dataset  : str,
        score    : float,
        severity : str,
        n_drifted: int,
    ) -> dict:
        entry = {
            "type"    : "drift",
            "timestamp": datetime.now().isoformat(),
            "dataset" : dataset,
            "score"   : score,
            "severity": severity,
            "n_drifted_features": n_drifted,
        }
        self._log.append(entry)
        self._persist(entry)
        return entry

    # ── Lecture ───────────────────────────────────────────────────────────────

    def get_recent(self, n: int = 100, machine_id: str = None,
                   entry_type: str = None) -> list:
        entries = list(self._log)
        if machine_id:
            entries = [e for e in entries if e.get("machine_id") == machine_id]
        if entry_type:
            entries = [e for e in entries if e.get("type") == entry_type]
        return list(reversed(entries))[:n]

    def get_stats(self) -> dict:
        entries     = list(self._log)
        predictions = [e for e in entries if e.get("type") == "prediction"]
        alerts      = [e for e in entries if e.get("type") == "alert"]
        retrains    = [e for e in entries if e.get("type") == "retrain"]
        drifts      = [e for e in entries if e.get("type") == "drift"]

        return {
            "total_entries"  : len(entries),
            "n_predictions"  : len(predictions),
            "n_alerts"       : len(alerts),
            "n_retrains"     : len(retrains),
            "n_drifts"       : len(drifts),
            "machines_logged": list(set(
                e.get("machine_id") for e in entries if e.get("machine_id")
            )),
        }

    def acknowledge_alert(self, timestamp: str) -> bool:
        """Marque une alerte comme acquittée (par timestamp unique)."""
        for entry in self._log:
            if entry.get("timestamp") == timestamp and entry.get("type") == "alert":
                entry["acknowledged"] = True
                return True
        return False

    # ── Persistance ───────────────────────────────────────────────────────────

    def _persist(self, entry: dict):
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self._log_dir / f"audit_{date_str}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def load_from_disk(self, date_str: str = None) -> list:
        """Recharge un journal archivé depuis le disque."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self._log_dir / f"audit_{date_str}.jsonl"
        if not log_file.exists():
            return []
        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
        return entries


# Instance globale partagée par toute l'API
audit_trail = AuditTrail()
