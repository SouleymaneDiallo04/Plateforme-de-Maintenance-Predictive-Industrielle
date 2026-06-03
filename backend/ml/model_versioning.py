"""
ModelVersionManager — versioning des modèles (MLOps basique).

Chaque réentraînement crée une nouvelle version persistée :
  - le binaire du modèle est copié dans models/versions/
  - une ligne ModelVersion est enregistrée en base (métriques + actif/inactif)

Permet de lister l'historique et de revenir (rollback) à une version
antérieure si un réentraînement a dégradé les performances.
"""

import pickle
from pathlib import Path

from sqlalchemy.orm import Session

from backend.db.models import ModelVersion


class ModelVersionManager:

    MODEL_DIR = Path("models/versions")

    def __init__(self):
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)

    def save_version(self, db: Session, model_obj, dataset: str,
                     model_name: str, metrics: dict,
                     triggered_by: str = "user") -> dict:
        """Sauvegarde un modèle comme nouvelle version active."""
        # Désactiver l'ancienne version active
        db.query(ModelVersion).filter(
            ModelVersion.dataset == dataset,
            ModelVersion.model_name == model_name,
            ModelVersion.is_active == True,   # noqa: E712
        ).update({"is_active": False})

        # Numéro de version suivant
        last = (
            db.query(ModelVersion)
            .filter(ModelVersion.dataset == dataset,
                    ModelVersion.model_name == model_name)
            .order_by(ModelVersion.version.desc())
            .first()
        )
        version = (last.version + 1) if last else 1

        # Persister le binaire
        fname = f"{dataset}_{model_name.replace(' ', '_')}_v{version}.pkl"
        fpath = self.MODEL_DIR / fname
        try:
            with open(fpath, "wb") as f:
                pickle.dump(model_obj, f)
        except Exception as e:
            return {"error": f"Sauvegarde binaire échouée : {e}"}

        entry = ModelVersion(
            dataset       = dataset,
            model_name    = model_name,
            version       = version,
            accuracy      = metrics.get("accuracy"),
            f1_score      = metrics.get("f1_score"),
            n_samples     = metrics.get("n_samples"),
            n_classes     = metrics.get("n_classes"),
            file_path     = str(fpath),
            is_active     = True,
            triggered_by  = triggered_by,
            drift_score_at_trigger = metrics.get("drift_score"),
            notes         = metrics.get("notes", ""),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {"version": version, "file_path": str(fpath), "id": entry.id}

    def list_versions(self, db: Session, dataset: str, model_name: str) -> list:
        rows = (
            db.query(ModelVersion)
            .filter(ModelVersion.dataset == dataset,
                    ModelVersion.model_name == model_name)
            .order_by(ModelVersion.version.desc())
            .all()
        )
        return [
            {
                "version"     : v.version,
                "trained_at"  : v.trained_at.isoformat() if v.trained_at else None,
                "accuracy"    : v.accuracy,
                "f1_score"    : v.f1_score,
                "n_samples"   : v.n_samples,
                "is_active"   : v.is_active,
                "triggered_by": v.triggered_by,
                "drift_score" : v.drift_score_at_trigger,
                "notes"       : v.notes,
            }
            for v in rows
        ]

    def rollback(self, db: Session, dataset: str, model_name: str,
                 version: int) -> dict:
        """Réactive une version antérieure et la recharge dans le registry."""
        target = (
            db.query(ModelVersion)
            .filter(ModelVersion.dataset == dataset,
                    ModelVersion.model_name == model_name,
                    ModelVersion.version == version)
            .first()
        )
        if not target or not Path(target.file_path).exists():
            return {"error": "Version introuvable ou binaire manquant"}

        # Charger le binaire
        try:
            with open(target.file_path, "rb") as f:
                model_obj = pickle.load(f)
        except Exception as e:
            return {"error": f"Chargement échoué : {e}"}

        # Marquer actif en base
        db.query(ModelVersion).filter(
            ModelVersion.dataset == dataset,
            ModelVersion.model_name == model_name,
        ).update({"is_active": False})
        target.is_active = True
        db.commit()

        # Injecter dans le registry en mémoire
        from backend.ml.model_registry import registry
        registry._models.setdefault(dataset, {})[model_name] = model_obj
        registry.set_active_model(dataset, model_name)

        return {
            "rolled_back_to": version,
            "dataset"       : dataset,
            "model_name"    : model_name,
            "active"        : True,
        }


# Instance globale
version_manager = ModelVersionManager()
