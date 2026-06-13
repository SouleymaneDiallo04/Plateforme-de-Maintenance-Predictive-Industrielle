"""PrognoSense — Backend FastAPI — Version finale."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

load_dotenv()   # charge le .env automatiquement

from backend.api.routes import (
    predict, benchmark, health, simulation,
    retrain, dataset, alerts, spectral,
    kpi, fault_injection, config, copilot,
    notifications, export, docs_tech, explainability,
    kpi_real, analytics, anomaly, ingest, workorders,
    technicians
)
from backend.api.routes.auth_routes import router as auth_router
from backend.ml.model_registry import registry
from backend.ml.health_tracker import fleet_manager
from backend.ml.audit_trail import audit_trail
from backend.db.models import init_db

app = FastAPI(
    title       = "PrognoSense API",
    description = "Plateforme de Maintenance Prédictive par l'IA — ENSAM-Meknès",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:5173",
                         "http://localhost:5174",
                         "http://localhost:5175",
                         "http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

def _seed_demo_accounts():
    """
    Crée les comptes de démonstration s'ils n'existent pas : un admin et
    quatre techniciens aux compétences/certifications variées (pour illustrer
    l'affectation par compétence). Idempotent.
    """
    from backend.db.models import SessionLocal, User
    from backend.api.auth import hash_password

    demo_techs = [
        # email, nom, compétences, certif (1..4)
        ("karim@prognosense.com",   "Karim B.",   ["Roulements & montage", "Turbomachines"], 3),
        ("salma@prognosense.com",   "Salma R.",   ["Roulements & montage", "Alignement"],    2),
        ("yassine@prognosense.com", "Yassine M.", ["Engrenages / réducteurs", "Mécanique générale"], 2),
        ("omar@prognosense.com",    "Omar T.",    ["Équilibrage", "Alignement", "Mécanique générale"], 1),
        # Profils seniors / experts garantissant la couverture de TOUS les défauts
        ("fatima@prognosense.com",  "Fatima Z.",  ["Analyse vibratoire", "Roulements & montage", "Turbomachines"], 4),
        ("hicham@prognosense.com",  "Hicham A.",  ["Engrenages / réducteurs", "Analyse vibratoire"], 3),
        ("nadia@prognosense.com",   "Nadia E.",   ["Équilibrage", "Alignement", "Roulements & montage", "Mécanique générale"], 2),
    ]
    db = SessionLocal()
    try:
        created = []
        # Admin de démo
        if not db.query(User).filter(User.email == "demo@prognosense.com").first():
            db.add(User(email="demo@prognosense.com",
                        hashed_password=hash_password("Demo1234!"),
                        role="admin", name="Admin Démo"))
            created.append("admin demo@prognosense.com")
        # Techniciens de démo
        for email, name, comps, certif in demo_techs:
            if not db.query(User).filter(User.email == email).first():
                db.add(User(email=email, hashed_password=hash_password("Tech1234!"),
                            role="technicien", name=name, competences=comps,
                            certif_niveau=certif, statut="disponible"))
                created.append(name)
        db.commit()
        if created:
            print(f"  [OK] Comptes demo crees : {', '.join(created)}")
        else:
            print("  [OK] Comptes demo deja presents")
    except Exception as e:
        db.rollback()
        print(f"  [WARN] Seed comptes demo : {e}")
    finally:
        db.close()


def _seed_spare_parts():
    """Garnit le magasin de pièces de rechange (références réalistes). Idempotent.
    NSK 6207 volontairement en RUPTURE (qty 0) pour illustrer le cas « à commander »."""
    from backend.db.models import SessionLocal, SparePart

    parts = [
        # reference, designation, category, qty, location, cout
        ("SKF 6205-2RS", "Roulement à billes 25×52×15", "Roulement", 6, "Magasin A — Rayon R-03", 28.0),
        ("SKF 6203-2RS", "Roulement à billes 17×40×12", "Roulement", 4, "Magasin A — Rayon R-03", 19.0),
        ("NSK 6207",     "Roulement à billes 35×72×17", "Roulement", 0, "Magasin A — Rayon R-04", 41.0),
        ("REICH ROTEX 28", "Garniture élastomère d'accouplement", "Accouplement", 3, "Magasin B — Rayon R-11", 75.0),
        ("Pignon réducteur Z21 m3", "Pignon acier 20MnCr5, Z=21 module 3", "Engrenage", 1, "Magasin C — Rayon R-20", 240.0),
        ("Boulonnerie M16-8.8", "Kit boulonnerie palier M16 classe 8.8", "Visserie", 25, "Magasin A — Rayon R-01", 6.0),
        ("Masses d'équilibrage", "Jeu de masses correctrices d'équilibrage", "Consommable", 10, "Magasin B — Rayon R-09", 12.0),
    ]
    db = SessionLocal()
    try:
        added = 0
        for ref, desig, cat, qty, loc, cost in parts:
            if not db.query(SparePart).filter(SparePart.reference == ref).first():
                db.add(SparePart(reference=ref, designation=desig, category=cat,
                                 stock_qty=qty, location=loc, unit_cost_eur=cost))
                added += 1
        db.commit()
        print(f"  [OK] Stock magasin : {added} pieces ajoutees" if added
              else "  [OK] Stock magasin deja present")
    except Exception as e:
        db.rollback()
        print(f"  [WARN] Seed stock : {e}")
    finally:
        db.close()


@app.on_event("startup")
async def startup():
    print("=" * 50)
    print("  PrognoSense API v1.0 - Demarrage")
    print("=" * 50)

    # Initialise la base SQLite (crée les tables si absentes)
    init_db()
    print("  [OK] Base de donnees initialisee")

    _seed_demo_accounts()
    _seed_spare_parts()

    registry.load_all()

    # Charger les datasets pour le replay de signaux réels
    from backend.ml.signal_replayer import replayer
    for ds in ["cmapss", "vbl", "cwru", "mf"]:
        replayer.load_dataset(ds)

    # Flotte de démo
    demo_machines = [
        ("M01", "CWRU"),
        ("M02", "CWRU"),
        ("M03", "CWRU"),
        ("M04", "VBL"),
        ("M05", "MF"),
        ("Turbine_01", "CMAPSS"),
        ("Turbine_02", "CMAPSS"),
    ]
    for mid, ds in demo_machines:
        fleet_manager.add_machine(mid, ds)

    # Bridges IIoT (s'activent seulement si configurés)
    from backend.api.mqtt_bridge import start_mqtt_bridge
    start_mqtt_bridge()
    from backend.api.opcua_bridge import start_opcua_bridge
    start_opcua_bridge()

    print(f"\n  Flotte : {len(fleet_manager._machines)} machines initialisees")
    print("  API prete -- http://localhost:8000/docs\n")


# ── Routes ────────────────────────────────────────────────────────────────
app.include_router(predict.router,        prefix="/api")
app.include_router(benchmark.router,      prefix="/api")
app.include_router(health.router,         prefix="/api")
app.include_router(simulation.router,     prefix="/api")
app.include_router(retrain.router,        prefix="/api")
app.include_router(dataset.router,        prefix="/api")
app.include_router(alerts.router,         prefix="/api")
app.include_router(spectral.router,       prefix="/api")
app.include_router(kpi.router,            prefix="/api")
app.include_router(fault_injection.router, prefix="/api")
app.include_router(config.router,         prefix="/api")
app.include_router(copilot.router,        prefix="/api")
app.include_router(notifications.router,  prefix="/api")
app.include_router(export.router,         prefix="/api")
app.include_router(docs_tech.router,        prefix="/api")
app.include_router(explainability.router,  prefix="/api")
app.include_router(kpi_real.router,         prefix="/api")
app.include_router(analytics.router,        prefix="/api")
app.include_router(anomaly.router,          prefix="/api")
app.include_router(ingest.router,           prefix="/api")
app.include_router(workorders.router,       prefix="/api")
app.include_router(technicians.router,      prefix="/api")
app.include_router(auth_router,            prefix="/api")


# ── Routes système (drift, audit, fiabilité modèle) ───────────────────────

@app.get("/api/drift/status")
def drift_status():
    """Score de dérive par dataset (concept drift KS-test)."""
    return registry.get_drift_status()


@app.get("/api/audit/recent")
def audit_recent(n: int = 100, machine_id: str = None):
    """Journal de traçabilité des N dernières décisions IA."""
    return {
        "entries": audit_trail.get_recent(n, machine_id),
        "stats"  : audit_trail.get_stats(),
    }


@app.get("/api/audit/stats")
def audit_stats():
    """Statistiques globales de l'audit trail."""
    return audit_trail.get_stats()


@app.get("/api/model/reliability/{dataset}")
def model_reliability(dataset: str):
    """État de fiabilité complet d'un dataset (drift + modèle actif)."""
    drift = registry.get_drift_status().get(dataset, {})
    return {
        "dataset"     : dataset,
        "drift"       : drift,
        "active_model": registry.get_active_model(dataset),
        "note"        : "Calibration Platt disponible via POST /api/explain/reliability",
    }


@app.post("/api/signal/order-spectrum")
def order_spectrum(payload: dict):
    """
    Analyse d'ordre — rééchantillonnage angulaire du signal.
    Détecte les défauts indépendamment de la vitesse de rotation.

    Body: { "signal": [...], "fs": 12800, "rpm_mean": 1750,
            "rpm_signal": [...] (optionnel), "max_order": 20 }
    """
    from backend.ml.order_tracking import (
        compute_order_spectrum, extract_order_energy,
        compute_kinematic_orders
    )
    import numpy as np
    from backend.api.routes.config import load_config

    signal  = np.array(payload.get("signal", []), dtype=np.float64)
    if len(signal) == 0:
        return {"error": "Signal vide"}

    fs       = float(payload.get("fs", 12800.0))
    rpm_mean = float(payload.get("rpm_mean", 1750.0))
    rpm_sig  = payload.get("rpm_signal")
    rpm_arr  = np.array(rpm_sig, dtype=np.float64) if rpm_sig else None

    spectrum = compute_order_spectrum(
        signal=signal, rpm_signal=rpm_arr,
        fs=fs, rpm_mean=rpm_mean,
        max_order=float(payload.get("max_order", 20.0)),
    )

    # Ordres cinématiques depuis la config
    cfg    = load_config()
    bp     = cfg.get("bearing_params", {})
    orders = compute_kinematic_orders(
        shaft_freq    = bp.get("shaft_freq", 20.6),
        n_balls       = int(bp.get("n_balls", 9)),
        ball_diam     = bp.get("ball_diam", 7.94),
        pitch_diam    = bp.get("pitch_diam", 38.5),
        contact_angle = bp.get("contact_angle", 0.0),
    )

    # Énergie aux ordres défauts
    energies = {
        name: extract_order_energy(spectrum, order_val)
        for name, order_val in orders.items()
    }

    return {**spectrum, "kinematic_orders": orders, "order_energies": energies}


@app.get("/")
def root():
    return {
        "name"    : "PrognoSense API",
        "version" : "2.0.0",
        "status"  : "running",
        "docs"    : "/docs",
        "endpoints": {
            "predict"        : "/api/predict",
            "fleet"          : "/api/fleet",
            "benchmark"      : "/api/benchmark",
            "copilot"        : "/api/copilot/chat",
            "simulation"     : "ws://localhost:8000/api/ws/simulation",
            "drift"          : "/api/drift/status",
            "audit"          : "/api/audit/recent",
            "explainability" : "/api/explain/shap",
            "reliability"    : "/api/model/reliability/{dataset}",
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host    = "0.0.0.0",
        port    = 8000,
        reload  = True
    )