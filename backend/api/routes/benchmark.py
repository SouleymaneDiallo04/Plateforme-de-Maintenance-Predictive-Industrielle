"""Routes du benchmark IA Lab."""

from fastapi import APIRouter
from backend.ml.model_registry import registry

router = APIRouter(tags=["Benchmark"])


@router.get("/benchmark")
def get_benchmark():
    """Retourne tous les résultats du benchmark pour le dashboard IA Lab."""
    results = registry.get_benchmark_results()

    # Formater pour le frontend
    classif = results.get('classification', {})
    regress = results.get('regression',     {})

    return {
        "classification" : classif,
        "regression"     : regress,
        "active_models"  : {
            ds: registry.get_active_model(ds)
            for ds in ['VBL', 'CWRU', 'MF', 'CMAPSS']
        }
    }


@router.get("/benchmark/{dataset}")
def get_benchmark_dataset(dataset: str):
    """Benchmark pour un dataset spécifique."""
    return {
        "dataset"       : dataset,
        "results"       : registry.get_benchmark_results(dataset),
        "active_model"  : registry.get_active_model(dataset),
        "available"     : registry.get_available_models(dataset),
    }