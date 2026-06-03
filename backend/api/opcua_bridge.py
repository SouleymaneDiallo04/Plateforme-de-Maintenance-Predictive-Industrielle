"""
Bridge OPC-UA → ingestion (le protocole standard de l'automatisme industriel).

Activé UNIQUEMENT si `OPC_UA_ENDPOINT` est défini (sinon silencieux). Se
connecte à un serveur OPC-UA (automate, passerelle, système d'acquisition),
lit périodiquement un nœud contenant la forme d'onde vibratoire, et la
pousse dans le même pipeline que /api/ingest/signal.

Variables d'env :
  OPC_UA_ENDPOINT       ex. opc.tcp://192.168.0.10:4840/
  OPC_UA_SIGNAL_NODE    NodeId du tableau de mesure, ex. "ns=2;s=VibrationSignal"
  OPC_UA_MACHINE_ID     identifiant machine (défaut OPCUA_MACHINE)
  OPC_UA_FS             fréquence d'échantillonnage (défaut 12800)
  OPC_UA_INTERVAL       période de lecture en s (défaut 5)
  OPC_UA_MACHINE_CLASS  classe ISO 10816 (défaut II)
  OPC_UA_INPUT_UNIT     'g' ou 'm/s2' (défaut g)
"""

import os
import time
import threading


def start_opcua_bridge():
    endpoint = os.getenv("OPC_UA_ENDPOINT", "").strip()
    if not endpoint:
        print("  OPC-UA bridge: désactivé (OPC_UA_ENDPOINT non défini)")
        return
    threading.Thread(target=_run, args=(endpoint,), daemon=True).start()


def _run(endpoint: str):
    try:
        from asyncua.sync import Client
    except ImportError:
        print("  OPC-UA bridge: asyncua non installé (pip install asyncua)")
        return

    node_id   = os.getenv("OPC_UA_SIGNAL_NODE", "").strip()
    machine   = os.getenv("OPC_UA_MACHINE_ID", "OPCUA_MACHINE")
    fs        = float(os.getenv("OPC_UA_FS", "12800"))
    interval  = float(os.getenv("OPC_UA_INTERVAL", "5"))
    mclass    = os.getenv("OPC_UA_MACHINE_CLASS", "II")
    unit      = os.getenv("OPC_UA_INPUT_UNIT", "g")

    while True:
        client = None
        try:
            client = Client(endpoint)
            client.connect()
            node = client.get_node(node_id)
            print(f"  [OK] OPC-UA bridge connecté {endpoint} — nœud {node_id}")
            while True:
                try:
                    value = node.read_value()
                    signal = list(value) if value is not None else []
                    if len(signal) >= 64:
                        from backend.api.routes.ingest import ingest_signal, IngestSignal
                        ingest_signal(IngestSignal(
                            machine_id    = machine,
                            signal        = [float(v) for v in signal],
                            fs            = fs,
                            input_unit    = unit,
                            machine_class = mclass,
                        ))
                except Exception as e:
                    print(f"  OPC-UA bridge: lecture ignorée ({e})")
                time.sleep(interval)
        except Exception as e:
            print(f"  OPC-UA bridge: connexion échouée ({e}) — nouvel essai dans 10 s")
            time.sleep(10)
        finally:
            try:
                if client:
                    client.disconnect()
            except Exception:
                pass
