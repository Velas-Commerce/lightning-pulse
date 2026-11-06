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
from services import channel_closes, report_card as rc  # noqa: E402
from services.channel_flow import _median as median_sats  # noqa: E402

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
DAY, FROM, TO = "Thursday", 968_922, 969_066


def verdict(opens, btc_in, o_series, b_series, pct=50, gini_days=112, **kw):
    """Positional signature is long; keep the checks readable."""
    return rc.build_verdict(opens, btc_in, o_series, b_series, pct, gini_days,
                            DAY, FROM, TO, **kw)


check("weekday is locale-independent", rc.weekday_of("2026-09-28"), "Monday")
check("block span renders a range", rc._block_span(100, 250),
      "Across blocks 100–250, ")
check("block span empty when unknown", rc._block_span(0, 250), "")
check("block span empty when inverted", rc._block_span(300, 250), "")

v = verdict(110, 12.0, short, short, pct=80)
check("calibrating lead", v.lead_metric, "opens")
check("calibrating no deviation claim", v.deviation, 0.0)
check("calibrating names the weekday", v.headline.endswith(f"on {DAY}."), True)
check("calibrating states live count", "5 of 14 days" in v.subline, True)
check("calibrating carries block range", "Across blocks 968,922" in v.subline, True)

v = verdict(100, 10.0, flat, btc, pct=55)
check("quiet headline", v.headline, f"{DAY} was quiet on Lightning.")
check("quiet gini phrasing", "unremarkable" in v.subline, True)
check("quiet has no highlight", v.highlight, None)

v = verdict(400, 12.0, spread, btc, pct=85)
check("busy leads on opens", v.lead_metric, "opens")
check("busy headline", v.headline, f"400 new channels — a busy {DAY}.")
check("busy highlight is the count", v.highlight, "400 new channels")
check("busy gini phrasing", "running high" in v.subline, True)
check("norm uses live window", "30-day norm" in v.subline, True)
check("gini uses its own window", "last 112 days" in v.subline, True)

v = verdict(100, 190.0, flat, spread)
check("high capacity leads", v.lead_metric, "btc_in")
check("high capacity headline", v.headline, f"190.0 BTC entered Lightning on {DAY}.")
check("high capacity highlight", v.highlight, "190.0 BTC")
check("high capacity deviation positive", v.deviation > 0, True)

# Regression: this branch used to narrate low capacity as low *activity*, quoting
# a channel count that was sitting exactly on its median.
v = verdict(100, 1.0, flat, spread)
check("low capacity leads", v.lead_metric, "btc_in")
check("low capacity talks capacity not activity", "capacity" in v.subline, True)

v = verdict(20, 10.0, spread, btc)
check("low activity headline", v.headline, f"{DAY} ran light on Lightning.")

# Regression: a maximum reading was narrated as "the 99th percentile" (it can never
# score 100), the size of the move was never stated, and the clause asserted that
# "the graph grows" on no evidence at all.
g_series = [0.830 + i * 0.0002 for i in range(90)]
v = verdict(100, 10.0, flat, btc, pct=99, gini_days=90, gini_series=g_series)
check("gini at max is stated in words", "highest in the last 90 days" in v.subline, True)
check("gini at max avoids the percentile", "99th" in v.subline, False)
check("gini states how little it moved", "moved only" in v.subline, True)
check("gini makes no growth claim", "grows" in v.subline, False)
v = verdict(100, 10.0, flat, btc, pct=0, gini_days=90, gini_series=g_series[::-1])
check("gini at min is stated in words", "lowest in the last 90 days" in v.subline, True)
v = verdict(100, 10.0, flat, btc, pct=55, gini_days=90,
            gini_series=g_series + [0.8365])  # latest sits mid-range, not at an edge
check("gini mid-range keeps the percentile", "55th percentile" in v.subline, True)

# Regression: the gini clause used to borrow the flow window and print "last 0 days".
v = verdict(110, 12.0, short, short, pct=0, gini_days=0)
check("no gini data omits clause", "last 0 days" in v.subline, False)

# The frontend emphasises the headline by splitting it on `highlight`, so a
# highlight that is not a substring would silently render as no emphasis.
for label, vv in [("busy", verdict(400, 12.0, spread, btc)),
                  ("high capacity", verdict(100, 190.0, flat, spread)),
                  ("calibrating", verdict(110, 12.0, short, short))]:
    if vv.highlight is not None and vv.highlight not in vv.headline:
        fails.append(f"{label}: highlight {vv.highlight!r} not in headline")
