from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

import db


router = APIRouter(prefix="/history")


@router.get("/network-metrics")
async def network_metrics_history(days: int = Query(30, ge=1, le=365)):
    database = db.get_db()
    if database is None:
        raise HTTPException(status_code=503, detail="Database not available")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = database["network_metrics"].find(
        {"recorded_at": {"$gte": since}},
        {"_id": 0}
    ).sort("recorded_at", 1)
    return await cursor.to_list(length=None)


@router.get("/graph-info")
async def graph_info_history(days: int = Query(30, ge=1, le=365)):
    database = db.get_db()
    if database is None:
        raise HTTPException(status_code=503, detail="Database not available")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = database["graph_info"].find(
        {"recorded_at": {"$gte": since}},
        {"_id": 0}
    ).sort("recorded_at", 1)
    return await cursor.to_list(length=None)


@router.get("/lightning-stats")
async def lightning_stats_history(days: int = Query(30, ge=1, le=365)):
    database = db.get_db()
    if database is None:
        raise HTTPException(status_code=503, detail="Database not available")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = database["lightning_stats"].find(
        {"recorded_at": {"$gte": since}},
        {"_id": 0}
    ).sort("recorded_at", 1)
    return await cursor.to_list(length=None)