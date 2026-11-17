"""Network capacity measured from our own LND node's graph.

This replaces mempool.space's lightning statistics as the source for capacity,
channel and node counts. The method mirrors the lncli procedure the operator runs by
hand, so a reading can be reproduced from `lncli describegraph` with jq:

- Only take a reading when the node is synced to chain and to graph.
- Total capacity is the sum of `.edges[].capacity`; each channel appears once in
  `.edges`, so there is nothing to de-duplicate.
- Nodes are those with at least one public channel.
- Active capacity counts channels where at least one side's policy was updated in
  the last 14 days.

Deliberately not `getnetworkinfo`: every released LND undercounts capacity there and
the figure changes from call to call.
"""

from datetime import datetime, timezone

import db
from models import CapacityReading
from services.lnd import LND_URL, _client

ACTIVE_WINDOW_DAYS = 14

_latest: CapacityReading | None = None


def get_latest_reading() -> CapacityReading | None:
    return _latest


def compute_capacity(graph: dict, block_height: int, now: datetime) -> CapacityReading:
    """Pure: graph JSON from `describegraph` in, one reading out."""
    cutoff = now.timestamp() - ACTIVE_WINDOW_DAYS * 86400
    total = 0
    active = 0
    nodes: set[str] = set()
    edges = graph.get("edges", [])

    for edge in edges:
        capacity = int(edge.get("capacity") or 0)
        total += capacity
        for key in ("node1_pub", "node2_pub"):
            if edge.get(key):
                nodes.add(edge[key])
        # Policies are null until a side announces; `last_update` is a unix time.
        updated = max(
            int((edge.get(key) or {}).get("last_update") or 0)
            for key in ("node1_policy", "node2_policy")
        )
        if updated > cutoff:
            active += capacity

    return CapacityReading(
        date=now.strftime("%Y-%m-%d"),
        total_capacity=total,
        active_capacity=active,
        channel_count=len(edges),
        node_count=len(nodes),
        block_height=block_height,
        recorded_at=now,
        source="lnd",
    )


async def synced_height() -> int | None:
    """Block height if the node is synced to both chain and graph, else None."""
    async with _client() as client:
        response = await client.get(f"{LND_URL}/v1/getinfo", timeout=30.0)
        response.raise_for_status()
        info = response.json()
    if info.get("synced_to_chain") and info.get("synced_to_graph"):
        return int(info.get("block_height") or 0)
    return None


async def take_reading(graph: dict) -> CapacityReading | None:
    """Reading from an already-fetched graph, or None when the node isn't synced.

    A skipped run leaves the previous reading in place rather than recording a
    number taken while the graph was still catching up.
    """
    global _latest
    height = await synced_height()
    if height is None:
        print("capacity: node not synced to chain and graph — reading skipped")
        return None
    reading = compute_capacity(graph, height, datetime.now(timezone.utc))
    _latest = reading
    return reading


async def persist(reading: CapacityReading) -> None:
    database = db.get_db()
    if database is None:
        return
    # Upsert by UTC date, like every other snapshot: a restart refreshes the day.
    await database["capacity_snapshots"].update_one(
        {"date": reading.date}, {"$set": reading.model_dump()}, upsert=True
    )