print("ok   every highlight is a substring of its headline")

print("\n== language guard ==")
# "night" is banned alongside the superlatives: the window is a 24h UTC day on a
# global network, and the local date can differ from the UTC date by hours.
check("night is banned", "night" in rc.BANNED_PHRASES, True)
for phrase in rc.BANNED_PHRASES:
    for vv in (verdict(400, 99.0, spread, spread, pct=99),
               verdict(100, 10.0, flat, btc, pct=20),
               verdict(100, 1.0, flat, spread),
               verdict(20, 10.0, spread, btc),
               verdict(110, 12.0, short, short),
               verdict(100, 10.0, flat, btc, closes=100, btc_out=12.0,
                       closes_series=[40.0, 55.0] * 7, btc_out_series=[12.0] * 14,
                       closes_known=True),
               verdict(100, 10.0, flat, btc, closes=5, btc_out=0.2,
                       closes_series=[40.0, 55.0] * 7, btc_out_series=[12.0] * 14,
                       closes_known=True)):
        if phrase in (vv.headline + vv.subline).lower():
            fails.append(f"banned phrase {phrase!r} leaked into copy")
print("ok   no banned phrase in any branch")

print("\n== closes ==")
# Closes cannot be backfilled — there is no channel-set history to reconstruct
# them from — so their series starts empty and must not be allowed to lead.
closes_live = [40.0, 55.0, 48.0, 61.0, 44.0, 52.0, 58.0,
               46.0, 50.0, 63.0, 42.0, 57.0, 49.0, 54.0]
# Spread, not flat: a zero-MAD series yields deviation 0 by design, so a flat
# one could never lead and would silently test nothing.
out_live = [8.0, 12.0, 16.0, 10.0, 14.0, 9.0, 13.0,
            11.0, 15.0, 12.0, 10.0, 14.0, 11.0, 13.0]

v = verdict(100, 10.0, flat, btc, closes=900, btc_out=900.0,
            closes_series=[], btc_out_series=[], closes_known=True)
check("closes cannot lead without their own history", v.lead_metric in ("opens", "btc_in"), True)

v = verdict(100, 10.0, flat, btc, closes=100, btc_out=12.0,
            closes_series=closes_live, btc_out_series=out_live, closes_known=True)
check("closes lead once they have history", v.lead_metric, "closes")
check("closes-high headline", v.headline, f"100 channels closed on {DAY}.")
check("closes-high highlight", v.highlight, "100 channels")
check("net clause present when closes known", "nets +0 channels" in v.subline, True)

# The "heaviest closing day" claim is only true when it actually is the maximum.
check("heaviest claimed when it is the max", "heaviest closing day" in v.subline, True)
v2 = verdict(100, 10.0, flat, btc, closes=75, btc_out=12.0,
             closes_series=closes_live + [400.0], btc_out_series=out_live + [12.0],
             closes_known=True)
check("heaviest not claimed otherwise", "heaviest closing day" in v2.subline, False)

v = verdict(100, 10.0, flat, btc, closes=5, btc_out=12.0,
            closes_series=closes_live, btc_out_series=out_live, closes_known=True)
check("closes-low leads on closes", v.lead_metric, "closes")
check("closes-low headline", v.headline.startswith("Closures eased on"), True)

v = verdict(100, 10.0, flat, btc, closes=50, btc_out=90.0,
            closes_series=closes_live, btc_out_series=out_live, closes_known=True)
check("btc_out-high leads", v.lead_metric, "btc_out")
check("btc_out-high headline", v.headline, f"90.0 BTC left Lightning on {DAY}.")

v = verdict(100, 10.0, flat, btc, closes=50, btc_out=0.2,
            closes_series=closes_live, btc_out_series=out_live, closes_known=True)
check("btc_out-low leads", v.lead_metric, "btc_out")
check("btc_out-low headline", v.headline, f"Little capacity left Lightning on {DAY}.")

# A day recorded before detection existed has no closes at all; the copy must not
# imply a net figure it cannot compute.
v = verdict(100, 10.0, flat, btc, closes_known=False)
check("no net clause when closes unknown", "nets" in v.subline, False)
v = verdict(110, 12.0, short, short, closes=7, btc_out=3.0, closes_known=True)
check("calibrating still reports net when known", "nets +103 channels" in v.subline, True)

