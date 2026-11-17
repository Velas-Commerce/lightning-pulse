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

stale = [slow("velocity", [3.8, 3.9, 3.98], 50, stale=37, as_of="2026-08-30")]
a = rc.slow_analysis(stale)
check("stale reading says so up front", a["velocity"].startswith("The latest reading is from 30 Aug, 37 days"), True)
check("velocity admits it restates capacity", "held constant" in a["velocity"], True)
check("fresh reading carries no staleness note",
      "days before" in rc.slow_analysis([slow("velocity", [1.0, 2.0, 1.5], 50)])["velocity"], False)
check("capacity is no longer a slow index",
      "capacity" in rc.slow_analysis([slow("capacity", [1.0, 2.0], 50)]), False)

print("\n== capacity on the front page ==")
from datetime import date as _date, timedelta  # noqa: E402

TODAY = _date(2026, 11, 17)


def daily(values, end="2026-11-17"):
    """Ascending (date, sats), one reading a day ending on `end`."""
    end_day = _date.fromisoformat(end)
    n = len(values)
    return [((end_day - timedelta(days=n - 1 - i)).isoformat(), round(v * 100_000_000))
            for i, v in enumerate(values)]


steady = [4000 - i * (1000 / 89) for i in range(90)]
slowing = [4000 - i * 15 for i in range(60)] + [3115 - (i - 59) for i in range(60, 90)]
reversal = [4000 - i * 15 for i in range(60)] + [3115 + (i - 59) * 10 for i in range(60, 90)]
speeding = [4000.0] * 60 + [4000 - (i - 59) * (400 / 30) for i in range(60, 90)]
flat = [3500.0] * 90

t = rc.capacity_trend(daily(steady), TODAY)
check("a steady decline is called in line with its own pace", "in line with the 89-day pace" in t.analysis, True)
check("the recent change is stated against 30 days ago", "down 10.1% on 30 days ago" in t.analysis, True)
check("the level is stated in whole BTC", t.analysis.startswith("Capacity is 3,000 BTC"), True)
check("the low is stated in words, not as a percentile", "at its lowest of the last 90 readings" in t.analysis, True)
check("the long change is reported", t.long_change_pct, -25.0)
check("the block carries one point per reading", len(t.series), 90)

t = rc.capacity_trend(daily(slowing), TODAY)
check("a decline that has eased is called slower", "slower than the 89-day pace" in t.analysis, True)

t = rc.capacity_trend(daily(speeding), TODAY)
check("a decline that has quickened is called faster", "faster than the 89-day pace" in t.analysis, True)

t = rc.capacity_trend(daily(reversal), TODAY)
check("a recent rise against a long decline is called against it",
      "runs against the 89-day decline" in t.analysis, True)
check("a rise reads as up", " up " in t.analysis, True)

t = rc.capacity_trend(daily(flat), TODAY)
check("an unmoving window is called flat, with no pace claim",
      ("broadly flat" in t.analysis, "pace" in t.analysis), (True, False))

t = rc.capacity_trend(daily([3000 + i for i in range(90)]), TODAY)
check("the high is stated in words", "at its highest of the last 90 readings" in t.analysis, True)

check("one reading is not a trend", rc.capacity_trend(daily([3000.0]), TODAY), None)
check("no readings is not a trend", rc.capacity_trend([], TODAY), None)

t = rc.capacity_trend(daily([3000.0, 3010.0, 3020.0], end="2026-11-17"), TODAY)
check("a window too short for a recent change says so and makes no comparison",
      (t.change_pct, t.change_days, "Across the 2 days held" in t.analysis, "pace" in t.analysis),
      (None, None, True, False))

t = rc.capacity_trend(daily(steady), _date(2026, 11, 25))
check("a stale reading says so up front",
      t.analysis.startswith("The latest reading is from 17 Nov, 8 days before this report"), True)
check("a fresh reading carries no staleness note",
      "days before" in rc.capacity_trend(daily(steady), TODAY).analysis, False)

check("a day change is stated when known",
      "moved +12.3 BTC" in rc.capacity_trend(daily(steady), TODAY, 12.3).analysis, True)
check("a negative day change uses a true minus",
      "moved −4.0 BTC" in rc.capacity_trend(daily(steady), TODAY, -4.0).analysis, True)
check("no day change, no claim about the day",
      "reported day" in rc.capacity_trend(daily(steady), TODAY).analysis, False)
check("the source credits the imported history by name",
      "BitcoinVisuals.com" in rc.capacity_trend(daily(steady), TODAY).source, True)
