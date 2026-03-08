import httpx
from models import LightningStatsResponse, NodesPerCountry, OldestNodes, BtcPrice

# curl -sSL "https://mempool.space/api/v1/lightning/statistics/latest"
# curl -sSL "https://mempool.space/api/v1/lightning/nodes/rankings/age"
# curl -sSL "https://mempool.space/api/v1/prices"

MEMPOOL_BASE_URL="https://mempool.space/api/v1/"


async def get_lightning_stats() -> LightningStatsResponse:
    async with httpx.AsyncClient() as client:
        response = await client.get(MEMPOOL_BASE_URL + "lightning/statistics/latest")
        response.raise_for_status()
        return LightningStatsResponse(**response.json())


async def get_nodes_per_country() -> list[NodesPerCountry]:
    async with httpx.AsyncClient() as client:
        response = await client.get(MEMPOOL_BASE_URL + "lightning/nodes/countries")
        response.raise_for_status()
        return response.json()


async def get_oldest_nodes() -> list[OldestNodes]:
    async with httpx.AsyncClient() as client:
        response = await client.get(MEMPOOL_BASE_URL + "lightning/nodes/rankings/age")
        response.raise_for_status()
        return response.json()
    

async def get_btc_price() -> BtcPrice:
    async with httpx.AsyncClient() as client:
        response = await client.get(MEMPOOL_BASE_URL + "prices")
        response.raise_for_status()
        return BtcPrice(**response.json())
    