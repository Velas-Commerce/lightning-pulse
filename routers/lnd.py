from fastapi import APIRouter, HTTPException
from services.lnd import get_graph_info
from services.graph_metrics import get_cached_metrics
from models import GraphInfo, NetworkMetrics

router = APIRouter()


@router.get("/node/graph-info", response_model=GraphInfo)
async def graph_info():
    return await get_graph_info()


@router.get("/node/network-metrics", response_model=NetworkMetrics)
def network_metrics():
    metrics = get_cached_metrics()
    if metrics is None:
        raise HTTPException(status_code=503, detail="Metrics not yet computed, check back shortly.")
    return metrics
