"""Injection de défauts simulés avec gestion de durée."""

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional
import numpy as np
import asyncio
from backend.api.auth import require_admin

router = APIRouter(tags=["Injection de défauts"])

_injection_state = {
    "active"         : False,
    "fault_type"     : None,
    "intensity"      : 0.0,
    "remaining_cycles": 0,
    "total_cycles"   : 0,
}


class InjectionRequest(BaseModel):
    fault_type : str
    intensity  : float      # 0.0 à 1.0
    duration   : int = 50   # nombre de cycles avant arrêt automatique


@router.post("/inject/fault", dependencies=[Depends(require_admin)])
def inject_fault(req: InjectionRequest,
                  background_tasks: BackgroundTasks):
    """Injecte un défaut simulé pour N cycles."""
    _injection_state.update({
        "active"          : True,
        "fault_type"      : req.fault_type,
        "intensity"       : max(0.0, min(1.0, req.intensity)),
        "remaining_cycles": req.duration,
        "total_cycles"    : req.duration,
    })

    effects = {
        "imbalance"    : "Pic amplifié à 1×f0",
        "misalignment" : "Pics à 2×f0 et 3×f0",
        "bearing_outer": "Pic à BPFO + bruit impulsionnel",
        "bearing_inner": "Pic à BPFI + bruit impulsionnel",
        "looseness"    : "Harmoniques sous-multiples + largebande",
        "gear_wear"    : "GMF et sidebands amplifiés",
    }
    return {
        "message"  : f"Défaut '{req.fault_type}' injecté pour "
                     f"{req.duration} cycles",
        "effect"   : effects.get(req.fault_type, "Défaut générique"),
        "state"    : _injection_state
    }


@router.post("/inject/stop", dependencies=[Depends(require_admin)])
def stop_injection():
    _injection_state.update({
        "active"          : False,
        "fault_type"      : None,
        "intensity"       : 0.0,
        "remaining_cycles": 0,
        "total_cycles"    : 0,
    })
    return {"message": "Injection arrêtée", "state": _injection_state}


@router.get("/inject/status")
def injection_status():
    return _injection_state


def apply_fault_injection(signal: np.ndarray,
                            shaft_freq: float = 20.6) -> np.ndarray:
    """
    Applique le défaut sur le signal et décrémente le compteur de cycles.
    Arrêt automatique quand remaining_cycles atteint 0.
    """
    if not _injection_state["active"]:
        return signal

    # Décrémenter le compteur
    _injection_state["remaining_cycles"] -= 1
    if _injection_state["remaining_cycles"] <= 0:
        _injection_state["active"]    = False
        _injection_state["fault_type"] = None
        _injection_state["intensity"] = 0.0
        return signal

    fault  = _injection_state["fault_type"]
    intens = _injection_state["intensity"]
    n      = len(signal)
    t      = np.linspace(0, n / 12800, n)
    out    = signal.copy().astype(np.float64)

    if fault == "imbalance":
        out += intens * 2.0 * np.sin(2 * np.pi * shaft_freq * t)

    elif fault == "misalignment":
        out += intens * 1.5 * np.sin(2 * np.pi * shaft_freq * 2 * t)
        out += intens * 0.8 * np.sin(2 * np.pi * shaft_freq * 3 * t)

    elif fault == "bearing_outer":
        bpfo  = shaft_freq * 3.5
        out  += intens * 1.2 * np.sin(2 * np.pi * bpfo * t)
        # Impulsions aléatoires à la période BPFO
        period_samples = int(12800 / bpfo)
        for k in range(0, n, period_samples):
            if k < n:
                out[k] += intens * 3.0 * np.random.exponential(1.0)

    elif fault == "bearing_inner":
        bpfi  = shaft_freq * 5.4
        out  += intens * 1.2 * np.sin(2 * np.pi * bpfi * t)
        period_samples = int(12800 / bpfi)
        for k in range(0, n, period_samples):
            if k < n:
                out[k] += intens * 3.0 * np.random.exponential(1.0)

    elif fault == "looseness":
        # Sous-harmoniques + bruit large bande
        out += intens * 0.8 * np.sin(2 * np.pi * shaft_freq * 0.5 * t)
        out += intens * np.random.exponential(1.5, n) * \
               np.sign(np.random.randn(n))

    elif fault == "gear_wear":
        gmf   = shaft_freq * 20
        out  += intens * 1.0 * np.sin(2 * np.pi * gmf * t)
        out  += intens * 0.4 * np.sin(2 * np.pi * (gmf + shaft_freq) * t)
        out  += intens * 0.4 * np.sin(2 * np.pi * (gmf - shaft_freq) * t)

    return out.astype(np.float32)