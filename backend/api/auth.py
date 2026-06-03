"""
Authentification JWT — PrognoSense.

Flux :
  1. POST /api/auth/register  → crée un compte (email + mot de passe hashé bcrypt)
  2. POST /api/auth/login     → vérifie les identifiants, retourne un JWT signé
  3. Chaque requête protégée → le middleware vérifie le JWT via get_current_user()

Variables d'environnement :
  JWT_SECRET_KEY   : clé de signature (obligatoire en prod, défaut dev fourni)
  JWT_EXPIRE_HOURS : durée du token en heures (défaut 24)
"""

import os
import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.db.models import User, get_db

# Silence le warning cosmétique passlib↔bcrypt 4.x
# ("module 'bcrypt' has no attribute '__about__'") — bcrypt fonctionne normalement.
logging.getLogger("passlib").setLevel(logging.ERROR)

# ── Configuration ─────────────────────────────────────────────────────────────

SECRET_KEY      = os.getenv("JWT_SECRET_KEY", "prognosense-dev-secret-change-in-prod-2024")
ALGORITHM       = "HS256"
EXPIRE_HOURS    = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security    = HTTPBearer(auto_error=False)


# ── Utilitaires mot de passe ──────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Utilitaires JWT ───────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── Dépendances FastAPI ───────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
) -> dict:
    """Valide le JWT et retourne {"email": ..., "role": ..., "id": ...}."""
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Token d'authentification requis",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        email: str = payload.get("sub")
        if not email:
            raise ValueError("sub manquant")
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable ou désactivé")

    return {"id": user.id, "email": user.email, "role": user.role}


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Restreint l'accès aux admins uniquement."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Droits administrateur requis")
    return current_user


def optional_auth(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db),
) -> dict | None:
    """Authentification optionnelle — retourne le user dict ou None."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        email   = payload.get("sub")
        user    = db.query(User).filter(User.email == email).first()
        if user and user.is_active:
            return {"id": user.id, "email": user.email, "role": user.role}
    except Exception:
        pass
    return None
