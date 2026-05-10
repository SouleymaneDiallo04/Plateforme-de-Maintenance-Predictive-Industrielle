"""
Model Registry — gestionnaire central de tous les modèles PrognoSense.

Responsabilités :
  1. Charger et garder en mémoire tous les modèles entraînés
  2. Gérer le modèle "actif" par dataset (choix utilisateur)
  3. Exposer une interface de prédiction unifiée
  4. Gérer le réentraînement en arrière-plan
  5. Persister les préférences utilisateur
"""

import pickle
import asyncio
import numpy as np
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
import torch


class ModelRegistry:

    def __init__(self, models_dir: str = "models",
                       data_dir:   str = "data/processed"):
        self.models_dir = Path(models_dir)
        self.data_dir   = Path(data_dir)

        # Modèles chargés en mémoire
        self._models     = {}      # {dataset: {model_name: model_obj}}
        self._scalers    = {}      # {dataset: scaler}
        self._encoders   = {}      # {dataset: label_encoder}
        self._autoencoders = {}    # {dataset: AnomalyDetector}

        # Modèle actif par dataset (choix utilisateur)
        self._active_models = {}   # {dataset: model_name}

        # Métriques du benchmark
        self._benchmark_results = {}

        # État du réentraînement
        self._retrain_status = {
            'running'   : False,
            'progress'  : 0,
            'message'   : '',
            'started_at': None,
            'result'    : None
        }

        # Préférences persistées
        self._prefs_file = self.models_dir / "user_preferences.json"

    def load_all(self):
        """Charge tous les modèles au démarrage du serveur."""
        print("Chargement des modèles...")

        # Registre benchmark
        registry_path = self.models_dir / "benchmark_registry.pkl"
        if registry_path.exists():
            with open(registry_path, 'rb') as f:
                registry = pickle.load(f)
            self._models   = registry.get('models',   {})
            self._scalers  = registry.get('scalers',  {})
            self._encoders = registry.get('encoders', {})
            self._benchmark_results = registry.get('benchmark_results', {})
            print(f"  ✅ Benchmark registry chargé")

        # Autoencoders
        from backend.ml.anomaly.autoencoder import AnomalyDetector
        for name in ['vbl', 'cwru', 'mf', 'cmapss']:
            path = self.models_dir / f"autoencoder_{name}.pt"
            if path.exists():
                self._autoencoders[name.upper()] = \
                    AnomalyDetector.load(str(path))
                print(f"  ✅ Autoencoder {name.upper()} chargé")

        # Modèles spécialisés (MLP Mech. Faults, CNN Gear)
        mlp_path = self.models_dir / "mlp_mechanical_faults.pkl"
        if mlp_path.exists():
            with open(mlp_path, 'rb') as f:
                mlp_data = pickle.load(f)
            if 'MF' not in self._models:
                self._models['MF'] = {}
            self._models['MF']['MLP'] = mlp_data['model']
            self._scalers['MF_mlp']   = mlp_data['scaler']
            print(f"  ✅ MLP Mechanical Faults chargé")

        cnn_path = self.models_dir / "cnn_gear_mcc5.pt"
        if cnn_path.exists():
            from backend.ml.models.cnn_gear import GearFaultCNN
            checkpoint = torch.load(cnn_path, map_location='cpu')
            n_classes  = checkpoint['n_classes']
            cnn        = GearFaultCNN(n_classes=n_classes)
            cnn.load_state_dict(checkpoint['model_state'])
            cnn.eval()
            if 'MCC5' not in self._models:
                self._models['MCC5'] = {}
            self._models['MCC5']['CNN'] = cnn
            self._encoders['MCC5']      = checkpoint['label_encoder']
            print(f"  ✅ CNN MCC5-THU Gearbox chargé")

        # Charger les préférences utilisateur
        self._load_preferences()

        # Définir les modèles actifs par défaut
        defaults = {
            'VBL'   : 'XGBoost',
            'CWRU'  : 'XGBoost',
            'MF'    : 'MLP',
            'CMAPSS': 'XGBoost',
            'MCC5'  : 'CNN',
        }
        for dataset, model_name in defaults.items():
            if dataset not in self._active_models:
                self._active_models[dataset] = model_name

        print(f"\nModèles actifs par défaut :")
        for ds, mn in self._active_models.items():
            print(f"  {ds:10s} → {mn}")

    # ── Sélection du modèle actif ─────────────────────────────────────────

    def set_active_model(self, dataset: str, model_name: str) -> bool:
        """
        Définit le modèle actif pour un dataset.
        Persiste le choix utilisateur.
        """
        available = self.get_available_models(dataset)
        if model_name not in available:
            return False
        self._active_models[dataset] = model_name
        self._save_preferences()
        return True

    def get_active_model(self, dataset: str) -> str:
        return self._active_models.get(dataset, 'XGBoost')

    def get_available_models(self, dataset: str) -> list:
        """Retourne la liste des modèles disponibles pour un dataset."""
        base = ['Decision Tree', 'Random Forest', 'XGBoost', 'MLP']
        extras = {
            'MCC5'  : ['CNN'],
            'CMAPSS': ['Huber Regressor'] + base,
        }
        return extras.get(dataset, base)

    # ── Prédiction unifiée ────────────────────────────────────────────────

    def predict(self, dataset: str,
                X: np.ndarray,
                model_name: str = None) -> dict:
        """
        Prédiction avec le modèle actif (ou un modèle spécifié).
        Retourne toujours le même format de réponse.
        """
        model_name = model_name or self.get_active_model(dataset)

        # Récupérer le modèle
        model_obj  = self._models.get(dataset, {}).get(model_name)
        if model_obj is None:
            return {'error': f"Modèle {model_name} non disponible pour {dataset}"}

        # Normalisation si nécessaire
        scaler = self._scalers.get(dataset)
        X_input = scaler.transform(X) if (
            scaler is not None and model_name in ['MLP', 'Huber Regressor']
        ) else X

        # Prédiction
        task = 'regression' if dataset == 'CMAPSS' else 'classification'

        if task == 'classification':
            encoder     = self._encoders.get(dataset)
            y_pred_enc  = model_obj.predict(X_input)
            y_pred      = encoder.inverse_transform(y_pred_enc) \
                          if hasattr(encoder, 'inverse_transform') \
                          else y_pred_enc
            try:
                proba   = model_obj.predict_proba(X_input)
                confidence = float(proba.max(axis=1).mean())
            except Exception:
                confidence = None

            return {
                'task'       : 'classification',
                'model'      : model_name,
                'dataset'    : dataset,
                'predictions': y_pred.tolist()
                               if hasattr(y_pred, 'tolist') else list(y_pred),
                'confidence' : confidence,
                'timestamp'  : datetime.now().isoformat()
            }

        else:   # régression RUL
            y_pred = model_obj.predict(X_input)
            y_pred = np.clip(y_pred, 0, 125)
            return {
                'task'       : 'regression',
                'model'      : model_name,
                'dataset'    : dataset,
                'rul_pred'   : float(y_pred.mean()),
                'rul_std'    : float(y_pred.std()),
                'timestamp'  : datetime.now().isoformat()
            }

    def predict_anomaly(self, dataset: str,
                     X: np.ndarray) -> dict:
        """Score d'anomalie avec seuil configurable depuis la config."""
        from backend.api.routes.config import load_config

        detector = self._autoencoders.get(dataset)
        if detector is None:
            return {'error': f"Autoencoder non disponible pour {dataset}"}

    # Seuil dynamique depuis la configuration utilisateur
        cfg = load_config()
        dynamic_threshold = cfg.get(
            'autoencoder_thresholds', {}
        ).get(dataset, 50.0)

        result = detector.predict(X)

    # Recalculer is_anomaly avec le seuil dynamique
    # (le score 0-100% reste inchangé)
        is_anomaly = result['anomaly_score'] > dynamic_threshold

        return {
            'anomaly_score'   : float(result['anomaly_score'].mean()),
            'is_anomaly'      : bool(is_anomaly.any()),
            'confidence'      : float(result['confidence'].mean()),
            'threshold_used'  : dynamic_threshold,
            'timestamp'       : datetime.now().isoformat()
        }

    def get_benchmark_results(self, dataset: str = None) -> dict:
        """Retourne les métriques du benchmark pour le dashboard IA Lab."""
        if dataset:
            return {
                k: v for k, v in self._benchmark_results.items()
                if dataset in str(v)
            }
        return self._benchmark_results

    # ── Réentraînement ────────────────────────────────────────────────────

    async def retrain_async(self, dataset: str,
                            X_new: np.ndarray,
                            y_new: list,
                            new_label: str) -> None:
        """Réentraînement réel — modifie effectivement les modèles."""
        import pickle, time
        from sklearn.neural_network import MLPClassifier
        from sklearn.preprocessing import LabelEncoder

        self._retrain_status = {
            "running"   : True,
            "progress"  : 0,
            "message"   : "Préparation...",
            "started_at": datetime.now().isoformat(),
            "result"    : None,
        }

        try:
            # ── Étape 1 : Charger le modèle existant ─────────────────────────
            self._retrain_status.update({"progress": 10,
                                          "message": "Chargement du modèle..."})
            await asyncio.sleep(0.1)

            existing = self._models.get(dataset, {}).get("MLP")
            scaler   = self._scalers.get(dataset)

            if scaler is not None:
                X_scaled = scaler.transform(X_new)
            else:
                X_scaled = X_new

            # ── Étape 2 : Déterminer les classes existantes ───────────────────
            self._retrain_status.update({"progress": 20,
                                          "message": "Analyse des classes..."})
            await asyncio.sleep(0.1)

            existing_classes = []
            if existing and hasattr(existing, "classes_"):
                existing_classes = list(existing.classes_)

            all_classes = list(set(existing_classes + list(set(y_new))))

            # ── Étape 3 : Réentraînement MLP avec warm_start ─────────────────
            self._retrain_status.update({"progress": 30,
                                          "message": f"Réentraînement MLP — "
                                                     f"{len(X_new)} échantillons..."})
            await asyncio.sleep(0.1)

            if existing and hasattr(existing, "warm_start"):
                # Fine-tuning : on continue l'entraînement
                existing.warm_start = True
                existing.max_iter   = 100
                try:
                    existing.fit(X_scaled, y_new)
                    new_mlp = existing
                except Exception:
                    # Si le nombre de classes change → réentraînement complet
                    new_mlp = MLPClassifier(
                        hidden_layer_sizes=(256, 128, 64),
                        max_iter=200, random_state=42,
                        early_stopping=True, validation_fraction=0.1
                    )
                    new_mlp.fit(X_scaled, y_new)
            else:
                new_mlp = MLPClassifier(
                    hidden_layer_sizes=(256, 128, 64),
                    max_iter=200, random_state=42,
                    early_stopping=True, validation_fraction=0.1
                )
                new_mlp.fit(X_scaled, y_new)

            self._retrain_status.update({"progress": 60,
                                          "message": "Mise à jour du registry..."})
            await asyncio.sleep(0.1)

            if dataset not in self._models:
                self._models[dataset] = {}
            self._models[dataset]["MLP"] = new_mlp

            # ── Étape 4 : Mise à jour Autoencoder ────────────────────────────
            self._retrain_status.update({"progress": 75,
                                          "message": "Mise à jour Autoencoder..."})
            await asyncio.sleep(0.1)

            detector = self._autoencoders.get(dataset)
            if detector:
                X_normal_new = X_new[np.array(y_new) == "sain"] \
                               if "sain" in y_new else None
                if X_normal_new is not None and len(X_normal_new) > 5:
                    detector.fit(X_normal_new, epochs=20, verbose=False)
                    detector.save(f"models/autoencoder_{dataset.lower()}.pt")

            # ── Étape 5 : Sauvegarde persistante ─────────────────────────────
            self._retrain_status.update({"progress": 90,
                                          "message": "Sauvegarde..."})
            await asyncio.sleep(0.1)

            save_path = Path("models") / f"mlp_{dataset.lower()}_retrained.pkl"
            with open(save_path, "wb") as f:
                pickle.dump({
                    "model"    : new_mlp,
                    "classes"  : new_mlp.classes_.tolist()
                                 if hasattr(new_mlp, "classes_") else all_classes,
                    "new_label": new_label,
                    "trained_at": datetime.now().isoformat(),
                }, f)

            # ── Succès ────────────────────────────────────────────────────────
            test_score = None
            try:
                test_score = float(new_mlp.score(X_scaled, y_new))
            except Exception:
                pass

            self._retrain_status = {
                "running"  : False,
                "progress" : 100,
                "message"  : f"Réentraînement terminé — "
                             f"nouveau défaut '{new_label}' intégré",
                "result"   : {
                    "new_label"  : new_label,
                    "n_samples"  : len(X_new),
                    "dataset"    : dataset,
                    "train_score": test_score,
                    "model_saved": str(save_path),
                    "timestamp"  : datetime.now().isoformat(),
                }
            }

        except Exception as e:
            self._retrain_status = {
                "running"  : False,
                "progress" : 0,
                "message"  : f"Erreur : {str(e)}",
                "result"   : None,
            }
    def get_retrain_status(self) -> dict:
        return self._retrain_status

    # ── Persistance des préférences ───────────────────────────────────────

    def _save_preferences(self):
        prefs = {'active_models': self._active_models}
        with open(self._prefs_file, 'w') as f:
            json.dump(prefs, f, indent=2)

    def _load_preferences(self):
        if self._prefs_file.exists():
            with open(self._prefs_file, 'r') as f:
                prefs = json.load(f)
            self._active_models = prefs.get('active_models', {})
            print(f"  ✅ Préférences utilisateur chargées")


# Instance globale — partagée par toute l'API
registry = ModelRegistry()