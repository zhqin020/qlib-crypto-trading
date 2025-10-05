"""
Point-in-time snapshot creation for datasets
"""

import logging
from typing import Optional
from pathlib import Path
import json
from datetime import datetime

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
    try:
        from .qlib_converter import convert_crypto_data
        from .crypto_calendar import generate_crypto_calendars

        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "data"

        # Generate calendars if needed
        calendars_dir = data_dir / "qlib" / "calendars"
        if not calendars_dir.exists():
            logger.info("Generating crypto calendars...")
            generate_crypto_calendars(str(calendars_dir))

        # Extract frequency from calendar name
        freq = calendar.replace("crypto_", "")

        # Convert data if not already done
        csv_dir = data_dir / "raw"
        qlib_dir = data_dir / "qlib" / dataset

        if csv_dir.exists() and list(csv_dir.glob("*.csv")):
            logger.info(f"Converting data for dataset: {dataset}")
            result = convert_crypto_data(
                csv_dir=str(csv_dir),
                qlib_dir=str(qlib_dir),
                freq=freq
            )
        else:
            result = {"message": "No CSV files found, snapshot structure created"}

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

        logger.info(f"Snapshot created for dataset: {dataset}")
        return snapshot_meta

    except Exception as e:
        logger.error(f"Error creating snapshot: {e}", exc_info=True)
        return {"error": str(e), "dataset": dataset}
