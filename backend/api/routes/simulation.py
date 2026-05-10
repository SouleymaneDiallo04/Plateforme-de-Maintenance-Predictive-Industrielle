"""
Simulation temps réel multi-machines via WebSocket.
Chaque connexion WebSocket peut cibler n'importe quelle machine
et n'importe quel dataset.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio, numpy as np, pickle, json
from pathlib import Path
from backend.ml.model_registry import registry
from backend.ml.health_tracker import fleet_manager
from backend.ml.health_index import compute_health_index
from backend.api.routes.fault_injection import apply_fault_injection
from backend.api.routes.config import load_config
from scipy.stats import kurtosis as scipy_kurtosis, skew as scipy_skew
import math



router = APIRouter(tags=["Simulation"])

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
    """Génère un signal de 2048 points — suffisant pour FFT avec bonne résolution."""
    t   = np.linspace(0, n_points / 12800, n_points)
    rms = max(0.05, abs(float(features[0]))) if len(features) > 0 else 1.0
    amp = rms * np.sqrt(2)

    degradation = max(0, 1.0 - hi / 100.0)

    # Composante fondamentale
    sig = amp * np.sin(2 * np.pi * shaft_freq * t)

    # Harmoniques proportionnelles à la dégradation
    sig += degradation * amp * 0.4 * np.sin(2 * np.pi * shaft_freq * 2 * t)
    sig += degradation * amp * 0.2 * np.sin(2 * np.pi * shaft_freq * 3 * t)
    sig += degradation * amp * 0.1 * np.sin(2 * np.pi * shaft_freq * 4 * t)

    # Bruit gaussien
    noise_lvl = 0.05 + degradation * 0.25
    sig += np.random.normal(0, noise_lvl * amp, n_points)

    # Injection de défaut
    sig = apply_fault_injection(sig, shaft_freq=shaft_freq)

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
    await websocket.accept()

    # État de la session WebSocket
    state = {
        "running"    : True,
        "speed"      : 0.5,
        "machine_id" : "Turbine_01",
        "dataset"    : "CMAPSS",
        "unit_id"    : None,
        "idx"        : 0,
        "prev_hi"    : None,   # ← ajout
    }

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

            state["idx"] += 1
            await asyncio.sleep(state["speed"])

    except WebSocketDisconnect:
        print(f"WebSocket déconnecté — machine {state['machine_id']}")
    except Exception as e:
        print(f"Erreur WebSocket : {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


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