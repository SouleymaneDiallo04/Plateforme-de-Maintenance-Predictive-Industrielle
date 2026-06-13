"""KPIs industriels — MTBF, MTTR, MTTF, OEE."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import numpy as np
from datetime import datetime, timedelta
from backend.ml.health_tracker import fleet_manager

router = APIRouter(tags=["KPIs"])


def compute_kpis(alerts: list,
                 total_hours: float,
                 repair_times: List[float] = None) -> dict:
    """
    Calcule les KPIs de maintenance à partir de l'historique.

    MTBF = Total operating time / Number of failures
    MTTR = Total repair time / Number of repairs
    MTTF = Total time / Number of failures (pour composants non réparables)
    Availability = MTBF / (MTBF + MTTR)
    OEE  = Availability × Performance × Quality
    """
    # Compter les pannes (alertes critiques)
    n_failures = len([a for a in alerts if 'rouge' in a.get('type','')
                      or 'critique' in a.get('type','')])
    n_failures = max(1, n_failures)   # éviter division par zéro

    # MTBF
    mtbf = total_hours / n_failures

    # MTTR (estimation si pas de données réelles)
    if repair_times and len(repair_times) > 0:
        mttr = np.mean(repair_times)
    else:
        mttr = 4.0   # 4h par défaut

    # MTTF
    mttf = total_hours / n_failures

    # Disponibilité
    availability = mtbf / (mtbf + mttr) * 100

    # OEE simplifié (sans données de production réelles)
    performance  = min(100, availability * 1.02)
    quality      = 98.5   # valeur typique industrie
    oee          = (availability/100) * (performance/100) * (quality/100) * 100

    # Fiabilité (probabilité de fonctionner sans panne pendant T heures)
    # Modèle exponentiel : R(t) = e^(-t/MTBF)
    t_mission = 24   # 24 heures de mission
    reliability = np.exp(-t_mission / mtbf) * 100

    return {
        "MTBF"        : round(mtbf, 2),
        "MTTR"        : round(mttr, 2),
        "MTTF"        : round(mttf, 2),
        "availability": round(availability, 2),
        "reliability" : round(reliability, 2),
        "OEE"         : round(oee, 2),
        "n_failures"  : n_failures,
        "total_hours" : total_hours,
        "unit"        : "heures"
    }


@router.get("/kpi/{machine_id}")
def get_machine_kpi(machine_id: str,
                     total_hours: float = 720.0):
    """
    KPIs d'une machine spécifique.
    total_hours : durée totale d'observation (défaut 720h = 1 mois)
    """
    machine = fleet_manager.get_machine(machine_id)
    if machine is None:
        raise HTTPException(404, f"Machine {machine_id} introuvable")

    alerts = machine._alerts
    kpis   = compute_kpis(alerts, total_hours)

    # Tendance de dégradation
    history  = machine.get_history()
    hi_vals  = history.get('health_index', [])
    rul_vals = [r for r in history.get('rul', []) if r is not None]

    # Cycles restants avant intervention :
    #   1) machine avec pronostic RUL (turbomoteur) → la RUL réelle restante ;
    #   2) sinon, estimation par la pente du Health Index (si dégradation) ;
    #   3) sinon None — pas de dégradation détectée, on n'invente pas de chiffre
    #      (plutôt que l'ancien sentinel « 9999 » qui s'affichait en dur).
    cycles_to_maintenance = None
    if rul_vals:
        cycles_to_maintenance = int(round(rul_vals[-1]))
    elif len(hi_vals) > 10:
        slope      = float(np.polyfit(range(len(hi_vals)), hi_vals, 1)[0])
        current_hi = hi_vals[-1]
        if slope < -0.01 and current_hi > 20:
            cycles_to_maintenance = max(0, int((current_hi - 20) / abs(slope)))

    return {
        "machine_id"            : machine_id,
        "kpis"                  : kpis,
        "cycles_to_maintenance" : cycles_to_maintenance,
        "current_health_index"  : hi_vals[-1] if hi_vals else 100,
        "trend"                 : machine._compute_trend(),
    }


@router.get("/kpi/fleet/overview")
def get_fleet_kpi(total_hours: float = 720.0):
    """KPIs agrégés de toute la flotte avec comparaison."""
    fleet_kpis = {}
    for mid, machine in fleet_manager._machines.items():
        alerts = machine._alerts
        kpis   = compute_kpis(alerts, total_hours)
        fleet_kpis[mid] = {
            "kpis"   : kpis,
            "status" : machine.get_current_state()['status']
        }

    # Agrégation
    all_kpis   = [v['kpis'] for v in fleet_kpis.values()]
    avg_mtbf   = np.mean([k['MTBF']   for k in all_kpis])
    avg_oee    = np.mean([k['OEE']    for k in all_kpis])
    avg_avail  = np.mean([k['availability'] for k in all_kpis])

    return {
        "machines"       : fleet_kpis,
        "fleet_averages" : {
            "MTBF"        : round(float(avg_mtbf),  2),
            "OEE"         : round(float(avg_oee),   2),
            "availability": round(float(avg_avail), 2),
        }
    }