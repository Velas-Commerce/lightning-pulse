"""Fill gaps in the lightning_stats history from mempool.space's range endpoints.

For months the nightly snapshot stored whichever row mempool's `statistics/latest`
happened to return, and that endpoint serves rows weeks or months old from some of
its backends. The stored rows are real observations of the day they are dated, but
most days have none. The range endpoints answer consistently, so they can refill
the missing days:

    python scripts/repair_lightning_stats.py [days]            # dry run
    python scripts/repair_lightning_stats.py [days] --apply    # write

Insert-only. A day we already hold is never touched — any disagreement with mempool
is reported, not fixed. Inserted rows carry `is_repaired: True` and have no `date`
field, so the nightly upsert (keyed on `date`) can never match or overwrite them.
Undo with:  db.lightning_stats.deleteMany({is_repaired: true})

Kept out of the uvicorn import path per AGENTS.md.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import db  # noqa: E402
from services.mempool import added_date, get_stats_range  # noqa: E402

# The fields a range row carries; the rest of a full row cannot be reconstructed.
KEPT_FIELDS = (
    "channel_count", "total_capacity", "tor_nodes", "clearnet_nodes",
    "unannounced_nodes", "clearnet_tor_nodes",
)


# Every period at least as long as the window asked for. Periods are cached and
# served separately, so they often land on different backends and fill each other's gaps.
PERIODS = ("1m", "3m", "6m", "1y")
LENGTH = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}


def periods_for(days: int) -> list[str]:
    return [p for p in PERIODS if LENGTH[p] >= days] or [PERIODS[-1]]


# Each backend holds a different, patchy subset of days, and which one answers is a
# lottery (see services/mempool.py), so one call is never the whole picture. Several
# draws are merged by date; the first row seen for a day wins.
DRAWS = 12


async def gather_rows(periods: list[str], cutoff: str) -> list[dict]:
    by_day: dict[str, dict] = {}
    for i in range(DRAWS):
        for period in periods:
            try:
                for row in await get_stats_range(period):
                    day = added_date(row["added"])
                    if day >= cutoff:
                        by_day.setdefault(day, row)
            except Exception as e:  # one failed draw should not abandon the rest
                print(f"  {period} draw {i + 1} failed: {e}")
        await asyncio.sleep(1.0)  # let the upstream rotate between backends
    return list(by_day.values())


async def main(days: int, apply: bool) -> None:
    await db.connect()
    database = db.get_db()
    if database is None:
        print("MONGODB_URI not set — nothing to repair")
        return

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    periods = periods_for(days)
    rows = await gather_rows(periods, cutoff)
    print(f"mempool {'+'.join(periods)}, {DRAWS} draws each, merged: "
          f"{len(rows)} distinct days since {cutoff}")

    held = {
        (d.get("added") or "")[:10]: d.get("total_capacity")
        for d in await database["lightning_stats"].find(
            {}, {"_id": 0, "added": 1, "total_capacity": 1}
        ).to_list(length=None)
    }

    to_insert, disagree = [], []
    for row in sorted(rows, key=lambda r: r["added"]):
        day = added_date(row["added"])
        if day in held:
            if held[day] != row["total_capacity"]:
                disagree.append((day, held[day], row["total_capacity"]))
            continue
        observed = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        to_insert.append({
            "added": f"{day}T00:00:00.000Z",
            **{k: row[k] for k in KEPT_FIELDS if k in row},
            # The observation date, not now: this is when the figure describes.
            "recorded_at": observed,
            "is_repaired": True,
        })

    print(f"already held: {len(rows) - len(to_insert)}   missing: {len(to_insert)}")
    for d in to_insert:
        print(f"  + {d['added'][:10]}  {d['total_capacity']:>15,} sats  {d['channel_count']:,} channels")
    if disagree:
        print(f"held rows whose capacity differs from mempool's ({len(disagree)}, left untouched):")
        for day, ours, theirs in disagree:
            print(f"  ~ {day}  ours {ours:,}  mempool {theirs:,}  ({(ours - theirs) / theirs:+.1%})")

    if not to_insert:
        print("nothing to insert")
    elif apply:
        await database["lightning_stats"].insert_many(to_insert)
        print(f"inserted {len(to_insert)} rows")
    else:
        print("dry run — pass --apply to insert")

    await db.disconnect()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(main(int(args[0]) if args else 120, "--apply" in sys.argv))
