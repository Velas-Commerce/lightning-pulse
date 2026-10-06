"""Daily report card: baselines, percentiles and the generated verdict.

Baselines use median + MAD rather than mean + stddev because channel flow is
spiky — a single mass-close day would drag a mean baseline for weeks.

The window length is derived from the data actually held, never hardcoded, so
the generated copy grows with the archive instead of claiming a fixed 90 days.
"""

from datetime import datetime, timedelta, timezone

import db
from models import (
    DailyReport,
    HourlyFlow,
    ReportBaseline,
    ReportFlow,
    ReportVerdict,
    SlowIndex,
)
from services.velocity import (
    SATS_PER_BTC,
    capacity_by_observed_day,
    get_velocity_history,
)

BASELINE_WINDOW_DAYS = 90

# Below this many live-collected days the baseline is not trustworthy, because
# backfilled days undercount (only still-open channels are visible). Until then
# the verdict reports facts and makes no claim about significance.
MIN_LIVE_DAYS = 14

# A metric must deviate by at least this much to lead the verdict.
DEVIATION_THRESHOLD = 1.0

# Above this percentile, Gini phrasing says concentration is "running high".
CONCENTRATION_PERCENTILE = 70

# Named entities moving less than this are dropped from Movers (milestone 4).
MOVERS_MIN_BTC = 5.0

# Scales MAD to be comparable with a standard deviation for a normal sample.
MAD_TO_SIGMA = 0.6745

# The archive is ~3 months. Never imply it is longer than it is.
# "night" also covers "overnight" and "tonight": the window is a 24h UTC day and
# Lightning is global, so there is no shared night to refer to. No legitimate word
# in this copy contains the substring — "lightning" does not.
BANNED_PHRASES = (
    "record", "all-time", "all time", "first ever", "unprecedented", "night",
)

_WEEKDAYS = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
)


def weekday_of(date: str) -> str:
    """UTC weekday for a YYYY-MM-DD date, spelled out.

    Read from a fixed tuple rather than strftime("%A") so generated copy cannot
    change with the host's locale.
    """
    return _WEEKDAYS[datetime.fromisoformat(date).weekday()]


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def _mad(values: list[float], median: float) -> float:
    if not values:
        return 0.0
    return _median([abs(v - median) for v in values])


def deviation(value: float, series: list[float]) -> float:
    """Robust z-score: how far `value` sits from the median, in MAD units."""
    if not series:
        return 0.0
    median = _median(series)
    mad = _mad(series, median)
    if mad == 0:
        return 0.0
    return MAD_TO_SIGMA * (value - median) / mad


def percentile_of(value: float, series: list[float]) -> int:
    """Where `value` sits within `series`, 0-100."""
    if not series:
        return 0
    below = sum(1 for v in series if v < value)
    return round(below / len(series) * 100)


def window_phrase(days: int) -> str:
    return f"in {days} days"


def _guard(text: str) -> str:
    """Enforce the copy rules: no superlatives the ~3-month archive cannot support,
    and no night/overnight framing for a 24h UTC window on a global network.
    Warns rather than fails — a word choice should never take the endpoint down."""
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            print(f"report_card: banned phrase {phrase!r} in generated copy")
    return text


def _gini_clause(percentile: int, days: int, series: list[float] | None = None) -> str:
    """Where Gini sits, and — when the series is known — how far it actually moved.

    Two things this used to get wrong. At the edges a percentile reads as a bug (the
    maximum scores 99, never 100), so the extremes are stated in words, matching the
    panel. And a rank alone says nothing about size: Gini's whole range is a couple
    of percent of its value, so "running high" needs that said beside it. There is
    deliberately no claim about the graph growing — nothing here measures growth.
    """
    last = series[-1] if series else None
    at_max = bool(series) and last >= max(series)
    at_min = bool(series) and last <= min(series)

    if at_max:
        head = f"at its highest in the last {days} days"
    elif at_min:
        head = f"at its lowest in the last {days} days"
    else:
        head = f"at the {percentile}th percentile of the last {days} days"

    if at_min:
        tail = "concentration is at its lowest for the period"
    elif percentile > CONCENTRATION_PERCENTILE:
        tail = "concentration is running high"
    else:
        tail = "concentration is unremarkable for the period"

    if series and last:
        span_pct = (max(series) - min(series)) / abs(last) * 100
        tail += (
            f", though the whole window moved only {span_pct:.1f}%"
            if span_pct < 5
            else f", across a window that spans {span_pct:.1f}%"
        )
    return f" Gini sits {head} — {tail}."


