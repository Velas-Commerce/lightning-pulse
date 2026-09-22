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


def capacity_by_observed_day(docs: list[dict]) -> list[tuple[str, int]]:
    """Collapse lightning_stats documents to one capacity per *observed* day.

    Keyed on the upstream `added` date, not on when we fetched the row.
    mempool.space serves `statistics/latest` from several cache nodes whose rows
    can be months apart — measured median staleness is ~49 days, worst case 167 —
    so our fetch time says nothing about which day a capacity figure describes.
    Keying on `recorded_at` interleaved snapshots from different months and
    produced a ~30% day-to-day oscillation that was pure cache artifact.

    Returns ascending (YYYY-MM-DD, sats) pairs. Later fetches of the same `added`
    day are treated as refinements and win.
    """
    by_added: dict[str, int] = {}
    for doc in docs:
        added = (doc.get("added") or "")[:10]
        capacity = doc.get("total_capacity") or 0
        if added and capacity > 0:
            by_added[added] = capacity
    return sorted(by_added.items())


async def get_velocity_history(days: int) -> list[VelocityHistoryEntry] | None:
    """Derive velocity per observed day from the lightning_stats capacity snapshots
    joined with historical BTC prices, holding the latest monthly-volume estimate
    constant. Returns None when MongoDB is not configured.

    `recorded_at` on each entry carries the **observation** date (upstream `added`),
    not our fetch time — that is the date the capacity figure actually describes,
    and the date its BTC price must be joined at.
    """
    database = db.get_db()
    if database is None:
        return None

    docs = await database["lightning_stats"].find(
        {}, {"_id": 0, "added": 1, "total_capacity": 1},
    ).to_list(length=None)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    observations = [(a, c) for a, c in capacity_by_observed_day(docs) if a >= cutoff]

    prices = await get_historical_prices()
    pairs = sorted((p.time, p.USD) for p in prices)  # ascending for bisect
    times = [t for t, _ in pairs]
    volume_usd = get_lightning_growth_stats().monthly_volume[-1].volume_usd

    entries: list[VelocityHistoryEntry] = []
    for added, capacity_sats in observations:
        observed_at = datetime.fromisoformat(added).replace(tzinfo=timezone.utc)
        ts = observed_at.timestamp()
        idx = bisect.bisect_left(times, ts)
        candidates = [pairs[i] for i in (idx - 1, idx) if 0 <= i < len(pairs)]
        if not candidates:
            continue
        _, price_usd = min(candidates, key=lambda pair: abs(pair[0] - ts))
        capacity_usd = (capacity_sats / SATS_PER_BTC) * price_usd
        if capacity_usd <= 0:
            continue
        entries.append(VelocityHistoryEntry(
            recorded_at=observed_at.isoformat(),
            velocity=round(volume_usd / capacity_usd, 4),
            capacity_sats=capacity_sats,
            btc_price_usd=price_usd,
        ))
    return entries
