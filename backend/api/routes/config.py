"""Fenêtre de configuration globale."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict
import json
from pathlib import Path

router = APIRouter(tags=["Configuration"])

CONFIG_FILE = Path("data/config.json")

# Configuration par défaut
DEFAULT_CONFIG = {
    "n_sensors"       : 3,
    "n_machines"      : 5,
    "sampling_rate"   : 12800,
    "simulation_speed": 0.5,
    "alert_thresholds": {
        "green" : 70,
        "yellow": 40,
        "orange": 20,
    },
    "autoencoder_thresholds": {
        "VBL"   : 50,
        "CWRU"  : 60,    # relevé pour réduire FP
        "MF"    : 50,
        "CMAPSS": 65,    # relevé pour réduire 19% FP
    },
    "bearing_params": {
        "shaft_freq"    : 20.6,
        "n_balls"       : 9,
        "ball_diam"     : 7.94,
        "pitch_diam"    : 38.5,
        "contact_angle" : 0.0,
    },
    "notifications": {
        "email_enabled" : False,
        "email_address" : "",
        "smtp_server"   : "smtp.gmail.com",
        "smtp_port"     : 587,
    }
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


@router.get("/config")
def get_config():
    return load_config()


@router.post("/config/update")
def update_config(updates: Dict):
    cfg = load_config()
    cfg.update(updates)
    save_config(cfg)
    return {"message": "Configuration mise à jour", "config": cfg}


@router.post("/config/reset")
def reset_config():
    save_config(DEFAULT_CONFIG)
    return {"message": "Configuration réinitialisée", "config": DEFAULT_CONFIG}