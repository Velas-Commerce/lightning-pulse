from fastapi import APIRouter
from services.mempool import get_lightning_stats, get_nodes_per_country, get_largest_nodes, get_btc_price
from models import LightningStatsResponse, NodesPerCountry, LargestNode, BtcPrice


router = APIRouter()


@router.get("/lightning/stats", response_model=LightningStatsResponse)
async def lightning_stats():
    return await get_lightning_stats()


@router.get("/lightning/nodes-per-country", response_model=list[NodesPerCountry])
async def nodes_per_country():
    return await get_nodes_per_country()


@router.get("/lightning/largest-nodes", response_model=list[LargestNode])
async def largest_nodes():
    return await get_largest_nodes()


@router.get("/btc-price", response_model=BtcPrice)
async def btc_price():
    return await get_btc_price()

