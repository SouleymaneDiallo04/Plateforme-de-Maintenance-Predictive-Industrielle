"""Upload et configuration de datasets custom."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import shutil, yaml, io, tempfile
import numpy as np
import pandas as pd
from pathlib import Path

router = APIRouter(tags=["Dataset"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DatasetConfigRequest(BaseModel):
    name            : str
    sampling_rate   : float
    signal_columns  : List[str]
    label_column    : Optional[str] = None
    label_from_folder: bool = False
    label_mapping   : Optional[Dict[str, str]] = {}
    task            : str = "classification"   # ou "regression"


@router.get("/datasets")
def list_datasets():
    """Liste tous les datasets disponibles."""
    return {
        "datasets": [
            {
                "id"     : "VBL",
                "name"   : "VBL-VA001",
                "task"   : "classification",
                "defauts": ["sain", "roulement",
                            "desalignement", "desequilibre"],
                "n_classes": 4
            },
            {
                "id"     : "CWRU",
                "name"   : "CWRU Bearing Dataset",
                "task"   : "classification",
                "defauts": ["sain",
                            "roulement_interne_faible",
                            "roulement_interne_moyen",
                            "roulement_interne_grave",
                            "roulement_bille_faible",
                            "roulement_bille_moyen",
                            "roulement_bille_grave",
                            "roulement_externe_faible",
                            "roulement_externe_moyen",
                            "roulement_externe_grave"],
                "n_classes": 10
            },
            {
                "id"     : "MF",
                "name"   : "Mechanical Faults Mendeley",
                "task"   : "classification",
                "defauts": ["sain", "desalignement",
                            "desequilibre", "jeu_mecanique"],
                "n_classes": 4
            },
            {
                "id"     : "CMAPSS",
                "name"   : "NASA CMAPSS FD001",
                "task"   : "regression",
                "defauts": ["sain", "degradation_precoce",
                            "degradation_avancee", "critique"],
                "n_classes": 4
            },
            {
                "id"     : "MCC5",
                "name"   : "MCC5-THU Gearbox",
                "task"   : "classification",
                "defauts": ["sain", "pitting", "usure",
                            "dent_cassee", "fissure",
                            "dent_manquante",
                            "mixte_interne", "mixte_externe"],
                "n_classes": 8
            },
        ]
    }


@router.post("/dataset/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload un fichier dataset custom (CSV, MAT, ZIP, NPY).
    Retourne un aperçu des colonnes et premières lignes.
    """
    suffix   = Path(file.filename).suffix.lower()
    allowed  = ['.csv', '.mat', '.zip', '.npy', '.txt']

    if suffix not in allowed:
        raise HTTPException(
            400,
            f"Format non supporté : {suffix}. "
            f"Formats acceptés : {allowed}"
        )

    # Sauvegarder le fichier
    dest = UPLOAD_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Aperçu selon le format
    preview = {"filename": file.filename, "format": suffix}

    try:
        if suffix == '.csv':
            df = pd.read_csv(dest, nrows=5)
            preview.update({
                "columns"     : list(df.columns),
                "n_columns"   : len(df.columns),
                "sample_rows" : df.head(3).to_dict(orient='records'),
                "dtypes"      : {c: str(t)
                                 for c, t in df.dtypes.items()},
            })

        elif suffix == '.npy':
            arr = np.load(dest)
            preview.update({
                "shape" : list(arr.shape),
                "dtype" : str(arr.dtype),
                "min"   : float(arr.min()),
                "max"   : float(arr.max()),
            })

        elif suffix == '.txt':
            with open(dest) as f:
                lines = [f.readline() for _ in range(3)]
            preview["first_lines"] = lines

        elif suffix == '.mat':
            from scipy.io import loadmat
            mat  = loadmat(dest)
            keys = [k for k in mat.keys() if not k.startswith('__')]
            preview.update({
                "keys"  : keys,
                "shapes": {k: list(mat[k].shape)
                           for k in keys
                           if hasattr(mat[k], 'shape')}
            })

        elif suffix == '.zip':
            import zipfile
            with zipfile.ZipFile(dest) as z:
                names = z.namelist()
            preview.update({
                "n_files"         : len(names),
                "sample_files"    : names[:10],
                "csv_count"       : sum(1 for n in names
                                        if n.endswith('.csv')),
                "npy_count"       : sum(1 for n in names
                                        if n.endswith('.npy')),
            })

    except Exception as e:
        preview["error"] = str(e)

    preview["path"] = str(dest)
    return preview


@router.post("/dataset/configure")
def configure_dataset(req: DatasetConfigRequest,
                        filename: str):
    """
    Génère automatiquement le fichier YAML de configuration
    pour un dataset uploadé.
    """
    config = {
        "name"            : req.name,
        "format"          : "csv",
        "sampling_rate"   : req.sampling_rate,
        "task"            : req.task,
        "signal_columns"  : req.signal_columns,
        "label_from_folder": req.label_from_folder,
        "label_mapping"   : req.label_mapping or {},
    }

    if req.label_column:
        config["label_column"] = req.label_column

    # Sauvegarder le YAML
    yaml_name = f"{req.name.lower().replace(' ', '_')}.yaml"
    yaml_path = Path("configs/datasets") / yaml_name

    with open(yaml_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False,
                  allow_unicode=True)

    return {
        "message"  : f"Configuration générée → {yaml_path}",
        "yaml_path": str(yaml_path),
        "config"   : config
    }


@router.get("/dataset/preview/{filename}")
def preview_dataset(filename: str, n_rows: int = 10):
    """Aperçu des premières fenêtres d'un dataset uploadé."""
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404, f"Fichier {filename} introuvable")

    suffix = path.suffix.lower()
    try:
        if suffix == '.csv':
            df = pd.read_csv(path, nrows=n_rows)
            return {
                "format" : "csv",
                "rows"   : df.to_dict(orient='records'),
                "columns": list(df.columns)
            }
        elif suffix == '.npy':
            arr = np.load(path)
            return {
                "format": "npy",
                "shape" : list(arr.shape),
                "sample": arr[:n_rows].tolist()
                          if arr.ndim <= 2 else []
            }
    except Exception as e:
        raise HTTPException(500, str(e))