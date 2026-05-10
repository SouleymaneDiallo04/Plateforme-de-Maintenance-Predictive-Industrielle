"""Documentation technique pour les techniciens de maintenance."""

from fastapi import APIRouter

router = APIRouter(tags=["Documentation"])


FAULT_GUIDE = {
    "roulement_interne": {
        "nom"         : "Défaut bague interne",
        "description" : "Écaillage ou fissure sur la bague intérieure du roulement.",
        "signature_spectrale": [
            "Pic prononcé à BPFI (Ball Pass Frequency Inner race)",
            "Sidebands autour de BPFI espacés de f0",
            "Kurtosis élevé (> 4) en début de défaut",
        ],
        "indicateurs_cles": {
            "Kurtosis"    : "Augmente fortement en début de défaut",
            "BPFI"        : "Pic dominant dans le spectre FFT",
            "Enveloppe"   : "Pic à BPFI confirmé par analyse d'enveloppe",
        },
        "progression"    : [
            "Phase 1 — Kurtosis > 3, pic BPFI visible",
            "Phase 2 — Kurtosis > 6, harmoniques de BPFI",
            "Phase 3 — Kurtosis > 10, broadband noise",
            "Phase 4 — Kurtosis baisse (défaut généralisé)",
        ],
        "action"         : "Remplacement du roulement",
        "urgence"        : "haute",
        "delai"          : "Sous 48h",
        "causes"         : [
            "Surcharge radiale excessive",
            "Contamination du lubrifiant",
            "Montage incorrect (force excessive)",
            "Fatigue de contact après fin de vie",
        ],
    },
    "roulement_externe": {
        "nom"         : "Défaut bague externe",
        "description" : "Écaillage ou fissure sur la bague extérieure du roulement.",
        "signature_spectrale": [
            "Pic prononcé à BPFO",
            "Harmoniques de BPFO (2×BPFO, 3×BPFO)",
            "Pas de modulation par f0 (bague fixe)",
        ],
        "indicateurs_cles": {
            "BPFO"      : "Pic dominant — défaut bague externe",
            "Kurtosis"  : "Augmentation progressive",
            "Enveloppe" : "Confirme le BPFO",
        },
        "progression" : [
            "Phase 1 — Pic BPFO isolé",
            "Phase 2 — Harmoniques visibles",
            "Phase 3 — Sidebands apparaissent",
        ],
        "action"  : "Remplacement du roulement",
        "urgence" : "haute",
        "delai"   : "Sous 48h",
        "causes"  : [
            "Surcharge axiale",
            "Mauvais ajustement dans le logement",
            "Vibrations excessives de la machine",
        ],
    },
    "desequilibre": {
        "nom"         : "Déséquilibre rotor",
        "description" : "Distribution inégale de masse autour de l'axe de rotation.",
        "signature_spectrale": [
            "Pic dominant à 1×f0 (fréquence de rotation)",
            "Vibrations élevées dans les plans radial et axial",
            "Peu d'harmoniques — spectre relativement pur",
        ],
        "indicateurs_cles": {
            "1×f0"    : "Pic très dominant",
            "RMS"     : "Augmente proportionnellement au déséquilibre",
            "Phase"   : "Stable à 90° avec la fréquence de rotation",
        },
        "progression" : [
            "Phase 1 — Pic 1×f0 légèrement élevé",
            "Phase 2 — Pic dominant, vibrations ressenties",
            "Phase 3 — Surcharge roulements, dégradation accélérée",
        ],
        "action"  : "Rééquilibrage statique et dynamique du rotor",
        "urgence" : "modérée",
        "delai"   : "Sous 2 semaines",
        "causes"  : [
            "Accumulation de matière (corrosion, dépôts)",
            "Perte de palette ou de masse d'équilibrage",
            "Usure asymétrique",
            "Montage incorrect d'une pièce",
        ],
    },
    "desalignement": {
        "nom"         : "Désalignement",
        "description" : "Décalage angulaire ou parallèle entre deux arbres couplés.",
        "signature_spectrale": [
            "Pics à 1×f0, 2×f0 et 3×f0",
            "2×f0 souvent dominant (désalignement angulaire)",
            "Vibrations axiales élevées",
        ],
        "indicateurs_cles": {
            "2×f0"  : "Pic caractéristique du désalignement",
            "3×f0"  : "Présent en cas de désalignement sévère",
            "Axial" : "Vibrations axiales > 50% des vibrations radiales",
        },
        "progression" : [
            "Phase 1 — Pic 2×f0 visible",
            "Phase 2 — 3×f0 apparaît, vibrations axiales",
            "Phase 3 — Surcharge accouplement et roulements",
        ],
        "action"  : "Réalignement laser de l'accouplement",
        "urgence" : "modérée",
        "delai"   : "Sous 1 semaine",
        "causes"  : [
            "Déformation thermique du bâti",
            "Tassement des fondations",
            "Montage après maintenance mal réalisé",
            "Usure du couplage",
        ],
    },
    "jeu_mecanique": {
        "nom"         : "Jeu mécanique (Looseness)",
        "description" : "Fixations desserrées ou jeu excessif dans les assemblages.",
        "signature_spectrale": [
            "Nombreuses harmoniques de f0 (jusqu'à 10×f0)",
            "Sous-harmoniques (0.5×f0, 1.5×f0)",
            "Spectre 'dense' et large bande",
        ],
        "indicateurs_cles": {
            "Harmoniques" : "Très nombreuses — signature caractéristique",
            "0.5×f0"     : "Sous-harmonique typique du jeu",
            "Kurtosis"   : "Peut rester modéré",
        },
        "progression" : [
            "Phase 1 — Quelques harmoniques supplémentaires",
            "Phase 2 — Sous-harmoniques apparaissent",
            "Phase 3 — Spectre dense, vibrations erratiques",
        ],
        "action"  : "Vérification et serrage de toutes les fixations",
        "urgence" : "modérée",
        "delai"   : "Sous 1 semaine",
        "causes"  : [
            "Boulons de fixation desserrés",
            "Usure des portées de roulement",
            "Jeu dans les clavettes ou ajustements",
            "Vibrations excessives causant le desserrage",
        ],
    },
}


