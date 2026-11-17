import asyncio
import time
from datetime import datetime, timezone
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

# Tried in order. mempool.space is the primary; mempool.emzy.de is a public mirror
# that serves the same API, used only when the primary cannot be reached. It is a
# third party, so nothing here should be written to depend on it being there.
MEMPOOL_HOSTS = ("https://mempool.space", "https://mempool.emzy.de")

# A host that just failed is tried last for this long, so a dead primary costs one
# connect timeout, not one per call (close detection alone makes hundreds).
HOST_RETRY_AFTER_SECONDS = 300.0
CONNECT_TIMEOUT_SECONDS = 5.0

_host_down_until: dict[str, float] = {}

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


# mempool.space serves its lightning statistics from several backends that disagree
# about freshness: back-to-back calls to `statistics/latest` were measured returning
# rows dated 13 Jul, 30 Aug and 6 Oct, and the range endpoints (`statistics/1m` …)
# do the same — they only looked consistent when a burst of calls happened to land on
# one backend. There is therefore no trustworthy reference for "fresh" to compare
# against; the only defence is to draw more than once and keep the newest row.
# Draws are parallel, and the retry round only runs if the first came up stale.
STATS_FIRST_DRAWS = 3
STATS_RETRY_DRAWS = 6

# A row this recent (days before today, UTC) is as fresh as the data gets: the
# newest row is dated the day before it is served. Older, and we draw again.
STATS_FRESH_DAYS = 1

# A lightning_stats row older than this is not worth persisting; see graph_metrics.
STATS_MAX_AGE_DAYS = 3


def added_date(added: int | str) -> str:
    """UTC YYYY-MM-DD for a row's `added`, which is ISO text on `latest` and a unix
    timestamp on the range endpoints."""
    if isinstance(added, (int, float)):
        return datetime.fromtimestamp(added, timezone.utc).strftime("%Y-%m-%d")
    return str(added)[:10]


def _hosts_in_order() -> list[str]:
    """Hosts not recently down first, in configured order; recently failed ones last."""
    now = time.monotonic()
    up = [h for h in MEMPOOL_HOSTS if _host_down_until.get(h, 0.0) <= now]
    down = [h for h in MEMPOOL_HOSTS if h not in up]
    return up + down


async def _get(
    client: httpx.AsyncClient, path: str, timeout: float = 10.0
) -> httpx.Response:
    """GET `path` (relative to /api/, e.g. "v1/prices") with fallback to the mirror.

    Falls over on a connection failure, a timeout or a 5xx. A 4xx is the server
    answering, so it is raised as it stands rather than asked again elsewhere.
    """
    last: Exception | None = None
    for host in _hosts_in_order():
        try:
            response = await client.get(
                f"{host}/api/{path}",
                timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT_SECONDS),
            )
            if response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"{response.status_code} from {host}",
                    request=response.request, response=response,
                )
            response.raise_for_status()
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500:
                raise
            _host_down_until[host] = time.monotonic() + HOST_RETRY_AFTER_SECONDS
            last = e
            print(f"mempool: {host} failed on {path} ({type(e).__name__}) — trying next")
            continue
        if host != MEMPOOL_HOSTS[0]:
            print(f"mempool: served {path} from {host}")
        return response
    raise last if last is not None else RuntimeError("no mempool hosts configured")


async def get_stats_range(period: str = "1m") -> list[dict]:
    """Rows from mempool's `statistics/{period}`, newest first, `added` as a unix time.

    Thinner than `latest` (no id, node_count or avg/median fields), and subject to
    the same backend lottery — see above.
    """
    async with httpx.AsyncClient() as client:
        response = await _get(client, f"v1/lightning/statistics/{period}", timeout=30.0)
        return response.json()


async def _draw_latest(client: httpx.AsyncClient, draws: int) -> list[LightningStatsResponse]:
    async def one() -> LightningStatsResponse:
        response = await _get(client, "v1/lightning/statistics/latest")
        return LightningStatsResponse(**response.json())

    results = await asyncio.gather(*(one() for _ in range(draws)), return_exceptions=True)
    rows = [r for r in results if isinstance(r, LightningStatsResponse)]
    if not rows:
        raise next(r for r in results if isinstance(r, BaseException))
    return rows


