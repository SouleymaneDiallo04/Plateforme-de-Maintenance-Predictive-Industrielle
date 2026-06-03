"""
Bridge MQTT → ingestion (transport IIoT le plus répandu sur le terrain).

Activé UNIQUEMENT si `MQTT_BROKER` est défini dans l'environnement (sinon
silencieux). Souscrit à un topic et transfère chaque message JSON vers le
même pipeline que /api/ingest/signal. Une passerelle edge publie ainsi ses
mesures sans appeler le REST.

Format de message attendu (JSON) :
  { "machine_id": "...", "signal": [...], "fs": 12800,
    "input_unit": "g", "rpm": 1750, "machine_class": "II" }

Variables d'env : MQTT_BROKER, MQTT_PORT (1883), MQTT_TOPIC
(prognosense/+/signal), MQTT_USER, MQTT_PASSWORD.
"""

import os
import json


def start_mqtt_bridge():
    broker = os.getenv("MQTT_BROKER", "").strip()
    if not broker:
        print("  MQTT bridge: désactivé (MQTT_BROKER non défini)")
        return

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("  MQTT bridge: paho-mqtt non installé (pip install paho-mqtt)")
        return

    port  = int(os.getenv("MQTT_PORT", "1883"))
    topic = os.getenv("MQTT_TOPIC", "prognosense/+/signal")

    def on_connect(client, userdata, flags, reason_code, properties=None):
        client.subscribe(topic)
        print(f"  [OK] MQTT bridge connecté {broker}:{port} — topic '{topic}'")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            from backend.api.routes.ingest import ingest_signal, IngestSignal
            ingest_signal(IngestSignal(**payload))
        except Exception as e:
            print(f"  MQTT bridge: message ignoré ({e})")

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except Exception:
        client = mqtt.Client()  # compat anciennes versions

    user = os.getenv("MQTT_USER", "").strip()
    if user:
        client.username_pw_set(user, os.getenv("MQTT_PASSWORD", ""))

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker, port, 60)
        client.loop_start()   # thread de fond non bloquant
    except Exception as e:
        print(f"  MQTT bridge: connexion échouée ({e})")
