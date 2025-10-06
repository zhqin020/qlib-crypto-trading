"""
Use Qlib's official dump_bin.py script for guaranteed compatibility
Crypto-only, no fallbacks, fail fast on any error
"""
import pandas as pd
import subprocess
from pathlib import Path
from typing import Dict, List
import logging
import sys

logger = logging.getLogger(__name__)


def prepare_normalized_csv(csv_files: List[Path], output_dir: Path) -> Dict[str, Path]:
    """
    Convert crypto CSV files to Qlib's expected format

    Expected format by dump_bin.py:
    - Columns: instrument, date, open, high, low, close, volume, [optional: adjclose, factor]
    - One row per instrument per date

    NO FALLBACKS - Fails if data is invalid
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_files = {}

    for csv_file in csv_files:
        logger.info(f"Normalizing {csv_file.name}...")

        # Read CSV
        df = pd.read_csv(csv_file)

        # Validate required columns exist
        required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns in {csv_file.name}: {missing}")

        # Extract symbol from filename (e.g., BTC_USDT_1d.csv -> BTC)
        symbol = csv_file.stem.split('_')[0].upper()

        # Convert to Qlib format
        df['instrument'] = symbol
        df['date'] = pd.to_datetime(df['datetime']).dt.strftime('%Y-%m-%d')

        # Qlib expects these exact columns
        normalized = df[['instrument', 'date', 'open', 'high', 'low', 'close', 'volume']].copy()

        # Add optional columns for Qlib
        normalized['adjclose'] = normalized['close']  # No adjustment for crypto
        normalized['factor'] = 1.0

        # Validate data integrity
        if normalized.isnull().any().any():
            null_cols = normalized.columns[normalized.isnull().any()].tolist()
            raise ValueError(f"NULL values found in {csv_file.name} columns: {null_cols}")

        if len(normalized) == 0:
            raise ValueError(f"Empty data in {csv_file.name}")

        # Save normalized CSV
        output_file = output_dir / f"{symbol}.csv"
        normalized.to_csv(output_file, index=False)
        normalized_files[symbol] = output_file

        logger.info(f"✓ Normalized {symbol}: {len(normalized)} records from {normalized['date'].min()} to {normalized['date'].max()}")

    return normalized_files


def run_official_dump_bin(
    normalized_csv_dir: Path,
    qlib_output_dir: Path,
    freq: str = "day",
    include_fields: str = "open,close,high,low,volume,factor"
) -> Dict[str, any]:
    """
    Run Qlib's official dump_bin.py script

    NO FALLBACKS - Fails if dump_bin.py fails
    """
    # Find dump_bin.py in Qlib installation
    dump_bin_script = Path("/private/tmp/qlib/scripts/dump_bin.py")

    if not dump_bin_script.exists():
        raise FileNotFoundError(
            f"Qlib's dump_bin.py not found at {dump_bin_script}. "
            "Ensure Qlib is installed correctly."
        )

    # Build command - dump_bin.py uses positional arguments differently
    cmd = [
        sys.executable,
        str(dump_bin_script),
        "dump_all",
        f"--data_path={normalized_csv_dir}",
        f"--qlib_dir={qlib_output_dir}",
        f"--freq={freq}",
        f"--include_fields={include_fields}",
        "--date_field_name=date",
        "--symbol_field_name=instrument"
    ]

    logger.info(f"Running official Qlib dump_bin.py...")
    logger.info(f"Command: {' '.join(cmd)}")

    # Run dump_bin.py - NO FALLBACK, fail on error
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False  # Don't raise, we'll check return code ourselves
    )

    # Log output
    if result.stdout:
        logger.info(f"dump_bin.py stdout:\n{result.stdout}")
    if result.stderr:
        logger.warning(f"dump_bin.py stderr:\n{result.stderr}")

    # FAIL FAST - No fallbacks
    if result.returncode != 0:
        raise RuntimeError(
            f"dump_bin.py failed with return code {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    logger.info("✓ Official dump_bin.py completed successfully")

    # Verify output
    if not qlib_output_dir.exists():
        raise RuntimeError(f"dump_bin.py did not create output directory: {qlib_output_dir}")

    required_dirs = ['instruments', 'features', 'calendars']
    for dir_name in required_dirs:
        dir_path = qlib_output_dir / dir_name
        if not dir_path.exists():
            raise RuntimeError(f"dump_bin.py did not create required directory: {dir_name}")

    # Fix calendar names: Qlib expects 'day.txt' not '1d.txt' or other variants
    # dump_bin.py creates files with freq parameter name, but Qlib needs normalized names
    cal_dir = qlib_output_dir / 'calendars'
    freq_to_qlib_map = {
        'day': 'day',
        '1d': 'day',
        '1day': 'day',
        '1h': '1h',
        '1hour': '1h',
        '15m': '15min',
        '15min': '15min',
        '5m': '5min',
        '5min': '5min',
        '1m': '1min',
        '1min': '1min'
    }

    # Find and rename calendar files
    for cal_file in cal_dir.glob('*.txt'):
        if cal_file.stem in freq_to_qlib_map:
            target_name = freq_to_qlib_map[cal_file.stem]
            if cal_file.stem != target_name:
                target_path = cal_dir / f"{target_name}.txt"
                cal_file.rename(target_path)
                logger.info(f"✓ Renamed calendar: {cal_file.stem}.txt -> {target_name}.txt")

    return {
        "status": "success",
        "output_dir": str(qlib_output_dir),
        "stdout": result.stdout,
        "stderr": result.stderr
    }


def convert_crypto_data_official(
    csv_dir: str,
    qlib_dir: str,
    freq: str = "1d"
) -> Dict[str, any]:
    """
    Convert crypto CSV to Qlib format using OFFICIAL tools only

    Crypto-only, no fallbacks, fail fast
    """
    csv_path = Path(csv_dir)
    qlib_path = Path(qlib_dir)

    # Find CSV files
    csv_files = list(csv_path.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in {csv_dir}")

    # Filter for crypto only (daily frequency for now)
    crypto_csv_files = [f for f in csv_files if freq.replace("d", "D") in f.name or "1d" in f.name.lower()]
    if not crypto_csv_files:
        raise ValueError(f"No crypto CSV files found matching frequency {freq} in {csv_dir}")

    logger.info(f"Found {len(crypto_csv_files)} crypto CSV files for {freq} frequency")

    # Step 1: Normalize CSVs to Qlib format
    normalized_dir = qlib_path.parent / "normalized_temp"
    normalized_files = prepare_normalized_csv(crypto_csv_files, normalized_dir)

    # Step 2: Run official dump_bin.py
    result = run_official_dump_bin(
        normalized_csv_dir=normalized_dir,
        qlib_output_dir=qlib_path,
        freq="day",
        include_fields="open,close,high,low,volume,factor"
    )

    # Cleanup temp files
    import shutil
    shutil.rmtree(normalized_dir)

    result['converted_symbols'] = list(normalized_files.keys())
    result['total_files'] = len(crypto_csv_files)

    return result


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    result = convert_crypto_data_official(
        csv_dir='data/raw',
        qlib_dir='data/qlib/crypto_official',
        freq='1d'
    )

    print("\n✓ Conversion complete!")
    print(f"  Symbols: {result['converted_symbols']}")
    print(f"  Output: {result['output_dir']}")
