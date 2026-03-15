import httpx
from cachetools import TTLCache
from models import LightningStatsResponse, NodesPerCountry, LargestNode, BtcPrice

# curl -sSL "https://mempool.space/api/v1/lightning/statistics/latest"
# curl -sSL "https://mempool.space/api/v1/lightning/nodes/rankings/age"
# curl -sSL "https://mempool.space/api/v1/prices"

MEMPOOL_BASE_URL = "https://mempool.space/api/v1/"

# Each cache stores 1 result and expires after the given TTL (seconds).
_stats_cache:   TTLCache = TTLCache(maxsize=1, ttl=60)   # network stats — refresh every minute
_country_cache: TTLCache = TTLCache(maxsize=1, ttl=300)  # country breakdown — refresh every 5 min
_nodes_cache:   TTLCache = TTLCache(maxsize=1, ttl=300)  # largest nodes — refresh every 5 min
_price_cache:   TTLCache = TTLCache(maxsize=1, ttl=30)   # BTC price — refresh every 30 seconds


async def get_lightning_stats() -> LightningStatsResponse:
    if "result" not in _stats_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(MEMPOOL_BASE_URL + "lightning/statistics/latest")
            response.raise_for_status()
            _stats_cache["result"] = LightningStatsResponse(**response.json())
    return _stats_cache["result"]


async def get_nodes_per_country() -> list[NodesPerCountry]:
    if "result" not in _country_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(MEMPOOL_BASE_URL + "lightning/nodes/countries")
            response.raise_for_status()
            _country_cache["result"] = response.json()
    return _country_cache["result"]


async def get_largest_nodes() -> list[LargestNode]:
    if "result" not in _nodes_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(MEMPOOL_BASE_URL + "lightning/nodes/rankings/liquidity")
            response.raise_for_status()
            _nodes_cache["result"] = response.json()
    return _nodes_cache["result"]


async def get_btc_price() -> BtcPrice:
    if "result" not in _price_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(MEMPOOL_BASE_URL + "prices")
            response.raise_for_status()
            _price_cache["result"] = BtcPrice(**response.json())
    return _price_cache["result"]
    