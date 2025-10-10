"""
Point-in-time snapshot creation for datasets
"""

import logging
from typing import Optional
from pathlib import Path
import json
from datetime import datetime
import uuid

from ..monitoring.process_monitor import monitor, ProcessStatus
from .validation import (
    validate_dataset_name,
    validate_date_range,
    validate_calendar,
    ValidationError
)

try:  # Optional dependency: qlib calendar utilities
    from .crypto_calendar import generate_crypto_calendars as _generate_crypto_calendars
except ImportError:  # pragma: no cover - executed when qlib is unavailable
    _generate_crypto_calendars = None


if _generate_crypto_calendars is not None:
    generate_crypto_calendars = _generate_crypto_calendars
else:
    def generate_crypto_calendars(*args, **kwargs):  # type: ignore[override]
        raise ModuleNotFoundError(
            "Qlib calendar utilities are required to generate snapshot calendars."
        )

    generate_crypto_calendars._qlib_missing = True  # type: ignore[attr-defined]

from .official_qlib_converter import convert_crypto_data_official

logger = logging.getLogger(__name__)


async def create_snapshot(
    dataset: str,
    calendar: str,
    start: Optional[str] = None,
    end: Optional[str] = None
) -> dict:
    """
    Create a point-in-time snapshot for a dataset

    Args:
        dataset: Dataset name/path
        calendar: Calendar type (crypto_1d, crypto_1h, etc.)
        start: Start date (optional)
        end: End date (optional)

    Returns:
        Snapshot metadata

    Raises:
        ValidationError: If input validation fails
    """
    # Validate inputs FIRST before any processing
    try:
        dataset = validate_dataset_name(dataset)
        calendar = validate_calendar(calendar)
        start_dt, end_dt = validate_date_range(start, end)

        # Convert back to strings for processing
        start = start_dt.strftime("%Y-%m-%d")
        end = end_dt.strftime("%Y-%m-%d")

        logger.info(f"Creating snapshot: dataset={dataset}, calendar={calendar}, range={start} to {end}")
    except ValidationError as e:
        logger.error(f"Input validation failed: {e}")
        return {"error": f"Invalid input: {str(e)}", "dataset": dataset}

    # Generate process ID with timestamp to prevent collisions
    import time
    process_id = f"download_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

    # Total steps: init, generate_calendars, extract_freq, convert_data, save_meta
    total_steps = 5

    process_started = False
    try:
        # Start process monitoring
        await monitor.start_process(process_id, "download", total_steps=total_steps)
        process_started = True

        from .official_qlib_converter import convert_crypto_data_official

        # Step 1: Initialize paths
        await monitor.update_progress(process_id, 20.0, f"Initializing snapshot for dataset '{dataset}'", 1)

        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "data"

        # Step 2: Generate calendars
        await monitor.update_progress(process_id, 40.0, f"Generating crypto calendars for '{calendar}'", 2)

        # Generate calendars if needed
        calendars_dir = data_dir / "qlib" / "calendars"
        if not calendars_dir.exists():
            logger.info("Generating crypto calendars...")
            generate_crypto_calendars(str(calendars_dir))

        # Step 3: Extract frequency
        await monitor.update_progress(process_id, 60.0, f"Extracting frequency from calendar '{calendar}'", 3)

        # Extract frequency from calendar name
        freq = calendar.replace("crypto_", "")

        # Step 4: Convert data
        await monitor.update_progress(process_id, 80.0, f"Converting CSV data to Qlib format (freq={freq})", 4)

        # Convert data if not already done
        csv_dir = data_dir / "raw"
        qlib_dir = data_dir / "qlib" / dataset

        if csv_dir.exists() and list(csv_dir.glob("*.csv")):
            logger.info(f"Converting data for dataset: {dataset}")
            result = convert_crypto_data_official(
                csv_dir=str(csv_dir),
                qlib_dir=str(qlib_dir),
                freq=freq
            )
        else:
            result = {"message": "No CSV files found, snapshot structure created"}

        # Step 5: Save metadata
        await monitor.update_progress(process_id, 95.0, f"Saving snapshot metadata", 5)

        snapshot_meta = {
            "dataset": dataset,
            "calendar": calendar,
            "frequency": freq,
            "start_date": start or "2019-01-01",
            "end_date": end or datetime.now().strftime("%Y-%m-%d"),
            "created_at": datetime.now().isoformat(),
            "status": "ready",
            "qlib_dir": str(qlib_dir),
            "conversion_result": result
        }

        # Save metadata
        meta_file = qlib_dir / "snapshot_meta.json"
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_file, 'w') as f:
            json.dump(snapshot_meta, f, indent=2)

        # Complete process monitoring
        await monitor.complete_process(process_id, snapshot_meta)

        logger.info(f"Snapshot created for dataset: {dataset}")
        return snapshot_meta

    except Exception as e:
        logger.error(f"Error creating snapshot: {e}", exc_info=True)
        # Only fail process if it was successfully started
        if process_started:
            try:
                await monitor.fail_process(process_id, str(e))
            except Exception as monitor_error:
                logger.error(f"Failed to update process monitor: {monitor_error}")
        return {"error": str(e), "dataset": dataset}
