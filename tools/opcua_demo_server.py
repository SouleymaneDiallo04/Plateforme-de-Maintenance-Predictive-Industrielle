"""
Serveur OPC-UA de DÉMONSTRATION.

Simule un automate / système d'acquisition exposant un nœud de mesure
vibratoire, pour tester de bout en bout le connecteur OPC-UA de PrognoSense
sans matériel réel.

Lancer :
    venv\\Scripts\\python.exe tools\\opcua_demo_server.py

Puis configurer le bridge (dans .env ou variables d'env) :
    OPC_UA_ENDPOINT=opc.tcp://localhost:4840/prognosense/
    OPC_UA_SIGNAL_NODE=ns=2;s=VibrationSignal
    OPC_UA_MACHINE_ID=POMPE_OPCUA
"""

import time
import numpy as np
from asyncua.sync import Server, ua

FS = 12800
N = 2048


def make_signal(faulty: bool) -> list:
    t = np.arange(N) / FS
    if faulty:
        sig = 0.6 * np.sin(2 * np.pi * 30 * t) + 0.3 * np.sin(2 * np.pi * 60 * t)
        idx = np.random.choice(N, 30, replace=False)
        sig[idx] += np.random.exponential(1.5, 30)
        sig += np.random.normal(0, 0.05, N)
    else:
        sig = 0.05 * np.sin(2 * np.pi * 30 * t) + np.random.normal(0, 0.01, N)
    return [float(v) for v in sig]


def main():
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/prognosense/")
    server.set_server_name("PrognoSense Demo OPC-UA")
    idx = server.register_namespace("prognosense")

    machine = server.nodes.objects.add_object(idx, "Machine")
    signal_node = machine.add_variable(
        ua.NodeId("VibrationSignal", idx), "VibrationSignal",
        ua.Variant(make_signal(False), ua.VariantType.Double),
    )
    signal_node.set_writable()

    server.start()
    print("Serveur OPC-UA démo démarré :")
    print("  endpoint : opc.tcp://localhost:4840/prognosense/")
    print(f"  nœud     : ns={idx};s=VibrationSignal")
    print("  (Ctrl+C pour arrêter)")

    cycle = 0
    try:
        while True:
            # alterne : surtout sain, puis un défaut tous les 4 cycles
            faulty = (cycle % 4 == 3)
            signal_node.write_value(
                ua.Variant(make_signal(faulty), ua.VariantType.Double)
            )
            print(f"  cycle {cycle} publié ({'DÉFAUT' if faulty else 'sain'})")
            cycle += 1
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        print("Serveur arrêté.")


if __name__ == "__main__":
    main()
