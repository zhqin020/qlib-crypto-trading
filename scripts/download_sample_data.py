#!/usr/bin/env python3
"""Download sample crypto data for testing."""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
from data_pipeline.market_data import download_crypto_universe


def _default_start_end(days: int = 365) -> tuple[str, str]:
    """Return default start/end dates covering the recent period."""

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def load_config():
    """Load centralized trading parameters"""
    config_path = Path(__file__).parent.parent / "config" / "trading_params.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


async def main(args: argparse.Namespace):
    """Download sample data for configured cryptocurrencies."""

    symbols = [symbol.strip() for symbol in args.symbols.split(",") if symbol.strip()]

    # Dynamic end_date handling
    end_date = args.end_date
    if not end_date or end_date.lower() == "now":
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
    print("Downloading sample crypto data...")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Date range: {args.start_date} to {end_date}")
    print(f"Interval: {args.interval}\n")

    await download_crypto_universe(
        symbols=symbols,
        start_date=args.start_date,
        end_date=end_date,
        interval=args.interval,
        provider=args.provider,
        market_type=args.market_type,
        output_dir=args.output_dir,
    )

    print("\nData download complete!")
    print("Next steps:")
    print("  1. Convert data to Qlib format: python scripts/convert_to_qlib.py")
    print("  2. Train a model: python scripts/train_sample_model.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download historical OCHLV crypto data from exchanges (via CCXT)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    default_start, default_end = _default_start_end(days=730)

    config = load_config()
    data_config = config.get("data", {})

    default_symbols = data_config.get("symbols")
    if default_symbols and isinstance(default_symbols, list):
        default_symbols = ",".join(default_symbols)
    else:
        default_symbols = "BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,ADA/USDT,DOGE/USDT,AVAX/USDT,DOT/USDT,MATIC/USDT"

    parser.add_argument(
        "--symbols",
        default=default_symbols,
        help="Comma-separated list of symbols (e.g., 'BTC/USDT,ETH/USDT')",
    )
    
    default_start_cfg = data_config.get("start_time")
    default_end_cfg = data_config.get("end_time")
    
    parser.add_argument("--start", dest="start_date", default=default_start_cfg or default_start, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_date", default=default_end_cfg or default_end, help="End date (YYYY-MM-DD or 'now')")
    parser.add_argument("--interval", default=data_config.get("interval", "1d"), choices=["1d", "1h", "15m", "5m", "1m"], help="Candle time interval")
    parser.add_argument("--provider", default=data_config.get("exchange", "binance"), help="Exchange/provider ID (must be supported by CCXT)")
    parser.add_argument("--market-type", dest="market_type", default=data_config.get("market_type", "spot"), choices=["spot", "future", "swap"], help="Market category")
    parser.add_argument("--output-dir", default="data/raw", help="Local directory to store downloaded CSV files")

    parsed_args = parser.parse_args()

    asyncio.run(main(parsed_args))
