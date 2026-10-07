import asyncio
import db
from datetime import datetime, timedelta, timezone
from models import NetworkMetrics
from services import channel_closes, channel_flow
from services.lnd import _client, LND_URL, get_graph_info
from services.mempool import (
    STATS_MAX_AGE_DAYS,
    get_chain_tip,
    get_lightning_stats,
    stats_age_days,
)

# The snapshot runs at a fixed UTC time rather than every 24 h from process start,
# so restarts and deploys can't drift the sampling schedule the baselines rest on.
# A few minutes past midnight lets upstream sources settle on the day boundary.
SNAPSHOT_HOUR_UTC = 0
SNAPSHOT_MINUTE_UTC = 15

_cache: NetworkMetrics | None = None


def get_cached_metrics() -> NetworkMetrics | None:
    return _cache


def _gini(values: list[int]) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    sorted_vals = sorted(values)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumsum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    return round(cumsum / (n * total), 4)


def _centralization(capacities_by_node: dict[str, int], top_n: int) -> float:
    if not capacities_by_node:
        return 0.0
    total = sum(capacities_by_node.values())
    if total == 0:
        return 0.0
    top = sorted(capacities_by_node.values(), reverse=True)[:top_n]
    return round(sum(top) / total, 4)


def _median_fee_rate(edges: list[dict]) -> int:
    rates = []
    for edge in edges:
        for policy_key in ("node1_policy", "node2_policy"):
            policy = edge.get(policy_key)
            if policy and policy.get("fee_rate_milli_msat"):
                try:
                    rates.append(int(policy["fee_rate_milli_msat"]))
                except (ValueError, TypeError):
                    pass
    if not rates:
        return 0
    rates.sort()
    mid = len(rates) // 2
    return rates[mid]


