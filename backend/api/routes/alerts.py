# backend/api/routes/alerts.py
from fastapi import APIRouter
from backend.ml.health_tracker import fleet_manager

router = APIRouter(tags=["Alertes"])

@router.get("/alerts")
def get_alerts():
    return {"alerts": fleet_manager.get_all_alerts()}