from fastapi import APIRouter
from services.growth_stats import get_lightning_growth_stats
from services.velocity import get_liquidity_velocity
from models import LightningGrowthStats, LiquidityVelocity

router = APIRouter()


@router.get("/lightning/growth-stats", response_model=LightningGrowthStats)
def lightning_growth_stats():
    return get_lightning_growth_stats()


@router.get("/lightning/velocity", response_model=LiquidityVelocity)
async def liquidity_velocity():
    return await get_liquidity_velocity()
