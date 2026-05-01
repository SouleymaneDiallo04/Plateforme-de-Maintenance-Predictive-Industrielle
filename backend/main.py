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
    notifications, export, docs_tech
)
from backend.ml.model_registry import registry
from backend.ml.health_tracker import fleet_manager

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
                         "http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

@app.on_event("startup")
async def startup():
    print("=" * 50)
    print("  PrognoSense API v1.0 — Démarrage")
    print("=" * 50)

    registry.load_all()

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

    print(f"\n  Flotte : {len(fleet_manager._machines)} machines initialisées")
    print("  API prête — http://localhost:8000/docs\n")


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
app.include_router(docs_tech.router,      prefix="/api")

@app.get("/")
def root():
    return {
        "name"    : "PrognoSense API",
        "version" : "1.0.0",
        "status"  : "running",
        "docs"    : "/docs",
        "endpoints": {
            "predict"    : "/api/predict",
            "fleet"      : "/api/fleet",
            "benchmark"  : "/api/benchmark",
            "copilot"    : "/api/copilot/chat",
            "simulation" : "ws://localhost:8000/ws/simulation",
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host    = "0.0.0.0",
        port    = 8000,
        reload  = True
    )