def _block_span(block_from: int, block_height: int) -> str:
    """Opening clause naming the day's block range.

    The range is what was actually measured, and unlike a wall-clock time it is
    something a reader can go and verify. Empty when the range is unknown, which
    is only true for days recorded before it was captured.
    """
    if block_from <= 0 or block_height <= 0 or block_from > block_height:
        return ""
    return f"Across blocks {block_from:,}–{block_height:,}, "


def build_verdict(
    opens: int,
    btc_in: float,
    opens_series: list[float],
    btc_in_series: list[float],
    gini_percentile: int,
    gini_days: int,
    weekday: str,
    block_from: int,
    block_height: int,
    closes: int = 0,
    btc_out: float = 0.0,
    closes_series: list[float] | None = None,
    btc_out_series: list[float] | None = None,
    closes_known: bool = False,
    gini_series: list[float] | None = None,
) -> ReportVerdict:
    """Lead with whichever metric deviates most. If nothing clears the threshold,
    say it was quiet — do not manufacture significance.

    Time is referenced by UTC weekday in the headline and block range in the
    subline. Never "night" or "overnight": the window is a 24h UTC day and the
    network is global, so there is no shared night — and the local date can differ
    from the UTC date by hours, which is exactly how such copy goes wrong.

    All four series must contain **live-collected days only**. Backfilled days are
    systematically undercounted (only channels still open are visible), so mixing
    them in would pull the median down and make every ordinary day read as busy.
    They are fine for drawing a trend, not for judging one.

    Closes carry a second restriction: they cannot be backfilled at all, so their
    series starts empty and only becomes comparable once `MIN_LIVE_DAYS` of it
    exist. Until then closes are reported as a figure but never lead, and never
    imply a comparison. `closes_known` says whether today's closes are measured at
    all — a day recorded before detection existed has none.

    `gini_days` is the separately collected network-metrics history, a genuinely
    different and longer window — the copy must not conflate the two.
    """
    closes_series = closes_series or []
    btc_out_series = btc_out_series or []

    frame = _gini_clause(gini_percentile, gini_days, gini_series) if gini_days else ""
    span = _block_span(block_from, block_height)
    live_days = len(opens_series)
    highlight: str | None = None

    net_channels = opens - closes
    net_btc = btc_in - btc_out
    net_clause = (
        f" The day nets {net_channels:+,} channels and {net_btc:+.1f} BTC."
        if closes_known
        else ""
    )

    if live_days < MIN_LIVE_DAYS:
        highlight = f"{opens:,} new channels"
        return ReportVerdict(
            headline=_guard(f"{highlight} on {weekday}."),
            subline=_guard(
                span + f"{opens:,} channels opened carrying {btc_in:.1f} BTC of new "
                f"capacity.{net_clause} Baseline still calibrating — {live_days} of "
                f"{MIN_LIVE_DAYS} days collected live, so the day is reported "
                f"without comparison." + frame
            ),
            lead_metric="opens",
            deviation=0.0,
            highlight=highlight,
        )

    candidates = [
        ("opens", deviation(opens, opens_series)),
        ("btc_in", deviation(btc_in, btc_in_series)),
    ]
    # Closes only compete once their own history is long enough to judge against.
    if len(closes_series) >= MIN_LIVE_DAYS:
        candidates += [
            ("closes", deviation(closes, closes_series)),
            ("btc_out", deviation(btc_out, btc_out_series)),
        ]

    lead_metric, lead_deviation = max(candidates, key=lambda pair: abs(pair[1]))
    magnitude = f"{abs(lead_deviation):.1f}"
    norm = f"{live_days}-day norm"
    high = lead_deviation > 0

    if abs(lead_deviation) < DEVIATION_THRESHOLD:
        headline = f"{weekday} was quiet on Lightning."
        subline = (
            span + f"nothing moved more than a deviation from normal. {opens:,} "
            f"channels opened, carrying {btc_in:.1f} BTC of new capacity."
            + net_clause + frame
        )

    elif lead_metric == "opens":
        if high:
            highlight = f"{opens:,} new channels"
            headline = f"{highlight} — a busy {weekday}."
            subline = (
                span + f"that is {magnitude}σ above the {norm}, adding "
                f"{btc_in:.1f} BTC of capacity." + net_clause + frame
            )
        else:
            headline = f"{weekday} ran light on Lightning."
            subline = (
                span + f"activity sat {magnitude}σ below the {norm}. {opens:,} "
                f"channels opened, carrying {btc_in:.1f} BTC." + net_clause + frame
            )

    elif lead_metric == "btc_in":
        # Capacity is the outlier, so the copy must talk about capacity — the
        # channel count may well be sitting right on its median.
        highlight = f"{btc_in:.1f} BTC"
        if high:
            headline = f"{highlight} entered Lightning on {weekday}."
            subline = (
                span + f"that is {magnitude}σ above the {norm}, carried by a "
                f"handful of large opens rather than broad activity. {opens:,} "
                f"channels opened." + net_clause + frame
            )
        else:
            headline = f"New capacity ran thin on {weekday} — {highlight}."
            subline = (
                span + f"that is {magnitude}σ below the {norm} for capacity, "
                f"though {opens:,} channels still opened. The day's channels were "
                f"small ones." + net_clause + frame
            )

    elif lead_metric == "closes":
        highlight = f"{closes:,} channels"
        if high:
            # Only claim the heaviest day when it actually is one.
            heaviest = (
                f" — the heaviest closing day {window_phrase(len(closes_series))}"
                if closes >= max(closes_series)
                else ""
            )
            headline = f"{highlight} closed on {weekday}."
            subline = (
                span + f"that is {magnitude}σ above the {norm}, taking "
                f"{btc_out:.1f} BTC with them{heaviest}. Opens held nearer average "
                f"at {opens:,}." + net_clause + frame
            )
        else:
            headline = f"Closures eased on {weekday} — {highlight}."
            subline = (
                span + f"that is {magnitude}σ below the {norm} for closures, "
                f"against {opens:,} opens." + net_clause + frame
            )

    else:  # btc_out
        highlight = f"{btc_out:.1f} BTC"
        if high:
            headline = f"{highlight} left Lightning on {weekday}."
            subline = (
                span + f"that is {magnitude}σ above the {norm}, as {closes:,} "
                f"channels closed." + net_clause + frame
            )
        else:
            headline = f"Little capacity left Lightning on {weekday}."
            subline = (
                span + f"only {btc_out:.1f} BTC withdrawn, {magnitude}σ below "
                f"the {norm}, across {closes:,} closures." + net_clause + frame
            )
            highlight = None

    return ReportVerdict(
        headline=_guard(headline),
        subline=_guard(subline),
        lead_metric=lead_metric,
        deviation=round(lead_deviation, 2),
        highlight=highlight,
    )


