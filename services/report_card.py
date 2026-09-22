"""Daily report card: baselines, percentiles and the generated verdict.

Baselines use median + MAD rather than mean + stddev because channel flow is
spiky — a single mass-close night would drag a mean baseline for weeks.

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
from services.velocity import get_velocity_history

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
BANNED_PHRASES = ("record", "all-time", "all time", "first ever", "unprecedented")


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
    """The archive is short; superlatives would overclaim. Warn rather than fail —
    a word choice should never take the endpoint down."""
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            print(f"report_card: banned phrase {phrase!r} in generated copy")
    return text


def _gini_clause(percentile: int, days: int) -> str:
    tail = (
        "concentration is running high even as the graph grows."
        if percentile > CONCENTRATION_PERCENTILE
        else "concentration is unremarkable for the period."
    )
    return f" Gini sits at the {percentile}th percentile of the last {days} days — {tail}"


def build_verdict(
    opens: int,
    btc_in: float,
    opens_series: list[float],
    btc_in_series: list[float],
    gini_percentile: int,
    gini_days: int,
) -> ReportVerdict:
    """Lead with whichever metric deviates most. If nothing clears the threshold,
    say it was quiet — do not manufacture significance.

    `opens_series` and `btc_in_series` must contain **live-collected days only**.
    Backfilled days are systematically undercounted (only channels still open are
    visible), so mixing them in would pull the median down and make every ordinary
    night read as busy. They are fine for drawing a trend, not for judging one.

    `gini_days` is the separately collected network-metrics history, a genuinely
    different and longer window — the copy must not conflate the two.
    """
    frame = _gini_clause(gini_percentile, gini_days) if gini_days else ""
    live_days = len(opens_series)

    if live_days < MIN_LIVE_DAYS:
        return ReportVerdict(
            headline=_guard(f"{opens:,} channels opened in the last 24 hours."),
            subline=_guard(
                f"Carrying {btc_in:.1f} BTC of new capacity. Baseline still calibrating — "
                f"{live_days} of {MIN_LIVE_DAYS} days collected live, so tonight is "
                f"reported without comparison." + frame
            ),
            lead_metric="opens",
            deviation=0.0,
        )

    candidates = [
        ("opens", deviation(opens, opens_series)),
        ("btc_in", deviation(btc_in, btc_in_series)),
    ]
    lead_metric, lead_deviation = max(candidates, key=lambda pair: abs(pair[1]))
    magnitude = f"{abs(lead_deviation):.1f}"
    norm = f"{live_days}-day norm"

    if abs(lead_deviation) < DEVIATION_THRESHOLD:
        headline = "Quiet night on Lightning."
        subline = (
            f"Nothing moved more than a deviation from normal. {opens:,} channels "
            f"opened, carrying {btc_in:.1f} BTC of new capacity." + frame
        )
    elif lead_metric == "btc_in":
        # Capacity is the outlier, so the copy must talk about capacity — the
        # channel count may well be sitting right on its median.
        if lead_deviation > 0:
            headline = f"{btc_in:.1f} BTC entered Lightning overnight."
            subline = (
                f"{magnitude}σ above the {norm}, carried by a handful of large opens "
                f"rather than broad activity. {opens:,} channels opened." + frame
            )
        else:
            headline = f"New capacity ran thin — {btc_in:.1f} BTC."
            subline = (
                f"{magnitude}σ below the {norm} for capacity, though {opens:,} "
                f"channels still opened. The night's channels were small ones."
                + frame
            )
    else:
        if lead_deviation > 0:
            headline = f"{opens:,} new channels — a busy night."
            subline = (
                f"{magnitude}σ above the {norm}, adding {btc_in:.1f} BTC of capacity."
                + frame
            )
        else:
            headline = "Lighter than usual on Lightning."
            subline = (
                f"Activity ran {magnitude}σ below the {norm}. {opens:,} channels "
                f"opened, carrying {btc_in:.1f} BTC." + frame
            )

    return ReportVerdict(
        headline=_guard(headline),
        subline=_guard(subline),
        lead_metric=lead_metric,
        deviation=round(lead_deviation, 2),
    )


async def _slow_indices(database, window_days: int) -> list[SlowIndex]:
    """Percentile of today's value within the window, for each slow-moving index.

    Gini and top-10 share come straight from the persisted network_metrics
    snapshots; capacity from lightning_stats; velocity is derived (and inherits
    that derivation's constant-volume caveat).
    """
    since = datetime.now(timezone.utc) - timedelta(days=window_days)

    metrics = await database["network_metrics"].find(
        {"recorded_at": {"$gte": since}},
        {"_id": 0, "gini_coefficient": 1, "top10_centralization": 1},
    ).sort("recorded_at", 1).to_list(length=None)

    stats = await database["lightning_stats"].find(
        {"recorded_at": {"$gte": since}},
        {"_id": 0, "total_capacity": 1},
    ).sort("recorded_at", 1).to_list(length=None)

    velocity_entries = await get_velocity_history(window_days) or []

    sources: list[tuple[str, str, list[float]]] = [
        ("gini", "Gini coefficient",
         [float(d["gini_coefficient"]) for d in metrics if d.get("gini_coefficient")]),
        ("top10", "Top-10 share",
         [float(d["top10_centralization"]) for d in metrics if d.get("top10_centralization")]),
        ("velocity", "Velocity",
         [e.velocity for e in velocity_entries]),
        ("capacity", "Capacity",
         [float(d["total_capacity"]) for d in stats if d.get("total_capacity")]),
    ]

    indices: list[SlowIndex] = []
    for key, label, series in sources:
        if not series:
            continue
        latest = series[-1]
        indices.append(SlowIndex(
            key=key,
            label=label,
            value=latest,
            percentile=percentile_of(latest, series),
            series=series,
        ))
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

    slow = await _slow_indices(database, BASELINE_WINDOW_DAYS)
    gini = next((s for s in slow if s.key == "gini"), None)

    hourly = today.get("hourly")
    opens_median = _median(opens_series)
    btc_in_median = _median(btc_in_series)

    return DailyReport(
        date=today["date"],
        block_height=today.get("block_height", 0),
        flow=ReportFlow(
            opens=today["opens"],
            btc_in=today["btc_in"],
            hourly=[HourlyFlow(**h) for h in hourly] if hourly else None,
        ),
        baseline=ReportBaseline(
            window_days=len(history),   # everything held, i.e. what the trend spans
            live_days=len(live),        # of those, what the baseline is computed from
            opens_median=opens_median,
            opens_mad=_mad(opens_series, opens_median),
            btc_in_median=btc_in_median,
            btc_in_mad=_mad(btc_in_series, btc_in_median),
        ),
        slow=slow,
        verdict=build_verdict(
            opens=today["opens"],
            btc_in=today["btc_in"],
            opens_series=opens_series,
            btc_in_series=btc_in_series,
            gini_percentile=gini.percentile if gini else 0,
            gini_days=len(gini.series) if gini else 0,
        ),
        closes_available=False,
        coverage_note=(
            "Opens seen by our own LND node, which gossips a narrower view than the "
            "whole network. Channels closed before a snapshot are not visible, so "
            "older days undercount."
        ),
    )
