"""Routes d'authentification — register, login, me."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.db.models import User, get_db
from backend.api.auth import (
    hash_password, verify_password,
    create_access_token, get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Authentification"])


class RegisterRequest(BaseModel):
    email    : EmailStr
    password : str
    role     : str = "user"   # "user" par défaut ; "admin" possible si autorisé


class LoginRequest(BaseModel):
    email    : EmailStr
    password : str


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, detail="Email déjà utilisé")

    # On n'accepte que "user" ou "admin"
    role = req.role if req.role in ("user", "admin") else "user"

    user = User(
        email           = req.email,
        hashed_password = hash_password(req.password),
        role            = role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.email, "role": user.role})
    return {
        "access_token": token,
        "token_type"  : "bearer",
        "user"        : {"id": user.id, "email": user.email, "role": user.role},
    }


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(403, detail="Compte désactivé")

    token = create_access_token({"sub": user.email, "role": user.role})
    return {
        "access_token": token,
        "token_type"  : "bearer",
        "user"        : {"id": user.id, "email": user.email, "role": user.role},
    }


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
