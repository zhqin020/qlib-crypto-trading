#!/usr/bin/env python3
"""
Download sample crypto data for testing
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_pipeline.market_data import download_crypto_universe


async def main():
    """Download sample data for top cryptocurrencies"""

    # Top 10 crypto by market cap
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "SOL/USDT",
        "XRP/USDT",
        "ADA/USDT",
        "DOGE/USDT",
        "AVAX/USDT",
        "DOT/USDT",
        "MATIC/USDT",
    ]

    print("Downloading sample crypto data...")
    print(f"Symbols: {', '.join(symbols)}")
    print("Date range: 2023-01-01 to 2024-12-31")
    print("Interval: 1 day")
    print()

    await download_crypto_universe(
        symbols=symbols,
        start_date="2023-01-01",
        end_date="2024-12-31",
        interval="1d",
        provider="binance",
        output_dir="data/raw"
    )

    print("\nData download complete!")
    print("Next steps:")
    print("  1. Convert data to Qlib format: python scripts/convert_to_qlib.py")
    print("  2. Train a model: python scripts/train_sample_model.py")


if __name__ == "__main__":
    asyncio.run(main())
