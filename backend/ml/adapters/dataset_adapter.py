"""
DatasetAdapter v2 — avec support direct des archives ZIP.
Lit les CSV depuis un dossier ou depuis un fichier .zip sans décompresser.
"""

import os
import yaml
import pickle
import hashlib
import zipfile
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
from scipy.signal import resample_poly
from math import gcd
import io

# ── Constantes globales ─────────────────────────────────────────────────────
TARGET_FS   = 12_800   # Hz (fréquence cible pour tous les signaux temporels)
WINDOW_SIZE = 1_024    # points par fenêtre
HOP_SIZE    = 512      # chevauchement 50 %
CACHE_DIR   = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Labels par défaut pour VBL (peut être surchargé par la config YAML)
DEFAULT_VALID_LABELS = {'normal', 'bearing', 'misalignment', 'unbalance'}


# ── Structure de sortie unifiée ─────────────────────────────────────────────
@dataclass
class UnifiedSignal:
    signals:       np.ndarray        # (n_windows, window_size, n_channels)
    sampling_rate: Optional[float]   # None pour CMAPSS (cycles), sinon TARGET_FS
    label:         Optional[str]
    unit_id:       Optional[str]
    cycle:         Optional[int]
    rul:           Optional[float]
    source:        str
    metadata:      dict = field(default_factory=dict)


# ── Utilitaires ─────────────────────────────────────────────────────────────
def resample_signal(signal: np.ndarray, fs_in: float, fs_out: float) -> np.ndarray:
    """Rééchantillonne un signal (n_samples, n_channels) de fs_in vers fs_out."""
    if fs_in == fs_out:
        return signal
    g = gcd(int(fs_out), int(fs_in))
    up   = int(fs_out) // g
    down = int(fs_in)  // g
    resampled = resample_poly(signal, up, down, axis=0)
    return resampled.astype(np.float32)


def normalize_signal(signal: np.ndarray, mean=None, std=None):
    """Z-score par canal. Retourne (signal_normalisé, mean, std)."""
    if mean is None:
        mean = signal.mean(axis=0, keepdims=True)
    if std is None:
        std  = signal.std(axis=0, keepdims=True)
    std = np.where(std == 0, 1.0, std)
    return ((signal - mean) / std).astype(np.float32), mean, std


def sliding_windows(signal: np.ndarray,
                    window_size: int = WINDOW_SIZE,
                    hop_size: int    = HOP_SIZE) -> np.ndarray:
    """Découpe un signal (n_samples, n_channels) en fenêtres."""
    n_samples = signal.shape[0]
    windows = []
    start = 0
    while start + window_size <= n_samples:
        windows.append(signal[start:start+window_size])
        start += hop_size
    if not windows:   # signal trop court → padding
        pad = np.zeros((window_size, signal.shape[1]), dtype=np.float32)
        pad[:n_samples] = signal
        windows.append(pad)
    return np.stack(windows, axis=0)


def cache_key(path: str, config: dict) -> str:
    """Génère une clé de cache unique."""
    content = f"{path}{yaml.dump(config, sort_keys=True)}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def compute_norm_stats(arrays: list) -> tuple:
    """Calcule mean et std pour la normalisation à partir d'une liste d'arrays."""
    if not arrays:
        return None, None
    combined  = np.concatenate(arrays, axis=0)
    norm_mean = combined.mean(axis=0, keepdims=True)
    norm_std  = combined.std(axis=0, keepdims=True)
    norm_std  = np.where(norm_std == 0, 1.0, norm_std)
    return norm_mean, norm_std


