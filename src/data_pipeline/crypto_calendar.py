"""Crypto Trading Calendar - 24/7 trading support."""

import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class CryptoCalendar:
    """24/7 trading calendar for cryptocurrency markets"""

    def __init__(self, freq: str = "1d"):
        """
        Initialize crypto calendar

        Args:
            freq: Frequency ('1d' for daily, '1h' for hourly, '5m' for 5-minute, etc.)
        """
        self.freq = freq
        self.name = f"crypto_{freq}"

    def get_trading_dates(self, start_date: str, end_date: str) -> pd.DatetimeIndex:
        """
        Get all trading dates/times between start and end

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DatetimeIndex of all trading timestamps
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

        # Generate continuous date range (no holidays/weekends in crypto)
        dates = pd.date_range(start=start, end=end, freq=self.freq)

        logger.info(f"Generated {len(dates)} trading periods from {start_date} to {end_date}")
        return dates

    def is_trading_time(self, timestamp: pd.Timestamp) -> bool:
        """Check if given timestamp is a trading time (always True for crypto)"""
        return True

    def get_next_trading_time(self, timestamp: pd.Timestamp) -> pd.Timestamp:
        """Get next trading time after given timestamp"""
        freq_map = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1),
        }
        delta = freq_map.get(self.freq, timedelta(days=1))
        return timestamp + delta

    def to_qlib_format(self) -> dict:
        """Export calendar in qlib-compatible format"""
        return {
            "name": self.name,
            "freq": self.freq,
            "type": "crypto",
            "24_7_trading": True
        }


def generate_crypto_calendars(
    output_dir: str = "data/qlib/calendars",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    frequencies: Optional[List[str]] = None,
):
    """
    Generate crypto calendars for different frequencies

    Args:
        output_dir: Directory to save calendar files
    """
    from pathlib import Path
    import json

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    freq_list = frequencies or ['1d', '1h', '5m', '1m']

    # Default to the last five years if dates are not provided
    if end_date is None:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    if start_date is None:
        default_start = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=5 * 365)
        start_date = default_start.strftime("%Y-%m-%d")

    for freq in freq_list:
        calendar = CryptoCalendar(freq)
        dates = calendar.get_trading_dates(start_date, end_date)

        # Save as CSV
        df = pd.DataFrame({'datetime': dates})
        csv_path = output_path / f"crypto_{freq}.csv"
        df.to_csv(csv_path, index=False)

        # Save metadata as JSON
        meta_path = output_path / f"crypto_{freq}_meta.json"
        with open(meta_path, 'w') as f:
            json.dump(calendar.to_qlib_format(), f, indent=2)

        logger.info(f"Generated {freq} calendar with {len(dates)} periods: {csv_path}")

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Qlib-compatible crypto calendars")
    parser.add_argument("--output-dir", default="data/qlib/calendars", help="Directory to write calendar CSV/metadata")
    parser.add_argument("--start", dest="start_date", help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_date", help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument(
        "--frequencies",
        nargs="+",
        help="List of frequencies to generate (default: 1d 1h 5m 1m)",
    )

    cli_args = parser.parse_args()

    generate_crypto_calendars(
        output_dir=cli_args.output_dir,
        start_date=cli_args.start_date,
        end_date=cli_args.end_date,
        frequencies=cli_args.frequencies,
    )
