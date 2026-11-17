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


def _median(values: list[int]) -> int:
    """Median of a sorted-able list of sats.

    Local rather than reusing report_card's, to keep this module free of a
    dependency on the layer above it. Even counts take the mean of the two middle
    values, matching the baseline maths.
    """
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


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


# Fields a day can be missing if it was recorded by a backend older than the one that
# started storing them. `block_height` is included so a day lacking both ends of its
# range is filled consistently, but it is only ever filled in, never replaced.
SIZE_FIELDS = ("median_sats", "largest_sats", "smallest_sats", "block_from", "block_height")

# A rebuilt day this much thinner than what was recorded live has lost too many of its
# channels to closes for its sizes to stand in for the live figures. The rebuild only
# sees channels still open today, which is why it can only ever undercount.
MIN_REBUILT_SHARE = 0.8


def size_repairs(existing: list[dict], rebuilt: dict[str, dict]) -> dict[str, dict]:
    """Per date, the size fields a stored day lacks and `rebuilt` can supply.

    Only gaps are filled. A field the stored day already has is never replaced, and
    nothing else about the day (opens, capacity, hourly detail, closes) is touched,
    because those were measured at the time and a rebuild could only be worse.
    Days whose rebuild is too thin against what was recorded are left out entirely.
    """
    out: dict[str, dict] = {}
    for doc in existing:
        fresh = rebuilt.get(doc.get("date", ""))
        if not fresh:
            continue
        if fresh.get("opens", 0) < MIN_REBUILT_SHARE * (doc.get("opens") or 0):
            continue
        patch = {f: fresh[f] for f in SIZE_FIELDS if not doc.get(f) and fresh.get(f)}
        if patch:
            out[doc["date"]] = patch
    return out


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
                "min_height": height,
                "caps": [],
            }

        day["opens"] += 1
        day["capacity_sats"] += capacity_sats
        # Kept for every day, not just exactly-timed ones: interpolation costs us
        # *when* a channel opened, never *how big* it was. Summary figures derived
        # from these are therefore honest on every day in the archive.
        day["caps"].append(capacity_sats)
        day["max_height"] = max(day["max_height"], height)
        day["min_height"] = min(day["min_height"], height)

        if clock.is_exact(height):
            day["hourly"][moment.hour]["opens"].append(
                round(capacity_sats / SATS_PER_BTC, 8)
            )
        else:
            day["exact"] = False

    for day in days.values():
        day["btc_in"] = round(day["capacity_sats"] / SATS_PER_BTC, 4)
        # The block range is the day's real measurement window, and a far more
        # checkable statement than a wall-clock time for a global network.
        #
        # Both ends are defined by the opens themselves: the lowest and highest
        # block in which a channel opened that day. They are NOT the first and
        # last block of the UTC day — with ~120-190 opens spread over ~144 blocks
        # the two nearly coincide (measured median difference: 6 blocks), but they
        # are different claims, and mixing the definitions is how a field quietly
        # stops meaning one thing.
        day["block_height"] = day.pop("max_height")
        day["block_from"] = day.pop("min_height")

        caps = day.pop("caps")
        # Median, not mean: the distribution is heavily skewed — a handful of large
        # channels put the mean around 4x the median — so a mean would misrepresent
        # a typical channel badly.
        day["median_sats"] = _median(caps)
        day["largest_sats"] = max(caps) if caps else 0
        day["smallest_sats"] = min(caps) if caps else 0
        if not day["exact"]:
            day["hourly"] = None
        day.pop("exact")

    return days
