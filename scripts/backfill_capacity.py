"""One-shot import of historical network capacity from a BitcoinVisuals.com export.

    python scripts/backfill_capacity.py path/to/BitcoinVisuals.com_chart.csv          # dry run
    python scripts/backfill_capacity.py path/to/BitcoinVisuals.com_chart.csv --apply  # write

Fills capacity_snapshots for every day that has no reading yet, tagged
`source: "bitcoinvisuals"`. A day that already has one — in particular any reading
our own node took — is left exactly as it is, so the script is safe to run twice and
safe to run after the live job has started. Days where the source repeated itself or
drew a straight line are imported with a `quality` flag (see services/capacity_import).

It also tags the existing lightning_stats documents `source: "mempool"`. Nothing is
deleted: the mempool history stays in place, and the series simply stops reading it
from the first snapshot onward (services/velocity.merge_capacity).

Without --apply nothing is written and the plan is printed, because the database
this connects to is whichever MONGODB_URI names.

Kept out of the uvicorn import path per AGENTS.md.
"""

import asyncio
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import db  # noqa: E402
from models import CapacityReading  # noqa: E402
from services.capacity_import import flag_quality, parse_rows  # noqa: E402

SOURCE = "bitcoinvisuals"


async def main(path: str, apply: bool) -> None:
    text = Path(path).read_text(encoding="utf-8-sig")
    rows = parse_rows(text)
    flagged = flag_quality(rows)
    blank = sum(1 for _, s in rows if s is None)
    print(f"{path}: {len(rows):,} rows, {rows[0][0]} .. {rows[-1][0]}, {blank} blank")
    print(f"readings: {dict(Counter(q or 'plain' for *_, q in flagged))}")

    await db.connect()
    database = db.get_db()
    if database is None:
        print("MONGODB_URI not set — nothing to import into")
        return
    print(f"database: {database.name}  ({'APPLY' if apply else 'dry run'})")

    existing = {
        d["date"]: d.get("source")
        async for d in database["capacity_snapshots"].find({}, {"_id": 0, "date": 1, "source": 1})
    }
    todo = [(d, s, q) for d, s, q in flagged if d not in existing]
    print(
        f"capacity_snapshots already holds {len(existing)} day(s) "
        f"{dict(Counter(existing.values()))}; importing {len(todo):,}, "
        f"leaving {len(flagged) - len(todo)} untouched"
    )

    untagged = await database["lightning_stats"].count_documents({"source": {"$exists": False}})
    print(f"lightning_stats documents to tag source=mempool: {untagged}")

    if not apply:
        print("dry run — pass --apply to write")
        await db.disconnect()
        return

    now = datetime.now(timezone.utc)
    written = 0
    for date, sats, quality in todo:
        doc = CapacityReading(
            date=date, total_capacity=sats, recorded_at=now, source=SOURCE, quality=quality,
        ).model_dump()
        # $setOnInsert: a day that appeared since the check above is not overwritten.
        result = await database["capacity_snapshots"].update_one(
            {"date": date}, {"$setOnInsert": doc}, upsert=True
        )
        written += result.upserted_id is not None

    tagged = await database["lightning_stats"].update_many(
        {"source": {"$exists": False}}, {"$set": {"source": "mempool"}}
    )
    print(f"wrote {written:,} day(s); tagged {tagged.modified_count} lightning_stats document(s)")
    await db.disconnect()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    asyncio.run(main(args[0], "--apply" in sys.argv))
