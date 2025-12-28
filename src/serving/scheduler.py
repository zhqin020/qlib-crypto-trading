"""
Job scheduling system using RRULE
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Global scheduler registry
SCHEDULES = {}


async def create_schedule(
    job: str,
    rrule: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create or update a scheduled job

    Args:
        job: Job type (train_model, run_backtest, generate_predictions)
        rrule: Recurrence rule (e.g., "FREQ=DAILY;HOUR=9")
        params: Job-specific parameters

    Returns:
        Schedule metadata
    """
    try:
        from dateutil.rrule import rrulestr

        # Parse RRULE
        rule = rrulestr(rrule)

        schedule_id = f"{job}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        schedule = {
            "schedule_id": schedule_id,
            "job": job,
            "rrule": rrule,
            "params": params or {},
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "next_run": rule.after(datetime.now()).isoformat() if rule.after(datetime.now()) else None
        }

        # Store schedule
        SCHEDULES[schedule_id] = schedule

        # Save to file
        project_root = Path(__file__).parent.parent.parent
        schedules_dir = project_root / "schedules"
        schedules_dir.mkdir(parents=True, exist_ok=True)

        schedule_file = schedules_dir / f"{schedule_id}.json"
        with open(schedule_file, 'w') as f:
            json.dump(schedule, f, indent=2)

        logger.info(f"Created schedule: {schedule_id} for job {job}")
        return schedule

    except Exception as e:
        logger.error(f"Error creating schedule: {e}", exc_info=True)
        return {
            "error": str(e),
            "job": job,
            "status": "failed"
        }


async def execute_scheduled_job(schedule_id: str) -> Dict[str, Any]:
    """Execute a scheduled job"""

    if schedule_id not in SCHEDULES:
        return {"error": "Schedule not found"}

    schedule = SCHEDULES[schedule_id]
    job = schedule["job"]
    params = schedule["params"]

    logger.info(f"Executing scheduled job: {schedule_id} ({job})")

    try:
        if job == "train_model":
            from models.trainer import train_model
            result = await train_model(**params)

        elif job == "run_backtest":
            from backtesting.engine import run_backtest
            result = await run_backtest(**params)

        elif job == "generate_predictions":
            from serving.predictor import predict_today
            result = await predict_today(**params)

        elif job == "download_data":
            from data_pipeline.market_data import download_crypto_universe
            result = await download_crypto_universe(**params)

        else:
            result = {"error": f"Unknown job type: {job}"}

        # Update schedule
        schedule["last_run"] = datetime.now().isoformat()
        schedule["last_result"] = result.get("status", "unknown")

        return result

    except Exception as e:
        logger.error(f"Error executing scheduled job: {e}", exc_info=True)
        return {"error": str(e), "schedule_id": schedule_id}