print("\n== bucket_closes ==")
cl = BlockClock({100: 1_700_000_000, 200: 1_700_086_400}, exact_from=150)
buckets = channel_closes.bucket_closes([(160, 100_000_000), (170, 50_000_000)], cl)
day = next(iter(buckets.values()))
check("closes counted", day["closes"], 2)
check("btc_out summed", day["btc_out"], 1.5)
check("hourly closes is 24 buckets", len(day["hourly"]), 24)

print("\n== backfilled days must not reach the baseline ==")
# Regression: 88 undercounted backfilled days dragged 'normal' 23% below the live
# truth, which would have made every ordinary day read as above the norm.
backfilled = [89.0] * 88
live = [117.0, 110.0, 123.0, 130.0, 97.0, 105.0, 120.0,
        112.0, 108.0, 125.0, 99.0, 118.0, 115.0, 121.0]
check("mixed median is depressed", rc._median(backfilled + live), 89.0)
check("live median is the real one", rc._median(live), 116.0)
check("live baseline calls an ordinary day quiet",
      verdict(117, 30.0, live, [30.0] * 14).headline,
      f"{DAY} was quiet on Lightning.")

print("\n== bucket_by_day ==")
clock2 = BlockClock({100: 1_700_000_000, 200: 1_700_086_400}, exact_from=150)
days = bucket_by_day([(160, 100_000_000), (170, 50_000_000), (110, 200_000_000)], clock2)
check("every event bucketed", sum(d["opens"] for d in days.values()), 3)
check("interpolated day drops hourly",
      any(d["hourly"] is None for d in days.values()), True)

print("\n== per-day channel sizes ==")
check("median of odd count", median_sats([1, 5, 3]), 3)
check("median of even count", median_sats([10, 20, 30, 40]), 25)
check("median of nothing", median_sats([]), 0)

clock3 = BlockClock({100: 1_700_000_000, 200: 1_700_086_400}, exact_from=150)
# Deliberately skewed, the way real channel sizes are: one whale and four minnows.
day3 = next(iter(bucket_by_day(
    [(160, 10), (161, 20), (162, 30), (163, 40), (164, 100_000)], clock3).values()))
check("median resists the whale", day3["median_sats"], 30)
check("largest is the whale", day3["largest_sats"], 100_000)
check("smallest is kept too", day3["smallest_sats"], 10)
mean = day3["capacity_sats"] / day3["opens"]
check("a mean would have been far off", mean > day3["median_sats"] * 100, True)

# Sizes must survive on days whose hour-binning does not: interpolation costs us
# *when* a channel opened, never *how big* it was. This was the actual bug — the
# frontend fell back to a mean labelled "Median open" on 88 of 97 stored days.
interp = next(iter(bucket_by_day([(110, 10), (111, 90)], clock3).values()))
check("interpolated day drops hourly", interp["hourly"], None)
check("interpolated day keeps its median", interp["median_sats"], 50)
check("interpolated day keeps its largest", interp["largest_sats"], 90)

print("\n== per-panel analysis ==")
from models import SlowIndex  # noqa: E402


def slow(key, series, pct=50, stale=0, as_of="2026-10-06"):
    return SlowIndex(key=key, label=key, value=series[-1], percentile=pct,
                     series=series, as_of=as_of, stale_days=stale)


rising = [0.830 + i * 0.0002 for i in range(90)]
mid = rising[:-1] + [0.8365]
a = rc.slow_analysis([slow("gini", rising, 99), slow("top10", rising, 99)])
check("gini names the extreme in words", "more unequal than at any point in the last 90 days" in a["gini"], True)
check("gini avoids the percentile at an edge", "99th" in a["gini"], False)
check("gini says how little it moved", "moved only" in a["gini"], True)
check("gini notes agreement with top-10", "both measures agree" in a["gini"], True)
check("top10 notes agreement with gini", "both measures agree" in a["top10"], True)
check("top10 states points moved", "up 1.8 points" in a["top10"], True)

a = rc.slow_analysis([slow("gini", rising, 99), slow("top10", mid, 55)])
check("gini edge without top-10 edge is called out", "not at the top of the node ranking" in a["gini"], True)
check("top10 mid-range keeps the percentile", "55th percentile" in a["top10"], True)
check("disagreement is not called agreement", "agree" in a["top10"], False)