_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# Where each index comes from. Shown in place of the card-wide coverage note, which
# describes opens and closes and says nothing true about these four.
SLOW_SOURCES = {
    "gini": "Channel sizes from our own LND node's graph, snapshotted daily at 00:15 UTC.",
    "top10": "Node capacity from our own LND node's graph, snapshotted daily at 00:15 UTC.",
    "capacity": (
        "Network capacity from mempool.space. Readings arrive irregularly and can run "
        "weeks behind the day being reported."
    ),
    "velocity": (
        "A hand-curated monthly volume estimate, held constant, over mempool.space "
        "capacity at hourly BTC prices."
    ),
}


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{('th', 'st', 'nd', 'rd')[n % 10] if n % 10 < 4 else 'th'}"


def _day_label(iso: str) -> str:
    # From the ISO parts, never through a locale-aware formatter (see weekday_of).
    _, m, d = iso.split("-")
    return f"{int(d)} {_MONTHS[int(m) - 1]}"


def _edge(series: list[float]) -> str | None:
    """'max' or 'min' when the latest reading is the extreme of its window."""
    if len(series) < 2:
        return None
    if series[-1] >= max(series):
        return "max"
    if series[-1] <= min(series):
        return "min"
    return None


def _change_pct(series: list[float]) -> float | None:
    if len(series) < 2 or not series[0]:
        return None
    return (series[-1] - series[0]) / abs(series[0]) * 100


