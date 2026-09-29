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