@router.get("/docs/fault-guide")
def get_fault_guide():
    """Guide complet des défauts pour les techniciens."""
    return {
        "title"  : "Guide de Diagnostic Vibratoire — PrognoSense",
        "version": "1.0",
        "faults" : FAULT_GUIDE,
        "quick_reference": {
            "Kurtosis > 4"  : "Défaut de roulement probable",
            "Pic 1×f0 fort" : "Déséquilibre",
            "Pic 2×f0 fort" : "Désalignement",
            "Nombreux harmoniques": "Jeu mécanique",
            "BPFO/BPFI"    : "Défaut roulement (bague externe/interne)",
        }
    }


@router.get("/docs/fault-guide/{fault_type}")
def get_fault_detail(fault_type: str):
    """Détail d'un type de défaut spécifique."""
    if fault_type not in FAULT_GUIDE:
        from fastapi import HTTPException
        raise HTTPException(
            404,
            f"Défaut '{fault_type}' non référencé. "
            f"Disponibles : {list(FAULT_GUIDE.keys())}"
        )
    return FAULT_GUIDE[fault_type]


@router.get("/docs/indicators-guide")
def get_indicators_guide():
    """Guide des indicateurs vibratoires pour les techniciens."""
    return {
        "temporal": {
            "RMS": {
                "description": "Valeur efficace — énergie globale du signal",
                "normal"     : "< 2 mm/s (ISO 10816)",
                "alarm"      : "> 4.5 mm/s",
                "danger"     : "> 11.2 mm/s",
                "usage"      : "Surveillance globale, tendance de dégradation"
            },
            "Kurtosis": {
                "description": "Impulsivité du signal",
                "normal"     : "Kurtosis ≈ 3 (signal gaussien)",
                "alarm"      : "Kurtosis > 4",
                "danger"     : "Kurtosis > 10",
                "usage"      : "Détection précoce défauts roulements"
            },
            "Crest Factor": {
                "description": "Rapport crête / RMS",
                "normal"     : "< 2.5",
                "alarm"      : "> 4",
                "danger"     : "> 6",
                "usage"      : "Chocs mécaniques, début de défaut"
            },
        },
        "frequency": {
            "FFT": {
                "description": "Décomposition fréquentielle du signal",
                "usage"      : "Identification du type de défaut par les pics"
            },
            "Enveloppe": {
                "description": "Spectre de l'enveloppe du signal filtré",
                "usage"      : "Confirmation et localisation des défauts de roulements"
            },
        }
    }