def _size_of_move(series: list[float]) -> str:
    """How far the window moved, so a rank is never read without its scale."""
    if not series or not series[-1]:
        return ""
    span = (max(series) - min(series)) / abs(series[-1]) * 100
    return (
        f"the whole window moved only {span:.1f}%"
        if span < 5
        else f"the window spans {span:.1f}%"
    )


def _staleness(s: SlowIndex) -> str:
    if s.stale_days <= 2:
        return ""
    return (
        f"The latest reading is from {_day_label(s.as_of)}, {s.stale_days} days "
        f"before this report, so read it as a trend rather than a current figure. "
    )


def slow_analysis(indices: list[SlowIndex]) -> dict[str, str]:
    """A sentence or two per slow index, keyed by index key.

    Rank statements are made only about the window actually held and, as in the
    verdict, the extremes are stated in words because a percentile can never reach
    100. Gini and Top-10 are compared with each other, since agreement between two
    independent measures says more than either does alone. Where an index has no
    real signal the copy says so rather than inventing a story.
    """
    by_key = {s.key: s for s in indices}
    out: dict[str, str] = {}

    gini, top10 = by_key.get("gini"), by_key.get("top10")
    g_edge = _edge(gini.series) if gini else None
    t_edge = _edge(top10.series) if top10 else None

    if gini:
        n = len(gini.series)
        if g_edge == "max":
            lead = f"Channel sizes are more unequal than at any point in the last {n} days"
        elif g_edge == "min":
            lead = f"Channel sizes are more even than at any point in the last {n} days"
        else:
            lead = (
                f"Channel-size inequality sits at the {_ordinal(gini.percentile)} "
                f"percentile of the last {n} days"
            )
        text = f"{lead}; {_size_of_move(gini.series)}."
        if top10 and g_edge and g_edge == t_edge:
            text += " Top-10 share is at the same extreme, so both measures agree."
        elif top10 and g_edge and t_edge is None:
            text += (
                " Top-10 share is not at an extreme, so the change is in how channel "
                "sizes are spread, not at the top of the node ranking."
            )
        out["gini"] = text

    if top10:
        n = len(top10.series)
        pts = (top10.series[-1] - top10.series[0]) * 100 if n > 1 else 0.0
        move = f"{'up' if pts >= 0 else 'down'} {abs(pts):.1f} points over the window"
        text = (
            f"The ten largest nodes hold {top10.value * 100:.1f}% of node capacity, "
            f"{move}"
        )
        if t_edge == "max":
            text += f" and the most in the last {n} days."
        elif t_edge == "min":
            text += f" and the least in the last {n} days."
        else:
            text += f"; {_ordinal(top10.percentile)} percentile of the last {n} days."
        if gini and t_edge and t_edge == g_edge:
            text += " Gini is at the same extreme, so both measures agree."
        out["top10"] = text

    for key, subject in (("capacity", "Network capacity"), ("velocity", "Velocity")):
        s = by_key.get(key)
        if not s:
            continue
        n = len(s.series)
        change = _change_pct(s.series)
        edge = _edge(s.series)
        if edge == "max":
            rank = f"at its highest of the last {n} readings"
        elif edge == "min":
            rank = f"at its lowest of the last {n} readings"
        else:
            rank = f"at the {_ordinal(s.percentile)} percentile of {n} readings"
        moved = (
            f", {'up' if change >= 0 else 'down'} {abs(change):.1f}% across them"
            if change is not None
            else ""
        )
        text = _staleness(s) + f"{subject} sits {rank}{moved}."
        if key == "velocity":
            # The estimate is constant, so this is capacity and price restated.
            text += (
                " The volume estimate is held constant, so it moves only with capacity "
                "and BTC price and says nothing new about payment activity."
            )
        out[key] = text

    return out


