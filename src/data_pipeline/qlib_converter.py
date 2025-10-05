"""
Convert crypto CSV data to Qlib binary format
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CryptoToQlibConverter:
    """Convert cryptocurrency CSV data to Qlib binary format"""

    def __init__(
        self,
        csv_dir: str,
        qlib_dir: str,
        calendar_path: Optional[str] = None,
        freq: str = "1d"
    ):
        """
        Initialize converter

        Args:
            csv_dir: Directory containing CSV files
            qlib_dir: Output directory for Qlib binary files
            calendar_path: Path to calendar CSV (optional)
            freq: Data frequency (1d, 1h, 5m, etc.)
        """
        self.csv_dir = Path(csv_dir)
        self.qlib_dir = Path(qlib_dir)
        self.freq = freq

        # Create output structure
        self.instruments_dir = self.qlib_dir / "instruments"
        self.features_dir = self.qlib_dir / "features"
        self.calendars_dir = self.qlib_dir / "calendars"

        for d in [self.instruments_dir, self.features_dir, self.calendars_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Load or generate calendar
        if calendar_path:
            self.calendar = pd.read_csv(calendar_path, parse_dates=['datetime'])
        else:
            from .crypto_calendar import CryptoCalendar
            cal = CryptoCalendar(freq)
            self.calendar = pd.DataFrame({
                'datetime': cal.get_trading_dates("2019-01-01", "2024-12-31")
            })

    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol name (BTC/USDT -> BTC_USDT)"""
        return symbol.replace("/", "_").replace("-", "_").upper()

    def convert_csv_to_dataframe(self, csv_path: Path) -> pd.DataFrame:
        """
        Load and normalize CSV data

        Expected CSV columns: datetime, open, high, low, close, volume
        """
        df = pd.read_csv(csv_path)

        # Handle different datetime column names
        datetime_cols = ['datetime', 'timestamp', 'date', 'time']
        datetime_col = None
        for col in datetime_cols:
            if col in df.columns:
                datetime_col = col
                break

        if not datetime_col:
            raise ValueError(f"No datetime column found in {csv_path}")

        # Parse datetime
        df['datetime'] = pd.to_datetime(df[datetime_col])
        df.set_index('datetime', inplace=True)
        df.sort_index(inplace=True)

        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Add derived features
        df['vwap'] = ((df['high'] + df['low'] + df['close']) / 3).round(8)
        df['factor'] = 1.0  # No adjustment factor for crypto

        # Forward fill missing values
        df.fillna(method='ffill', inplace=True)

        return df[['open', 'high', 'low', 'close', 'volume', 'vwap', 'factor']]

    def save_to_qlib_format(self, symbol: str, df: pd.DataFrame):
        """
        Save DataFrame in Qlib binary format

        Qlib stores each feature in a separate binary file
        """
        symbol_dir = self.features_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)

        # Align with calendar
        df_aligned = df.reindex(self.calendar['datetime'])

        # Save each column as binary
        features = ['open', 'high', 'low', 'close', 'volume', 'vwap', 'factor']

        for feature in features:
            if feature in df_aligned.columns:
                data = df_aligned[feature].values.astype(np.float32)
                bin_path = symbol_dir / f"{feature}.bin"
                data.tofile(str(bin_path))
                logger.debug(f"Saved {feature} for {symbol}: {len(data)} values")

    def create_instruments_list(self, symbols: List[str]):
        """
        Create instruments list file

        Format: symbol,start_date,end_date
        """
        instruments_file = self.instruments_dir / "all.txt"

        with open(instruments_file, 'w') as f:
            for symbol in symbols:
                # For crypto, use a wide date range
                f.write(f"{symbol}\t2019-01-01\t2099-12-31\n")

        logger.info(f"Created instruments list with {len(symbols)} symbols")

    def convert_all(self) -> Dict[str, any]:
        """
        Convert all CSV files in the directory

        Returns:
            Summary statistics
        """
        csv_files = list(self.csv_dir.glob("*.csv"))

        if not csv_files:
            raise ValueError(f"No CSV files found in {self.csv_dir}")

        converted_symbols = []
        errors = []

        for csv_file in csv_files:
            try:
                # Extract symbol from filename
                symbol = self.normalize_symbol(csv_file.stem.split('_')[0])

                logger.info(f"Converting {symbol} from {csv_file.name}...")

                # Load and convert
                df = self.convert_csv_to_dataframe(csv_file)
                self.save_to_qlib_format(symbol, df)

                converted_symbols.append(symbol)
                logger.info(f"✓ Converted {symbol}: {len(df)} records")

            except Exception as e:
                logger.error(f"✗ Failed to convert {csv_file.name}: {e}")
                errors.append((csv_file.name, str(e)))

        # Create instruments list
        if converted_symbols:
            self.create_instruments_list(converted_symbols)

        # Save calendar
        calendar_file = self.calendars_dir / f"crypto_{self.freq}.txt"
        self.calendar['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').to_csv(
            calendar_file, index=False, header=False
        )

        summary = {
            "total_files": len(csv_files),
            "converted": len(converted_symbols),
            "failed": len(errors),
            "symbols": converted_symbols,
            "errors": errors,
            "output_dir": str(self.qlib_dir),
            "calendar_periods": len(self.calendar)
        }

        logger.info(f"Conversion complete: {len(converted_symbols)}/{len(csv_files)} successful")

        return summary


def convert_crypto_data(
    csv_dir: str = "data/raw",
    qlib_dir: str = "data/qlib",
    freq: str = "1d"
) -> Dict[str, any]:
    """
    Convenience function to convert crypto CSV data to Qlib format

    Args:
        csv_dir: Directory containing CSV files with OHLCV data
        qlib_dir: Output directory for Qlib binary format
        freq: Data frequency

    Returns:
        Conversion summary
    """
    converter = CryptoToQlibConverter(csv_dir, qlib_dir, freq=freq)
    return converter.convert_all()


if __name__ == "__main__":
    import sys

    csv_dir = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
    qlib_dir = sys.argv[2] if len(sys.argv) > 2 else "data/qlib"
    freq = sys.argv[3] if len(sys.argv) > 3 else "1d"

    result = convert_crypto_data(csv_dir, qlib_dir, freq)
    print(f"\nConversion Summary:")
    print(f"  Converted: {result['converted']}/{result['total_files']}")
    print(f"  Symbols: {', '.join(result['symbols'])}")
    print(f"  Output: {result['output_dir']}")
