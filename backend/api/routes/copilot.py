"""
LLM Copilot — API Mistral (mistral.ai)
Modèle : mistral-large-latest (ou mistral-small-latest pour économiser)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import httpx, os
from datetime import datetime
from backend.ml.health_tracker import fleet_manager
from backend.ml.model_registry import registry

router = APIRouter(tags=["Copilot LLM"])

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL   = "mistral-large-latest"   # ou "mistral-small-latest"


class ChatRequest(BaseModel):
    message    : str
    machine_id : Optional[str] = None
    history    : Optional[List[dict]] = []


def build_system_prompt() -> str:
    """Construit le prompt système avec le contexte temps réel."""
    fleet    = fleet_manager.get_fleet_overview()
    machines = fleet.get("machines", [])

    machines_summary = "\n".join([
        f"  - {m['machine_id']}: HI={m['health_index']}%, "
        f"statut={m['status']}, RUL={m.get('rul','N/A')} cycles"
        for m in machines[:10]
    ]) or "  Aucune machine active"

    alerts_recent = fleet_manager.get_all_alerts()[:5]
    alerts_summary = "\n".join([
        f"  [{a['timestamp'][:16]}] {a['machine_id']}: {a['message']}"
        for a in alerts_recent
    ]) or "  Aucune alerte récente"

    active_models = {
        ds: registry.get_active_model(ds)
        for ds in ['VBL', 'CWRU', 'MF', 'CMAPSS']
    }

    return (
        "Tu es PrognoSense Copilot, un expert en maintenance prédictive "
        "industrielle. Tu analyses en temps réel les données de "
        f"{fleet.get('n_machines', 0)} machines surveillées.\n\n"
        "ÉTAT ACTUEL DE LA FLOTTE :\n"
        f"{machines_summary}\n\n"
        "KPIs GLOBAUX :\n"
        f"  Machines saines     : {fleet.get('n_healthy', 0)}\n"
        f"  En surveillance     : {fleet.get('n_surveillance', 0)}\n"
        f"  En alerte           : {fleet.get('n_alert', 0)}\n"
        f"  Critiques           : {fleet.get('n_critical', 0)}\n"
        f"  Health Index moyen  : {fleet.get('avg_health_index', 0)}%\n"
        f"  RUL minimale flotte : {fleet.get('min_rul', 'N/A')} cycles\n\n"
        "DERNIÈRES ALERTES :\n"
        f"{alerts_summary}\n\n"
        f"MODÈLES IA ACTIFS : {active_models}\n\n"
        "INSTRUCTIONS :\n"
        "- Réponds en français, de façon concise et actionnable\n"
        "- Propose toujours une action concrète\n"
        "- Justifie tes recommandations avec les données disponibles\n"
        "- Pour les fiches d'intervention utilise ce format :\n"
        "  MACHINE | DÉFAUT | SÉVÉRITÉ | ACTION | DÉLAI\n"
    )


async def call_mistral(messages: list, system: str) -> str:
    """Appelle l'API Mistral et retourne la réponse texte."""
    api_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            500,
            "MISTRAL_API_KEY non configurée. "
            "Obtenez une clé sur https://console.mistral.ai"
        )

    # Construire la liste de messages avec le system en premier
    full_messages = [{"role": "system", "content": system}] + messages

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            MISTRAL_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type" : "application/json",
            },
            json={
                "model"      : MISTRAL_MODEL,
                "messages"   : full_messages,
                "max_tokens" : 1000,
                "temperature": 0.3,
            }
        )

    if response.status_code == 401:
        raise HTTPException(401, "Clé API Mistral invalide")
    if response.status_code == 429:
        raise HTTPException(429, "Quota API Mistral dépassé")
    if response.status_code != 200:
        raise HTTPException(500,
            f"Erreur API Mistral ({response.status_code}): {response.text[:200]}"
        )

    data = response.json()
    return data["choices"][0]["message"]["content"]


def build_rag_context(query: str) -> tuple:
    """Récupère la documentation technique pertinente (normes, défauts)."""
    try:
        from backend.ml.rag import knowledge_base
        docs = knowledge_base.retrieve(query, k=3)
    except Exception:
        docs = []
    if not docs:
        return "", []
    block = "\n\n".join(
        f"[{d['source']} — {d['title']}]\n{d['text']}" for d in docs
    )
    context = (
        "\n\nDOCUMENTATION TECHNIQUE PERTINENTE "
        "(appuie-toi dessus et cite les normes/signatures quand c'est utile) :\n"
        + block
    )
    sources = [{"source": d["source"], "title": d["title"], "score": d["score"]} for d in docs]
    return context, sources