async def _slow_indices(database, window_days: int) -> list[SlowIndex]:
    """Percentile of the latest value within the window, for each slow-moving index.

    Gini and top-10 share come from our own node's persisted network_metrics and are
    current. Capacity and velocity come from mempool.space, which serves stale rows
    from several cache nodes — both are therefore keyed on the upstream `added` date
    and carry how far behind they are, rather than posing as today's numbers.
    """
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    today = datetime.now(timezone.utc).date()

    metrics = await database["network_metrics"].find(
        {"recorded_at": {"$gte": since}},
        {"_id": 0, "recorded_at": 1, "gini_coefficient": 1, "top10_centralization": 1},
    ).sort("recorded_at", 1).to_list(length=None)

    # One per UTC day, last wins — restarts persisted several before the upsert fix.
    metrics_by_day = {str(d["recorded_at"])[:10]: d for d in metrics}
    metric_days = [metrics_by_day[k] for k in sorted(metrics_by_day)]
    metrics_as_of = max(metrics_by_day, default=today.isoformat())

    stats = await database["lightning_stats"].find(
        {}, {"_id": 0, "added": 1, "total_capacity": 1},
    ).to_list(length=None)
    cutoff = since.strftime("%Y-%m-%d")
    capacity_obs = [(a, c) for a, c in capacity_by_observed_day(stats) if a >= cutoff]
    capacity_as_of = capacity_obs[-1][0] if capacity_obs else today.isoformat()

    velocity_entries = await get_velocity_history(window_days) or []
    velocity_as_of = (
        velocity_entries[-1].recorded_at[:10] if velocity_entries else today.isoformat()
    )

    sources: list[tuple[str, str, list[float], str]] = [
        ("gini", "Gini coefficient",
         [float(d["gini_coefficient"]) for d in metric_days if d.get("gini_coefficient")],
         metrics_as_of),
        ("top10", "Top-10 share",
         [float(d["top10_centralization"]) for d in metric_days if d.get("top10_centralization")],
         metrics_as_of),
        ("velocity", "Velocity",
         [e.velocity for e in velocity_entries], velocity_as_of),
        ("capacity", "Capacity",
         [float(c) for _, c in capacity_obs], capacity_as_of),
    ]

    indices: list[SlowIndex] = []
    for key, label, series, as_of in sources:
        if not series:
            continue
        latest = series[-1]
        stale_days = max(0, (today - datetime.fromisoformat(as_of).date()).days)
        indices.append(SlowIndex(
            key=key,
            label=label,
            value=latest,
            percentile=percentile_of(latest, series),
            series=series,
            as_of=as_of,
            stale_days=stale_days,
            source=SLOW_SOURCES.get(key, ""),
        ))
    for key, text in slow_analysis(indices).items():
        next(s for s in indices if s.key == key).analysis = _guard(text)
    return indices


