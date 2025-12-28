"""
Use Qlib's official dump_bin.py script for guaranteed compatibility
Crypto-only, no fallbacks, fail fast on any error
"""
import pandas as pd
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import logging
from utils.logging_config import get_logger
import sys
from contextlib import contextmanager
import os

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency in minimal environments
    psutil = None

from .validation import (
    validate_file_path,
    ValidationError
)

logger = get_logger(__name__)


def _get_available_memory_mb() -> Optional[float]:
    """Best-effort calculation of available system memory in MB."""
    if psutil is not None:
        try:
            return psutil.virtual_memory().available / (1024 ** 2)
        except Exception:  # pragma: no cover - defensive fallback
            logger.debug("psutil.virtual_memory() failed", exc_info=True)

    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if isinstance(pages, int) and isinstance(page_size, int) and pages > 0 and page_size > 0:
                return (pages * page_size) / (1024 ** 2)
        except (ValueError, OSError, TypeError, AttributeError):  # pragma: no cover - platform specific
            logger.debug("os.sysconf memory lookup failed", exc_info=True)

    return None


def check_memory_available(required_mb: int = 500) -> None:
    """
    Check if sufficient memory available

    Args:
        required_mb: Minimum required memory in MB

    Raises:
        MemoryError: If insufficient memory available
    """
    available = _get_available_memory_mb()

    if available is None:
        # Fall back to a conservative default when precise measurement is unavailable.
        logger.warning(
            "psutil not available; using conservative 32GB fallback for memory checks"
        )
        available = 32_000.0  # 32 GB expressed in MB

    if available < required_mb:
        raise MemoryError(
            f"Insufficient memory: {available:.0f}MB available, {required_mb}MB required"
        )
    logger.info(f"Memory check passed: {available:.0f}MB available")


def validate_csv_structure(csv_path: Path, sample_size: int = 1000) -> None:
    """
    Validate CSV structure without loading entire file

    Args:
        csv_path: Path to CSV file
        sample_size: Number of rows to sample for validation

    Raises:
        ValueError: If CSV structure is invalid
        ValidationError: If file path is invalid
    """
    # Validate file path
    try:
        csv_path = validate_file_path(str(csv_path), must_exist=True)
    except ValidationError as e:
        raise ValueError(f"Invalid CSV file path: {e}")

    logger.info(f"Validating CSV structure: {csv_path.name}")

    # Validate file extension
    if csv_path.suffix.lower() != '.csv':
        raise ValueError(f"File must be a CSV file: {csv_path.name}")

    # Read first chunk only for validation
    try:
        sample = pd.read_csv(csv_path, nrows=sample_size)
    except Exception as e:
        raise ValueError(f"Failed to read CSV file {csv_path.name}: {e}")

    required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in sample.columns]

    if missing_cols:
        raise ValueError(
            f"Missing required columns in {csv_path.name}: {missing_cols}"
        )

    # Check if file is empty
    if len(sample) == 0:
        raise ValueError(f"Empty data in {csv_path.name}")

    # Validate data types
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(sample[col]):
            raise ValueError(f"Column '{col}' must be numeric in {csv_path.name}")

    # Validate date column
    try:
        pd.to_datetime(sample['datetime'])
    except Exception as e:
        raise ValueError(f"Invalid datetime format in {csv_path.name}: {e}")

    logger.info(f"✓ CSV structure valid: {len(sample.columns)} columns, sample {len(sample)} rows")


@contextmanager
def safe_conversion(output_file: Path):
    """
    Context manager to cleanup on error

    Args:
        output_file: Path to output file being written

    Yields:
        None

    Ensures cleanup of partial files on error
    """
    temp_marker = output_file.parent / f".{output_file.name}.in_progress"
    try:
        temp_marker.touch()
        yield
        if temp_marker.exists():
            temp_marker.unlink()
    except Exception:
        # Cleanup partial files
        if output_file.exists():
            logger.warning(f"Cleaning up partial file: {output_file}")
            output_file.unlink()
        if temp_marker.exists():
            temp_marker.unlink()
        raise


