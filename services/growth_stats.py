from models import LightningGrowthStats, MonthlyVolumeEntry

# Source: https://river.com/content/bitcoin-adoption-2026

def get_lightning_growth_stats() -> LightningGrowthStats:
    return LightningGrowthStats(
        sources=["https://river.com/content/bitcoin-adoption-2026", "https://breez.technology/report/"],
        avg_transaction_usd=223,
        num_lightning_users=650_000_000,
        monthly_volume=[
            MonthlyVolumeEntry(date="2021-08", volume_usd=12_100_000, transactions=503_000),
            MonthlyVolumeEntry(date="2023-08", volume_usd=78_200_000, transactions=6_600_000),
            MonthlyVolumeEntry(date="2024-11", volume_usd=286_500_000, transactions=2_420_000),
            MonthlyVolumeEntry(date="2025-11", volume_usd=1_170_000_000, transactions=5_220_000),
        ]   
    )