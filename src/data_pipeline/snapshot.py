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
    """
    # Generate process ID
    process_id = f"download_{uuid.uuid4().hex[:8]}"

    # Total steps: init, generate_calendars, extract_freq, convert_data, save_meta
    total_steps = 5

    try:
        # Start process monitoring
        await monitor.start_process(process_id, "download", total_steps=total_steps)

        from .official_qlib_converter import convert_crypto_data_official
        from .crypto_calendar import generate_crypto_calendars

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
        await monitor.fail_process(process_id, str(e))
        return {"error": str(e), "dataset": dataset}
