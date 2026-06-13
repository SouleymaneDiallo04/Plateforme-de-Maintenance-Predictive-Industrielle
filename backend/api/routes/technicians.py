"""
Gestion des techniciens et affectation des interventions — PrognoSense.

Ferme la dernière boucle de la maintenance : une fois qu'une panne est
prédite et qu'un ordre de travail (OT) est créé, l'admin AFFECTE un
technicien QUALIFIÉ (compétence + certification ISO 18436), qui reçoit la
mission, l'exécute, et rédige un compte-rendu. Ce compte-rendu re-nourrit
automatiquement les KPIs réels (MaintenanceEvent) et le taux de fausses
alarmes (AlertVerdict).

Flux :
  admin  : liste techniciens, candidats qualifiés, affectation, vérification
  techn. : « mes interventions », démarrage, clôture + compte-rendu (CRI)
  tous   : notifications
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.db.models import (
    get_db, User, WorkOrder, Notification, InterventionReport,
    MaintenanceEvent, AlertVerdict, SparePart,
)
from backend.api.auth import get_current_user, require_admin, hash_password
from backend.api.routes.workorders import _serialize as serialize_wo
from backend.competency import (
    COMPETENCES, CERTIF_LABELS, certif_label,
    required_competency, evaluate_candidate,
)

router = APIRouter(tags=["Techniciens & interventions"])

_ACTIVE_STATES = ("assigned", "in_progress", "on_hold")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _charge(db: Session, tech_id: int) -> int:
    """Nombre d'OT actifs (non terminés) affectés à un technicien."""
    return (db.query(WorkOrder)
            .filter(WorkOrder.assigned_to == tech_id,
                    WorkOrder.status.in_(_ACTIVE_STATES))
            .count())


def _tech_dict(db: Session, u: User) -> dict:
    return {
        "id"           : u.id,
        "name"         : u.name or u.email.split("@")[0],
        "email"        : u.email,
        "competences"  : u.competences or [],
        "certif_niveau": u.certif_niveau,
        "certif_label" : certif_label(u.certif_niveau),
        "statut"       : u.statut or "disponible",
        "charge"       : _charge(db, u.id),
    }


def _wo_requirements(wo: WorkOrder) -> tuple:
    """Compétence + certification requises d'un OT (recalculées si absentes)."""
    if wo.competence_requise and wo.certif_requise:
        return wo.competence_requise, wo.certif_requise
    req = required_competency(wo.fault, priority=wo.priority, iso_zone=wo.iso_zone)
    return req["competence"], req["certif_requise"]


def _notify(db: Session, user_id: int, wo_id: Optional[int],
            ntype: str, message: str):
    db.add(Notification(user_id=user_id, workorder_id=wo_id,
                        type=ntype, message=message))


# ── Référentiel (pour les formulaires frontend) ───────────────────────────────

@router.get("/competency/referential")
def competency_referential():
    """Référentiel de compétences + niveaux de certification ISO 18436."""
    return {
        "competences"  : COMPETENCES,
        "certif_levels": [{"value": k, "label": v} for k, v in CERTIF_LABELS.items()],
    }


# ── Techniciens (admin) ───────────────────────────────────────────────────────

class TechnicianCreate(BaseModel):
    email         : EmailStr
    password      : str
    name          : Optional[str] = None
    competences   : List[str] = []
    certif_niveau : int = 1
    statut        : str = "disponible"


class TechnicianUpdate(BaseModel):
    name          : Optional[str] = None
    competences   : Optional[List[str]] = None
    certif_niveau : Optional[int] = None
    statut        : Optional[str] = None


@router.get("/technicians")
def list_technicians(db: Session = Depends(get_db),
                     _: dict = Depends(get_current_user)):
    """Liste des techniciens avec leur charge actuelle (accessible à tous les connectés)."""
    techs = (db.query(User)
             .filter(User.role == "technicien", User.is_active == True)  # noqa: E712
             .order_by(User.name.asc()).all())
    return {"technicians": [_tech_dict(db, t) for t in techs]}


