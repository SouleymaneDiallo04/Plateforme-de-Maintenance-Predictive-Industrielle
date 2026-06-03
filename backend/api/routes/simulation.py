"""
Simulation temps réel multi-machines via WebSocket.
Chaque connexion WebSocket peut cibler n'importe quelle machine
et n'importe quel dataset.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio, numpy as np, pickle, json, uuid
from pathlib import Path
from backend.ml.model_registry import registry
from backend.ml.health_tracker import fleet_manager
from backend.ml.health_index import compute_health_index
from backend.api.routes.fault_injection import apply_fault_injection
from backend.api.routes.config import load_config
from backend.ml.audit_trail import audit_trail
from backend.ml.signal_replayer import replayer
import math



router = APIRouter(tags=["Simulation"])


# ── ConnectionManager — gestion N connexions WebSocket simultanées ─────────

class ConnectionManager:
    """
    Gère plusieurs connexions WebSocket en parallèle.
    Chaque connexion maintient son propre état (machine, dataset, vitesse).
    """

    def __init__(self):
        # {conn_id: {"ws": websocket, "state": state_dict}}
        self._connections: dict = {}

    async def connect(self, ws: WebSocket, conn_id: str, initial_state: dict):
        await ws.accept()
        self._connections[conn_id] = {"ws": ws, "state": initial_state}

    def disconnect(self, conn_id: str):
        self._connections.pop(conn_id, None)

    def get_state(self, conn_id: str) -> dict:
        return self._connections.get(conn_id, {}).get("state", {})

    async def broadcast_fleet(self, payload: dict):
        """Envoie un message à toutes les connexions actives."""
        dead = []
        for conn_id, conn in list(self._connections.items()):
            try:
                await conn["ws"].send_json(payload)
            except Exception:
                dead.append(conn_id)
        for conn_id in dead:
            self.disconnect(conn_id)

    @property
    def n_connections(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


# ── Chargement des datasets en mémoire au démarrage ───────────────────────
_datasets = {}

def load_simulation_data():
    """Charge tous les datasets pour la simulation."""
    global _datasets
    base = Path("data/processed")

    for name in ["cmapss", "vbl", "cwru", "mf"]:
        try:
            X = np.load(base / f"X_{name}.npy")
            with open(base / f"y_{name}.pkl", "rb") as f:
                y = pickle.load(f)
            with open(base / f"meta_{name}.pkl", "rb") as f:
                meta = pickle.load(f)
            _datasets[name.upper()] = {"X": X, "y": y, "meta": meta}
            print(f"  Dataset {name.upper()} chargé pour simulation")
        except Exception as e:
            print(f"  Dataset {name} non disponible : {e}")


def clean_nan(value):
    """Remplace NaN par None (qui sera sérialisé en null)."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


# ── Générateur de signal vibratoire réaliste ──────────────────────────────
def generate_signal_from_features(features, hi, shaft_freq=20.6, n_points=2048):
    """
    Signal de 2048 points calibré sur les features réelles via le SignalReplayer
    (RMS/Kurtosis réels → amplitude + impulsions), puis injection de défaut éventuelle.
    """
    sig = replayer.signal_from_features(features, hi, shaft_freq, n_points=n_points)
    sig = apply_fault_injection(np.asarray(sig, dtype=np.float64), shaft_freq=shaft_freq)
    return sig.tolist()