def _median_node_degree(edges: list[dict]) -> int:
    degree: dict[str, int] = {}
    for edge in edges:
        for key in ("node1_pub", "node2_pub"):
            pub = edge.get(key)
            if pub:
                degree[pub] = degree.get(pub, 0) + 1
    if not degree:
        return 0
    counts = sorted(degree.values())
    return counts[len(counts) // 2]


def _pulse_score(gini: float, top10: float, fee_rate: int) -> int:
    # Equity: lower Gini = better. Lightning typically ranges 0.60–0.95.
    equity = max(0.0, min(100.0, (0.95 - gini) / 0.35 * 100))

    # Decentralization: lower top10 concentration = better. Typical range 0.20–0.70.
    decentralization = max(0.0, min(100.0, (0.70 - top10) / 0.50 * 100))

    # Fee market: score peaks in a healthy mid-range, penalizes extremes.
    # fee_rate_milli_msat: healthy routing sits roughly 500–5000.
    if fee_rate <= 0:
        fee = 0.0
    elif fee_rate < 500:
        fee = fee_rate / 500 * 60          # ramp up to 60 at the low end
    elif fee_rate <= 5000:
        fee = 100.0                        # sweet spot
    elif fee_rate <= 20000:
        fee = max(0.0, 100.0 - (fee_rate - 5000) / 150)
    else:
        fee = 0.0

    score = equity * 0.35 + decentralization * 0.35 + fee * 0.30
    return round(score)


def _compute(graph: dict) -> NetworkMetrics:
    edges = graph.get("edges", [])
    nodes = graph.get("nodes", [])

    # capacity per node (sum across all their channels)
    node_capacity: dict[str, int] = {n["pub_key"]: 0 for n in nodes}
    all_capacities = []
    for edge in edges:
        cap = int(edge.get("capacity", 0))
        all_capacities.append(cap)
        for key in ("node1_pub", "node2_pub"):
            pub = edge.get(key)
            if pub in node_capacity:
                node_capacity[pub] += cap

    gini = _gini(all_capacities)
    top10 = _centralization(node_capacity, 10)
    fee_rate = _median_fee_rate(edges)

    return NetworkMetrics(
        pulse_score=_pulse_score(gini, top10, fee_rate),
        gini_coefficient=gini,
        top10_centralization=top10,
        top100_centralization=_centralization(node_capacity, 100),
        median_fee_rate=fee_rate,
        median_node_degree=_median_node_degree(edges),
        last_computed=datetime.now(timezone.utc).isoformat(),
    )


async def _persist_snapshot() -> None:
    if _cache is None:
        return
    database = db.get_db()
    if database is None:
        return
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")

    documents = {
        "network_metrics": _cache.model_dump(),
        "graph_info": (await get_graph_info()).model_dump(),
    }

    # mempool.space sometimes serves months-old rows even after retries (see
    # services/mempool.py). A stale row would be stored as if it described today, and
    # on a restart it would also overwrite the good row the 00:15 run wrote — so a
    # row that is not recent is skipped rather than persisted.
    stats = await get_lightning_stats()
    if stats_age_days(stats) <= STATS_MAX_AGE_DAYS:
        documents["lightning_stats"] = stats.latest.model_dump()
    else:
        print(
            f"lightning_stats not persisted: freshest row is from "
            f"{stats.latest.added[:10]}, {stats_age_days(stats)} days old"
        )

    for collection, doc in documents.items():
        doc["recorded_at"] = now
        doc["date"] = day
        if collection == "lightning_stats":
            # Never replace the day's row with an older observation of the network.
            existing = await database[collection].find_one({"date": day}, {"added": 1})
            if existing and str(existing.get("added") or "") > str(doc["added"]):
                continue
        # Upsert by UTC date: a restart refreshes the day's snapshot instead of
        # appending a second one. Documents written before `date` existed have no
        # date field, so they never match and are left untouched.
        await database[collection].update_one(
            {"date": day}, {"$set": doc}, upsert=True
        )


async def _persist_flow(graph: dict) -> None:
    """Record completed days of channel opens and closes.

    Today is deliberately skipped — the card reports a finished day, not a partial
    one. Days whose blocks all carry exact timestamps are refreshed on every run;
    older days, whose times are interpolated and so cannot honestly be binned to
    the hour, are only filled in if missing. That makes a missed run self-healing
    without ever overwriting hourly detail with a coarser version of the same day.

    Opens come from the graph itself. Closes need the previous run's channel set to
    diff against and an on-chain check per candidate, so they only start once a set
    has been stored — see services/channel_closes.py.
    """
    database = db.get_db()
    if database is None:
        return

    edges = graph.get("edges", [])
    events = channel_flow.open_events(edges)
    if not events:
        return

    tip = max(height for height, _ in events)
    try:
        tip = max(tip, await get_chain_tip())
    except Exception:
        pass  # our own highest channel is a good enough stand-in

    # Only the recent window is needed here; history comes from the backfill script.
    lookback = channel_flow.EXACT_BLOCKS + channel_flow.ANCHOR_SPACING
    floor = tip - lookback
    clock = await channel_flow.build_clock(floor, tip)
    recent = [(h, c) for h, c in events if h >= floor]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    closed_by_day: dict[str, dict] = {}
    try:
        result = await channel_closes.detect_closes(database, edges, today)
        in_window = [c for c in result["closes"] if c[0] >= floor]
        dropped = len(result["closes"]) - len(in_window)
        closed_by_day = channel_closes.bucket_closes(in_window, clock)
        print(
            f"closes: {len(in_window)} confirmed, {result['watching']} still watching, "
            f"{result['expired']} expired unspent, {dropped} outside the window"
            + (" (first run — set established, nothing to diff yet)"
               if result["first_run"] else "")
        )
    except Exception as e:
        # Closes are a bonus on top of opens; never let them cost us the opens.
        print(f"close detection failed: {e}")

    days = channel_flow.bucket_by_day(recent, clock)
    for date in sorted(set(days) | set(closed_by_day)):
        if date >= today:
            continue

        doc = days.get(date)
        if doc is None:
            continue  # closes with no opens bucket: nothing to anchor the day to
        doc.pop("date")  # supplied by the filter
        exact = doc["hourly"] is not None

        closed = closed_by_day.get(date)
        if closed is not None:
            doc["closes"] = closed["closes"]
            doc["btc_out"] = closed["btc_out"]
            # Merge into the same hourly array the opens use, so one hour is one
            # object carrying both sides of the flow.
            if doc["hourly"] is not None and closed["hourly"] is not None:
                for hour, caps in enumerate(closed["hourly"]):
                    doc["hourly"][hour]["closes"] = caps
        if doc["hourly"] is not None:
            for entry in doc["hourly"]:
                entry.setdefault("closes", [])

        doc["is_backfilled"] = not exact
        doc["recorded_at"] = datetime.now(timezone.utc)
        await database["daily_flow"].update_one(
            {"date": date},
            {"$set": doc} if exact else {"$setOnInsert": doc},
            upsert=True,
        )


async def refresh_metrics() -> None:
    global _cache
    async with _client() as client:
        response = await client.get(f"{LND_URL}/v1/graph", timeout=120.0)
        response.raise_for_status()
        graph = response.json()
    _cache = _compute(graph)
    await _persist_snapshot()
    try:
        await _persist_flow(graph)
    except Exception as e:
        # Flow needs upstream block times; a failure there must not cost us the
        # metrics snapshot, which is already safely written above.
        print(f"daily_flow persist failed: {e}")


def _seconds_until_next_run(now: datetime) -> float:
    target = now.replace(
        hour=SNAPSHOT_HOUR_UTC, minute=SNAPSHOT_MINUTE_UTC, second=0, microsecond=0
    )
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def refresh_loop() -> None:
    while True:
        try:
            await refresh_metrics()
        except Exception as e:
            print(f"graph_metrics refresh failed: {e}")
        await asyncio.sleep(_seconds_until_next_run(datetime.now(timezone.utc)))
