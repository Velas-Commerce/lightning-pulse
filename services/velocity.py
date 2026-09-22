import asyncio
import bisect
from datetime import datetime, timedelta, timezone

import db
from models import LiquidityVelocity, VelocityHistoryEntry
from services.mempool import get_lightning_stats, get_btc_price, get_historical_prices
from services.growth_stats import get_lightning_growth_stats

SATS_PER_BTC = 100_000_000


async def get_liquidity_velocity() -> LiquidityVelocity:
    stats, price = await asyncio.gather(get_lightning_stats(), get_btc_price())

    latest_volume = get_lightning_growth_stats().monthly_volume[-1]

    capacity_sats = stats.latest.total_capacity
    btc_price_usd = price.USD
    capacity_usd = (capacity_sats / SATS_PER_BTC) * btc_price_usd
    velocity = latest_volume.volume_usd / capacity_usd

    return LiquidityVelocity(
        velocity=round(velocity, 4),
        monthly_volume_usd=latest_volume.volume_usd,
        volume_date=latest_volume.date,
        capacity_sats=capacity_sats,
        capacity_usd=round(capacity_usd, 2),
        btc_price_usd=btc_price_usd,
    )


async def get_velocity_history(days: int) -> list[VelocityHistoryEntry] | None:
    """Derive daily velocity from the lightning_stats capacity snapshots joined with
    historical BTC prices, holding the latest monthly-volume estimate constant.
    Returns None when MongoDB is not configured."""
    database = db.get_db()
    if database is None:
        return None

    since = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = database["lightning_stats"].find(
        {"recorded_at": {"$gte": since}},
        {"_id": 0, "recorded_at": 1, "total_capacity": 1},
    ).sort("recorded_at", 1)
    docs = await cursor.to_list(length=None)

    prices = await get_historical_prices()
    pairs = sorted((p.time, p.USD) for p in prices)  # ascending for bisect
    times = [t for t, _ in pairs]
    volume_usd = get_lightning_growth_stats().monthly_volume[-1].volume_usd

    entries: list[VelocityHistoryEntry] = []
    for doc in docs:
        recorded_at: datetime = doc["recorded_at"]
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)
        capacity_sats = doc.get("total_capacity") or 0
        if capacity_sats <= 0:
            continue
        ts = recorded_at.timestamp()
        idx = bisect.bisect_left(times, ts)
        candidates = [pairs[i] for i in (idx - 1, idx) if 0 <= i < len(pairs)]
        if not candidates:
            continue
        _, price_usd = min(candidates, key=lambda pair: abs(pair[0] - ts))
        capacity_usd = (capacity_sats / SATS_PER_BTC) * price_usd
        if capacity_usd <= 0:
            continue
        entries.append(VelocityHistoryEntry(
            recorded_at=recorded_at.isoformat(),
            velocity=round(volume_usd / capacity_usd, 4),
            capacity_sats=capacity_sats,
            btc_price_usd=price_usd,
        ))
    return entries
