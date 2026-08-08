import httpx
from fastapi import APIRouter, HTTPException
from services.lnd import get_graph_info
from services.graph_metrics import get_cached_metrics
from models import GraphInfo, NetworkMetrics

router = APIRouter()


@router.get("/node/graph-info", response_model=GraphInfo)
async def graph_info():
    try:
        return await get_graph_info()
    except httpx.HTTPError as e:
        # Node offline / TLS or upstream 5xx — same 503 contract as /node/network-metrics
        raise HTTPException(status_code=503, detail="LND node unavailable, check back shortly.") from e


@router.get("/node/network-metrics", response_model=NetworkMetrics)
def network_metrics():
    metrics = get_cached_metrics()
    if metrics is None:
        raise HTTPException(status_code=503, detail="Metrics not yet computed, check back shortly.")
    return metrics