@router.post("/technicians", status_code=201)
def create_technician(req: TechnicianCreate, db: Session = Depends(get_db),
                      _: dict = Depends(require_admin)):
    """Crée un compte technicien (admin)."""
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email déjà utilisé")
    u = User(
        email           = req.email,
        hashed_password = hash_password(req.password),
        role            = "technicien",
        name            = req.name or req.email.split("@")[0],
        competences     = req.competences,
        certif_niveau   = req.certif_niveau,
        statut          = req.statut,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _tech_dict(db, u)


@router.patch("/technicians/{tech_id}")
def update_technician(tech_id: int, req: TechnicianUpdate,
                      db: Session = Depends(get_db),
                      _: dict = Depends(require_admin)):
    """Met à jour le profil d'un technicien (compétences, certif, statut)."""
    u = db.query(User).filter(User.id == tech_id, User.role == "technicien").first()
    if not u:
        raise HTTPException(404, "Technicien introuvable")
    if req.name is not None:          u.name = req.name
    if req.competences is not None:   u.competences = req.competences
    if req.certif_niveau is not None: u.certif_niveau = req.certif_niveau
    if req.statut is not None:        u.statut = req.statut
    db.commit()
    db.refresh(u)
    return _tech_dict(db, u)


# ── Candidats à une affectation (admin) ───────────────────────────────────────

@router.get("/workorders/{wo_id}/candidates")
def workorder_candidates(wo_id: int, db: Session = Depends(get_db),
                         _: dict = Depends(get_current_user)):
    """
    Techniciens candidats pour un OT, classés par qualification.
    L'admin choisit (affectation manuelle assistée par compétence).
    """
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Ordre de travail introuvable")

    comp_req, certif_req = _wo_requirements(wo)
    techs = (db.query(User)
             .filter(User.role == "technicien", User.is_active == True)  # noqa: E712
             .all())

    out = []
    for t in techs:
        charge = _charge(db, t.id)
        ev = evaluate_candidate(t.competences, t.certif_niveau, t.statut,
                                charge, comp_req, certif_req)
        out.append({**_tech_dict(db, t), **ev})

    # Tri : qualifiés d'abord, puis disponibles, puis charge croissante
    out.sort(key=lambda c: (not c["qualified"], not c["available"],
                            c["charge"], -(c["certif_niveau"] or 0)))
    return {
        "workorder_id"      : wo.id,
        "competence_requise": comp_req,
        "certif_requise"    : certif_req,
        "certif_requise_label": certif_label(certif_req),
        "candidates"        : out,
    }


# ── Affectation (admin) ───────────────────────────────────────────────────────

class AssignRequest(BaseModel):
    technicien_id : int


@router.post("/workorders/{wo_id}/assign")
def assign_workorder(wo_id: int, req: AssignRequest,
                     db: Session = Depends(get_db),
                     _: dict = Depends(require_admin)):
    """Affecte un OT à un technicien et le notifie."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Ordre de travail introuvable")
    if wo.status == "closed":
        raise HTTPException(400, "OT déjà clôturé")

    tech = db.query(User).filter(User.id == req.technicien_id,
                                 User.role == "technicien").first()
    if not tech:
        raise HTTPException(404, "Technicien introuvable")

    comp_req, certif_req = _wo_requirements(wo)
    wo.competence_requise = comp_req
    wo.certif_requise     = certif_req
    wo.assigned_to        = tech.id
    wo.assigned_to_name   = tech.name or tech.email.split("@")[0]
    wo.status             = "assigned"
    wo.assigned_at        = datetime.utcnow()

    _notify(db, tech.id, wo.id, "assignment",
            f"Nouvelle intervention {wo.priority} sur {wo.machine_id} — "
            f"{wo.fault or 'défaut'} (compétence : {comp_req}).")
    db.commit()
    db.refresh(wo)
    return serialize_wo(wo)


# ── Côté technicien ───────────────────────────────────────────────────────────

@router.get("/me/workorders")
def my_workorders(status: Optional[str] = None,
                  db: Session = Depends(get_db),
                  user: dict = Depends(get_current_user)):
    """OT affectés à l'utilisateur courant (le technicien connecté)."""
    q = db.query(WorkOrder).filter(WorkOrder.assigned_to == user["id"])
    if status:
        q = q.filter(WorkOrder.status == status)
    rows = q.order_by(WorkOrder.assigned_at.desc().nullslast()).all()
    return {"work_orders": [serialize_wo(w) for w in rows]}


def _owns_or_admin(wo: WorkOrder, user: dict):
    if user["role"] != "admin" and wo.assigned_to != user["id"]:
        raise HTTPException(403, "Cet ordre de travail ne vous est pas affecté")


@router.post("/workorders/{wo_id}/start")
def start_workorder(wo_id: int, db: Session = Depends(get_db),
                    user: dict = Depends(get_current_user)):
    """Le technicien démarre son intervention."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Ordre de travail introuvable")
    _owns_or_admin(wo, user)
    if wo.status not in ("assigned", "open", "on_hold"):
        raise HTTPException(400, f"Transition invalide depuis « {wo.status} »")
    wo.status     = "in_progress"
    wo.started_at = wo.started_at or datetime.utcnow()
    db.commit()
    db.refresh(wo)
    return serialize_wo(wo)


class CompleteRequest(BaseModel):
    cause_racine    : Optional[str] = None
    actions         : Optional[str] = None
    pieces          : List[str] = []
    temps_passe_h   : Optional[float] = None
    defaut_confirme : Optional[bool] = None
    cost_euros      : Optional[float] = None


@router.post("/workorders/{wo_id}/complete")
def complete_workorder(wo_id: int, req: CompleteRequest,
                       db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    """
    Le technicien clôt son intervention en rédigeant le compte-rendu (CRI).
    Effets de bord (la boucle vertueuse) :
      - MaintenanceEvent  → alimente MTBF / MTTR / disponibilité réels
      - AlertVerdict      → alimente le taux de fausses alarmes
      - Notification admin
    """
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Ordre de travail introuvable")
    _owns_or_admin(wo, user)
    if wo.status in ("closed",):
        raise HTTPException(400, "OT déjà clôturé")

    now      = datetime.utcnow()
    tech_name = wo.assigned_to_name or user.get("email", "technicien")

    # 1) Compte-rendu d'intervention
    report = InterventionReport(
        workorder_id    = wo.id,
        machine_id      = wo.machine_id,
        technicien_id   = wo.assigned_to,
        technicien_name = tech_name,
        cause_racine    = req.cause_racine,
        actions         = req.actions,
        pieces          = req.pieces,
        temps_passe_h   = req.temps_passe_h,
        defaut_confirme = req.defaut_confirme,
        cost_euros      = req.cost_euros,
    )
    db.add(report)

    # 2) Transition OT → terminé (en attente de vérification admin)
    wo.status       = "done"
    wo.completed_at = now

    # 3) Événement de maintenance réel → KPIs (MTBF/MTTR/disponibilité)
    started = wo.started_at or wo.assigned_at or wo.created_at or now
    duration = req.temps_passe_h
    if duration is None and started:
        duration = round((now - started).total_seconds() / 3600.0, 2)
    db.add(MaintenanceEvent(
        machine_id     = wo.machine_id,
        event_type     = "corrective",
        started_at     = started,
        ended_at       = now,
        duration_hours = duration,
        fault_type     = wo.fault,
        technician     = tech_name,
        parts_replaced = req.pieces,
        cost_euros     = req.cost_euros,
        notes          = (req.cause_racine or "") + (
                          f" — {req.actions}" if req.actions else ""),
    ))

    # 4) Verdict (vrai/faux positif) → taux de fausses alarmes
    if req.defaut_confirme is not None:
        db.add(AlertVerdict(
            machine_id = wo.machine_id,
            verdict    = "true_positive" if req.defaut_confirme else "false_positive",
            analyst    = tech_name,
            comment    = req.cause_racine,
        ))

    # 5) Décrément du stock magasin si une pièce a été consommée
    if wo.part_reference:
        sp = db.query(SparePart).filter(SparePart.reference == wo.part_reference).first()
        if sp and (sp.stock_qty or 0) > 0:
            sp.stock_qty = sp.stock_qty - 1

    # 6) Notifier les admins
    for adm in db.query(User).filter(User.role == "admin",
                                     User.is_active == True).all():  # noqa: E712
        _notify(db, adm.id, wo.id, "completed",
                f"Intervention terminée sur {wo.machine_id} par {tech_name} — "
                f"à vérifier.")

    db.commit()
    db.refresh(wo)
    return {"work_order": serialize_wo(wo), "report_id": report.id}


# ── Vérification / clôture (admin) ────────────────────────────────────────────

@router.post("/workorders/{wo_id}/verify")
def verify_workorder(wo_id: int, db: Session = Depends(get_db),
                     _: dict = Depends(require_admin)):
    """L'admin vérifie l'intervention et clôture définitivement l'OT."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(404, "Ordre de travail introuvable")
    if wo.status != "done":
        raise HTTPException(400, "L'OT doit être terminé avant vérification")
    now = datetime.utcnow()
    wo.status      = "closed"
    wo.verified_at = now
    wo.closed_at   = now
    if wo.assigned_to:
        _notify(db, wo.assigned_to, wo.id, "verified",
                f"Votre intervention sur {wo.machine_id} a été validée et clôturée.")
    db.commit()
    db.refresh(wo)
    return serialize_wo(wo)


@router.get("/workorders/{wo_id}/report")
def get_report(wo_id: int, db: Session = Depends(get_db),
               _: dict = Depends(get_current_user)):
    """Compte-rendu d'intervention d'un OT (s'il existe)."""
    r = (db.query(InterventionReport)
         .filter(InterventionReport.workorder_id == wo_id)
         .order_by(InterventionReport.created_at.desc()).first())
    if not r:
        return {"report": None}
    return {"report": {
        "id"             : r.id,
        "workorder_id"   : r.workorder_id,
        "machine_id"     : r.machine_id,
        "technicien_name": r.technicien_name,
        "cause_racine"   : r.cause_racine,
        "actions"        : r.actions,
        "pieces"         : r.pieces or [],
        "temps_passe_h"  : r.temps_passe_h,
        "defaut_confirme": r.defaut_confirme,
        "cost_euros"     : r.cost_euros,
        "created_at"     : r.created_at.isoformat() if r.created_at else None,
    }}


# ── Notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications")
def list_notifications(unread_only: bool = False, limit: int = 50,
                       db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    """Notifications de l'utilisateur courant (+ compteur non lues)."""
    q = db.query(Notification).filter(Notification.user_id == user["id"])
    if unread_only:
        q = q.filter(Notification.lu == False)  # noqa: E712
    rows = q.order_by(Notification.created_at.desc()).limit(limit).all()
    unread = (db.query(Notification)
              .filter(Notification.user_id == user["id"],
                      Notification.lu == False)  # noqa: E712
              .count())
    return {
        "unread": unread,
        "notifications": [{
            "id"          : n.id,
            "workorder_id": n.workorder_id,
            "type"        : n.type,
            "message"     : n.message,
            "lu"          : bool(n.lu),
            "created_at"  : n.created_at.isoformat() if n.created_at else None,
        } for n in rows],
    }


@router.post("/notifications/{notif_id}/read")
def read_notification(notif_id: int, db: Session = Depends(get_db),
                      user: dict = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notif_id,
                                      Notification.user_id == user["id"]).first()
    if not n:
        raise HTTPException(404, "Notification introuvable")
    n.lu = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db),
                           user: dict = Depends(get_current_user)):
    (db.query(Notification)
     .filter(Notification.user_id == user["id"], Notification.lu == False)  # noqa: E712
     .update({Notification.lu: True}, synchronize_session=False))
    db.commit()
    return {"ok": True}


# ── Magasin / stock de pièces de rechange ─────────────────────────────────────

@router.get("/stock")
def list_stock(db: Session = Depends(get_db), _: dict = Depends(get_current_user)):
    """État du magasin de pièces de rechange (référence, quantité, emplacement)."""
    rows = db.query(SparePart).order_by(SparePart.category, SparePart.reference).all()
    return {"parts": [{
        "id"           : p.id,
        "reference"    : p.reference,
        "designation"  : p.designation,
        "category"     : p.category,
        "stock_qty"    : p.stock_qty or 0,
        "in_stock"     : (p.stock_qty or 0) > 0,
        "location"     : p.location,
        "unit_cost_eur": p.unit_cost_eur,
    } for p in rows]}