@router.post("/copilot/chat")
async def chat(req: ChatRequest):
    """Chat avec le Copilot — contexte flotte + documentation (RAG) injectés."""
    # Construire le contexte machine si fourni
    user_content = req.message
    if req.machine_id:
        machine = fleet_manager.get_machine(req.machine_id)
        if machine:
            state = machine.get_current_state()
            user_content += (
                f"\n\n[Contexte machine {req.machine_id}]\n"
                f"Health Index : {state['health_index']}%\n"
                f"Statut       : {state['status']}\n"
                f"RUL estimée  : {state.get('rul', 'N/A')}\n"
                f"Tendance     : {state['trend']['description']}\n"
                f"Diagnostics  : {state.get('last_diagnosis', {})}"
            )

    # Documentation pertinente (RAG)
    rag_context, sources = build_rag_context(req.message)

    # Construire l'historique
    messages = list(req.history or [])
    messages.append({"role": "user", "content": user_content})

    reply = await call_mistral(messages, build_system_prompt() + rag_context)

    return {
        "reply"    : reply,
        "model"    : MISTRAL_MODEL,
        "sources"  : sources,      # documentation citée (traçabilité de la réponse)
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/copilot/report/{machine_id}")
async def generate_report(machine_id: str):
    """Génère une fiche d'intervention pour une machine."""
    machine = fleet_manager.get_machine(machine_id)
    if not machine:
        raise HTTPException(404, f"Machine {machine_id} introuvable")

    state   = machine.get_current_state()
    diag    = state.get("last_diagnosis") or {}
    trend   = state.get("trend", {})

    prompt = (
        f"Génère une fiche d'intervention de maintenance complète "
        f"pour la machine {machine_id}.\n\n"
        f"Données actuelles :\n"
        f"- Health Index    : {state['health_index']}%\n"
        f"- Statut          : {state['status']}\n"
        f"- RUL estimée     : {state.get('rul', 'N/A')} cycles\n"
        f"- Tendance        : {trend.get('description', 'N/A')}\n"
        f"- Défaut détecté  : {diag.get('fault', 'N/A')}\n"
        f"- Sévérité        : {diag.get('severity', 'N/A')}\n\n"
        "La fiche doit contenir :\n"
        "1. Résumé de l'état\n"
        "2. Défaut(s) détecté(s) et niveau de confiance\n"
        "3. Causes probables\n"
        "4. Actions recommandées (priorité, délai, ressources)\n"
        "5. Risques si non-intervention\n"
        "6. Prochaine inspection recommandée\n\n"
        "Format professionnel et concis."
    )

    messages = [{"role": "user", "content": prompt}]
    reply    = await call_mistral(messages, build_system_prompt())

    return {
        "machine_id": machine_id,
        "reply"     : reply,
        "timestamp" : datetime.now().isoformat(),
    }


@router.post("/copilot/risk-analysis")
async def risk_analysis(machine_id: str, delay_cycles: int = 10):
    """Analyse le risque d'un report d'intervention."""
    machine = fleet_manager.get_machine(machine_id)
    if not machine:
        raise HTTPException(404, f"Machine {machine_id} introuvable")

    state = machine.get_current_state()
    rul   = state.get("rul")
    hi    = state["health_index"]
    trend = state["trend"]

    prompt = (
        f"Analyse le risque de reporter l'intervention sur la machine "
        f"{machine_id} de {delay_cycles} cycles.\n\n"
        f"État actuel :\n"
        f"- Health Index : {hi}%\n"
        f"- RUL estimée  : {rul} cycles\n"
        f"- Tendance     : {trend['description']} "
        f"({trend['slope']:.3f}%/cycle)\n\n"
        "Réponds à :\n"
        f"1. Le report de {delay_cycles} cycles est-il risqué ?\n"
        f"2. HI et RUL estimés après {delay_cycles} cycles ?\n"
        f"3. Probabilité de panne dans ce délai ?\n"
        "4. Recommandation finale."
    )

    messages = [{"role": "user", "content": prompt}]
    reply    = await call_mistral(messages, build_system_prompt())

    return {
        "machine_id"   : machine_id,
        "delay_cycles" : delay_cycles,
        "reply"        : reply,
        "timestamp"    : datetime.now().isoformat(),
    }