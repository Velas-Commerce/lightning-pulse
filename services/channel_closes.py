"""Channel closes, detected by watching funding outputs get spent.

Gossip alone cannot tell us a channel closed. A channel leaving `describegraph`
means only that it left *our node's view*, which happens for two very different
reasons: it was closed on-chain, or it went quiet long enough to be pruned as a
zombie. Counting the second as a close would inflate every close figure.

So a disappearance is only a *candidate*. It becomes a close when the channel's
funding output is confirmed spent on-chain, and the spending block is what dates
the close. Candidates whose output is still unspent are kept on a watchlist and
re-checked, because a channel can drop out of gossip before its close confirms.

This needs the previous run's channel set to diff against, so closes cannot be
backfilled the way opens can — there is no record of channels we never saw. The
first run establishes the baseline set and reports nothing.
"""

from datetime import date, timedelta

from services import channel_flow
from services.mempool import get_outspends

# Single overwritten document; the set is a snapshot, not a history.
SET_ID = "current"

# A candidate whose funding output is still unspent after this long left gossip
# for some other reason — almost certainly zombie pruning. Stop watching it.
WATCH_MAX_DAYS = 30


async def detect_closes(database, edges: list[dict], today: str) -> dict:
    """Diff the current channel set against the stored one and confirm on-chain.

    Returns the confirmed closes as (spend_block_height, capacity_sats) pairs,
    alongside counts that keep the uncertainty visible rather than hidden.
    """
    current = {
        edge["chan_point"]: int(edge.get("capacity", 0))
        for edge in edges
        if edge.get("chan_point")
    }

    stored = await database["channel_set"].find_one({"_id": SET_ID}) or {}
    previous = dict(zip(stored.get("points") or [], stored.get("caps") or []))
    watching = stored.get("watching") or []

    # Candidates: gone since the last run, plus everything already being watched
    # that still has not come back.
    candidates = {p: c for p, c in previous.items() if p not in current}
    seen_since = {}
    for entry in watching:
        if entry["point"] not in current:
            candidates.setdefault(entry["point"], entry["cap"])
            seen_since[entry["point"]] = entry["since"]

    closes: list[tuple[int, int]] = []
    still_watching: list[dict] = []

    if candidates:
        spends = await get_outspends(candidates)
        for point, cap in candidates.items():
            info = spends.get(point) or {}
            status = info.get("status") or {}
            if info.get("spent") and status.get("confirmed") and status.get("block_height"):
                closes.append((int(status["block_height"]), cap))
            else:
                still_watching.append({
                    "point": point,
                    "cap": cap,
                    "since": seen_since.get(point, today),
                })

    cutoff = (date.fromisoformat(today) - timedelta(days=WATCH_MAX_DAYS)).isoformat()
    expired = [e for e in still_watching if e["since"] < cutoff]
    still_watching = [e for e in still_watching if e["since"] >= cutoff]

    await database["channel_set"].update_one(
        {"_id": SET_ID},
        {"$set": {
            "date": today,
            "points": list(current.keys()),
            "caps": list(current.values()),
            "watching": still_watching,
        }},
        upsert=True,
    )

    return {
        "closes": closes,
        "first_run": not previous,
        "channels_seen": len(current),
        "watching": len(still_watching),
        "expired": len(expired),
    }


def bucket_closes(closes: list[tuple[int, int]], clock: channel_flow.BlockClock) -> dict:
    """Group confirmed closes into UTC days by the block that spent the funding output.

    The maths is identical to opens, so `bucket_by_day` does the work and its
    fields are renamed here rather than parameterised — one implementation of the
    bucketing, two vocabularies.
    """
    out: dict[str, dict] = {}
    for day, bucket in channel_flow.bucket_by_day(closes, clock).items():
        out[day] = {
            "closes": bucket["opens"],
            "btc_out": bucket["btc_in"],
            "hourly": (
                [h["opens"] for h in bucket["hourly"]] if bucket["hourly"] else None
            ),
        }
    return out
