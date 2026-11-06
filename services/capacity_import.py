"""Historical network capacity from BitcoinVisuals.com's chart export.

Pure parsing and quality flagging; the database work lives in
scripts/backfill_capacity.py. The export is one row per UTC day with the capacity in
BTC. Its timestamps are start-of-day, which is the same convention our own readings
use (taken just after 00:00 UTC, describing the network at the start of that day), so
dates are used as they stand.

The export has three kinds of row we should not take at face value, and each gets a
flag rather than being dropped, so the series stays complete and the reader can tell:

- blank       no reading at all. Nothing to import, so the day is left empty.
- carried     identical to the day before. The source repeated its last value, which
              says the feed went quiet, not that capacity stood still. Runs of 28, 46
              and 88 days exist.
- interpolated  a straight line between two real readings. The daily step is constant
              to within rounding, which real data never is over several days; the
              file has runs of 40 and 180 days. The two readings either side of the
              line are real and are left unflagged.
"""

import csv
import io
from decimal import Decimal

SATS_PER_BTC = 100_000_000

# Flags stored on a snapshot as `quality`. Absent means a plain observation.
CARRIED = "carried_forward"
INTERPOLATED = "interpolated"

# Three equal daily steps in a row (four points on one line) is the shortest run we
# call interpolated; real capacity does not repeat a step to within a tolerance this
# tight, so a false positive is not a practical worry.
MIN_LINE_STEPS = 3
LINE_TOLERANCE_SATS = 2_000  # 0.00002 BTC: rounding noise on a mid-run step


def parse_rows(text: str) -> list[tuple[str, int | None]]:
    """(YYYY-MM-DD, sats) for every row, sats None where the BTC cell is blank.

    BTC is read as a decimal string, not a float, so the conversion to sats is exact.
    """
    rows: list[tuple[str, int | None]] = []
    for record in csv.DictReader(io.StringIO(text)):
        day = (record.get("DateTime") or "").strip()[:10]
        if not day:
            continue
        raw = (record.get("BTC") or "").strip()
        sats = int(Decimal(raw) * SATS_PER_BTC) if raw else None
        rows.append((day, sats))
    return rows


def flag_quality(rows: list[tuple[str, int | None]]) -> list[tuple[str, int, str | None]]:
    """(date, sats, quality) for each day that has a reading, in date order.

    `quality` is CARRIED, INTERPOLATED or None. Blank days are omitted.
    """
    held = [(d, s) for d, s in sorted(rows) if s is not None]
    flags: list[str | None] = [None] * len(held)

    for i in range(1, len(held)):
        if held[i][1] == held[i - 1][1]:
            flags[i] = CARRIED

    # Straight lines: maximal runs of points whose consecutive steps are all equal.
    # Carried points have a zero step, which would read as a perfect line, so they
    # are kept out of it and keep their own flag.
    i = 0
    while i < len(held) - 2:
        step = held[i + 1][1] - held[i][1]
        if step == 0:
            i += 1
            continue
        j = i + 1
        while (
            j + 1 < len(held)
            and abs((held[j + 1][1] - held[j][1]) - step) <= LINE_TOLERANCE_SATS
        ):
            j += 1
        if j - i >= MIN_LINE_STEPS:
            for k in range(i + 1, j):  # interior only: both ends are real readings
                flags[k] = INTERPOLATED
            i = j
        else:
            i += 1

    return [(d, s, flags[k]) for k, (d, s) in enumerate(held)]