t = rc.capacity_trend(daily(steady), TODAY)
check("the chart gets a date for every reading, oldest first",
      (len(t.dates), t.dates[0], t.dates[-1], t.dates == sorted(t.dates)),
      (90, "2026-08-20", "2026-11-17", True))
check("the card's one-line note keeps both halves: whose view, and the credit",
      ("LND node" in rc.COVERAGE_NOTE, "BitcoinVisuals.com" in rc.COVERAGE_NOTE), (True, True))
check("the card's note is a tenth of the paragraph it replaced", len(rc.COVERAGE_NOTE) <= 60, True)

docs = {
    "2026-11-16": {"date": "2026-11-16", "total_capacity": 3_000 * 10**8, "source": "lnd"},
    "2026-11-17": {"date": "2026-11-17", "total_capacity": 2_990 * 10**8, "source": "lnd"},
    "2026-11-10": {"date": "2026-11-10", "total_capacity": 3_000 * 10**8, "source": "bitcoinvisuals"},
    "2026-11-11": {"date": "2026-11-11", "total_capacity": 3_050 * 10**8, "source": "lnd"},
    "2026-11-12": {"date": "2026-11-12", "total_capacity": 3_000 * 10**8, "source": "bitcoinvisuals",
                   "quality": "interpolated"},
    "2026-11-13": {"date": "2026-11-13", "total_capacity": 3_000 * 10**8, "source": "bitcoinvisuals"},
}
check("a day change needs a reading at each end of the day, from the same method",
      rc.day_change(docs, "2026-11-16"), -10.0)
check("a day with no reading after it has no change", rc.day_change(docs, "2026-11-17"), None)
check("a change across two methods is not reported", rc.day_change(docs, "2026-11-10"), None)
check("a day the import flagged is not reported", rc.day_change(docs, "2026-11-12"), None)
check("a day with no reading at its start has no change", rc.day_change(docs, "2026-11-14"), None)

check("ordinals: 11th 12th 13th 21st 102nd", [rc._ordinal(n) for n in (11, 12, 13, 21, 102)],
      ["11th", "12th", "13th", "21st", "102nd"])
trend_copy = [rc.capacity_trend(daily(v), TODAY, 5.0).analysis
              for v in (steady, slowing, reversal, speeding, flat)]
every = " ".join(list(rc.slow_analysis([slow("gini", rising, 99), slow("top10", rising, 99)]).values())
                 + list(a.values()) + list(rc.SLOW_SOURCES.values())
                 + trend_copy + [rc.CAPACITY_SOURCE, rc.COVERAGE_NOTE]).lower()
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

print("\n== imported capacity history ==")
from services.capacity_import import (  # noqa: E402
    CARRIED, INTERPOLATED, flag_quality, parse_rows,
)

csv_text = '"DateTime","BTC","USD"\n' + "\n".join(
    f'"{d} 00:00:00",{b},1.0' for d, b in [
        ("2020-01-01", "100.00000001"),
        ("2020-01-02", ""),                 # blank: no reading, omitted
        ("2020-01-03", "101.5"),
        ("2020-01-04", "101.5"),            # repeated: carried forward
        ("2020-01-05", "101.5"),
        ("2020-01-06", "103.0"),
        ("2020-01-07", "104.0"),            # 103 -> 104 -> 105 -> 106: one straight line
        ("2020-01-08", "105.0"),
        ("2020-01-09", "106.0"),
        ("2020-01-10", "107.3"),
        ("2020-01-11", "106.1"),
    ]
)
parsed = parse_rows(csv_text)
check("BTC converts to sats exactly, not via float", parsed[0], ("2020-01-01", 10_000_000_001))
check("a blank cell parses as no reading", parsed[1], ("2020-01-02", None))

flagged = flag_quality(parsed)
check("blank days are omitted", [d for d, _, _ in flagged].count("2020-01-02"), 0)
by_date = {d: q for d, _, q in flagged}
check("a day equal to the one before is carried forward",
      (by_date["2020-01-04"], by_date["2020-01-05"]), (CARRIED, CARRIED))
check("the first of a flat run is a real reading", by_date["2020-01-03"], None)
check("the interior of a straight line is interpolated",
      (by_date["2020-01-07"], by_date["2020-01-08"]), (INTERPOLATED, INTERPOLATED))
check("both ends of a straight line are real readings",
      (by_date["2020-01-06"], by_date["2020-01-09"]), (None, None))
check("ordinary movement is left unflagged",
      (by_date["2020-01-10"], by_date["2020-01-11"]), (None, None))
