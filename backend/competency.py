"""
Référentiel de compétences et règles de qualification — PrognoSense.

Le pont entre le DIAGNOSTIC (produit par la plateforme) et l'HUMAIN
(le technicien qui intervient). Chaque famille de défaut diagnostiquée est
reliée à :
  - une COMPÉTENCE requise (parmi un référentiel court et lisible) ;
  - un NIVEAU de CERTIFICATION minimal (ISO 18436, catégories I à IV).

Un technicien est QUALIFIÉ pour un ordre de travail s'il possède la
compétence requise ET un niveau de certification suffisant. Les cas
critiques (P1 / zone ISO D) relèvent l'exigence à la catégorie III.

Ce module est volontairement sans dépendance (constantes + fonctions pures),
réutilisable côté routes API comme côté seed de démonstration.
"""

from typing import Optional

# ── Référentiel de compétences ────────────────────────────────────────────────

COMPETENCES = [
    "Roulements & montage",
    "Engrenages / réducteurs",
    "Équilibrage",
    "Alignement",
    "Mécanique générale",
    "Turbomachines",
    "Analyse vibratoire",
]

# ── Niveaux de certification ISO 18436 (entier ↔ libellé) ─────────────────────

CERTIF_LABELS = {1: "Cat. I", 2: "Cat. II", 3: "Cat. III", 4: "Cat. IV"}


def certif_label(niveau: Optional[int]) -> str:
    """Libellé lisible d'un niveau de certification (None → '—')."""
    if not niveau:
        return "—"
    return CERTIF_LABELS.get(int(niveau), f"Cat. {niveau}")


# ── Mapping défaut → (compétence, certification minimale) ──────────────────────
# Recherche par mot-clé sur le libellé du défaut : robuste aux variantes
# (roulement_externe, roulement_interne_grave, bearing, misalignment, …).
# Ordre important : du plus spécifique au plus générique.

_FAULT_RULES = [
    # (mots-clés, compétence, certif mini)
    (("mixte", "combine"),                         "Analyse vibratoire",     3),
    (("roulement", "bearing", "bpfo", "bpfi", "bille"), "Roulements & montage", 2),
    (("engrenage", "gear", "pitting", "usure", "dent", "fissure"), "Engrenages / réducteurs", 2),
    (("desequilibre", "déséquilibre", "balourd", "unbalance"), "Équilibrage",    1),
    (("desalignement", "désalignement", "misalignment"), "Alignement",          1),
    (("jeu", "desserrage", "looseness"),           "Mécanique générale",      1),
    (("degradation", "dégradation", "turbo", "rul", "critique", "moteur"), "Turbomachines", 3),
    (("anomalie", "inconnu", "unknown"),           "Analyse vibratoire",      2),
]

_DEFAULT_RULE = ("Mécanique générale", 1)


def required_competency(fault: Optional[str],
                        priority: Optional[str] = None,
                        iso_zone: Optional[str] = None) -> dict:
    """
    Détermine la compétence et la certification requises pour un défaut donné.

    Règle de criticité : un OT P1 ou en zone ISO D exige au minimum la
    catégorie III, quel que soit le défaut (un cas grave demande un analyste
    expérimenté — défendable devant un fiabiliste).

    Retourne : {competence, certif_requise, certif_label}
    """
    label = (fault or "").lower()
    competence, certif = _DEFAULT_RULE
    for keywords, comp, lvl in _FAULT_RULES:
        if any(k in label for k in keywords):
            competence, certif = comp, lvl
            break

    # Montée d'exigence sur les cas critiques
    if (priority or "").upper() == "P1" or (iso_zone or "").upper() == "D":
        certif = max(certif, 3)

    return {
        "competence"   : competence,
        "certif_requise": certif,
        "certif_label" : certif_label(certif),
    }


# ── Qualification d'un technicien ─────────────────────────────────────────────

def evaluate_candidate(tech_competences, tech_certif: Optional[int],
                       tech_statut: Optional[str], charge: int,
                       competence_requise: str, certif_requise: int) -> dict:
    """
    Évalue un technicien pour un OT donné.

    Retourne un dict de décision :
      qualified  : compétence présente ET certification suffisante
      has_comp   : possède la compétence
      certif_ok  : niveau de certification suffisant
      available  : statut « disponible »
      reason     : libellé court de l'état (qualifié / certif insuffisante / …)
    """
    comps = tech_competences or []
    has_comp  = competence_requise in comps
    certif_ok = (tech_certif or 0) >= (certif_requise or 0)
    available = (tech_statut or "disponible") == "disponible"
    qualified = has_comp and certif_ok

    if not has_comp:
        reason = "pas la compétence"
    elif not certif_ok:
        reason = f"certif. insuffisante (requis {certif_label(certif_requise)})"
    elif not available:
        reason = "indisponible"
    elif charge >= 4:
        reason = "surchargé"
    else:
        reason = "qualifié"

    return {
        "qualified" : qualified,
        "has_comp"  : has_comp,
        "certif_ok" : certif_ok,
        "available" : available,
        "charge"    : charge,
        "reason"    : reason,
    }
