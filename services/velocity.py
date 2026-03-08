import asyncio
from models import LiquidityVelocity
from services.mempool import get_lightning_stats, get_btc_price
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
