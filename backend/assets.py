"""
Référentiel des équipements et catalogue des défauts — PrognoSense.

Transforme un libellé de défaut GÉNÉRIQUE issu de l'IA (ex. « roulement_interne »)
en un diagnostic EXPLICITE nommant l'élément défaillant réel de la machine
(ex. « Roulement SKF 6205-2RS — bague interne, palier côté entraînement ») et
en une PIÈCE de rechange précise (référence catalogue) que l'on pourra
rechercher dans le stock du magasin.

Deux briques :
  - MACHINE_ASSETS : la nomenclature réelle de chaque machine (références des
    roulements, accouplement, pignon, localisation atelier).
  - FAULT_CATALOG  : pour chaque famille de défaut, le gabarit d'élément
    défaillant, la pièce à prévoir et l'action de maintenance.
"""

from typing import Optional

# ── Nomenclature des machines (composants réels + références) ──────────────────
# bearing_de  : roulement côté entraînement (drive-end)
# bearing_nde : roulement côté libre (non-drive-end)
# coupling    : accouplement
# pinion      : pignon de réducteur (si machine à engrenages)

MACHINE_ASSETS = {
    "M01": {"equipment": "Motopompe centrifuge P-101", "location": "Station de pompage — Ligne A",
            "bearing_de": "SKF 6205-2RS", "bearing_nde": "SKF 6203-2RS",
            "coupling": "REICH ROTEX 28", "pinion": None},
    "M02": {"equipment": "Ventilateur de tirage V-205", "location": "Chaufferie — Ligne B",
            "bearing_de": "SKF 6205-2RS", "bearing_nde": "SKF 6203-2RS",
            "coupling": "REICH ROTEX 28", "pinion": None},
    "M03": {"equipment": "Compresseur d'air C-300", "location": "Salle des compresseurs",
            "bearing_de": "SKF 6203-2RS", "bearing_nde": "SKF 6203-2RS",
            "coupling": "REICH ROTEX 28", "pinion": None},
    "M04": {"equipment": "Banc moteur d'essai B-04", "location": "Laboratoire essais vibratoires",
            "bearing_de": "SKF 6205-2RS", "bearing_nde": "SKF 6205-2RS",
            "coupling": "REICH ROTEX 28", "pinion": None},
    "M05": {"equipment": "Réducteur à engrenages G-500", "location": "Ligne de production — Réducteur",
            "bearing_de": "NSK 6207", "bearing_nde": "NSK 6207",
            "coupling": "REICH ROTEX 28", "pinion": "Pignon réducteur Z21 m3"},
    "Turbine_01": {"equipment": "Turbine à gaz GT-01", "location": "Centrale — Tranche 1",
                   "bearing_de": "Palier lisse TG", "bearing_nde": "Palier lisse TG",
                   "coupling": None, "pinion": None},
    "Turbine_02": {"equipment": "Turbine à gaz GT-02", "location": "Centrale — Tranche 2",
                   "bearing_de": "Palier lisse TG", "bearing_nde": "Palier lisse TG",
                   "coupling": None, "pinion": None},
    "_default": {"equipment": "Machine tournante", "location": "Atelier",
                 "bearing_de": "SKF 6205-2RS", "bearing_nde": "SKF 6203-2RS",
                 "coupling": "REICH ROTEX 28", "pinion": None},
}


def get_asset(machine_id: str) -> dict:
    return MACHINE_ASSETS.get(machine_id, MACHINE_ASSETS["_default"])


# ── Catalogue des défauts → élément défaillant explicite + pièce + action ──────
# part_key : champ de l'asset utilisé comme référence pièce ("bearing_de"…),
#            ou None si l'action ne consomme pas de pièce remplaçable de stock.
# fixed_part : référence pièce fixe (indépendante de la machine).

