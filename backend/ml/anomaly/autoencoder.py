"""
Autoencoder pour détection d'anomalies non supervisée.
Entraîné uniquement sur données saines.
Fonctionne sur n'importe quel dataset — c'est le module universel
qui détecte les défauts inconnus des modèles supervisés.
"""

import torch
import torch.nn as nn
import numpy as np
import pickle
from pathlib import Path
from torch.utils.data import Dataset, DataLoader


class Autoencoder(nn.Module):
    """
    Autoencoder fully-connected pour signaux vibratoires.
    Entrée/Sortie : vecteur de features (45, 73, 128 features selon dataset)
    Latent space  : 16 dimensions
    """
    def __init__(self, input_dim: int, latent_dim: int = 16):
        super().__init__()

        # Encodeur : input_dim → latent_dim
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, latent_dim)
        )

        # Décodeur : latent_dim → input_dim
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, input_dim)
        )

    def forward(self, x):
        z    = self.encoder(x)
        x_hat = self.decoder(z)
        return x_hat

    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        """Erreur de reconstruction par échantillon."""
        x_hat = self.forward(x)
        return ((x - x_hat) ** 2).mean(dim=1)


class AnomalyDetector:
    """
    Wrapper haut niveau pour l'Autoencoder.
    Gère l'entraînement, le seuillage et la prédiction.
    """

    def __init__(self, input_dim: int, latent_dim: int = 16,
                 device: str = None):
        self.device = torch.device(
            device or ('cuda' if torch.cuda.is_available() else 'cpu')
        )
        self.model      = Autoencoder(input_dim, latent_dim).to(self.device)
        self.threshold  = None   # fixé après entraînement
        self.train_errors = None
        self.input_dim  = input_dim
        self.scaler_mean = None
        self.scaler_std  = None

    def _normalize(self, X: np.ndarray) -> np.ndarray:
        """Normalisation Z-score interne."""
        if self.scaler_mean is None:
            self.scaler_mean = X.mean(axis=0)
            self.scaler_std  = X.std(axis=0)
            self.scaler_std  = np.where(
                self.scaler_std == 0, 1.0, self.scaler_std
            )
        return (X - self.scaler_mean) / self.scaler_std

    def fit(self, X_normal: np.ndarray,
            epochs: int = 50,
            batch_size: int = 256,
            lr: float = 1e-3,
            threshold_percentile: float = 95.0,
            verbose: bool = True) -> dict:
        """
        Entraîne l'Autoencoder sur les données saines uniquement.
        Le seuil d'anomalie est fixé au percentile P des erreurs de
        reconstruction sur les données d'entraînement.

        threshold_percentile=95 → 95% des données saines
        seront correctement identifiées comme normales.
        """
        X_norm = self._normalize(X_normal)
        X_tensor = torch.tensor(X_norm, dtype=torch.float32)

        dataset    = torch.utils.data.TensorDataset(X_tensor)
        dataloader = DataLoader(
            dataset, batch_size=batch_size, shuffle=True
        )

        optimizer = torch.optim.Adam(
            self.model.parameters(), lr=lr, weight_decay=1e-5
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, patience=5, factor=0.5
        )
        criterion = nn.MSELoss()

        history = []
        self.model.train()

        for epoch in range(epochs):
            epoch_loss = 0.0
            for (batch,) in dataloader:
                batch = batch.to(self.device)
                optimizer.zero_grad()
                recon = self.model(batch)
                loss  = criterion(recon, batch)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * len(batch)

            avg_loss = epoch_loss / len(X_normal)
            scheduler.step(avg_loss)
            history.append(avg_loss)

            if verbose and (epoch + 1) % 10 == 0:
                print(f"  Epoch {epoch+1:3d}/{epochs} | "
                      f"Loss: {avg_loss:.6f}")

        # Calcul du seuil sur les données d'entraînement
        self.model.eval()
        with torch.no_grad():
            X_t      = torch.tensor(X_norm, dtype=torch.float32).to(self.device)
            errors   = self.model.reconstruction_error(X_t).cpu().numpy()

        self.train_errors = errors
        self.threshold    = float(np.percentile(errors, threshold_percentile))

        if verbose:
            print(f"\n  Seuil anomalie (P{threshold_percentile:.0f}) : "
                  f"{self.threshold:.6f}")
            print(f"  Erreur min : {errors.min():.6f}")
            print(f"  Erreur max : {errors.max():.6f}")
            print(f"  Erreur moy : {errors.mean():.6f}")

        return {'history': history, 'threshold': self.threshold}

    def predict(self, X: np.ndarray) -> dict:
        """
        Prédit le score d'anomalie pour chaque échantillon.

        Retourne un dict avec :
          - anomaly_score  : float 0-100% par échantillon
          - is_anomaly     : bool (True si > seuil)
          - recon_error    : erreur de reconstruction brute
          - confidence     : confiance de la décision
        """
        X_norm   = (X - self.scaler_mean) / self.scaler_std
        X_tensor = torch.tensor(
            X_norm.astype(np.float32), dtype=torch.float32
        ).to(self.device)

        self.model.eval()
        with torch.no_grad():
            errors = self.model.reconstruction_error(X_tensor).cpu().numpy()

        # Normalisation du score 0-100%
        # Basée sur la distribution des erreurs d'entraînement
        p5  = np.percentile(self.train_errors, 5)
        p99 = np.percentile(self.train_errors, 99)

        scores = np.clip(
            (errors - p5) / (p99 - p5 + 1e-10) * 100,
            0, 100
        )

        is_anomaly = errors > self.threshold
        confidence = np.where(
            is_anomaly,
            np.clip((errors - self.threshold) /
                    (p99 - self.threshold + 1e-10), 0, 1),
            np.clip((self.threshold - errors) /
                    (self.threshold - p5 + 1e-10), 0, 1)
        )

        return {
            'anomaly_score' : scores,
            'is_anomaly'    : is_anomaly,
            'recon_error'   : errors,
            'confidence'    : confidence
        }

    def save(self, path: str):
        """Sauvegarde le modèle et ses paramètres."""
        torch.save({
            'model_state'  : self.model.state_dict(),
            'threshold'    : self.threshold,
            'train_errors' : self.train_errors,
            'input_dim'    : self.input_dim,
            'scaler_mean'  : self.scaler_mean,
            'scaler_std'   : self.scaler_std,
        }, path)
        print(f"✅ AnomalyDetector sauvegardé → {path}")

    @classmethod
    def load(cls, path: str) -> 'AnomalyDetector':
        """Charge un modèle sauvegardé."""
        checkpoint = torch.load(path, map_location='cpu', weights_only=False)
        detector   = cls(
            input_dim  = checkpoint['input_dim'],
            device     = 'cpu'
        )
        detector.model.load_state_dict(checkpoint['model_state'])
        detector.model.eval()
        detector.threshold    = checkpoint['threshold']
        detector.train_errors = checkpoint['train_errors']
        detector.scaler_mean  = checkpoint['scaler_mean']
        detector.scaler_std   = checkpoint['scaler_std']
        return detector