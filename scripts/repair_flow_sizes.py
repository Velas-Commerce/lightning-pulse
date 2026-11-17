"""Fill in the per-day channel-size fields that some recorded days are missing.

    python scripts/repair_flow_sizes.py [days]            # dry run
    python scripts/repair_flow_sizes.py [days] --apply    # write

A daily_flow day recorded by a backend older than the one that started storing
`median_sats`, `largest_sats`, `smallest_sats` and `block_from` has none of them, so
the report card hides its Median open / Largest open tiles and its block range. The
live job cannot fix this itself: it rewrites only the last few days, and older days
are insert-only. `backfill_opens.py` is insert-only too.

This rebuilds those fields from the current graph (every channel's short ID carries
its funding block, so a day's channel sizes can be recovered) and writes only the
fields a day lacks. It never changes opens, capacity, hourly detail or closes, never
creates a day, and skips a day whose rebuild is much thinner than what was recorded.
Repaired days are marked `sizes_repaired: True`.

Caveat, and the reason for the skip: the graph only holds channels still open today,
so a rebuilt day can only undercount. Over a few days that is a small difference;
over months it is not, which is why `days` defaults to 30.

Needs mempool.space (or its mirror) for block timestamps. Without --apply nothing is
written. Kept out of the uvicorn import path per AGENTS.md.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import db  # noqa: E402
from services import channel_flow  # noqa: E402
from services.lnd import _client, LND_URL  # noqa: E402
from services.mempool import get_chain_tip  # noqa: E402

BLOCKS_PER_DAY = 144


async def main(days: int, apply: bool) -> None:
    await db.connect()
    database = db.get_db()
    if database is None:
        print("MONGODB_URI not set — nothing to repair")
        return
    print(f"database: {database.name}  ({'APPLY' if apply else 'dry run'})")

    stored = await database["daily_flow"].find({}, {"_id": 0}).sort("date", -1).to_list(length=None)
    needing = [
        d for d in stored[:days]
        if any(not d.get(f) for f in channel_flow.SIZE_FIELDS)
    ]
    print(f"{len(needing)} of the newest {min(days, len(stored))} day(s) are missing size fields")
    if not needing:
        await db.disconnect()
        return

    print("fetching /v1/graph ...")
    async with _client() as client:
        response = await client.get(f"{LND_URL}/v1/graph", timeout=120.0)
        response.raise_for_status()
        graph = response.json()

    events = channel_flow.open_events(graph.get("edges", []))
    tip = max(height for height, _ in events)
    try:
        tip = max(tip, await get_chain_tip())
    except Exception:
        pass  # our own highest channel is a good enough stand-in

    floor = tip - (days + 2) * BLOCKS_PER_DAY
    print(f"resolving block times for heights {floor:,}..{tip:,} ...")
    clock = await channel_flow.build_clock(floor, tip)
    rebuilt = channel_flow.bucket_by_day([(h, c) for h, c in events if h >= floor], clock)

    repairs = channel_flow.size_repairs(needing, rebuilt)
    by_date = {d["date"]: d for d in needing}
    for date in sorted(by_date):
        doc, patch = by_date[date], repairs.get(date)
        fresh = rebuilt.get(date, {})
        if patch:
            print(f"  {date}: fill {', '.join(patch)}  (opens {doc.get('opens')} stored, "
                  f"{fresh.get('opens')} rebuilt)")
        else:
            why = "no rebuilt day" if not fresh else (
                f"rebuilt opens {fresh.get('opens')} vs {doc.get('opens')} stored — too thin"
                if fresh.get("opens", 0) < channel_flow.MIN_REBUILT_SHARE * (doc.get("opens") or 0)
                else "nothing to fill"
            )
            print(f"  {date}: skipped ({why})")

    if not apply:
        print(f"dry run — {len(repairs)} day(s) would be repaired; pass --apply to write")
        await db.disconnect()
        return

    written = 0
    for date, patch in repairs.items():
        # No upsert: this repairs days that exist, it never creates one.
        result = await database["daily_flow"].update_one(
            {"date": date}, {"$set": {**patch, "sizes_repaired": True}}
        )
        written += result.modified_count
    print(f"repaired {written} day(s)")
    await db.disconnect()


if __name__ == "__main__":
    nums = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(int(nums[0]) if nums else 30, "--apply" in sys.argv))