async def get_lightning_stats() -> LightningStatsResponse:
    """The freshest `latest` row mempool will give us. See STATS_FIRST_DRAWS."""
    if "result" not in _stats_cache:
        best: LightningStatsResponse | None = None
        async with httpx.AsyncClient() as client:
            for draws in (STATS_FIRST_DRAWS, STATS_RETRY_DRAWS):
                for row in await _draw_latest(client, draws):
                    if best is None or added_date(row.latest.added) > added_date(best.latest.added):
                        best = row
                if stats_age_days(best) <= STATS_FRESH_DAYS:
                    break
            else:
                print(
                    f"mempool: no fresh lightning stats after "
                    f"{STATS_FIRST_DRAWS + STATS_RETRY_DRAWS} draws "
                    f"(best is {added_date(best.latest.added)})"
                )
        _stats_cache["result"] = best
    return _stats_cache["result"]


def stats_age_days(stats: LightningStatsResponse) -> int:
    """How many days before today the row describes."""
    added = datetime.fromisoformat(added_date(stats.latest.added)).date()
    return (datetime.now(timezone.utc).date() - added).days


async def get_nodes_per_country() -> list[NodesPerCountry]:
    if "result" not in _country_cache:
        async with httpx.AsyncClient() as client:
            response = await _get(client, "v1/lightning/nodes/countries")
            _country_cache["result"] = response.json()
    return _country_cache["result"]


async def get_largest_nodes() -> list[LargestNode]:
    if "result" not in _nodes_cache:
        async with httpx.AsyncClient() as client:
            response = await _get(client, "v1/lightning/nodes/rankings/liquidity")
            _nodes_cache["result"] = response.json()
    return _nodes_cache["result"]


async def get_btc_price() -> BtcPrice:
    if "result" not in _price_cache:
        async with httpx.AsyncClient() as client:
            response = await _get(client, "v1/prices")
            _price_cache["result"] = BtcPrice(**response.json())
    return _price_cache["result"]


async def get_historical_prices() -> list[HistoricalPricePoint]:
    # Hourly BTC prices back to 2010 (~2 MB payload) — used to derive historical velocity
    if "result" not in _history_cache:
        async with httpx.AsyncClient() as client:
            response = await _get(client, "v1/historical-price", timeout=60.0)
            _history_cache["result"] = HistoricalPriceResponse(**response.json()).prices
    return _history_cache["result"]


async def get_chain_tip() -> int:
    if "result" not in _tip_cache:
        async with httpx.AsyncClient() as client:
            response = await _get(client, "blocks/tip/height", timeout=30.0)
            _tip_cache["result"] = int(response.text)
    return _tip_cache["result"]


async def get_outspends(points: Iterable[str]) -> dict[str, dict]:
    """Resolve funding outpoints to their on-chain spend status.

    `points` are LND `chan_point` strings ("<txid>:<vout>"). A **spent** funding
    output means the channel genuinely closed; an **unspent** one means the channel
    only left our gossip view, which is a different thing entirely and must never
    be counted as a close. That distinction is the whole reason this call exists.

    Only outpoints that resolved are returned — a failed lookup is indistinguishable
    from "don't know yet", so the caller keeps watching rather than guessing.
    """
    wanted = list(dict.fromkeys(points))
    if not wanted:
        return {}

    # Public API, and a busy day can ask about a couple of hundred outpoints.
    semaphore = asyncio.Semaphore(5)
    results: dict[str, dict] = {}

    async with httpx.AsyncClient() as client:
        async def fetch(point: str) -> tuple[str, dict | None]:
            txid, _, vout = point.rpartition(":")
            if not txid or not vout.isdigit():
                return point, None
            async with semaphore:
                response = await _get(
                    client, f"tx/{txid}/outspend/{vout}", timeout=30.0
                )
                return point, response.json()

        for outcome in await asyncio.gather(
            *(fetch(p) for p in wanted), return_exceptions=True
        ):
            if isinstance(outcome, BaseException):
                continue
            point, info = outcome
            if info is not None:
                results[point] = info

    return results


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
                    response = await _get(client, f"v1/blocks/{window}", timeout=30.0)
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
