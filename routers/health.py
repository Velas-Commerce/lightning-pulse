from fastapi import APIRouter
from services.graph_metrics import get_cached_metrics

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "metrics_ready": get_cached_metrics() is not None,
    }