# ── DatasetAdapter principal ────────────────────────────────────────────────
class DatasetAdapter:
    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.name = self.config.get("name", "unknown")
        self.valid_labels = set(self.config.get("valid_labels", DEFAULT_VALID_LABELS))

    def _extract_label_from_path(self, path_in_zip: str) -> Optional[str]:
        known = self.valid_labels
        for part in Path(path_in_zip).parts:
            if part.lower() in known:
                return part.lower()
        return None

    def load(self, data_path: str,
         max_files: Optional[int] = None,
         use_cache: bool = True) -> list:

        key = cache_key(data_path, self.config)
        cache_file = CACHE_DIR / f"{key}.pkl"

        if use_cache and cache_file.exists():
            print(f"  Cache trouvé ({cache_file.name}) — chargement rapide...")
            with open(cache_file, "rb") as f:
               return pickle.load(f)

        path = Path(data_path)
        fmt  = self.config.get("format", "csv")

        if fmt == "txt":
            signals = self._load_txt_cmapss(data_path)
        elif fmt == "mat":
            signals = self._load_mat(path, max_files)
        elif fmt == "mechanical_faults":
            signals = self._load_mechanical_faults(path, max_files)
        elif path.suffix.lower() == ".zip":
            signals = self._load_from_zip(path, max_files)
        elif path.is_dir():
            signals = self._load_from_folder(path, max_files)
        else:
            raise ValueError(f"Chemin non reconnu : {data_path}")

        if use_cache:
            print(f"  Sauvegarde cache → {cache_file.name}")
            with open(cache_file, "wb") as f:
                pickle.dump(signals, f)

        return signals

    # ─── Chargement depuis un dossier décompressé (CSV) ─────────────────────
    def _load_from_folder(self, folder_path: Path, max_files=None) -> List[UnifiedSignal]:
        signals = []
        label_mapping = self.config.get("label_mapping", {})
        signal_cols = self.config.get("signal_columns", [])
        fs_in = float(self.config.get("sampling_rate", TARGET_FS))

        class_folders = []
        for d in sorted(folder_path.iterdir()):
            if not d.is_dir():
                continue
            label_raw = self._extract_label_from_path(d.name)
            if label_raw:
                class_folders.append((label_raw, d))

        if not class_folders:
            raise ValueError(
                f"Aucun sous-dossier de classe trouvé dans {folder_path}. "
                f"Labels attendus : {self.valid_labels}"
            )

        print(f"  Classes trouvées : {[lbl for lbl, _ in class_folders]}")

        norm_mean, norm_std = None, None
        for label_raw, folder in class_folders:
            if label_raw == 'normal':
                files = sorted(folder.glob('*.csv'))[:50]
                arrays = []
                for f in files:
                    try:
                        df = pd.read_csv(f)
                        arr = self._extract_columns(df, signal_cols)
                        arrays.append(resample_signal(arr, fs_in, TARGET_FS))
                    except Exception:
                        pass
                norm_mean, norm_std = compute_norm_stats(arrays)
                if norm_mean is not None:
                    print(f"  Stats normalisation calculées sur {len(arrays)} fichiers 'normal'")
                break

        for label_raw, folder in class_folders:
            label = label_mapping.get(label_raw, label_raw)
            csv_files = sorted(folder.glob('*.csv'))
            if max_files:
                csv_files = csv_files[:max_files]

            print(f"  [{label:20s}] {len(csv_files)} fichiers...")

            for csv_file in csv_files:
                try:
                    df = pd.read_csv(csv_file)
                    arr = self._extract_columns(df, signal_cols)
                    arr = resample_signal(arr, fs_in, TARGET_FS)
                    arr, _, _ = normalize_signal(arr, norm_mean, norm_std)
                    windows = sliding_windows(arr)
                    signals.append(UnifiedSignal(
                        signals=windows,
                        sampling_rate=TARGET_FS,
                        label=label,
                        unit_id=csv_file.stem,
                        cycle=None,
                        rul=None,
                        source=self.name
                    ))
                except Exception as e:
                    print(f"    ERREUR {csv_file.name}: {e}")

        print(f"\n  Total : {len(signals)} signaux chargés depuis dossier")
        return signals

    # ─── Chargement depuis une archive ZIP (sans décompresser) ──────────────
    def _load_from_zip(self, zip_path: Path,
                       max_files: Optional[int] = None) -> List[UnifiedSignal]:
        """
        Charge les CSV depuis une archive ZIP.
        Deux modes selon le YAML :
          - label_from_folder: true   → label = nom du sous-dossier (VBL)
          - label_from_filename: true → label = extrait du nom de fichier (MCC5‑THU)
        """
        signals = []
        label_mapping = self.config.get("label_mapping", {})
        signal_cols = self.config.get("signal_columns", [])
        fs_in = float(self.config.get("sampling_rate", TARGET_FS))
        label_from_folder = self.config.get("label_from_folder", False)
        label_from_file = self.config.get("label_from_filename", False)
        label_rules = self.config.get("filename_label_rules", [])

        with zipfile.ZipFile(zip_path, 'r') as archive:
            all_csv = [
                f for f in archive.namelist()
                if f.lower().endswith('.csv')
                and '__MACOSX' not in f
                and not Path(f).name.startswith('._')
            ]
            print(f"  CSV trouvés dans le ZIP : {len(all_csv)}")

            csv_by_label = {}
            for csv_path in all_csv:
                stem = Path(csv_path).stem
                if label_from_folder:
                    raw_label = self._extract_label_from_path(csv_path)
                elif label_from_file:
                    raw_label = self._label_from_filename(stem, label_rules)
                else:
                    raw_label = None

                if raw_label is None:
                    continue
                csv_by_label.setdefault(raw_label, []).append(csv_path)

            if not csv_by_label:
                raise ValueError(
                    f"Aucun label détecté dans {zip_path.name}.\n"
                    f"Vérifie label_from_folder / label_from_filename dans le YAML."
                )

            print(f"  Classes détectées :")
            for lbl, files in sorted(csv_by_label.items()):
                print(f"    {lbl:30s} : {len(files)} fichiers")

            # Statistiques normalisation sur données saines
            norm_mean, norm_std = None, None
            normal_key = next(
                (k for k in csv_by_label if 'normal' in k or 'health' in k or 'sain' in k),
                None
            )
            if normal_key:
                arrays = []
                for csv_path in csv_by_label[normal_key][:30]:
                    try:
                        with archive.open(csv_path) as f:
                            df = pd.read_csv(f)
                            arr = self._extract_columns(df, signal_cols)
                            if fs_in != TARGET_FS:
                                arr = resample_signal(arr, fs_in, TARGET_FS)
                            arrays.append(arr)
                    except Exception:
                        pass
                norm_mean, norm_std = compute_norm_stats(arrays)
                if norm_mean is not None:
                    print(f"  Stats calculées sur {len(arrays)} fichiers '{normal_key}'")

            # Chargement par label
            for raw_label, csv_files in sorted(csv_by_label.items()):
                label = label_mapping.get(raw_label, raw_label)
                files_to_load = csv_files[:max_files] if max_files else csv_files
                print(f"  [{label:25s}] {len(files_to_load)} fichiers...")

                for csv_path in files_to_load:
                    try:
                        with archive.open(csv_path) as f:
                            df = pd.read_csv(f)
                            arr = self._extract_columns(df, signal_cols)

                        if fs_in != TARGET_FS:
                            arr = resample_signal(arr, fs_in, TARGET_FS)

                        arr, _, _ = normalize_signal(arr, norm_mean, norm_std)
                        windows = sliding_windows(arr)

                        signals.append(UnifiedSignal(
                            signals=windows,
                            sampling_rate=TARGET_FS,
                            label=label,
                            unit_id=Path(csv_path).stem,
                            cycle=None,
                            rul=None,
                            source=self.name
                        ))
                    except Exception as e:
                        print(f"    ERREUR {Path(csv_path).name}: {e}")

        print(f"\n  Total : {len(signals)} signaux chargés depuis ZIP")
        return signals

    # ─── Extraction robuste des colonnes signal ────────────────────────────
    def _extract_columns(self, df: pd.DataFrame, signal_cols: list) -> np.ndarray:
        existing = [c for c in signal_cols if c in df.columns]
        if existing:
            return df[existing].values.astype(np.float32)
        n = len(signal_cols)
        return df.iloc[:, :n].values.astype(np.float32)

    # ─── Chargement spécifique pour CMAPSS (format TXT) ─────────────────────
    def _load_txt_cmapss(self, data_path: str) -> List[UnifiedSignal]:
        signals = []
        data_path = Path(data_path)
        signal_cols = self.config.get("signal_columns", [])
        meta_cols = self.config.get("meta_columns", [])
        all_cols = meta_cols + signal_cols
        window_cycles = 30

        train_file = data_path / "train_FD001.txt"
        if not train_file.exists():
            raise FileNotFoundError(f"Fichier introuvable : {train_file}")

        print(f"  Chargement CMAPSS : {train_file.name}...")
        df = pd.read_csv(train_file, sep=r'\s+', header=None, names=all_cols, engine='python')

        required = ['unit_id', 'cycle']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Colonne manquante : {col}")

        max_cycles = df.groupby('unit_id')['cycle'].max()
        df['max_cycle'] = df['unit_id'].map(max_cycles)
        df['rul'] = (df['max_cycle'] - df['cycle']).clip(upper=125)

        sain_df = df[df['rul'] > 100][signal_cols]
        if len(sain_df) == 0:
            print("  Attention : aucune donnée saine trouvée (RUL>100). Normalisation sur tout le dataset.")
            sain_df = df[signal_cols]

        norm_mean = sain_df.mean().values.astype(np.float32)
        norm_std = sain_df.std().values.astype(np.float32)
        norm_std = np.where(norm_std == 0, 1.0, norm_std)

        for unit_id, unit_df in df.groupby('unit_id'):
            unit_df = unit_df.sort_values('cycle').reset_index(drop=True)
            sensor_vals = unit_df[signal_cols].values.astype(np.float32)
            sensor_vals = (sensor_vals - norm_mean) / norm_std

            for i in range(0, len(sensor_vals) - window_cycles + 1, 1):
                window = sensor_vals[i:i+window_cycles]
                rul_value = unit_df.loc[i+window_cycles-1, 'rul']
                cycle_num = unit_df.loc[i+window_cycles-1, 'cycle']

                if rul_value > 80:
                    label = "sain"
                elif rul_value > 40:
                    label = "degradation_precoce"
                elif rul_value > 15:
                    label = "degradation_avancee"
                else:
                    label = "critique"

                signals.append(UnifiedSignal(
                    signals=window[np.newaxis, :, :],
                    sampling_rate=None,
                    label=label,
                    unit_id=str(unit_id),
                    cycle=int(cycle_num),
                    rul=float(rul_value),
                    source=self.name
                ))

        print(f"  Total : {len(signals)} fenêtres CMAPSS chargées")
        return signals

    # ── Chargement des fichiers .mat (CWRU) ─────────────────────────────────
    def _load_mat(self, folder_path: Path, max_files=None) -> List[UnifiedSignal]:
        from scipy.io import loadmat
        import re

        signals = []
        signal_cols = self.config.get("signal_columns", [])
        fs_in = float(self.config.get("sampling_rate", TARGET_FS))
        label_mapping = self.config.get("label_mapping", {})
        label_rules = self.config.get("filename_label_rules", [])

        mat_files = sorted(folder_path.glob("*.mat"))
        if max_files:
            mat_files = mat_files[:max_files]

        print(f"  Chargement CWRU : {len(mat_files)} fichiers .mat...")

        norm_mean, norm_std = None, None
        normal_arrays = []
        for mat_file in mat_files:
            raw_label = self._label_from_filename(mat_file.stem, label_rules)
            if raw_label == "normal":
                try:
                    mat_data = loadmat(mat_file)
                    key_de = self._find_mat_key(mat_data, "DE_time")
                    if key_de:
                        arr = mat_data[key_de].flatten().astype(np.float32)
                        arr = arr.reshape(-1, 1)
                        normal_arrays.append(resample_signal(arr, fs_in, TARGET_FS))
                except Exception:
                    pass

        if normal_arrays:
            norm_mean, norm_std = compute_norm_stats(normal_arrays)
            print(f"  Stats calculées sur {len(normal_arrays)} fichiers normaux")

        for mat_file in mat_files:
            try:
                raw_label = self._label_from_filename(mat_file.stem, label_rules)
                if raw_label is None:
                    print(f"  Fichier ignoré (label inconnu) : {mat_file.name}")
                    continue

                label = label_mapping.get(raw_label, raw_label)
                mat_data = loadmat(mat_file)
                key_de = self._find_mat_key(mat_data, "DE_time")
                if key_de is None:
                    print(f"  Clé DE_time introuvable dans {mat_file.name}")
                    continue

                arr = mat_data[key_de].flatten().astype(np.float32)
                arr = arr.reshape(-1, 1)
                arr = resample_signal(arr, fs_in, TARGET_FS)
                arr, _, _ = normalize_signal(arr, norm_mean, norm_std)
                windows = sliding_windows(arr)

                signals.append(UnifiedSignal(
                    signals=windows,
                    sampling_rate=TARGET_FS,
                    label=label,
                    unit_id=mat_file.stem,
                    cycle=None,
                    rul=None,
                    source=self.name
                ))
                print(f"  ✓ {mat_file.name:15s} → {label} ({windows.shape[0]} fenêtres)")
            except Exception as e:
                print(f"  ERREUR {mat_file.name}: {e}")

        print(f"\n  Total : {len(signals)} signaux CWRU chargés")
        return signals

    def _find_mat_key(self, mat_data: dict, key_suffix: str) -> Optional[str]:
        for key in mat_data.keys():
            if key.endswith(key_suffix) and not key.startswith("__"):
                return key
        return None

    def _label_from_filename(self, filename: str, rules: list) -> Optional[str]:
        import re
        for rule in rules:
            if re.search(rule["pattern"], filename):
                return rule["label"]
        return None


    def _load_mechanical_faults(self, data_path: Path,
                                max_files: Optional[int] = None) -> list:
        """
        Charge le dataset Mechanical Faults Mendeley.
        Structure : ZIP principal → 20 sous-ZIPs → fichiers .npy (4, 25000)
        """
        signals = []
        label_rules = self.config.get("filename_label_rules", [])
        label_mapping = self.config.get("label_mapping", {})
        fs_in = float(self.config.get("sampling_rate", 25000))

        # ── Détecter ZIP principal ou dossier de ZIPs ─────────────────────────
        if data_path.suffix.lower() == '.zip':
            outer_zip = zipfile.ZipFile(data_path, 'r')
            sub_zips = [
                f for f in outer_zip.namelist()
                if f.lower().endswith('.zip')
                and '__MACOSX' not in f
            ]
            zip_source = 'nested'
            print(f"  Sous-ZIPs trouvés : {len(sub_zips)}")
        else:
            sub_zips = sorted(data_path.glob('*.zip'))
            zip_source = 'folder'
            outer_zip = None
            print(f"  ZIPs trouvés : {len(sub_zips)}")

        # ── Première passe : stats normalisation sur données saines ───────────
        norm_mean, norm_std = None, None
        normal_arrays = []

        for zip_entry in sub_zips:
            zip_name = zip_entry if isinstance(zip_entry, str) else str(zip_entry)
            raw_label = self._label_from_filename(
                Path(zip_name).stem, label_rules
            )
            if raw_label != 'normal':
                continue
            try:
                arrays = self._read_mech_fault_zip(
                    zip_entry, outer_zip, zip_source, max_files=10
                )
                normal_arrays.extend(arrays)
            except Exception as e:
                print(f"  ERREUR normalisation {Path(zip_name).name}: {e}")

        if normal_arrays:
            combined = np.concatenate(normal_arrays, axis=0)
            norm_mean = combined.mean(axis=0, keepdims=True).astype(np.float32)
            norm_std = combined.std(axis=0, keepdims=True).astype(np.float32)
            norm_std = np.where(norm_std == 0, 1.0, norm_std)
            print(f"  Stats normalisation : {len(normal_arrays)} segments sains")

        # ── Deuxième passe : chargement complet ───────────────────────────────
        label_counts = {}

        for zip_entry in sub_zips:
            zip_name = zip_entry if isinstance(zip_entry, str) else str(zip_entry)
            raw_label = self._label_from_filename(
                Path(zip_name).stem, label_rules
            )
            if raw_label is None:
                print(f"  ⚠ Label inconnu : {Path(zip_name).name}")
                continue

            label = label_mapping.get(raw_label, raw_label)

            try:
                arrays = self._read_mech_fault_zip(
                    zip_entry, outer_zip, zip_source, max_files=max_files
                )

                # Remplace cette partie dans _load_mechanical_faults
                for arr in arrays:
    # 1. Resampling 25 kHz → 12 800 Hz
                    arr_rs = resample_signal(
                        arr.astype(np.float32), fs_in, TARGET_FS
              )

    # 2. Normalisation Z-score par canal (global, pas sur sains uniquement)
    # Pour Mechanical Faults : normalisation indépendante par fichier
                    arr_norm, _, _ = normalize_signal(arr_rs)   # sans mean/std externe

    # 3. Fenêtrage avec grande fenêtre pour bonne résolution fréquentielle
                    windows = sliding_windows(
                        arr_norm,
                        window_size=4096,   # résolution 3.125 Hz — voit les harmoniques
                        hop_size=1024
                   )

                    signals.append(UnifiedSignal(
                        signals = windows,
                        sampling_rate = TARGET_FS,
                        label = label,
                        unit_id = Path(zip_name).stem,
                        cycle = None,
                        rul = None,
                        source = self.name
                   ))

                label_counts[label] = label_counts.get(label, 0) + len(arrays)

            except Exception as e:
                print(f"  ERREUR {Path(zip_name).name}: {e}")

        if outer_zip:
            outer_zip.close()

        print(f"\n  Distribution :")
        for lbl, cnt in sorted(label_counts.items()):
            print(f"    {lbl:20s} : {cnt} fichiers .npy")
        print(f"  Total : {len(signals)} signaux chargés")
        return signals


    def _read_mech_fault_zip(self, zip_entry, outer_zip,
                          zip_source: str,
                          max_files: Optional[int] = None) -> list:
        """
    Lit les fichiers .npy depuis un sous-ZIP Mechanical Faults.
    Chaque .npy a shape (4, 25000) → on transpose en (25000, 4).
    Retourne une liste de np.ndarray (25000, 4).
        """
        import io
        arrays = []

    # Ouvrir le sous-ZIP
        if zip_source == 'nested':
            with outer_zip.open(zip_entry) as f:
                inner_zip = zipfile.ZipFile(io.BytesIO(f.read()))
        else:
            inner_zip = zipfile.ZipFile(zip_entry, 'r')

    # Lister les .npy
        npy_files = [
            f for f in inner_zip.namelist()
            if f.lower().endswith('.npy')
            and '__MACOSX' not in f
            and not Path(f).name.startswith('._')
        ]

        if max_files:
            npy_files = npy_files[:max_files]

        for npy_path in npy_files:
            try:
                with inner_zip.open(npy_path) as f:
                    data = np.load(f)          # shape (4, 25000)

            # Validation de la shape
                if data.ndim != 2:
                    continue
                if data.shape[0] == 4:
                    arr = data.T               # → (25000, 4)
                elif data.shape[1] == 4:
                    arr = data                 # déjà (N, 4)
                else:
                    continue

                arrays.append(arr.astype(np.float32))

            except Exception:
                pass

        inner_zip.close()
        return arrays

    