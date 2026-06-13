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
from datetime import datetime


class ModelRegistry:

    def __init__(self, models_dir: str = "models",
                       data_dir:   str = "data/processed"):
        self.models_dir = Path(models_dir)
        self.data_dir   = Path(data_dir)

        # Modèles chargés en mémoire
        self._models       = {}    # {dataset: {model_name: model_obj}}
        self._scalers      = {}    # {dataset: scaler}
        self._encoders     = {}    # {dataset: label_encoder}
        self._autoencoders = {}    # {dataset: AnomalyDetector}

        # Détecteurs de drift (un par dataset)
        self._drift_detectors = {}  # {dataset: DriftDetector}

        # Ensembles d'anomalie (lazy, un par dataset) — None si indisponible
        self._anomaly_ensembles = {}  # {dataset: AnomalyEnsemble | None}

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
            print(f"  [OK] Benchmark registry chargé")

        # Autoencoders
        from backend.ml.anomaly.autoencoder import AnomalyDetector
        for name in ['vbl', 'cwru', 'mf', 'cmapss']:
            path = self.models_dir / f"autoencoder_{name}.pt"
            if path.exists():
                self._autoencoders[name.upper()] = \
                    AnomalyDetector.load(str(path))
                print(f"  [OK] Autoencoder {name.upper()} chargé")

        # Modèles spécialisés (MLP Mech. Faults, CNN Gear)
        mlp_path = self.models_dir / "mlp_mechanical_faults.pkl"
        if mlp_path.exists():
            with open(mlp_path, 'rb') as f:
                mlp_data = pickle.load(f)
            if 'MF' not in self._models:
                self._models['MF'] = {}
            self._models['MF']['MLP'] = mlp_data['model']
            self._scalers['MF_mlp']   = mlp_data['scaler']
            print(f"  [OK] MLP Mechanical Faults chargé")

        cnn_path = self.models_dir / "cnn_gear_mcc5.pt"
        if cnn_path.exists():
            import torch
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
            print(f"  [OK] CNN MCC5-THU Gearbox chargé")

        # Initialiser les détecteurs de drift
        from backend.ml.drift_detector import DriftDetector
        for ds_name in ['VBL', 'CWRU', 'MF', 'CMAPSS']:
            self._drift_detectors[ds_name] = DriftDetector(ds_name)

        # Charger les données de référence pour le drift
        ref_files = {
            'VBL':    'X_vbl',
            'CWRU':   'X_cwru',
            'MF':     'X_mf',
            'CMAPSS': 'X_cmapss',
        }
        for ds_name, fname in ref_files.items():
            ref_path = self.data_dir / f"{fname}.npy"
            if ref_path.exists():
                try:
                    X_ref = np.load(ref_path)
                    self._drift_detectors[ds_name].set_reference(X_ref)
                    print(f"  [OK] Référence drift {ds_name} chargée ({len(X_ref)} samples)")
                except Exception as e:
                    print(f"  [WARN] Référence drift {ds_name} non disponible : {e}")

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
            print(f"  {ds:10s} -> {mn}")

    # ── Accès direct aux objets modèles ──────────────────────────────────────

    def get_model(self, dataset: str, model_name: str = None):
        """Retourne l'objet modèle brut (pour SHAP, calibration, etc.)."""
        model_name = model_name or self.get_active_model(dataset)
        return self._models.get(dataset, {}).get(model_name)

    def get_encoder(self, dataset: str):
        """Retourne le LabelEncoder associé à un dataset."""
        return self._encoders.get(dataset)

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

        # Récupérer le modèle. Alias : le modèle de régression CMAPSS est stocké
        # sous « Huber » mais référencé « Huber Regressor » (préférences, UI,
        # benchmark) → sans cet alias, la prédiction RUL échouait silencieusement.
        models_for_ds = self._models.get(dataset, {})
        _ALIASES = {"Huber Regressor": "Huber"}
        lookup_name = model_name if model_name in models_for_ds \
            else _ALIASES.get(model_name, model_name)
        model_obj = models_for_ds.get(lookup_name)
        if model_obj is None:
            return {'error': f"Modèle {model_name} non disponible pour {dataset}"}

        # Nettoyage NaN/Inf (CMAPSS : capteurs constants = valeurs manquantes)
        # sinon la prédiction RUL renvoie NaN → courbe vide côté frontend.
        X = np.nan_to_num(np.asarray(X, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)

        # Normalisation si nécessaire
        scaler = self._scalers.get(dataset)
        X_input = scaler.transform(X) if (
            scaler is not None and model_name in ['MLP', 'Huber Regressor']
        ) else X

        # Prédiction
        task = 'regression' if dataset == 'CMAPSS' else 'classification'

        # Monitoring du drift en parallèle de la prédiction
        drift_report = None
        detector = self._drift_detectors.get(dataset)
        if detector is not None:
            drift_report = detector.add_production_sample(X)

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
                'drift'      : drift_report,
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
                'drift'      : drift_report,
                'timestamp'  : datetime.now().isoformat()
            }

    def get_anomaly_ensemble(self, dataset: str):
        """
        Retourne l'ensemble d'anomalie du dataset (entraîné paresseusement sur
        les échantillons sains). None si dataset non supporté/indisponible.
        """
        if dataset in self._anomaly_ensembles:
            return self._anomaly_ensembles[dataset]

        ds_key = {"VBL": "vbl", "CWRU": "cwru", "MF": "mf"}.get(dataset)
        if not ds_key:
            self._anomaly_ensembles[dataset] = None
            return None

        try:
            X = np.load(self.data_dir / f"X_{ds_key}.npy")
            with open(self.data_dir / f"y_{ds_key}.pkl", "rb") as f:
                y = pickle.load(f)
            y_low = np.array([str(v).lower() for v in y])
            mask  = np.array(["sain" in v or "normal" in v for v in y_low])
            X_norm = X[mask] if mask.any() else X
            if len(X_norm) > 2000:
                rng = np.random.default_rng(42)
                X_norm = X_norm[rng.choice(len(X_norm), 2000, replace=False)]

            from backend.ml.anomaly_ensemble import AnomalyEnsemble
            ens = AnomalyEnsemble()
            ens.fit(X_norm)
            self._anomaly_ensembles[dataset] = ens
            print(f"  [OK] Ensemble anomalie {dataset} entraîné ({len(X_norm)} samples)")
        except Exception as e:
            print(f"  [WARN] Ensemble anomalie {dataset} indisponible : {e}")
            self._anomaly_ensembles[dataset] = None

        return self._anomaly_ensembles[dataset]

    def predict_anomaly(self, dataset: str,
                     X: np.ndarray) -> dict:
        """Score d'anomalie : autoencoder + consensus de l'ensemble (3 algos)."""
        from backend.api.routes.config import load_config

        detector = self._autoencoders.get(dataset)
        if detector is None:
            return {'error': f"Autoencoder non disponible pour {dataset}"}

        # Seuil dynamique depuis la configuration utilisateur
        cfg = load_config()
        dynamic_threshold = cfg.get(
            'autoencoder_thresholds', {}
        ).get(dataset, 50.0)

        # Nettoyage NaN/Inf : CMAPSS contient des capteurs constants (valeurs
        # manquantes) qui, sans traitement, font diverger l'erreur de
        # reconstruction → score NaN → courbe d'anomalie vide côté frontend.
        X = np.nan_to_num(np.asarray(X, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)

        result = detector.predict(X)

        # Recalculer is_anomaly avec le seuil dynamique
        # (le score 0-100% reste inchangé)
        is_anomaly = result['anomaly_score'] > dynamic_threshold

        score_mean = float(np.nan_to_num(
            np.asarray(result['anomaly_score'], dtype=float), nan=0.0).mean())
        conf_mean = float(np.nan_to_num(
            np.asarray(result['confidence'], dtype=float), nan=0.0).mean())

        out = {
            'anomaly_score'   : score_mean,
            'is_anomaly'      : bool(is_anomaly.any()),
            'confidence'      : conf_mean,
            'threshold_used'  : dynamic_threshold,
            'timestamp'       : datetime.now().isoformat()
        }

        # Consensus de l'ensemble (3 algos) en parallèle de l'autoencoder
        ens = self.get_anomaly_ensemble(dataset)
        if ens is not None:
            try:
                er = ens.predict(X)
                out['ensemble'] = {
                    'consensus_score'  : er.get('consensus_score'),
                    'is_anomaly'       : er.get('is_anomaly'),
                    'votes'            : er.get('votes'),
                    'individual_scores': er.get('individual_scores'),
                }
                # Décision renforcée : anomalie confirmée si AE ET ensemble d'accord
                out['is_anomaly_confirmed'] = bool(out['is_anomaly'] and er.get('is_anomaly'))
            except Exception:
                pass

        return out

    def get_drift_status(self) -> dict:
        """Retourne l'état du drift pour tous les datasets."""
        return {
            ds: det.get_status()
            for ds, det in self._drift_detectors.items()
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
        import pickle
        from sklearn.neural_network import MLPClassifier

        self._retrain_status = {
            "running"   : True,
            "progress"  : 0,
            "message"   : "Préparation...",
            "started_at": datetime.now().isoformat(),
            "result"    : None,
        }

        try:
            from sklearn.preprocessing import LabelEncoder, StandardScaler

            # ── Étape 1 : Charger les données existantes du dataset ──────────
            self._retrain_status.update({"progress": 10,
                                          "message": "Chargement des données existantes..."})
            await asyncio.sleep(0.1)

            ds_key = {"VBL": "vbl", "CWRU": "cwru", "MF": "mf"}.get(dataset)
            X_old, y_old = None, None
            if ds_key:
                try:
                    X_old = np.load(self.data_dir / f"X_{ds_key}.npy")
                    with open(self.data_dir / f"y_{ds_key}.pkl", "rb") as f:
                        y_old = [str(v) for v in pickle.load(f)]
                except Exception:
                    X_old, y_old = None, None

            # ── Étape 2 : Combiner ancien + nouveau (rééquilibrage) ──────────
            self._retrain_status.update({"progress": 25,
                                          "message": "Combinaison des échantillons..."})
            await asyncio.sleep(0.1)

            y_new = [str(v) for v in y_new]
            if (X_old is not None and len(X_old) > 0
                    and X_old.shape[1] == X_new.shape[1]):
                rng    = np.random.default_rng(42)
                n_keep = min(len(X_old), max(300, len(X_new) * 4))
                idx    = rng.choice(len(X_old), n_keep, replace=False)
                X_comb = np.vstack([X_old[idx], X_new])
                y_comb = [y_old[i] for i in idx] + y_new
            else:
                X_comb, y_comb = X_new, y_new

            # Garde-fou : un classifieur exige au moins 2 classes
            if len(set(y_comb)) < 2:
                raise ValueError(
                    "Réentraînement impossible avec une seule classe. Fournir "
                    "aussi des exemples d'autres états, ou utiliser un dataset "
                    "dont les données de référence sont disponibles."
                )

            # ── Étape 3 : Encodage + normalisation + entraînement MLP ────────
            self._retrain_status.update({"progress": 40,
                                          "message": f"Réentraînement MLP — "
                                                     f"{len(X_comb)} échantillons, "
                                                     f"{len(set(y_comb))} classes..."})
            await asyncio.sleep(0.1)

            encoder  = LabelEncoder()
            y_enc    = encoder.fit_transform(y_comb)
            scaler   = StandardScaler()
            X_scaled = scaler.fit_transform(X_comb)

            new_mlp = MLPClassifier(
                hidden_layer_sizes=(256, 128, 64),
                max_iter=200, random_state=42,
                early_stopping=True, validation_fraction=0.1,
            )
            new_mlp.fit(X_scaled, y_enc)
            all_classes = list(encoder.classes_)

            self._retrain_status.update({"progress": 60,
                                          "message": "Mise à jour du registry..."})
            await asyncio.sleep(0.1)

            # Modèle + encodeur + scaler cohérents (prédictions en labels texte)
            self._models.setdefault(dataset, {})["MLP"] = new_mlp
            self._encoders[dataset] = encoder
            self._scalers[dataset]  = scaler
            self.set_active_model(dataset, "MLP")

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
                    "encoder"  : encoder,
                    "scaler"   : scaler,
                    "classes"  : [str(c) for c in all_classes],
                    "new_label": new_label,
                    "trained_at": datetime.now().isoformat(),
                }, f)

            # ── Succès ────────────────────────────────────────────────────────
            test_score = None
            try:
                test_score = float(new_mlp.score(X_scaled, y_enc))
            except Exception:
                pass

            # Versioning du modèle (best-effort, indépendant)
            try:
                from backend.db.models import SessionLocal
                from backend.ml.model_versioning import version_manager

                _db = SessionLocal()
                try:
                    version_manager.save_version(
                        _db, new_mlp, dataset, "MLP",
                        metrics={
                            "accuracy" : test_score,
                            "n_samples": len(X_comb),
                            "n_classes": int(len(new_mlp.classes_)) if hasattr(new_mlp, "classes_") else None,
                            "notes"    : f"Réentraînement — nouveau défaut '{new_label}'",
                        },
                        triggered_by="user",
                    )
                finally:
                    _db.close()
            except Exception as ve:
                print(f"  [WARN] Versioning échoué : {ve}")

            # Journal d'audit (best-effort, indépendant du versioning)
            try:
                from backend.ml.audit_trail import audit_trail
                audit_trail.log_retrain(
                    dataset      = dataset,
                    model_name   = "MLP",
                    n_samples    = len(X_comb),
                    new_accuracy = test_score or 0.0,
                    triggered_by = "user",
                )
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
            print(f"  [OK] Préférences utilisateur chargées")


# Instance globale — partagée par toute l'API
registry = ModelRegistry()