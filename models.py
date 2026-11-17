from datetime import datetime

from pydantic import BaseModel
from typing import Dict


class LightningStats(BaseModel):
    id: int
    added: str
    channel_count: int
    node_count: int
    total_capacity: int
    tor_nodes: int
    clearnet_nodes: int
    unannounced_nodes: int
    avg_capacity: int
    avg_fee_rate: int
    avg_base_fee_mtokens: int
    med_capacity: int
    med_fee_rate: int
    med_base_fee_mtokens: int
    clearnet_tor_nodes: int


class CapacityReading(BaseModel):
    """One daily reading of network capacity, dated by the start of the UTC day.

    Taken from our own LND node's graph (`source="lnd"`) or, for history before the
    node started recording, imported from BitcoinVisuals.com (`source="bitcoinvisuals"`).
    Imported days carry capacity only, so the other measures are None there.
    """
    date: str
    total_capacity: int
    recorded_at: datetime
    source: str = "lnd"
    active_capacity: int | None = None
    channel_count: int | None = None
    node_count: int | None = None
    block_height: int | None = None
    # How far to trust an imported day: "carried_forward" (the source repeated its
    # last value) or "interpolated" (a straight line between two real readings).
    # None is a plain observation, which is every reading our own node takes.
    quality: str | None = None


class LightningStatsResponse(BaseModel):
    latest: LightningStats


class NodesPerCountry(BaseModel):
    name: Dict[str, str]
    iso: str
    count: int
    share: float
    capacity: str | None


class LargestNode(BaseModel):
    publicKey: str
    alias: str
    channels: int
    capacity: int
    firstSeen: int
    updatedAt: int
    city: Dict[str, str] | None
    country: Dict[str, str] | None


class MonthlyVolumeEntry(BaseModel):
    date: str
    volume_usd: int
    transactions: int


class LightningGrowthStats(BaseModel):
    sources: list[str]
    avg_transaction_usd: int
    num_lightning_users: int
    monthly_volume: list[MonthlyVolumeEntry]


class NetworkMetrics(BaseModel):
    pulse_score: int
    gini_coefficient: float
    top10_centralization: float
    top100_centralization: float
    median_fee_rate: int
    median_node_degree: int
    last_computed: str


class GraphInfo(BaseModel):
    graph_diameter: int
    avg_out_degree: float
    max_out_degree: int
    num_nodes: int
    num_channels: int
    total_network_capacity: str
    avg_channel_size: float
    min_channel_size: str
    max_channel_size: str
    median_channel_size_sat: str
    num_zombie_chans: str


class LiquidityVelocity(BaseModel):
    velocity: float
    monthly_volume_usd: int
    volume_date: str
    capacity_sats: int
    capacity_usd: float
    btc_price_usd: int


class VelocityHistoryEntry(BaseModel):
    recorded_at: str
    velocity: float
    capacity_sats: int
    btc_price_usd: float


class HistoricalPricePoint(BaseModel):
    time: int
    USD: float


class HistoricalPriceResponse(BaseModel):
    prices: list[HistoricalPricePoint]


class BtcPrice(BaseModel):
    time: int
    USD: int
    EUR: int
    GBP: int
    CAD: int
    CHF: int
    AUD: int
    JPY: int


class HourlyFlow(BaseModel):
    hour: int
    opens: list[float]   # one entry per channel, capacity in BTC
    closes: list[float]


class ReportFlow(BaseModel):
    opens: int
    btc_in: float
    closes: int          # 0 until close detection has a set to diff against
    btc_out: float
    net_channels: int
    net_btc: float
    # Channel sizes in BTC. Median rather than mean: the distribution is skewed
    # about 4:1, so a mean badly misrepresents a typical channel. Stored per day at
    # collection time, so they hold even for days whose hourly detail is absent.
    median_open: float
    largest_open: float
    hourly: list[HourlyFlow] | None  # None when block times were interpolated


class ReportBaseline(BaseModel):
    window_days: int      # days of history actually held, not a fixed 90
    live_days: int        # of those, how many were collected live rather than backfilled
    opens_median: float
    opens_mad: float
    btc_in_median: float
    btc_in_mad: float
    # Zero-width until enough days carry close data; closes cannot be backfilled.
    closes_days: int
    closes_median: float
    closes_mad: float
    btc_out_median: float
    btc_out_mad: float
    # Per-day channel sizes are stored only from the day they began being recorded, so
    # this count is usually shorter than live_days. Typical values are in BTC and are
    # medians of the live days' own medians / largest, zero while sizes_days is zero.
    sizes_days: int
    median_open_typical: float
    largest_open_typical: float


class SlowIndex(BaseModel):
    key: str
    label: str
    value: float
    percentile: int       # position within the window, never a daily delta
    series: list[float]
    # Date the value actually describes. Mempool-derived indices run weeks behind
    # our own, so the card labels them rather than implying they are current.
    as_of: str
    stale_days: int
    # What the reading means in words, and where it comes from. Both are generated
    # server-side, beside the verdict copy, so they share its tests and language guard.
    analysis: str = ""
    source: str = ""


class CapacityTrend(BaseModel):
    """Network capacity against its own trend, for the front page of the report card.

    This is what the separate Capacity slide used to show — the level, where it sits
    in the window, the line to draw — plus how far it moved recently and how that
    compares with the longer run, which is the part that was buried.
    """
    value: float                    # BTC, the latest reading
    as_of: str                      # date of that reading
    stale_days: int                 # days between that reading and today
    change_pct: float | None        # over `change_days`; None when the series is too short
    change_btc: float | None
    change_days: int | None
    long_change_pct: float | None   # first to last reading held
    long_days: int
    percentile: int                 # position of the latest reading within the window
    series: list[float]             # BTC, one per reading, oldest first
    # BTC the reading moved across the reported UTC day. None unless two consecutive
    # daily readings exist and came from the same method, since a change measured
    # across two methods is the method, not the network.
    day_change_btc: float | None
    analysis: str = ""
    source: str = ""


class ReportVerdict(BaseModel):
    headline: str
    subline: str
    lead_metric: str
    deviation: float
    # Substring of the headline to emphasise. Sent as plain text rather than
    # markup so no HTML crosses the API boundary.
    highlight: str | None


class DailyReport(BaseModel):
    date: str
    weekday: str        # UTC weekday, not the viewer's — the copy is generated here
    block_from: int     # first block of the day; the range is the real window
    block_height: int
    flow: ReportFlow
    baseline: ReportBaseline
    slow: list[SlowIndex]
    verdict: ReportVerdict
    closes_available: bool  # False until on-chain close detection lands
    coverage_note: str
    capacity: CapacityTrend | None = None