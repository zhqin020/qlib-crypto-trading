"""
Real-time prediction service
"""

import asyncio
import logging
import json
import os
import pickle
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import uuid

from analytics.investment_kpis import kpi_registry
from monitoring.process_monitor import monitor, ProcessStatus
from utils.qlib_state import qlib_init_context
from utils.datasets import load_snapshot_metadata

logger = logging.getLogger(__name__)


MAX_DATA_STALENESS_HOURS = int(os.getenv("PREDICTION_MAX_DATA_AGE_HOURS", "24"))

try:  # Optional dependency: qlib
    from qlib.utils import init_instance_by_config as _QLIB_init_instance_by_config
except ImportError:  # pragma: no cover - executed when qlib is unavailable
    _QLIB_init_instance_by_config = None


if _QLIB_init_instance_by_config is not None:
    init_instance_by_config = _QLIB_init_instance_by_config
else:
    def init_instance_by_config(*args, **kwargs):  # type: ignore[override]
        raise ModuleNotFoundError(
            "Qlib is required for prediction workflows. Install qlib to enable this feature."
        )

    init_instance_by_config._qlib_missing = True  # type: ignore[attr-defined]


async def predict_today(model_id: str, dataset_ref: str) -> Dict[str, Any]:
    """
    Generate predictions for current trading session

    Args:
        model_id: Trained model ID
        dataset_ref: Dataset reference

    Returns:
        Predictions with confidence scores
    """
    # Generate process ID with timestamp to prevent collisions
    import time
    process_id = f"prediction_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

    # Total steps: validation, init, load_model, load_config, create_dataset, predict, save
    total_steps = 7

    process_started = False

    # Create the actual work as a separate coroutine
    async def do_prediction():
        nonlocal process_started
        try:
            # Start process monitoring
            await monitor.start_process(process_id, "prediction", total_steps=total_steps)
            process_started = True

            # Check for cancellation
            process = await monitor.get_process(process_id)
            if process and process.status == ProcessStatus.CANCELLED:
                return {"status": "cancelled", "process_id": process_id}

            project_root = Path(__file__).parent.parent.parent
            models_dir = project_root / "models" / "trained"
            qlib_dir = project_root / "data" / "qlib" / dataset_ref

            # Step 1: Validate dataset
            await monitor.update_progress(process_id, 14.3, f"Validating dataset '{dataset_ref}'", 1)

            # Validate dataset exists
            if not qlib_dir.exists():
                logger.error(f"Dataset directory not found: {qlib_dir}")
                await monitor.fail_process(process_id, f"Dataset '{dataset_ref}' not found at {qlib_dir}")
                return {
                    "error": f"Dataset '{dataset_ref}' not found at {qlib_dir}",
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id
                }

            # Validate dataset has required structure
            if not (qlib_dir / "calendars").exists() and not (qlib_dir / "instruments").exists():
                logger.error(f"Dataset directory exists but appears empty: {qlib_dir}")
                await monitor.fail_process(process_id, f"Dataset '{dataset_ref}' appears to be empty or invalid")
                return {
                    "error": f"Dataset '{dataset_ref}' appears to be empty or invalid",
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id
                }

            snapshot_meta = load_snapshot_metadata(qlib_dir)
            data_staleness_hours: Optional[float] = None
            if snapshot_meta and MAX_DATA_STALENESS_HOURS > 0:
                end_date_str = snapshot_meta.get("end_date")
                if end_date_str:
                    try:
                        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                    except ValueError:
                        logger.warning("Snapshot metadata for %s has invalid end_date: %s", dataset_ref, end_date_str)
                    else:
                        staleness_hours = (datetime.now() - end_dt).total_seconds() / 3600
                        data_staleness_hours = staleness_hours
                        if staleness_hours > MAX_DATA_STALENESS_HOURS:
                            message = (
                                f"Dataset '{dataset_ref}' is stale (last date {end_date_str}). "
                                "Run data download/conversion before generating predictions."
                            )
                            await monitor.fail_process(process_id, message)
                            return {
                                "error": message,
                                "status": "failed",
                                "dataset": dataset_ref,
                                "model_id": model_id
                            }

            # Step 2: Initialize Qlib
            await monitor.update_progress(process_id, 28.6, f"Initializing Qlib with dataset '{dataset_ref}'", 2)

            async with qlib_init_context(
                provider_uri=str(qlib_dir),
                region="cn",
                auto_mount=True
            ):
                # Check for cancellation after init
                process = await monitor.get_process(process_id)
                if process and process.status == ProcessStatus.CANCELLED:
                    return {"status": "cancelled", "process_id": process_id}

                # Step 3: Load model
                await monitor.update_progress(process_id, 42.9, f"Loading model '{model_id}'", 3)

                # Load model
                model_path = models_dir / f"{model_id}.pkl"
                if not model_path.exists():
                    await monitor.fail_process(process_id, f"Model {model_id} not found")
                    return {"error": f"Model {model_id} not found"}

                with open(model_path, 'rb') as f:
                    model = pickle.load(f)

                # Load model metadata
                meta_file = models_dir / f"{model_id}_meta.json"
                with open(meta_file) as f:
                    model_meta = json.load(f)

                # Get latest data for prediction
                today = datetime.now().strftime("%Y-%m-%d")

                # Step 4: Load feature configuration
                await monitor.update_progress(process_id, 57.1, f"Loading feature configuration", 4)

                # Load feature configuration
                config_dir = project_root / "config" / "features"
                feature_set_ref = model_meta.get("feature_set", "alpha158_crypto")
                feature_config_file = config_dir / f"{feature_set_ref}.json"

                if feature_config_file.exists():
                    with open(feature_config_file) as f:
                        feature_config = json.load(f)
                    handler_config = feature_config["config"]
                else:
                    from data_pipeline.features import get_alpha158_config
                    handler_config = get_alpha158_config()

                # Update handler config for today's data
                handler_config["kwargs"]["start_time"] = today
                handler_config["kwargs"]["end_time"] = today

                # Add fit range from model metadata to handler config
                fit_range = model_meta.get("segments", {}).get("train")
                if fit_range and "kwargs" in handler_config:
                    if handler_config["kwargs"].get("fit_start_time") is None:
                        handler_config["kwargs"]["fit_start_time"] = fit_range[0]
                    if handler_config["kwargs"].get("fit_end_time") is None:
                        handler_config["kwargs"]["fit_end_time"] = fit_range[1]

                # Step 5: Create dataset
                await monitor.update_progress(process_id, 71.4, f"Creating dataset for {today}", 5)

                # Create dataset for prediction
                dataset_config = {
                    "class": "DatasetH",
                    "module_path": "qlib.data.dataset",
                    "kwargs": {
                        "handler": handler_config,
                        "segments": {
                            "test": (today, today)
                        },
                    },
                }

                dataset = await asyncio.to_thread(init_instance_by_config, dataset_config)

                # Check for cancellation before prediction
                process = await monitor.get_process(process_id)
                if process and process.status == ProcessStatus.CANCELLED:
                    return {"status": "cancelled", "process_id": process_id}

                # Step 6: Generate predictions
                await monitor.update_progress(process_id, 85.7, f"Generating predictions for {today}", 6)

                # Make predictions
                logger.info(f"Generating predictions for {today} using model {model_id}")
                predictions = await asyncio.to_thread(model.predict, dataset)

                # Convert predictions to readable format
                if isinstance(predictions, pd.Series):
                    pred_df = predictions.to_frame("score")
                elif isinstance(predictions, pd.DataFrame):
                    pred_df = predictions
                else:
                    pred_df = pd.DataFrame(predictions, columns=["score"])

                # Sort by prediction score (top signals)
                pred_df = pred_df.sort_values("score", ascending=False)

                # Get top predictions
                top_predictions = []
                for idx, row in pred_df.head(20).iterrows():
                    if isinstance(idx, tuple):
                        date, symbol = idx
                    else:
                        date = today
                        symbol = str(idx)

                    top_predictions.append({
                        "symbol": symbol,
                        "score": float(row["score"]),
                        "date": date,
                        "rank": len(top_predictions) + 1
                    })

                result = {
                    "model_id": model_id,
                    "dataset": dataset_ref,
                    "prediction_date": today,
                    "predictions": top_predictions,
                    "total_symbols": len(pred_df),
                    "generated_at": datetime.now().isoformat(),
                    "status": "success"
                }

                coverage_ratio = 0.0
                if len(pred_df) > 0:
                    coverage_ratio = len(top_predictions) / float(len(pred_df))

                prediction_metrics = {
                    "data_staleness_hours": data_staleness_hours,
                    "coverage_ratio": coverage_ratio,
                    "total_symbols": len(pred_df),
                }

                evaluation = kpi_registry.record(
                    "prediction",
                    {
                        "model_id": model_id,
                        "dataset": dataset_ref,
                        "prediction_date": today,
                    },
                    prediction_metrics,
                )

                result["kpi_metrics"] = prediction_metrics
                result["kpi_evaluation"] = evaluation.to_dict()
                result["deployment_ready"] = evaluation.passed

                log_level = "INFO" if evaluation.passed else "WARNING"
                if evaluation.breaches:
                    breach_summary = ", ".join(
                        f"{b['metric']}->{b.get('actual')}" for b in evaluation.breaches
                    )
                    message = f"Investment KPI check failed: {breach_summary}"
                else:
                    message = "Investment KPI check passed"

                await monitor.add_log(process_id, log_level, message)

                # Step 7: Save predictions
                await monitor.update_progress(process_id, 95.0, f"Saving {len(top_predictions)} predictions", 7)

                # Save predictions
                pred_dir = project_root / "predictions"
                pred_dir.mkdir(parents=True, exist_ok=True)

                pred_file = pred_dir / f"{model_id}_{today}.json"
                with open(pred_file, 'w') as f:
                    json.dump(result, f, indent=2, default=str)

                # Complete process monitoring
                await monitor.complete_process(process_id, result)

                logger.info(f"Generated {len(top_predictions)} predictions for {today}")
                return result

        except asyncio.CancelledError:
            # Task was cancelled
            logger.info(f"Prediction task cancelled: {process_id}")
            if process_started:
                await monitor.fail_process(process_id, "Cancelled by user")
            raise
        except Exception as e:
            logger.error(f"Error generating predictions: {e}", exc_info=True)
            # Only fail process if it was successfully started
            if process_started:
                try:
                    await monitor.fail_process(process_id, str(e))
                except Exception as monitor_error:
                    logger.error(f"Failed to update process monitor: {monitor_error}")
            return {
                "error": str(e),
                "model_id": model_id,
                "status": "failed"
            }

    # Register the task for cancellation support
    task = asyncio.create_task(do_prediction())
    await monitor.register_task(process_id, task)

    # Wait for task to complete
    try:
        result = await task
        return result
    except asyncio.CancelledError:
        return {"status": "cancelled", "process_id": process_id}


async def get_model_predictions_history(
    model_id: str,
    days: int = 7
) -> List[Dict[str, Any]]:
    """
    Get historical predictions from a model

    Args:
        model_id: Model ID
        days: Number of days to retrieve

    Returns:
        List of prediction records
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        pred_dir = project_root / "predictions"

        if not pred_dir.exists():
            return []

        # Find all prediction files for this model
        pred_files = list(pred_dir.glob(f"{model_id}_*.json"))
        pred_files.sort(reverse=True)

        predictions = []
        for pred_file in pred_files[:days]:
            with open(pred_file) as f:
                pred_data = json.load(f)
                predictions.append(pred_data)

        return predictions

    except Exception as e:
        logger.error(f"Error loading prediction history: {e}")
        return []
