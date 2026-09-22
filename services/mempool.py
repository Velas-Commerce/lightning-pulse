import asyncio
from typing import Iterable

import httpx
from cachetools import TTLCache
from models import LightningStatsResponse, NodesPerCountry, LargestNode, BtcPrice, HistoricalPricePoint, HistoricalPriceResponse

# curl -sSL "https://mempool.space/api/v1/lightning/statistics/latest"
# curl -sSL "https://mempool.space/api/v1/lightning/nodes/rankings/age"
# curl -sSL "https://mempool.space/api/v1/prices"
# curl -sSL "https://mempool.space/api/v1/historical-price"
# curl -sSL "https://mempool.space/api/blocks/tip/height"
# curl -sSL "https://mempool.space/api/v1/blocks/913548"

MEMPOOL_BASE_URL = "https://mempool.space/api/v1/"
MEMPOOL_API_URL = "https://mempool.space/api/"

# One /v1/blocks/{height} call returns this many blocks, counting down from height.
BLOCKS_PER_CALL = 15

# Each cache stores 1 result and expires after the given TTL (seconds).
_stats_cache:   TTLCache = TTLCache(maxsize=1, ttl=60)   # network stats — refresh every minute
_country_cache: TTLCache = TTLCache(maxsize=1, ttl=300)  # country breakdown — refresh every 5 min
_nodes_cache:   TTLCache = TTLCache(maxsize=1, ttl=300)  # largest nodes — refresh every 5 min
_price_cache:   TTLCache = TTLCache(maxsize=1, ttl=30)   # BTC price — refresh every 30 seconds
_history_cache: TTLCache = TTLCache(maxsize=1, ttl=21600)  # historical BTC prices — refresh every 6 h
_tip_cache:     TTLCache = TTLCache(maxsize=1, ttl=300)  # chain tip height — refresh every 5 min

# Block timestamps are immutable once buried, so this is a plain height -> unix-time
# store with a long TTL. Sized for ~90 days of weekly anchors plus a few days of
# contiguous recent blocks (see services/channel_flow.py).
_block_time_cache: TTLCache = TTLCache(maxsize=4096, ttl=21600)


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


async def get_historical_prices() -> list[HistoricalPricePoint]:
    # Hourly BTC prices back to 2010 (~2 MB payload) — used to derive historical velocity
    if "result" not in _history_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(MEMPOOL_BASE_URL + "historical-price", timeout=60.0)
            response.raise_for_status()
            _history_cache["result"] = HistoricalPriceResponse(**response.json()).prices
    return _history_cache["result"]


async def get_chain_tip() -> int:
    if "result" not in _tip_cache:
        async with httpx.AsyncClient() as client:
            response = await client.get(MEMPOOL_API_URL + "blocks/tip/height", timeout=30.0)
            response.raise_for_status()
            _tip_cache["result"] = int(response.text)
    return _tip_cache["result"]


async def get_block_timestamps(heights: Iterable[int]) -> dict[int, int]:
    """Resolve block heights to unix timestamps.

    One upstream call returns BLOCKS_PER_CALL blocks, so requests are aligned to
    fixed windows and harvested in full — asking for 15 neighbouring heights costs
    a single call. Only used by the daily snapshot job and the backfill script,
    never per-request.
    """
    wanted = {int(h) for h in heights}
    missing = {h for h in wanted if h not in _block_time_cache}

    if missing:
        windows = sorted({
            (h // BLOCKS_PER_CALL) * BLOCKS_PER_CALL + (BLOCKS_PER_CALL - 1)
            for h in missing
        })
        # Cap concurrency — this is a public API and a backfill can ask for many windows.
        semaphore = asyncio.Semaphore(5)

        async with httpx.AsyncClient() as client:
            async def fetch(window: int) -> list[dict]:
                async with semaphore:
                    response = await client.get(
                        MEMPOOL_BASE_URL + f"blocks/{window}", timeout=30.0
                    )
                    response.raise_for_status()
                    return response.json()

            results = await asyncio.gather(
                *(fetch(w) for w in windows), return_exceptions=True
            )

        for result in results:
            if isinstance(result, BaseException):
                continue  # a gap just means those heights fall back to interpolation
            for block in result:
                _block_time_cache[block["height"]] = block["timestamp"]

    return {h: _block_time_cache[h] for h in wanted if h in _block_time_cache}