async def get_daily_report() -> DailyReport | None:
    """Assemble today's report card. Returns None when MongoDB is not configured."""
    database = db.get_db()
    if database is None:
        return None

    days = await database["daily_flow"].find(
        {}, {"_id": 0}
    ).sort("date", 1).to_list(length=None)
    if not days:
        return None

    today = days[-1]
    history = days[:-1]

    # Baselines come from live days only — backfilled days undercount by a growing
    # margin and would bias every comparison upward. The full history still feeds
    # the trend the card draws.
    live = [d for d in history if not d.get("is_backfilled")]
    opens_series = [float(d["opens"]) for d in live]
    btc_in_series = [float(d["btc_in"]) for d in live]

    # Closes exist only from the day detection started — there is no channel-set
    # history to reconstruct them from, so this series is shorter than the others
    # and stays empty until then.
    closed_live = [d for d in live if d.get("closes") is not None]
    closes_series = [float(d["closes"]) for d in closed_live]
    btc_out_series = [float(d.get("btc_out") or 0.0) for d in closed_live]

    # Sizes began being stored after live collection did, so some live days lack them.
    # Medians, not means: the size distribution is skewed roughly 4:1.
    sized_live = [d for d in live if d.get("median_sats")]
    median_open_typical = _median([d["median_sats"] / SATS_PER_BTC for d in sized_live])
    largest_open_typical = _median(
        [d["largest_sats"] / SATS_PER_BTC for d in sized_live if d.get("largest_sats")]
    )

    slow = await _slow_indices(database, BASELINE_WINDOW_DAYS)
    gini = next((s for s in slow if s.key == "gini"), None)

    hourly = today.get("hourly")
    opens_median = _median(opens_series)
    btc_in_median = _median(btc_in_series)
    closes_median = _median(closes_series)
    btc_out_median = _median(btc_out_series)

    closes_known = today.get("closes") is not None
    closes = int(today.get("closes") or 0)
    btc_out = float(today.get("btc_out") or 0.0)

    block_height = today.get("block_height", 0)
    # Days recorded before the range was captured have no block_from; the copy and
    # the header both degrade to omitting the range rather than inventing one.
    block_from = today.get("block_from", 0)

    return DailyReport(
        date=today["date"],
        weekday=weekday_of(today["date"]),
        block_from=block_from,
        block_height=block_height,
        flow=ReportFlow(
            opens=today["opens"],
            btc_in=today["btc_in"],
            closes=closes,
            btc_out=btc_out,
            net_channels=today["opens"] - closes,
            net_btc=round(today["btc_in"] - btc_out, 4),
            median_open=round((today.get("median_sats") or 0) / SATS_PER_BTC, 8),
            largest_open=round((today.get("largest_sats") or 0) / SATS_PER_BTC, 8),
            hourly=[
                HourlyFlow(hour=h["hour"], opens=h["opens"], closes=h.get("closes") or [])
                for h in hourly
            ] if hourly else None,
        ),
        baseline=ReportBaseline(
            window_days=len(history),   # everything held, i.e. what the trend spans
            live_days=len(live),        # of those, what the baseline is computed from
            opens_median=opens_median,
            opens_mad=_mad(opens_series, opens_median),
            btc_in_median=btc_in_median,
            btc_in_mad=_mad(btc_in_series, btc_in_median),
            closes_days=len(closes_series),
            closes_median=closes_median,
            closes_mad=_mad(closes_series, closes_median),
            btc_out_median=btc_out_median,
            btc_out_mad=_mad(btc_out_series, btc_out_median),
            sizes_days=len(sized_live),
            median_open_typical=round(median_open_typical, 8),
            largest_open_typical=round(largest_open_typical, 8),
        ),
        slow=slow,
        verdict=build_verdict(
            opens=today["opens"],
            btc_in=today["btc_in"],
            opens_series=opens_series,
            btc_in_series=btc_in_series,
            gini_percentile=gini.percentile if gini else 0,
            gini_days=len(gini.series) if gini else 0,
            weekday=weekday_of(today["date"]),
            block_from=block_from,
            block_height=block_height,
            closes=closes,
            btc_out=btc_out,
            closes_series=closes_series,
            btc_out_series=btc_out_series,
            closes_known=closes_known,
            gini_series=gini.series if gini else None,
        ),
        closes_available=closes_known,
        coverage_note=(
            "Opens and closes seen by our own LND node, which gossips a narrower view "
            "than the whole network. Opens are decoded from each channel's short "
            "channel ID; closes are confirmed by the funding output being spent "
            "on-chain, so a channel that merely left our view is not counted. "
            "Channels closed before a snapshot are invisible, so older days "
            "undercount opens."
        ),
    )
