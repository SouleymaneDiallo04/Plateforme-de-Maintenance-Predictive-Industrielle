"""
CNN 1D pour classification des défauts d'engrenages MCC5-THU.
Travaille directement sur le signal brut (1024 points × 3 canaux)
sans extraction de features manuelles.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from pathlib import Path


class GearFaultCNN(nn.Module):
    """
    CNN 1D pour défauts d'engrenages.
    Entrée  : (batch, 3, 1024) — 3 canaux, 1024 points
    Sortie  : (batch, n_classes)
    """
    def __init__(self, n_classes: int, dropout: float = 0.3):
        super().__init__()

        # Bloc 1 — features basse fréquence (grande fenêtre)
        self.conv1 = nn.Sequential(
            nn.Conv1d(3, 32, kernel_size=64, stride=2, padding=32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )

        # Bloc 2 — features moyenne fréquence
        self.conv2 = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=32, stride=1, padding=16),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )

        # Bloc 3 — features haute fréquence (petite fenêtre)
        self.conv3 = nn.Sequential(
            nn.Conv1d(64, 128, kernel_size=16, stride=1, padding=8),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )

        # Bloc 4 — abstraction finale
        self.conv4 = nn.Sequential(
            nn.Conv1d(128, 256, kernel_size=8, stride=1, padding=4),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(8)   # output fixe quelle que soit la taille
        )

        # Classifieur
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 8, 512),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, n_classes)
        )

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        return self.classifier(x)


class GearDataset(Dataset):
    """Dataset PyTorch pour les signaux d'engrenages."""

    def __init__(self, signals: list, labels: list,
                 label_encoder, rpm_list: list = None):
        """
        signals     : liste de np.ndarray (1024, 3)
        labels      : liste de strings
        label_encoder : sklearn LabelEncoder fitté
        rpm_list    : liste de float (RPM par signal) — optionnel
        """
        self.X   = torch.tensor(signals, dtype=torch.float32)
        # Transposer : (N, 1024, 3) → (N, 3, 1024) pour Conv1d
        self.X   = self.X.permute(0, 2, 1)
        self.y   = torch.tensor(
            label_encoder.transform(labels), dtype=torch.long
        )
        self.rpm = rpm_list

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


def prepare_cnn_data(signals_mcc: list,
                     label_encoder) -> tuple:
    """
    Prépare les données brutes pour le CNN.
    Retourne (all_windows, all_labels, all_meta).
    """
    import re
    all_windows, all_labels, all_meta = [], [], []

    for sig in signals_mcc:
        rpm_match = re.search(r'(\d{3,4})rpm', sig.unit_id)
        rpm = float(rpm_match.group(1)) if rpm_match else 2000.0

        for w_idx in range(sig.signals.shape[0]):
            window = sig.signals[w_idx]   # (1024, 3)
            all_windows.append(window)
            all_labels.append(sig.label)
            all_meta.append({
                'unit_id'   : sig.unit_id,
                'window_idx': w_idx,
                'rpm'       : rpm
            })

    return np.array(all_windows), all_labels, all_meta

class LazyGearDataset(Dataset):
    """Dataset qui lit les fenêtres à la demande (sans copie massive)."""

    def __init__(self, signals: list, label_encoder,
                 indices: list = None):
        """
        signals : liste de UnifiedSignal
        label_encoder : LabelEncoder déjà fitté
        indices : liste optionnelle de (sig_idx, win_idx)
        """
        self.signals = signals
        self.le = label_encoder

        if indices is None:
            self.indices = []
            for sig_idx, sig in enumerate(signals):
                for win_idx in range(sig.signals.shape[0]):
                    self.indices.append((sig_idx, win_idx))
        else:
            self.indices = indices

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        sig_idx, win_idx = self.indices[idx]
        sig = self.signals[sig_idx]
        # (1024, 3) -> (3, 1024) pour Conv1d
        win = sig.signals[win_idx].astype(np.float32)
        tensor = torch.from_numpy(win).permute(1, 0)
        label = self.le.transform([sig.label])[0]
        return tensor, label