_FAULT_RULES = [
    # (mots-clés, gabarit d'élément, part_key, fixed_part, action)
    (("mixte", "combine"),
     "Défaut combiné — denture engrenage + roulement {bearing_de}",
     "pinion", None,
     "Démontage réducteur : remplacer pignon et roulement, contrôler la lubrification."),

    (("interne", "bpfi"),
     "Roulement {bearing_de} — défaut de bague INTERNE (BPFI), palier côté entraînement",
     "bearing_de", None,
     "Remplacer le roulement, contrôler l'ajustement de l'arbre et la lubrification."),

    (("externe", "bpfo"),
     "Roulement {bearing_de} — défaut de bague EXTERNE (BPFO), palier côté entraînement",
     "bearing_de", None,
     "Remplacer le roulement, contrôler l'ajustement du logement (portée)."),

    (("bille", "rouleau", "bsf", "element_roulant"),
     "Roulement {bearing_de} — défaut d'ÉLÉMENT ROULANT (BSF / bille)",
     "bearing_de", None,
     "Remplacer le roulement et vérifier la qualité de la graisse."),

    (("roulement", "bearing"),
     "Roulement {bearing_de} — dégradation détectée (palier côté entraînement)",
     "bearing_de", None,
     "Remplacer le roulement et contrôler l'alignement après montage."),

    (("pitting", "piqure", "piqûre"),
     "Engrenage {pinion} — PIQÛRES (pitting) sur la denture",
     "pinion", None,
     "Inspecter la denture, contrôler la lubrification, planifier remplacement pignon."),

    (("dent", "fissure", "cassee", "cassée", "manquante"),
     "Engrenage {pinion} — DENT endommagée (cassée / fissurée) sur le pignon",
     "pinion", None,
     "Remplacer le pignon, contrôler l'entraxe et le jeu de denture."),

    (("usure", "wear"),
     "Engrenage {pinion} — USURE abrasive de la denture",
     "pinion", None,
     "Contrôler le profil de denture et la lubrification, prévoir remplacement."),

    (("engrenage", "gear", "gmf"),
     "Engrenage {pinion} — défaut de denture détecté",
     "pinion", None,
     "Inspecter la denture du réducteur, contrôler la lubrification."),

    (("desalignement", "désalignement", "misalignment"),
     "Accouplement {coupling} — DÉSALIGNEMENT arbre (composantes 2×)",
     "coupling", None,
     "Réaligner au comparateur/laser, remplacer la garniture d'accouplement si usée."),

    (("desequilibre", "déséquilibre", "balourd", "unbalance"),
     "Rotor — BALOURD (déséquilibre massique de l'arbre)",
     None, "Masses d'équilibrage",
     "Équilibrage dynamique sur site (1 ou 2 plans), pose de masses correctrices."),

    (("jeu", "desserrage", "looseness"),
     "Fixation palier — JEU MÉCANIQUE / desserrage des boulons d'ancrage",
     None, "Boulonnerie M16-8.8",
     "Resserrer la boulonnerie au couple, remplacer les goujons fatigués, contrôler le jeu."),

    (("degradation", "dégradation", "turbo", "rul", "critique", "moteur"),
     "Module turbine — DÉGRADATION du chemin gaz (perte de rendement)",
     None, None,
     "Inspection borescopique, intervention lourde sur arrêt programmé (pièces sur devis)."),

    (("anomalie", "inconnu", "unknown"),
     "Comportement ANORMAL non catégorisé — écart au régime sain",
     None, None,
     "Diagnostic vibratoire approfondi requis pour identifier l'organe en cause."),
]

_DEFAULT_RULE = (
    "Organe à confirmer — anomalie détectée",
    None, None,
    "Inspection sur site pour localiser l'élément défaillant.",
)


def resolve_fault(machine_id: str, fault: Optional[str]) -> dict:
    """
    Résout un défaut générique en diagnostic explicite pour une machine donnée.

    Retourne :
      equipment        : désignation de l'équipement
      location         : localisation atelier
      failing_element  : élément défaillant nommé (avec référence composant)
      part_reference   : référence de la pièce de rechange (ou None)
      action           : action de maintenance recommandée
    """
    asset = get_asset(machine_id)
    label = (fault or "").lower()

    element_tpl, part_key, fixed_part, action = _DEFAULT_RULE
    for keywords, tpl, pkey, fpart, act in _FAULT_RULES:
        if any(k in label for k in keywords):
            element_tpl, part_key, fixed_part, action = tpl, pkey, fpart, act
            break

    # Référence pièce : champ de l'asset, sinon pièce fixe du catalogue
    part_ref = None
    if part_key:
        part_ref = asset.get(part_key)
    if not part_ref and fixed_part:
        part_ref = fixed_part

    failing_element = element_tpl.format(
        bearing_de=asset.get("bearing_de") or "roulement",
        bearing_nde=asset.get("bearing_nde") or "roulement",
        coupling=asset.get("coupling") or "accouplement",
        pinion=asset.get("pinion") or "pignon réducteur",
    )

    return {
        "equipment"      : asset["equipment"],
        "location"       : asset.get("location"),
        "failing_element": failing_element,
        "part_reference" : part_ref,
        "action"         : action,
    }