stale = [slow("capacity", [450e9, 440e9, 375e9], 0, stale=37, as_of="2026-08-30"),
         slow("velocity", [3.8, 3.9, 3.98], 50, stale=37, as_of="2026-08-30")]
a = rc.slow_analysis(stale)
check("stale reading says so up front", a["capacity"].startswith("The latest reading is from 30 Aug, 37 days"), True)
check("capacity at its low is stated in words", "lowest of the last 3 readings" in a["capacity"], True)
check("velocity admits it restates capacity", "held constant" in a["velocity"], True)
check("fresh reading carries no staleness note",
      "days before" in rc.slow_analysis([slow("capacity", [1.0, 2.0, 1.5], 50)])["capacity"], False)

check("ordinals: 11th 12th 13th 21st 102nd", [rc._ordinal(n) for n in (11, 12, 13, 21, 102)],
      ["11th", "12th", "13th", "21st", "102nd"])
every = " ".join(list(rc.slow_analysis([slow("gini", rising, 99), slow("top10", rising, 99)]).values())
                 + list(a.values()) + list(rc.SLOW_SOURCES.values())).lower()
check("copy passes the language guard", [p for p in rc.BANNED_PHRASES if p in every], [])

print("\n== mempool stats freshness ==")
from datetime import datetime, timedelta, timezone  # noqa: E402
from models import LightningStats, LightningStatsResponse  # noqa: E402
from services import mempool  # noqa: E402

# `latest` serves ISO text, the range endpoints a unix time; both must read as a date.
check("added_date from ISO text", mempool.added_date("2026-10-06T00:00:00.000Z"), "2026-10-06")
check("added_date from unix time", mempool.added_date(1791244800), "2026-10-06")


def stats_row(days_old: int) -> LightningStatsResponse:
    day = (datetime.now(timezone.utc) - timedelta(days=days_old)).strftime("%Y-%m-%d")
    fields = {k: 0 for k in LightningStats.model_fields if k != "added"}
    return LightningStatsResponse(latest=LightningStats(added=f"{day}T00:00:00.000Z", **fields))


check("a row from yesterday is 1 day old", mempool.stats_age_days(stats_row(1)), 1)
check("a 38-day-old row is over the persist limit",
      mempool.stats_age_days(stats_row(38)) > mempool.STATS_MAX_AGE_DAYS, True)
check("yesterday's row counts as fresh",
      mempool.stats_age_days(stats_row(1)) <= mempool.STATS_FRESH_DAYS, True)

print("\n== capacity from our own node ==")
from services.capacity import ACTIVE_WINDOW_DAYS, compute_capacity  # noqa: E402
from services.velocity import merge_capacity  # noqa: E402

now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
ts = int(now.timestamp())
day = 86400


def edge(cap, a, b, u1=None, u2=None):
    return {
        "capacity": str(cap), "node1_pub": a, "node2_pub": b,
        "node1_policy": {"last_update": u1} if u1 is not None else None,
        "node2_policy": {"last_update": u2} if u2 is not None else None,
    }


graph = {"edges": [
    edge(100, "a", "b", ts - day, None),                             # one side fresh: active
    edge(200, "b", "c", None, ts - (ACTIVE_WINDOW_DAYS + 1) * day),  # stale: not active
    edge(400, "a", "c"),                                             # no policies at all
    edge(800, "d", "e", ts - 2 * day, ts - 90 * day),                # one fresh side is enough
]}
r = compute_capacity(graph, 970000, now)
check("total capacity sums every edge once", r.total_capacity, 1500)
check("active needs only one side updated in the window", r.active_capacity, 900)
check("channel count is the edge count", r.channel_count, 4)
check("nodes are the unique endpoints", r.node_count, 5)
check("reading is dated by UTC day", r.date, "2026-11-05")
check("an empty graph reads as zero, not an error",
      compute_capacity({}, 1, now).total_capacity, 0)

mem = [("2026-08-30", 10), ("2026-10-06", 11), ("2026-11-05", 12)]
check("no readings: mempool history is untouched", merge_capacity(mem, []), mem)
check("readings replace mempool from the switchover day, keeping what came before",
      merge_capacity(mem, [("2026-11-05", 20), ("2026-11-06", 21)]),
      [("2026-08-30", 10), ("2026-10-06", 11), ("2026-11-05", 20), ("2026-11-06", 21)])

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILURE(S):"))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