@router.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    """
    WebSocket principal de simulation.

    Commandes acceptées depuis le frontend :
      { action: 'play' }
      { action: 'pause' }
      { action: 'reset' }
      { action: 'set_speed', speed: 0.5 }
      { action: 'set_machine', machine_id: 'M01', dataset: 'CWRU' }
      { action: 'set_unit', unit_id: '5' }    ← pour CMAPSS
    """
    conn_id = str(uuid.uuid4())

    # État isolé par connexion
    initial_state = {
        "running"    : True,
        "speed"      : 0.5,
        "machine_id" : "Turbine_01",
        "dataset"    : "CMAPSS",
        "unit_id"    : None,
        "idx"        : 0,
        "prev_hi"    : None,
    }

    await manager.connect(websocket, conn_id, initial_state)
    state = manager.get_state(conn_id)

    # Charger les données si pas encore fait
    if not _datasets:
        load_simulation_data()

    def get_unit_indices(dataset: str, unit_id: str) -> list:
        """Retourne les indices triés par cycle pour un dataset/unité."""
        ds_data = _datasets.get(dataset, {})
        meta    = ds_data.get("meta", [])

        if dataset == "CMAPSS":
            indices = [
                i for i, m in enumerate(meta)
                if str(m.get("unit_id", "")) == str(unit_id)
            ]
            indices.sort(key=lambda i: meta[i].get("cycle", 0))
        else:
            indices = list(range(len(meta)))

        return indices

    def pick_default_unit(dataset: str) -> str:
        """Choisit une unité par défaut pour le dataset."""
        ds_data = _datasets.get(dataset, {})
        meta    = ds_data.get("meta", [])
        if not meta:
            return "0"
        if dataset == "CMAPSS":
            units = list(set(str(m.get("unit_id", "1")) for m in meta))
            return sorted(units)[0]
        return "0"

    # Initialisation
    if state["unit_id"] is None:
        state["unit_id"] = pick_default_unit(state["dataset"])

    unit_indices = get_unit_indices(state["dataset"], state["unit_id"])

    try:
        while True:
            # ── Lire les commandes du frontend ────────────────────────────
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.01
                )
                cmd = json.loads(raw)
                action = cmd.get("action", "")

                if action == "play":
                    state["running"] = True
                elif action == "pause":
                    state["running"] = False
                elif action == "reset":
                    state["idx"] = 0
                    machine = fleet_manager.get_machine(state["machine_id"])
                    if machine:
                        machine._hi_history.clear()
                        machine._rul_history.clear()
                        machine._anomaly_history.clear()
                elif action == "set_speed":
                    state["speed"] = float(cmd.get("speed", 0.5))
                elif action == "set_machine":
                    # Changer de machine
                    new_mid = cmd.get("machine_id", state["machine_id"])
                    new_ds  = cmd.get("dataset", state["dataset"])
                    state["machine_id"] = new_mid
                    state["dataset"]    = new_ds
                    state["unit_id"]    = cmd.get(
                        "unit_id",
                        pick_default_unit(new_ds)
                    )
                    state["idx"]        = 0
                    unit_indices        = get_unit_indices(
                        state["dataset"], state["unit_id"]
                    )
                    # Créer la machine si elle n'existe pas
                    if not fleet_manager.get_machine(new_mid):
                        fleet_manager.add_machine(new_mid, new_ds)
                elif action == "set_unit":
                    state["unit_id"] = str(cmd.get("unit_id", "1"))
                    state["idx"]     = 0
                    unit_indices     = get_unit_indices(
                        state["dataset"], state["unit_id"]
                    )

            except asyncio.TimeoutError:
                pass

            # ── Pause ─────────────────────────────────────────────────────
            if not state["running"]:
                await asyncio.sleep(0.1)
                continue

            # ── Fin de cycle ──────────────────────────────────────────────
            if state["idx"] >= len(unit_indices):
                state["idx"] = 0
                await websocket.send_json({
                    "type"      : "simulation_end",
                    "machine_id": state["machine_id"],
                    "message"   : "Cycle de simulation terminé — redémarrage"
                })
                continue

            # ── Données du cycle courant ──────────────────────────────────
            ds_data   = _datasets.get(state["dataset"], {})
            X         = ds_data.get("X")
            y_list    = ds_data.get("y", [])
            meta_list = ds_data.get("meta", [])

            if X is None or len(unit_indices) == 0:
                await asyncio.sleep(0.5)
                continue

            data_idx  = unit_indices[state["idx"]]
            X_cycle   = X[data_idx : data_idx + 1]
            meta      = meta_list[data_idx] if data_idx < len(meta_list) else {}
            y_label   = y_list[data_idx] if data_idx < len(y_list) else "unknown"
            rul_true  = meta.get("rul", None)
            cycle     = meta.get("cycle", state["idx"])

            # ── Prédictions réelles depuis les modèles ────────────────────
            try:
                pred_result = registry.predict(state["dataset"], X_cycle)
            except Exception:
                pred_result = {}

            try:
                anomaly_result = registry.predict_anomaly(
                    state["dataset"], X_cycle
                )
            except Exception:
                anomaly_result = {"anomaly_score": 50.0, "is_anomaly": False}

            # ── Health Index réel ─────────────────────────────────────────
            raw_hi = compute_health_index(
                anomaly_score = anomaly_result.get("anomaly_score", 50.0),
                rul = rul_true,
                rul_max = 125.0,
            )

