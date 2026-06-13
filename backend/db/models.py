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
    role          = Column(String(32), default="user", nullable=False)  # user|admin|technicien
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    # ── Profil technicien (affectation par compétence) ────────────────────────
    name          = Column(String(128))           # nom affiché
    competences   = Column(JSON)                   # liste de compétences (référentiel)
    certif_niveau = Column(Integer)                # certification ISO 18436 (1..4)
    statut        = Column(String(16), default="disponible")  # disponible|occupe|absent


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
    # Cycle de vie : open(créé) | assigned | in_progress | on_hold | done | closed
    status        = Column(String(16), default="open", index=True)
    title         = Column(String(200))
    description   = Column(Text)
    fault         = Column(String(128))
    iso_zone      = Column(String(4))
    health_index  = Column(Float)
    source        = Column(String(16), default="auto")   # auto | manual
    cmms_ref      = Column(String(64))                    # id externe GMAO
    pushed_to_cmms = Column(Boolean, default=False)
    closed_at     = Column(DateTime)
    # ── Affectation à un technicien (par compétence) ──────────────────────────
    assigned_to       = Column(Integer, index=True)   # users.id du technicien
    assigned_to_name  = Column(String(128))           # nom dénormalisé (affichage)
    competence_requise = Column(String(64))
    certif_requise    = Column(Integer)
    assigned_at       = Column(DateTime)
    started_at        = Column(DateTime)
    completed_at      = Column(DateTime)
    verified_at       = Column(DateTime)
    # ── Élément défaillant explicite + pièce de rechange (stock magasin) ───────
    failing_element   = Column(String(200))   # ex. « Roulement SKF 6205-2RS — bague interne »
    part_reference    = Column(String(64))     # référence catalogue de la pièce
    part_designation  = Column(String(128))    # désignation lisible (depuis le stock)
    part_in_stock     = Column(Boolean)        # None = sans pièce / N/A
    part_stock_qty    = Column(Integer)        # quantité disponible au moment de la création
    part_location     = Column(String(64))     # emplacement magasin


class SparePart(Base):
    """
    Pièce de rechange tenue au magasin de l'usine. Permet d'indiquer, dès la
    création de l'ordre de travail, si la pièce nécessaire est disponible en
    stock (et où), ou si elle est en rupture (à commander).
    """
    __tablename__ = "spare_parts"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    reference     = Column(String(64), unique=True, index=True, nullable=False)
    designation   = Column(String(128))
    category      = Column(String(48))
    stock_qty     = Column(Integer, default=0)
    location      = Column(String(64))         # emplacement magasin (rayon)
    unit_cost_eur = Column(Float)
    updated_at    = Column(DateTime, default=datetime.utcnow)


class InterventionReport(Base):
    """
    Compte-rendu d'intervention (CRI) rédigé par le technicien à la clôture
    de son travail. Source de vérité « terrain » : il re-nourrit
    automatiquement les KPIs réels (via MaintenanceEvent) et le taux de
    fausses alarmes (via AlertVerdict), et constitue à terme une étiquette
    vérifiée pour le réentraînement (apprentissage actif).
    """
    __tablename__ = "intervention_reports"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    workorder_id    = Column(Integer, index=True, nullable=False)
    machine_id      = Column(String(64), index=True)
    technicien_id   = Column(Integer, index=True)
    technicien_name = Column(String(128))
    cause_racine    = Column(Text)
    actions         = Column(Text)
    pieces          = Column(JSON)            # pièces remplacées
    temps_passe_h   = Column(Float)           # durée réelle (heures)
    defaut_confirme = Column(Boolean)         # le défaut prédit était-il réel ?
    cost_euros      = Column(Float)
    created_at      = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """
    Notification destinée à un utilisateur (technicien affecté, admin à
    informer d'une intervention terminée…). Matérialise « le technicien
    reçoit le message » et le suivi côté admin.
    """
    __tablename__ = "notifications"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, index=True, nullable=False)
    workorder_id = Column(Integer, index=True)
    type         = Column(String(32))     # assignment | completed | verified | info
    message      = Column(Text)
    lu           = Column(Boolean, default=False, index=True)
    created_at   = Column(DateTime, index=True, default=datetime.utcnow)


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


def _migrate_sqlite():
    """
    Migration légère SQLite : `create_all` crée les tables manquantes mais
    n'ajoute PAS les colonnes nouvelles à une table existante. On ajoute donc
    les colonnes manquantes via ALTER TABLE (idempotent, best-effort).
    """
    if not _is_sqlite:
        return
    new_columns = {
        "users": {
            "name"         : "VARCHAR(128)",
            "competences"  : "JSON",
            "certif_niveau": "INTEGER",
            "statut"       : "VARCHAR(16)",
        },
        "work_orders": {
            "assigned_to"       : "INTEGER",
            "assigned_to_name"  : "VARCHAR(128)",
            "competence_requise": "VARCHAR(64)",
            "certif_requise"    : "INTEGER",
            "assigned_at"       : "DATETIME",
            "started_at"        : "DATETIME",
            "completed_at"      : "DATETIME",
            "verified_at"       : "DATETIME",
            "failing_element"   : "VARCHAR(200)",
            "part_reference"    : "VARCHAR(64)",
            "part_designation"  : "VARCHAR(128)",
            "part_in_stock"     : "BOOLEAN",
            "part_stock_qty"    : "INTEGER",
            "part_location"     : "VARCHAR(64)",
        },
    }
    with engine.begin() as conn:
        for table, cols in new_columns.items():
            try:
                existing = {row[1] for row in conn.exec_driver_sql(
                    f"PRAGMA table_info({table})")}
            except Exception:
                continue  # table absente → create_all s'en chargera
            for name, ddl_type in cols.items():
                if name not in existing:
                    try:
                        conn.exec_driver_sql(
                            f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}")
                    except Exception:
                        pass


def init_db():
    """Crée toutes les tables si elles n'existent pas, puis migre les colonnes."""
    Base.metadata.create_all(engine)
    _migrate_sqlite()


def get_db():
    """Dépendance FastAPI — session SQLAlchemy par requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