check("two equal steps are not enough to call a line",
      [q for _, _, q in flag_quality(
          [(d, v * 100_000_000) for d, v in (("a", 100), ("b", 110), ("c", 120), ("d", 135))]
      )],
      [None, None, None, None])

print("\n== mempool mirror fallback ==")
import asyncio  # noqa: E402
import httpx  # noqa: E402

PRIMARY, MIRROR = mempool.MEMPOOL_HOSTS[0], mempool.MEMPOOL_HOSTS[1]


async def fetch_with(handler, path="v1/prices"):
    mempool._host_down_until.clear()
    seen: list[str] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(wrapped)) as client:
        try:
            response = await mempool._get(client, path)
            return response.json(), seen
        except Exception as e:  # noqa: BLE001
            return type(e).__name__, seen


def primary_down(request):
    if request.url.host == "mempool.space":
        raise httpx.ConnectTimeout("down", request=request)
    return httpx.Response(200, json={"from": "mirror"})


got, seen = asyncio.run(fetch_with(primary_down))
check("primary unreachable: the mirror answers", got, {"from": "mirror"})
check("primary is tried first, then the mirror", seen, ["mempool.space", "mempool.emzy.de"])

got, seen = asyncio.run(fetch_with(lambda r: httpx.Response(503) if r.url.host == "mempool.space"
                                   else httpx.Response(200, json={"from": "mirror"})))
check("a 5xx from the primary also falls over", got, {"from": "mirror"})

got, seen = asyncio.run(fetch_with(lambda r: httpx.Response(404)))
check("a 404 is raised, not retried on the mirror", (got, seen), ("HTTPStatusError", ["mempool.space"]))

got, seen = asyncio.run(fetch_with(lambda r: httpx.Response(200, json={"from": r.url.host})))
check("healthy primary: the mirror is never touched", (got, seen), ({"from": "mempool.space"}, ["mempool.space"]))

got, seen = asyncio.run(fetch_with(lambda r: (_ for _ in ()).throw(httpx.ConnectError("down", request=r))))
check("both down: the error surfaces", (got, seen), ("ConnectError", ["mempool.space", "mempool.emzy.de"]))


async def second_call_skips_dead_host():
    mempool._host_down_until.clear()
    seen: list[str] = []

    def handler(request):
        seen.append(request.url.host)
        return primary_down(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await mempool._get(client, "v1/prices")
        seen.clear()
        await mempool._get(client, "v1/prices")
    return seen


check("a host that just failed is not retried first on the next call",
      asyncio.run(second_call_skips_dead_host()), ["mempool.emzy.de"])
mempool._host_down_until.clear()

print("\n== repairing missing channel sizes ==")
from services.channel_flow import SIZE_FIELDS, size_repairs  # noqa: E402

rebuilt_days = {
    "2026-11-10": {"opens": 98, "median_sats": 5_000_000, "largest_sats": 400_000_000,
                   "smallest_sats": 20_000, "block_from": 975_000, "block_height": 975_140},
    "2026-11-11": {"opens": 40, "median_sats": 4_000_000, "largest_sats": 100_000_000,
                   "smallest_sats": 20_000, "block_from": 975_150, "block_height": 975_290},
    "2026-11-12": {"opens": 170, "median_sats": 3_000_000, "largest_sats": 50_000_000,
                   "smallest_sats": 20_000, "block_from": 975_300, "block_height": 975_440},
}
stored_days = [
    {"date": "2026-11-10", "opens": 99, "block_height": 975_140},        # sizes + block_from missing
    {"date": "2026-11-11", "opens": 99},                                  # rebuild far too thin
    {"date": "2026-11-12", "opens": 170, "median_sats": 7_777_777,       # already has a median
     "largest_sats": 1, "smallest_sats": 1, "block_from": 1, "block_height": 1},
    {"date": "2026-11-13", "opens": 150},                                 # no rebuilt day at all
]
fix = size_repairs(stored_days, rebuilt_days)
check("a day missing sizes is filled from the rebuild",
      sorted(fix.get("2026-11-10", {})), ["block_from", "largest_sats", "median_sats", "smallest_sats"])
check("a field the day already has is never replaced",
      "block_height" in fix.get("2026-11-10", {}), False)
check("a rebuild much thinner than what was recorded is skipped", "2026-11-11" in fix, False)
check("a day that already has every field is left alone", "2026-11-12" in fix, False)
check("a day with no rebuilt counterpart is left alone", "2026-11-13" in fix, False)
check("only size fields are ever offered", set().union(*fix.values()) <= set(SIZE_FIELDS), True)

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILURE(S):"))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