# Lissage exponentiel : 85% ancienne valeur + 15% nouvelle valeur
            if state["prev_hi"] is None:
                state["prev_hi"] = raw_hi["health_index"]
            smoothed = 0.85 * state["prev_hi"] + 0.15 * raw_hi["health_index"]
            state["prev_hi"] = smoothed

            hi_result = {**raw_hi, "health_index": round(smoothed, 2)}

            # ── Mise à jour HealthTracker ─────────────────────────────────
            machine = fleet_manager.get_machine(state["machine_id"])
            if machine is None:
                machine = fleet_manager.add_machine(
                    state["machine_id"], state["dataset"]
                )

            # Lire les paramètres depuis la config
            cfg        = load_config()
            shaft_freq = cfg.get("bearing_params", {}).get("shaft_freq", 20.6)

            # Générer signal depuis les features réelles
            signal = generate_signal_from_features(
                X_cycle[0], hi_result["health_index"], shaft_freq
            )

            signal_np = np.array(signal, dtype=np.float64)
            from scipy.stats import kurtosis as scipy_kurtosis, skew as scipy_skew
            rms_val   = float(np.sqrt(np.mean(signal_np**2)))
            kurt_val  = float(scipy_kurtosis(signal_np, fisher=True))
            skew_val  = float(scipy_skew(signal_np))
            peak_val  = float(np.max(np.abs(signal_np)))
            p2p_val   = float(np.max(signal_np) - np.min(signal_np))
            std_val   = float(np.std(signal_np))
            crest_val = float(peak_val / (rms_val + 1e-10))

            features_payload = {
                "RMS"         : round(rms_val,  6),
                "Kurtosis"    : round(kurt_val, 4),
                "Skewness"    : round(skew_val, 4),
                "Peak"        : round(peak_val, 6),
                "Peak_to_Peak": round(p2p_val,  6),
                "Crest_Factor": round(crest_val, 4),
                "Std"         : round(std_val,  6),
                "Kurtosis_flag": "anomalie" if kurt_val > 4 else "normal",
            }

            # Stocker le signal dans le tracker
            machine.update_signal(np.array(signal), 12800.0)

            update = machine.update(
                health_index  = hi_result["health_index"],
                anomaly_score = anomaly_result.get("anomaly_score", 50.0),
                rul           = rul_true,
                cycle         = cycle,
            )


            # ── Payload complet vers le frontend ─────────────────────────
            payload = {
                "type"          : "cycle_update",
                "machine_id"    : state["machine_id"],
                "dataset"       : state["dataset"],
                "unit_id"       : state["unit_id"],
                "cycle"         : int(cycle) if cycle else state["idx"],
                "y_true"        : y_label,
                "rul_true"      : clean_nan(float(rul_true)) if rul_true is not None else None,
                "rul_pred"      : clean_nan(pred_result.get("rul_pred")),
                "health_index"  : clean_nan(float(hi_result["health_index"])),
                "status"        : hi_result["status"],
                "color"         : hi_result["color"],
                "action"        : hi_result["action"],
                "anomaly_score" : clean_nan(float(anomaly_result.get("anomaly_score", 0))),
                "is_anomaly"    : bool(anomaly_result.get("is_anomaly", False)),
                "anomaly_ensemble": anomaly_result.get("ensemble"),
                "prediction"    : pred_result.get("predictions", [y_label])[0]
                                  if pred_result.get("predictions") else y_label,
                "confidence"    : clean_nan(pred_result.get("confidence")),
                "trend"         : update["trend"],
                "new_alerts"    : update["new_alerts"],
                "signal"        : signal,
                "features"      : {k: clean_nan(v) for k, v in features_payload.items()},
                "progress"      : {
                    "current": state["idx"] + 1,
                    "total"  : len(unit_indices),
                    "pct"    : round(
                        (state["idx"] + 1) / max(1, len(unit_indices)) * 100,
                        1
                    ),
                },
            }
            await websocket.send_json(payload)

            # Enregistrer dans l'audit trail tous les 5 cycles
            if state["idx"] % 5 == 0:
                audit_trail.log_prediction(
                    machine_id       = state["machine_id"],
                    dataset          = state["dataset"],
                    model_name       = registry.get_active_model(state["dataset"]),
                    prediction       = str(payload["prediction"]),
                    confidence       = payload["confidence"] or 0.0,
                    health_index     = payload["health_index"] or 0.0,
                    rul              = payload.get("rul_pred"),
                    features_summary = {k: v for k, v in features_payload.items()
                                        if isinstance(v, (int, float))},
                )
                for alert in update.get("new_alerts", []):
                    audit_trail.log_alert(
                        machine_id   = state["machine_id"],
                        alert_type   = alert.get("type", "unknown"),
                        message      = alert.get("message", ""),
                        health_index = payload["health_index"] or 0.0,
                    )

                # Persistance SQL via le repository (best-effort — ne doit jamais
                # casser le flux WS). Alimente l'historique persisté en base.
                try:
                    from backend.db.models import SessionLocal
                    from backend.db.repository import MachineRepository
                    _db = SessionLocal()
                    try:
                        repo = MachineRepository(_db)
                        repo.save_state(
                            machine_id    = state["machine_id"],
                            dataset       = state["dataset"],
                            health_index  = payload["health_index"],
                            rul_pred      = payload.get("rul_pred"),
                            anomaly_score = payload.get("anomaly_score"),
                            fault_label   = str(payload["prediction"]),
                            confidence    = payload["confidence"],
                            cycle         = int(cycle) if cycle else state["idx"],
                        )
                        for alert in update.get("new_alerts", []):
                            repo.save_alert(
                                machine_id   = state["machine_id"],
                                alert_type   = alert.get("type", "unknown"),
                                message      = alert.get("message", ""),
                                health_index = payload["health_index"],
                                rul          = alert.get("rul"),
                            )
                    finally:
                        _db.close()
                except Exception:
                    pass

            state["idx"] += 1
            await asyncio.sleep(state["speed"])

    except WebSocketDisconnect:
        print(f"WebSocket déconnecté — machine {state.get('machine_id', '?')} (conn={conn_id[:8]})")
    except Exception as e:
        print(f"Erreur WebSocket [{conn_id[:8]}] : {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        manager.disconnect(conn_id)


@router.get("/simulation/units")
def get_available_units():
    """Liste des unités disponibles par dataset."""
    if not _datasets:
        load_simulation_data()

    result = {}
    for ds_name, ds_data in _datasets.items():
        meta = ds_data.get("meta", [])
        if ds_name == "CMAPSS":
            units = sorted(set(
                str(m.get("unit_id", "")) for m in meta
            ))
        else:
            units = ["all"]
        result[ds_name] = units

    return {"datasets": result}


@router.get("/replay/{dataset}/{idx}")
def replay_signal(dataset: str, idx: int):
    """
    Rejoue un signal calibré sur les vraies features d'un dataset (par index).
    Remplace la sinusoïde générique par un signal réaliste reconstruit.
    """
    if not replayer.datasets_loaded:
        for ds in ["cmapss", "vbl", "cwru", "mf"]:
            replayer.load_dataset(ds)
    result = replayer.replay_index(dataset, idx)
    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(404, result["error"])
    return result