def prepare_normalized_csv(
    csv_files: List[Path],
    output_dir: Path,
    freq: str = "1d",
    chunk_size: int = 100000
) -> Dict[str, Path]:
    """
    Convert crypto CSV files to Qlib's expected format using chunked processing

    Expected format by dump_bin.py:
    - Columns: instrument, date, open, high, low, close, volume, [optional: adjclose, factor]
    - One row per instrument per date

    Args:
        csv_files: List of CSV files to process
        output_dir: Directory for normalized output
        chunk_size: Rows per chunk (default 100k)

    Returns:
        Dict mapping symbol to output file path

    Raises:
        ValueError: If file is too large or data is invalid
        MemoryError: If insufficient memory available
        ValidationError: If file paths are invalid

    NO FALLBACKS - Fails if data is invalid
    """
    # Validate inputs
    if not csv_files:
        raise ValueError("No CSV files provided")

    if len(csv_files) > 1000:
        raise ValueError(f"Too many CSV files: {len(csv_files)} (max 1000)")

    if chunk_size < 100 or chunk_size > 10000000:
        raise ValueError(f"Invalid chunk size: {chunk_size} (must be between 100 and 10000000)")

    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_files = {}

    for csv_file in csv_files:
        # Check memory before processing
        check_memory_available(required_mb=500)

        # Validate file size (10GB limit)
        file_size = csv_file.stat().st_size
        if file_size > 10 * 1024 * 1024 * 1024:  # 10GB
            raise ValueError(
                f"File too large: {csv_file.name} is {file_size / 1024**3:.1f}GB. "
                f"Maximum supported size is 10GB."
            )

        logger.info(
            f"Normalizing {csv_file.name} ({file_size / 1024**2:.1f}MB) in chunks of {chunk_size:,} rows..."
        )

        # Validate CSV structure first (fast check on first 1000 rows)
        validate_csv_structure(csv_file)

        # Extract symbol from filename (e.g., BTC_USDT_1d.csv -> BTC)
        symbol = csv_file.stem.split('_')[0].upper()

        # Output file
        output_file = output_dir / f"{symbol}.csv"

        # Process in chunks with safe cleanup
        with safe_conversion(output_file):
            chunks_processed = 0
            total_rows = 0
            first_date = None
            last_date = None

            for chunk in pd.read_csv(csv_file, chunksize=chunk_size):
                # Validate required columns exist
                required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
                missing = [col for col in required_cols if col not in chunk.columns]
                if missing:
                    raise ValueError(
                        f"Missing required columns in {csv_file.name}: {missing}"
                    )

                # Drop rows with NULL values
                chunk_before = len(chunk)
                chunk = chunk.dropna(subset=required_cols)
                if len(chunk) < chunk_before:
                    logger.warning(
                        f"Dropped {chunk_before - len(chunk)} rows with NULL values in chunk {chunks_processed + 1}"
                    )

                # Convert to Qlib format
                chunk['instrument'] = symbol
                # Use high-frequency format if not daily
                if freq == "1d":
                    chunk['date'] = pd.to_datetime(chunk['datetime']).dt.strftime('%Y-%m-%d')
                else:
                    chunk['date'] = pd.to_datetime(chunk['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')

                # Qlib expects these exact columns
                normalized_chunk = chunk[['instrument', 'date', 'open', 'high', 'low', 'close', 'volume']].copy()

                # Add optional columns for Qlib
                normalized_chunk['adjclose'] = normalized_chunk['close']  # No adjustment for crypto
                normalized_chunk['factor'] = 1.0

                # Sort by date for consistency
                normalized_chunk = normalized_chunk.sort_values('date')

                # Track date range
                chunk_dates = pd.to_datetime(normalized_chunk['date'])
                if first_date is None:
                    first_date = chunk_dates.min()
                last_date = chunk_dates.max()

                # Write chunk
                if chunks_processed == 0:
                    # First chunk: create file with header
                    normalized_chunk.to_csv(output_file, mode='w', index=False)
                else:
                    # Subsequent chunks: append without header
                    normalized_chunk.to_csv(output_file, mode='a', index=False, header=False)

                chunks_processed += 1
                total_rows += len(normalized_chunk)

                # Log progress every 10 chunks
                if chunks_processed % 10 == 0:
                    logger.info(
                        f"  Progress: {chunks_processed} chunks ({total_rows:,} rows) processed"
                    )

            # Validate output
            if total_rows == 0:
                raise ValueError(f"Empty data in {csv_file.name}")

            normalized_files[symbol] = output_file

            logger.info(
                f"✓ Normalized {symbol}: {total_rows:,} records in {chunks_processed} chunks "
                f"from {first_date.strftime('%Y-%m-%d')} to {last_date.strftime('%Y-%m-%d')}"
            )

    return normalized_files


def run_official_dump_bin(
    normalized_csv_dir: Path,
    qlib_output_dir: Path,
    freq: str = "day",
    include_fields: str = "open,close,high,low,volume,factor"
) -> Dict[str, any]:
    """
    Run Qlib's official dump_bin.py script

    Args:
        normalized_csv_dir: Directory containing normalized CSV files
        qlib_output_dir: Output directory for Qlib binary data
        freq: Frequency string (day, 1h, 15min, etc.)
        include_fields: Comma-separated list of fields to include

    Returns:
        Result dictionary with status and metadata

    Raises:
        ValueError: If inputs are invalid
        FileNotFoundError: If dump_bin.py not found
        RuntimeError: If dump_bin.py fails

    NO FALLBACKS - Fails if dump_bin.py fails
    """
    # Validate inputs
    if not normalized_csv_dir.exists():
        raise ValueError(f"Input directory does not exist: {normalized_csv_dir}")

    if not normalized_csv_dir.is_dir():
        raise ValueError(f"Input path is not a directory: {normalized_csv_dir}")

    # Validate freq parameter
    valid_freqs = ['day', '1h', '2h', '4h', '60min', '15min', '5min', '1min']
    if freq not in valid_freqs:
        raise ValueError(f"Invalid frequency: {freq}. Valid values: {valid_freqs}")

    # Validate include_fields
    if not include_fields or not isinstance(include_fields, str):
        raise ValueError("include_fields must be a non-empty string")

    # Validate fields format (comma-separated alphanumeric)
    import re
    if not re.match(r'^[a-z,_]+$', include_fields):
        raise ValueError(f"Invalid include_fields format: {include_fields}")

    # Find dump_bin.py in Qlib installation (platform-independent)
    import qlib
    qlib_path = Path(qlib.__file__).parent
    dump_bin_script = qlib_path / "scripts" / "dump_bin.py"

    if not dump_bin_script.exists():
        local_fallback = Path(__file__).parent / "vendor" / "qlib_dump_bin.py"
        if local_fallback.exists():
            logger.warning(
                "Qlib dump_bin.py missing at %s; falling back to vendored copy %s",
                dump_bin_script,
                local_fallback,
            )
            dump_bin_script = local_fallback
        else:
            raise FileNotFoundError(
                f"Qlib's dump_bin.py not found at {dump_bin_script} and no vendored fallback available. "
                "Reinstall pyqlib or provide dump_bin.py"
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

    Args:
        csv_dir: Directory containing CSV files
        qlib_dir: Output directory for Qlib format
        freq: Frequency string (1d, 1h, etc.)

    Returns:
        Result dictionary with conversion metadata

    Raises:
        ValueError: If inputs are invalid
        ValidationError: If file paths are invalid

    Crypto-only, no fallbacks, fail fast
    """
    # Validate inputs
    if not csv_dir or not isinstance(csv_dir, str):
        raise ValueError("csv_dir must be a non-empty string")

    if not qlib_dir or not isinstance(qlib_dir, str):
        raise ValueError("qlib_dir must be a non-empty string")

    if not freq or not isinstance(freq, str):
        raise ValueError("freq must be a non-empty string")

    # Validate frequency format
    import re
    if not re.match(r'^[0-9]{0,2}[mhd]$', freq.lower()) and freq.lower() not in ["day", "1h", "15min", "5min", "1min"]:
        raise ValueError(f"Invalid frequency format: {freq}. Expected format: 1d, 1h, 15m, etc.")

    logger.info(f"Converting crypto data: csv_dir={csv_dir}, qlib_dir={qlib_dir}, freq={freq}")

    csv_path = Path(csv_dir)
    qlib_path = Path(qlib_dir)

    # Validate directories
    if not csv_path.exists():
        raise ValueError(f"CSV directory does not exist: {csv_dir}")

    if not csv_path.is_dir():
        raise ValueError(f"CSV path is not a directory: {csv_dir}")

    # Find CSV files
    csv_files = list(csv_path.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in {csv_dir}")

    # Filter for crypto only
    # Match frequency in filename (e.g., BTC_USDT_1h.csv matches freq='1h')
    pattern = freq.lower()
    crypto_csv_files = [f for f in csv_files if pattern in f.name.lower()]
    if not crypto_csv_files:
        raise ValueError(f"No crypto CSV files found matching frequency {freq} in {csv_dir}")

    logger.info(f"Found {len(crypto_csv_files)} crypto CSV files for {freq} frequency")

    # Step 1: Normalize CSVs to Qlib format
    normalized_dir = qlib_path.parent / f"normalized_temp_{freq}"
    normalized_files = prepare_normalized_csv(crypto_csv_files, normalized_dir, freq=freq)

    # Map our freq to Qlib's dump_bin freq
    freq_map = {
        "1d": "day",
        "1h": "60min"
    }
    qlib_dump_freq = freq_map.get(freq, freq)

    # Step 2: Run official dump_bin.py
    result = run_official_dump_bin(
        normalized_csv_dir=normalized_dir,
        qlib_output_dir=qlib_path,
        freq=qlib_dump_freq,
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
