"""
Modèles SQLAlchemy — PrognoSense.

Usage :
    from backend.db.models import Base, MachineState, Alert, DiagnosticLog, ModelMetadata
    engine = create_engine("sqlite:///data/prognosense.db")   # SQLite par défaut
    Base.metadata.create_all(engine)

Pour PostgreSQL :
    engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///data/prognosense.db"))
"""

from sqlalchemy import Column, Float, String, DateTime, Integer, JSON, Text, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class MachineState(Base):
    __tablename__ = "machine_states"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    machine_id    = Column(String(64), index=True, nullable=False)
    timestamp     = Column(DateTime, index=True, default=datetime.utcnow)
    health_index  = Column(Float)
    rul_pred      = Column(Float)
    anomaly_score = Column(Float)
    fault_label   = Column(String(128))
    dataset       = Column(String(32))
    cycle         = Column(Integer)
    confidence    = Column(Float)


class Alert(Base):
    __tablename__ = "alerts"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    machine_id   = Column(String(64), index=True, nullable=False)
    timestamp    = Column(DateTime, index=True, default=datetime.utcnow)
    alert_type   = Column(String(32))
    message      = Column(Text)
    health_index = Column(Float)
    rul          = Column(Float)
    acknowledged = Column(Integer, default=0)


class DiagnosticLog(Base):
    __tablename__ = "diagnostic_logs"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(64), index=True)
    timestamp  = Column(DateTime, default=datetime.utcnow)
    fault      = Column(String(128))
    confidence = Column(Float)
    severity   = Column(String(32))
    model_used = Column(String(64))
    features   = Column(JSON)


class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    id                  = Column(Integer, primary_key=True, autoincrement=True)
    model_name          = Column(String(64))
    dataset             = Column(String(32))
    trained_at          = Column(DateTime, default=datetime.utcnow)
    accuracy            = Column(Float)
    n_samples           = Column(Integer)
    false_positive_rate = Column(Float)
    version             = Column(Integer, default=1)


class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role          = Column(String(32), default="user", nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class MaintenanceEvent(Base):
    """
    Événements de maintenance réels saisis par les opérateurs.
    Source de vérité pour les KPIs réels (MTBF, MTTR, disponibilité, ROI)
    et pour mesurer l'efficacité prédictive (alerte vs panne effective).
    """
    __tablename__ = "maintenance_events"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    machine_id     = Column(String(64), index=True, nullable=False)
    event_type     = Column(String(30), index=True)   # failure | corrective | planned
    started_at     = Column(DateTime, index=True, nullable=False)
    ended_at       = Column(DateTime)
    duration_hours = Column(Float)
    fault_type     = Column(String(128))
    technician     = Column(String(128))
    parts_replaced = Column(JSON)
    cost_euros     = Column(Float)
    notes          = Column(Text)
    created_at     = Column(DateTime, default=datetime.utcnow)


class ModelVersion(Base):
    """
    Versioning des modèles (MLOps basique) : chaque réentraînement crée
    une version, on peut revenir (rollback) à une version antérieure.
    """
    __tablename__ = "model_versions"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    dataset       = Column(String(32), index=True, nullable=False)
    model_name    = Column(String(64), index=True, nullable=False)
    version       = Column(Integer, nullable=False)
    trained_at    = Column(DateTime, default=datetime.utcnow)
    accuracy      = Column(Float)
    f1_score      = Column(Float)
    n_samples     = Column(Integer)
    n_classes     = Column(Integer)
    file_path     = Column(String(255))
    is_active     = Column(Boolean, default=False)
    triggered_by  = Column(String(32))   # user | drift | scheduled
    drift_score_at_trigger = Column(Float)
    notes         = Column(Text)


class AlertVerdict(Base):
    """
    Verdict d'un analyste sur une alerte (human-in-the-loop) :
    vrai positif (panne confirmée) ou faux positif (fausse alerte).
    Permet de calculer le VRAI taux de fausses alarmes — le KPI que tout
    acheteur de PdM exige (un système qui crie au loup est désinstallé).
    """
    __tablename__ = "alert_verdicts"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    alert_id   = Column(Integer, index=True)
    machine_id = Column(String(64), index=True)
    verdict    = Column(String(16))   # true_positive | false_positive
    analyst    = Column(String(128))
    comment    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkOrder(Base):
    """
    Ordre de travail — boucle fermée maintenance. Créé automatiquement sur
    alerte critique (ou manuellement), poussable vers une GMAO externe
    (SAP PM / Maximo / Infor) via webhook configurable.
    """
    __tablename__ = "work_orders"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    machine_id    = Column(String(64), index=True, nullable=False)
    created_at    = Column(DateTime, index=True, default=datetime.utcnow)
    priority      = Column(String(16))   # P1 | P2 | P3
    status        = Column(String(16), default="open", index=True)  # open|in_progress|closed
    title         = Column(String(200))
    description   = Column(Text)
    fault         = Column(String(128))
    iso_zone      = Column(String(4))
    health_index  = Column(Float)
    source        = Column(String(16), default="auto")   # auto | manual
    cmms_ref      = Column(String(64))                    # id externe GMAO
    pushed_to_cmms = Column(Boolean, default=False)
    closed_at     = Column(DateTime)


# ── Connexion ────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/prognosense.db")

_is_sqlite = "sqlite" in DATABASE_URL
engine     = create_engine(
    DATABASE_URL,
    # timeout = busy timeout du driver sqlite3 (attend le verrou au lieu d'échouer)
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
)

# WAL + busy_timeout : lecteurs et un écrivain peuvent coexister sans
# « database is locked » (concurrence simulation WS / events / versioning).
if _is_sqlite:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    """Crée toutes les tables si elles n'existent pas."""
    Base.metadata.create_all(engine)


def get_db():
    """Dépendance FastAPI — session SQLAlchemy par requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
