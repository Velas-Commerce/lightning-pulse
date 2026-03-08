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


class OldestNodes(BaseModel):
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


class BtcPrice(BaseModel):
    time: int
    USD: int
    EUR: int
    GBP: int
    CAD: int
    CHF: int
    AUD: int
    JPY: int