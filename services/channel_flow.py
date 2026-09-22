"""Channel opens, derived from short channel IDs.

A BOLT 7 short channel ID encodes the block that confirmed the channel's funding
transaction, so every edge in the graph carries its own open height. One graph
fetch therefore yields the entire history of opens — no day-over-day diffing.

Two caveats travel with every number this module produces:

1. Only channels that are *still open* appear in the graph, so days further back
   are increasingly undercounted. Callers must not treat a backfilled day as
   comparable to a live-collected one (see services/report_card.py).
2. This is our own node's gossip view, which is narrower than the whole network.
   Counts are "channels we learned about", never ground truth.
"""

import bisect
from datetime import datetime, timezone

from services.mempool import get_block_timestamps
from services.velocity import SATS_PER_BTC

# Exact per-block timestamps are fetched for this many blocks back from the tip
# (~3 days at 10 min/block). Only days fully inside this window get hourly detail.
# Sized with margin: the job needs yesterday fully covered even if it runs late or
# the chain ran fast, and the extra day lets a missed run be picked up next time.
EXACT_BLOCKS = 432

# Beyond the exact window, anchors this far apart are interpolated between.
# Roughly one day of blocks. Weekly anchors were tried first and drifted day
# boundaries by hours — enough to shuffle a meaningful number of channels between
# adjacent days — because block production wanders well off 10 min/block over a
# week. At daily spacing the error stays within the hour.
ANCHOR_SPACING = 144

SECONDS_PER_BLOCK = 600


def decode_channel_id(channel_id: str | int) -> tuple[int, int, int]:
    """Split a BOLT 7 short channel ID into (block_height, tx_index, output_index)."""
    value = int(channel_id)
    return (value >> 40, (value >> 16) & 0xFFFFFF, value & 0xFFFF)


def open_events(edges: list[dict]) -> list[tuple[int, int]]:
    """(block_height, capacity_sats) for every edge whose channel ID decodes."""
    events: list[tuple[int, int]] = []
    for edge in edges:
        channel_id = edge.get("channel_id")
        if not channel_id:
            continue
        try:
            height, _, _ = decode_channel_id(channel_id)
            capacity = int(edge.get("capacity", 0))
        except (ValueError, TypeError):
            continue
        if height > 0:
            events.append((height, capacity))
    return events


class BlockClock:
    """Maps block heights to unix timestamps, interpolating between known anchors.

    `exact_from` marks the height at or above which every block's timestamp was
    fetched directly; below it, times are interpolated and only trustworthy at
    day resolution.
    """

    def __init__(self, anchors: dict[int, int], exact_from: int):
        ordered = sorted(anchors.items())
        self._heights = [h for h, _ in ordered]
        self._times = [t for _, t in ordered]
        self.exact_from = exact_from

    def is_exact(self, height: int) -> bool:
        return height >= self.exact_from

    def time_of(self, height: int) -> int:
        if not self._heights:
            raise ValueError("BlockClock has no anchors")

        index = bisect.bisect_left(self._heights, height)
        if index < len(self._heights) and self._heights[index] == height:
            return self._times[index]

        # Off either end: extrapolate at the nominal block interval.
        if index == 0:
            return self._times[0] - (self._heights[0] - height) * SECONDS_PER_BLOCK
        if index == len(self._heights):
            return self._times[-1] + (height - self._heights[-1]) * SECONDS_PER_BLOCK

        low_h, high_h = self._heights[index - 1], self._heights[index]
        low_t, high_t = self._times[index - 1], self._times[index]
        span = high_h - low_h
        if span <= 0:
            return low_t
        return round(low_t + (high_t - low_t) * (height - low_h) / span)


async def build_clock(min_height: int, tip_height: int) -> BlockClock:
    """Fetch the block timestamps needed to place `min_height`..`tip_height` in time.

    Costs roughly (EXACT_BLOCKS / 15) + (span / ANCHOR_SPACING) upstream calls,
    which is why this runs in the daily job rather than per request.
    """
    exact_from = max(min_height, tip_height - EXACT_BLOCKS)

    heights = set(range(exact_from, tip_height + 1))
    heights.update(range(min_height, exact_from, ANCHOR_SPACING))
    heights.add(min_height)

    anchors = await get_block_timestamps(heights)
    if not anchors:
        raise RuntimeError("could not resolve any block timestamps")

    # If the exact window came back short, don't claim hourly precision for it.
    resolved_exact = min((h for h in anchors if h >= exact_from), default=tip_height)
    return BlockClock(anchors, exact_from=resolved_exact)


def bucket_by_day(
    events: list[tuple[int, int]], clock: BlockClock
) -> dict[str, dict]:
    """Group open events into UTC days.

    Days composed entirely of exactly-timed blocks carry `hourly` detail; older
    days carry None, because interpolated block times cannot honestly be binned
    to the hour.
    """
    days: dict[str, dict] = {}

    for height, capacity_sats in events:
        moment = datetime.fromtimestamp(clock.time_of(height), tz=timezone.utc)
        key = moment.strftime("%Y-%m-%d")

        day = days.get(key)
        if day is None:
            day = days[key] = {
                "date": key,
                "opens": 0,
                "capacity_sats": 0,
                "hourly": [{"hour": h, "opens": []} for h in range(24)],
                "exact": True,
                "max_height": height,
            }

        day["opens"] += 1
        day["capacity_sats"] += capacity_sats
        day["max_height"] = max(day["max_height"], height)

        if clock.is_exact(height):
            day["hourly"][moment.hour]["opens"].append(
                round(capacity_sats / SATS_PER_BTC, 8)
            )
        else:
            day["exact"] = False

    for day in days.values():
        day["btc_in"] = round(day["capacity_sats"] / SATS_PER_BTC, 4)
        day["block_height"] = day.pop("max_height")
        if not day["exact"]:
            day["hourly"] = None
        day.pop("exact")

    return days
