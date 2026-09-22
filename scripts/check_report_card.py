"""Regression checks for the report card's pure logic. No network, no database.

    python scripts/check_report_card.py

Exits non-zero on failure. There is no CI, so this is the gate for the baseline
maths and the generated copy — the parts that are easy to break silently, because
a wrong verdict still renders perfectly.

Kept out of the uvicorn import path per AGENTS.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.channel_flow import (  # noqa: E402
    BlockClock, bucket_by_day, decode_channel_id, open_events,
)
from services import report_card as rc  # noqa: E402

fails: list[str] = []


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got!r}, want {want!r}")
    print(f"{'ok  ' if got == want else 'FAIL'} {name}: {got!r}")


print("== short channel id decode ==")
# Real channel_id from our node; a live graph probe reported min height 503,816.
check("real channel id", decode_channel_id("553951550347608065")[0], 503816)
check("full triple", decode_channel_id(str((800000 << 40) | (5 << 16) | 1)),
      (800000, 5, 1))

print("\n== open_events ==")
check("filters undecodable", open_events([
    {"channel_id": str(900000 << 40), "capacity": "1000000"},
    {"channel_id": None, "capacity": "500"},
    {"channel_id": "not-a-number", "capacity": "500"},
    {"capacity": "500"},
]), [(900000, 1000000)])

print("\n== BlockClock ==")
clock = BlockClock({1000: 1_000_000, 2000: 1_600_000}, exact_from=1900)
check("exact anchor", clock.time_of(1000), 1_000_000)
check("midpoint interpolation", clock.time_of(1500), 1_300_000)
check("extrapolate below", clock.time_of(999), 1_000_000 - 600)
check("extrapolate above", clock.time_of(2001), 1_600_000 + 600)
check("is_exact inside", clock.is_exact(1950), True)
check("is_exact outside", clock.is_exact(1899), False)

print("\n== median / MAD / deviation ==")
check("median odd", rc._median([3, 1, 2]), 2.0)
check("median even", rc._median([1, 2, 3, 4]), 2.5)
check("median empty", rc._median([]), 0.0)
check("mad", rc._mad([1, 2, 3, 4, 5], 3.0), 1.0)
check("deviation zero mad", rc.deviation(5, [3, 3, 3, 3]), 0.0)
check("deviation empty series", rc.deviation(5, []), 0.0)
check("deviation is signed", rc.deviation(6, [1, 2, 3, 4, 5]) > 0, True)

print("\n== percentile ==")
check("mid", rc.percentile_of(3, [1, 2, 3, 4, 5]), 40)
check("above all", rc.percentile_of(9, [1, 2, 3, 4, 5]), 100)
check("below all", rc.percentile_of(0, [1, 2, 3, 4, 5]), 0)
check("empty series", rc.percentile_of(1, []), 0)
check("window phrase", rc.window_phrase(37), "in 37 days")

print("\n== verdict ==")
# Series handed to build_verdict are LIVE days only; their length drives the guard.
short = [100.0] * 5          # under MIN_LIVE_DAYS
flat = [100.0] * 30          # median 100, MAD 0
spread = [80.0, 90.0, 100.0, 110.0, 120.0] * 6   # median 100, MAD 10
btc = [10.0] * 30

v = rc.build_verdict(110, 12.0, short, short, 80, 112)
check("calibrating lead", v.lead_metric, "opens")
check("calibrating no deviation claim", v.deviation, 0.0)
check("calibrating states live count", "5 of 14 days" in v.subline, True)

v = rc.build_verdict(100, 10.0, flat, btc, 55, 112)
check("quiet headline", v.headline, "Quiet night on Lightning.")
check("quiet gini phrasing", "unremarkable" in v.subline, True)

v = rc.build_verdict(400, 12.0, spread, btc, 85, 112)
check("busy leads on opens", v.lead_metric, "opens")
check("busy gini phrasing", "running high" in v.subline, True)
check("norm uses live window", "30-day norm" in v.subline, True)
check("gini uses its own window", "last 112 days" in v.subline, True)

v = rc.build_verdict(100, 190.0, flat, spread, 50, 112)
check("high capacity leads", v.lead_metric, "btc_in")
check("high capacity copy", v.headline.endswith("entered Lightning overnight."), True)
check("high capacity deviation positive", v.deviation > 0, True)

# Regression: this branch used to narrate low capacity as low *activity*, quoting
# a channel count that was sitting exactly on its median.
v = rc.build_verdict(100, 1.0, flat, spread, 50, 112)
check("low capacity leads", v.lead_metric, "btc_in")
check("low capacity talks capacity not activity", "capacity" in v.subline, True)

v = rc.build_verdict(20, 10.0, spread, btc, 50, 112)
check("low activity headline", v.headline, "Lighter than usual on Lightning.")

# Regression: the gini clause used to borrow the flow window and print "last 0 days".
v = rc.build_verdict(110, 12.0, short, short, 0, 0)
check("no gini data omits clause", "last 0 days" in v.subline, False)

print("\n== language guard ==")
for phrase in rc.BANNED_PHRASES:
    for vv in (rc.build_verdict(400, 99.0, spread, spread, 99, 112),
               rc.build_verdict(100, 10.0, flat, btc, 20, 112),
               rc.build_verdict(110, 12.0, short, short, 50, 112)):
        if phrase in (vv.headline + vv.subline).lower():
            fails.append(f"banned phrase {phrase!r} leaked into copy")
print("ok   no banned phrase in any branch")

print("\n== backfilled days must not reach the baseline ==")
# Regression: 88 undercounted backfilled days dragged 'normal' 23% below the live
# truth, which would have made every ordinary night read as above the norm.
backfilled = [89.0] * 88
live = [117.0, 110.0, 123.0, 130.0, 97.0, 105.0, 120.0,
        112.0, 108.0, 125.0, 99.0, 118.0, 115.0, 121.0]
check("mixed median is depressed", rc._median(backfilled + live), 89.0)
check("live median is the real one", rc._median(live), 116.0)
check("live baseline calls an ordinary night quiet",
      rc.build_verdict(117, 30.0, live, [30.0] * 14, 50, 112).headline,
      "Quiet night on Lightning.")

print("\n== bucket_by_day ==")
clock2 = BlockClock({100: 1_700_000_000, 200: 1_700_086_400}, exact_from=150)
days = bucket_by_day([(160, 100_000_000), (170, 50_000_000), (110, 200_000_000)], clock2)
check("every event bucketed", sum(d["opens"] for d in days.values()), 3)
check("interpolated day drops hourly",
      any(d["hourly"] is None for d in days.values()), True)

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILURE(S):"))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
