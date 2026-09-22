"""One-shot backfill of historical channel opens.

Every edge in the LND graph carries its own open block height in its short channel
ID, so a single fetch reconstructs the whole history. Run once after deploying the
daily_flow collection:

    python scripts/backfill_opens.py [days]

Backfilled days are marked `is_backfilled: True` and are never written over a day
the live job already recorded. They undercount — only channels still open today are
visible, and that bias grows with age — which is why services/report_card.py holds
off on comparative language until enough live days exist.

Kept out of the uvicorn import path per AGENTS.md.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from services import channel_flow  # noqa: E402
from services.lnd import _client, LND_URL  # noqa: E402
from services.mempool import get_chain_tip  # noqa: E402

BLOCKS_PER_DAY = 144


async def main(days: int) -> None:
    await db.connect()
    database = db.get_db()
    if database is None:
        print("MONGODB_URI not set — nothing to backfill into")
        return

    print("fetching /v1/graph ...")
    async with _client() as client:
        response = await client.get(f"{LND_URL}/v1/graph", timeout=120.0)
        response.raise_for_status()
        graph = response.json()

    events = channel_flow.open_events(graph.get("edges", []))
    print(f"decoded {len(events):,} channel opens")

    tip = max(height for height, _ in events)
    try:
        tip = max(tip, await get_chain_tip())
    except Exception:
        pass

    floor = tip - days * BLOCKS_PER_DAY
    window = [(h, c) for h, c in events if h >= floor]
    print(f"resolving block times for heights {floor:,}..{tip:,} ...")
    clock = await channel_flow.build_clock(floor, tip)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    buckets = channel_flow.bucket_by_day(window, clock)

    written = skipped = 0
    for date, doc in sorted(buckets.items()):
        if date >= today:
            continue  # never record a partial day
        doc.pop("date")  # supplied by the filter
        doc["is_backfilled"] = True
        doc["recorded_at"] = datetime.now(timezone.utc)
        result = await database["daily_flow"].update_one(
            {"date": date}, {"$setOnInsert": doc}, upsert=True
        )
        if result.upserted_id is not None:
            written += 1
        else:
            skipped += 1

    print(f"wrote {written} day(s), left {skipped} existing day(s) untouched")
    await db.disconnect()


if __name__ == "__main__":
    requested = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    asyncio.run(main(requested))
