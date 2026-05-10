"""Routes Health Index et état des machines."""

from fastapi import APIRouter, HTTPException
from backend.ml.health_tracker import fleet_manager

router = APIRouter(tags=["Health"])


@router.get("/fleet")
def get_fleet():
    """Vue globale de la flotte — Page Accueil dashboard."""
    return fleet_manager.get_fleet_overview()


@router.get("/machine/{machine_id}")
def get_machine(machine_id: str):
    """État d'une machine spécifique."""
    machine = fleet_manager.get_machine(machine_id)
    if machine is None:
        raise HTTPException(404, f"Machine {machine_id} introuvable")
    return machine.get_current_state()


@router.get("/machine/{machine_id}/history")
def get_machine_history(machine_id: str):
    """
    Historique complet d'une machine.
    Utilisé pour la courbe de dégradation — Page Pronostic.
    """
    machine = fleet_manager.get_machine(machine_id)
    if machine is None:
        raise HTTPException(404, f"Machine {machine_id} introuvable")
    return machine.get_history()


@router.get("/alerts")
def get_alerts(severity: str = None):
    """Journal des alertes — Page Log & Maintenance."""
    return {
        "alerts": fleet_manager.get_all_alerts(severity),
        "total" : len(fleet_manager.get_all_alerts())
    }