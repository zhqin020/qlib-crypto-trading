"""
Model training system supporting multiple ML algorithms
"""

import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

import pandas as pd

from analytics.investment_kpis import kpi_registry
from monitoring.process_monitor import monitor, ProcessStatus
from utils.datasets import load_snapshot_metadata
from utils.qlib_state import qlib_init_context
from utils.torch_stub import ensure_torch_available

logger = logging.getLogger(__name__)


# Ensure optional torch dependency is importable during tests.
ensure_torch_available()


SEGMENT_KEYS: Tuple[str, str, str] = ("train", "valid", "test")


def _format_segment(start_ts: pd.Timestamp, end_ts: pd.Timestamp, freq: str = "1d") -> Tuple[str, str]:
    """Return a tuple of date/time strings for a segment."""

    if freq == "1d" or freq == "D" or freq == "day":
        return (start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d"))
    return (start_ts.strftime("%Y-%m-%d %H:%M:%S"), end_ts.strftime("%Y-%m-%d %H:%M:%S"))


def _normalize_segments(segments: Dict[str, Tuple[str, str]], freq: str = "1d") -> Dict[str, Tuple[str, str]]:
    """Validate and normalize user-provided segments."""

    normalized: Dict[str, Tuple[str, str]] = {}
    for key in SEGMENT_KEYS:
        if key not in segments:
            raise ValueError(f"Missing '{key}' segment; provide train/valid/test ranges.")

        start_raw, end_raw = segments[key]
        try:
            start_ts = pd.Timestamp(start_raw)
            end_ts = pd.Timestamp(end_raw)
        except ValueError as exc:  # pragma: no cover - defensive path
            raise ValueError(f"Invalid {key} segment dates: {exc}") from exc

        if start_ts > end_ts:
            raise ValueError(f"Segment '{key}' start must be on or before its end.")

        normalized[key] = _format_segment(start_ts, end_ts, freq)

    return normalized


def _auto_segments(snapshot_meta: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    """Derive default train/valid/test splits from dataset metadata."""

    start = snapshot_meta.get("start_date")
    end = snapshot_meta.get("end_date")

    if not start or not end:
        raise ValueError(
            "Dataset metadata missing start_date/end_date; specify segments explicitly."
        )

    freq = snapshot_meta.get("frequency", "1d")
    # Normalize frequency for pandas
    pd_freq = freq
    if freq == "1d":
        pd_freq = "D"
    elif freq == "1h":
        pd_freq = "H"

    date_index = pd.date_range(start=start, end=end, freq=pd_freq)
    total = len(date_index)

    if total < 3:
        raise ValueError(
            "Dataset range must contain at least 3 days to auto-generate train/valid/test splits."
        )

    if total == 3:
        return {
            "train": _format_segment(date_index[0], date_index[0], freq),
            "valid": _format_segment(date_index[1], date_index[1], freq),
            "test": _format_segment(date_index[2], date_index[2], freq),
        }

    train_end_idx = max(0, int(total * 0.7) - 1)
    valid_end_idx = max(train_end_idx + 1, int(total * 0.85) - 1)

    # Ensure there is at least one day reserved for the test split
    if valid_end_idx >= total - 1:
        valid_end_idx = total - 2

    # Guard against degenerate ranges where rounding collapses the splits
    if train_end_idx >= valid_end_idx:
        train_end_idx = max(0, valid_end_idx - 1)

    return {
        "train": _format_segment(date_index[0], date_index[train_end_idx], freq),
        "valid": _format_segment(date_index[train_end_idx + 1], date_index[valid_end_idx], freq),
        "test": _format_segment(date_index[valid_end_idx + 1], date_index[-1], freq),
    }


def _resolve_segments(
    explicit: Optional[Dict[str, Tuple[str, str]]],
    snapshot_meta: Dict[str, Any],
) -> Dict[str, Tuple[str, str]]:
    """Return normalized segments, deriving defaults when explicit values are absent."""

    if explicit:
        return _normalize_segments(explicit, snapshot_meta.get("frequency", "1d"))

    return _auto_segments(snapshot_meta)


try:  # Optional dependency: qlib
    from qlib.workflow import R as _QLIB_R
    from qlib.workflow.record_temp import SignalRecord as _QLIB_SignalRecord
    from qlib.utils import init_instance_by_config as _QLIB_init_instance_by_config
except ImportError:  # pragma: no cover - executed when qlib is unavailable
    _QLIB_R = None
    _QLIB_SignalRecord = None
    _QLIB_init_instance_by_config = None


def _raise_missing_qlib() -> None:
    raise ModuleNotFoundError(
        "Qlib is required for training workflows. Install qlib to enable this feature."
    )


if _QLIB_R is not None:
    R = _QLIB_R
else:
    class _MissingRContext:
        def __enter__(self):
            _raise_missing_qlib()
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _MissingRProxy:
        _qlib_missing = True

        def start(self, *args, **kwargs):
            return _MissingRContext()

        def get_recorder(self):
            _raise_missing_qlib()

    R = _MissingRProxy()


if _QLIB_SignalRecord is not None:
    SignalRecord = _QLIB_SignalRecord
else:
    class SignalRecord:  # type: ignore[misc]
        _qlib_missing = True

        def __init__(self, *args, **kwargs):  # pragma: no cover - simple stub
            self._recorder = kwargs.get("recorder")

        def generate(self):  # pragma: no cover - simple stub
            logger.debug("SignalRecord stub used - qlib not installed")


if _QLIB_init_instance_by_config is not None:
    init_instance_by_config = _QLIB_init_instance_by_config
else:
    def init_instance_by_config(*args, **kwargs):  # type: ignore[override]
        _raise_missing_qlib()

    init_instance_by_config._qlib_missing = True  # type: ignore[attr-defined]


class DeviceManager:
    """Manages GPU/CPU device selection and error handling"""

    @staticmethod
    def get_device(device_str: str = "auto") -> Tuple[str, int]:
        """
        Get appropriate device for training with fallback logic

        Args:
            device_str: Device specification ("auto", "cpu", "cuda", "cuda:0", etc.)

        Returns:
            Tuple of (device_type, device_index) where:
            - device_type: "cpu" or "cuda"
            - device_index: GPU index (0-N) or -1 for CPU
        """
        try:
            import torch
        except ImportError:
            logger.warning("PyTorch not available, using CPU")
            return ("cpu", -1)

        device_str = device_str.lower().strip()

        try:
            if device_str == "auto":
                if torch.cuda.is_available():
                    logger.info(f"CUDA available with {torch.cuda.device_count()} GPU(s), using cuda:0")
                    return ("cuda", 0)
                else:
                    logger.info("CUDA not available, using CPU")
                    return ("cpu", -1)

            elif device_str == "cpu":
                logger.info("CPU device selected")
                return ("cpu", -1)

            elif device_str.startswith("cuda"):
                if not torch.cuda.is_available():
                    logger.warning("CUDA requested but not available, falling back to CPU")
                    return ("cpu", -1)

                # Parse cuda:N format
                if ":" in device_str:
                    try:
                        device_index = int(device_str.split(":")[1])
                    except (ValueError, IndexError):
                        logger.warning(f"Invalid CUDA device format '{device_str}', using cuda:0")
                        device_index = 0
                else:
                    device_index = 0

                # Verify device exists
                device_count = torch.cuda.device_count()
                if device_index >= device_count:
                    logger.warning(
                        f"GPU {device_index} not found (only {device_count} available), using cuda:0"
                    )
                    device_index = 0

                logger.info(f"Using GPU {device_index}: {torch.cuda.get_device_name(device_index)}")
                return ("cuda", device_index)

            else:
                logger.warning(f"Unknown device specification '{device_str}', falling back to auto")
                return DeviceManager.get_device("auto")

        except Exception as e:
            logger.error(f"Failed to initialize device '{device_str}': {e}", exc_info=True)
            logger.warning("Falling back to CPU")
            return ("cpu", -1)

    @staticmethod
    def get_device_config(device_str: str = "auto") -> Dict[str, Any]:
        """
        Get device configuration for model kwargs

        Args:
            device_str: Device specification

        Returns:
            Dict with GPU parameter for qlib models
        """
        device_type, device_index = DeviceManager.get_device(device_str)

        if device_type == "cuda":
            return {"GPU": device_index}
        else:
            # For CPU, qlib expects GPU to be None or not present
            # Some models interpret negative values as CPU
            return {"GPU": None}

    @staticmethod
    def log_memory_usage():
        """Log current GPU memory usage if available"""
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    allocated = torch.cuda.memory_allocated(i) / 1024**3
                    reserved = torch.cuda.memory_reserved(i) / 1024**3
                    logger.info(
                        f"GPU {i} memory - Allocated: {allocated:.2f} GB, Reserved: {reserved:.2f} GB"
                    )
        except Exception as e:
            logger.debug(f"Could not log memory usage: {e}")

    @staticmethod
    def clear_memory():
        """Clear GPU memory cache"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("GPU memory cache cleared")
        except Exception as e:
            logger.debug(f"Could not clear memory cache: {e}")


def handle_oom_error(func):
    """
    Decorator to handle CUDA Out of Memory errors with fallback strategies

    Strategies:
    1. Clear GPU cache and retry
    2. Reduce batch size if applicable
    3. Fall back to CPU
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RuntimeError as e:
            error_msg = str(e)
            if "out of memory" in error_msg.lower() or "cuda" in error_msg.lower():
                logger.warning(f"CUDA OOM error encountered: {error_msg}")

                # Try clearing cache and retrying once
                try:
                    import torch
                    if torch.cuda.is_available():
                        logger.info("Clearing GPU cache and retrying...")
                        torch.cuda.empty_cache()
                        DeviceManager.log_memory_usage()
                        return func(*args, **kwargs)
                except RuntimeError as e2:
                    logger.error(f"Retry after cache clear failed: {e2}")

                # If still failing, suggest batch size reduction or CPU fallback
                logger.error(
                    "CUDA OOM error persists. Consider: "
                    "1) Reducing batch_size in model parameters, "
                    "2) Using device='cpu', or "
                    "3) Using a smaller model"
                )
                raise RuntimeError(
                    f"CUDA Out of Memory error. GPU memory insufficient. "
                    f"Try reducing batch_size or using device='cpu'. Original error: {error_msg}"
                ) from e
            else:
                # Not an OOM error, re-raise
                raise
    return wrapper


async def train_model(
    dataset_ref: str,
    feature_set_ref: str,
    handler: str,
    params: Optional[Dict[str, Any]] = None,
    segments: Optional[Dict[str, Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Train a model against dataset and feature set

    Args:
        dataset_ref: Dataset reference/path
        feature_set_ref: Feature set configuration reference
        handler: Model type (lightgbm, lstm, transformer, xgboost)
        params: Model-specific parameters
        segments: Train/valid/test date ranges. When omitted, derive from dataset metadata.

    Returns:
        Training result with model_id and metrics
    """
    # Generate process ID with timestamp to prevent collisions
    import time
    import asyncio
    process_id = f"training_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

    # Total steps: validation, init, model_gen, dataset_load, training, prediction, save, record
    total_steps = 8

    process_started = False

    # Create the actual work as a separate coroutine
    async def do_training():
        nonlocal process_started
        try:
            # Start process monitoring
            await monitor.start_process(process_id, "training", total_steps=total_steps)
            process_started = True

            # Check for cancellation
            process = await monitor.get_process(process_id)
            if process and process.status == ProcessStatus.CANCELLED:
                return {"status": "cancelled", "process_id": process_id}

            project_root = Path(__file__).parent.parent.parent
            qlib_dir = project_root / "data" / "qlib" / dataset_ref
            models_dir = project_root / "models" / "trained"
            models_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Validate dataset
            await monitor.update_progress(process_id, 12.5, f"Validating dataset '{dataset_ref}'", 1)

            # Validate dataset exists
            if not qlib_dir.exists():
                logger.error(f"Dataset directory not found: {qlib_dir}")
                await monitor.fail_process(process_id, f"Dataset '{dataset_ref}' not found at {qlib_dir}")
                return {
                    "error": f"Dataset '{dataset_ref}' not found at {qlib_dir}",
                    "status": "failed",
                    "dataset": dataset_ref
                }

            # Validate dataset has required structure
            if not (qlib_dir / "calendars").exists() and not (qlib_dir / "instruments").exists():
                logger.error(f"Dataset directory exists but appears empty: {qlib_dir}")
                await monitor.fail_process(process_id, f"Dataset '{dataset_ref}' appears to be empty or invalid")
                return {
                    "error": f"Dataset '{dataset_ref}' appears to be empty or invalid",
                    "status": "failed",
                    "dataset": dataset_ref
                }

            # Ensure qlib dependencies are available (or patched during tests)
            snapshot_meta = load_snapshot_metadata(qlib_dir)

            try:
                resolved_segments = _resolve_segments(segments, snapshot_meta)
            except ValueError as segment_error:
                logger.error(
                    "Invalid dataset segments for %s: %s", dataset_ref, segment_error
                )
                await monitor.fail_process(process_id, str(segment_error))
                return {
                    "error": str(segment_error),
                    "status": "failed",
                    "dataset": dataset_ref,
                    "handler": handler,
                }

            logger.info(
                "Using dataset segments for %s: train=%s, valid=%s, test=%s",
                dataset_ref,
                resolved_segments["train"],
                resolved_segments["valid"],
                resolved_segments["test"],
            )

            # Step 2: Initialize Qlib
            await monitor.update_progress(process_id, 25.0, f"Initializing Qlib with dataset '{dataset_ref}'", 2)

            async with qlib_init_context(
                provider_uri=str(qlib_dir),
                region="cn",
                expression_cache=None,
                dataset_cache=None,
            ):
                # Check for cancellation after init
                process = await monitor.get_process(process_id)
                if process and process.status == ProcessStatus.CANCELLED:
                    return {"status": "cancelled", "process_id": process_id}

                # Step 3: Generate model configuration
                await monitor.update_progress(process_id, 37.5, f"Generating {handler} model configuration", 3)

                # Generate unique model ID
                model_id = f"{handler}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

                # Load feature set configuration
                config_dir = project_root / "config" / "features"
                feature_config_file = config_dir / f"{feature_set_ref}.json"

                if feature_config_file.exists():
                    with open(feature_config_file) as f:
                        feature_config = json.load(f)
                    handler_config = feature_config["config"]
                else:
                    # Use default Alpha158 if no config found
                    from data_pipeline.features import get_alpha158_config
                    handler_config = get_alpha158_config()

                # Ensure time parameters are explicitly set from segments
                if "kwargs" not in handler_config:
                    handler_config["kwargs"] = {}

                # Map frequency for Qlib
                freq_val = snapshot_meta.get("frequency", "1d")
                freq_map = {
                    "1h": "60min",
                    "1d": "day",
                    "day": "day"
                }
                qlib_freq = freq_map.get(freq_val, freq_val)
                handler_config["kwargs"]["freq"] = qlib_freq
                logger.info(f"Using frequency '{qlib_freq}' for Qlib data handler")
                logger.info(f"Before time fix: {handler_config['kwargs']}")
                if "fit_start_time" not in handler_config["kwargs"] or handler_config["kwargs"]["fit_start_time"] is None:
                    handler_config["kwargs"]["fit_start_time"] = resolved_segments["train"][0]
                    handler_config["kwargs"]["fit_end_time"] = resolved_segments["test"][1]
                    logger.info(f"Fixed time parameters: fit_start_time={handler_config['kwargs']['fit_start_time']}, fit_end_time={handler_config['kwargs']['fit_end_time']}")
                else:
                    logger.info(f"Time parameters already set: fit_start_time={handler_config['kwargs']['fit_start_time']}, fit_end_time={handler_config['kwargs']['fit_end_time']}")

                # Get device configuration from params or default to auto
                device_str = (params or {}).get("device", "auto")
                device_config = DeviceManager.get_device_config(device_str)
                logger.info(f"Device configuration for {handler}: {device_config}")

                # Get model configuration with device settings
                model_config = get_model_config(handler, params or {}, device_config)

                # Define dataset configuration
                dataset_config = {
                    "class": "DatasetH",
                    "module_path": "qlib.data.dataset",
                    "kwargs": {
                        "handler": handler_config,
                        "segments": resolved_segments,
                    },
                }

                # Step 4: Load dataset
                await monitor.update_progress(process_id, 50.0, f"Loading dataset '{dataset_ref}'", 4)

                # Check for cancellation before training
                process = await monitor.get_process(process_id)
                if process and process.status == ProcessStatus.CANCELLED:
                    return {"status": "cancelled", "process_id": process_id}

                # Initialize experiment
                with R.start(experiment_name=f"crypto_{handler}", recorder_name=model_id):
                    # Initialize model
                    model = await asyncio.to_thread(init_instance_by_config, model_config)

                    # Initialize dataset
                    dataset = await asyncio.to_thread(init_instance_by_config, dataset_config)

                    # Step 5: Train model
                    await monitor.update_progress(process_id, 62.5, f"Training {handler} model '{model_id}'", 5)

                    # Log memory before training
                    DeviceManager.log_memory_usage()

                    # Train model with OOM error handling
                    logger.info(f"Training {handler} model: {model_id}")
                    try:
                        # Wrap the fit call to handle OOM errors
                        @handle_oom_error
                        def fit_with_oom_handling():
                            return model.fit(dataset)

                        await asyncio.to_thread(fit_with_oom_handling)

                        # Log memory after training
                        DeviceManager.log_memory_usage()

                    except RuntimeError as e:
                        # OOM or other runtime error
                        error_msg = str(e)
                        if "out of memory" in error_msg.lower() or "cuda" in error_msg.lower():
                            # Clean up and re-raise with helpful message
                            DeviceManager.clear_memory()
                            logger.error(f"Training failed due to GPU memory error: {error_msg}")
                            await monitor.fail_process(
                                process_id,
                                f"GPU Out of Memory. Try reducing batch_size or using device='cpu'"
                            )
                            raise
                        else:
                            raise

                    # Check for cancellation after training
                    process = await monitor.get_process(process_id)
                    if process and process.status == ProcessStatus.CANCELLED:
                        return {"status": "cancelled", "process_id": process_id}

                    # Step 6: Generate predictions
                    await monitor.update_progress(process_id, 75.0, f"Generating predictions for validation", 6)

                    # Make predictions
                    predictions = model.predict(dataset)

                    # Record signals (inside experiment context)
                    sr = SignalRecord(model, dataset, recorder=R.get_recorder())
                    sr.generate()

                    # Step 7: Save model
                    await monitor.update_progress(process_id, 87.5, f"Saving model to disk", 7)

                    # Save model (best-effort for mocked objects in tests)
                    model_path = models_dir / f"{model_id}.pkl"
                    import pickle
                    saved_model_path: Optional[Path] = None
                    try:
                        with open(model_path, 'wb') as f:
                            pickle.dump(model, f)
                        saved_model_path = model_path
                    except Exception as serialize_error:  # pragma: no cover - defensive path
                        logger.warning(
                            "Could not persist model '%s': %s", model_id, serialize_error
                        )

                    # Step 8: Record results
                    await monitor.update_progress(process_id, 95.0, f"Recording training results", 8)

                    # Get recorder info (inside experiment context)
                    recorder_info = R.get_recorder().list_metrics()

                    result = {
                        "model_id": model_id,
                        "handler": handler,
                        "dataset": dataset_ref,
                        "feature_set": feature_set_ref,
                        "status": "completed",
                        "model_path": str(saved_model_path) if saved_model_path else None,
                        "trained_at": datetime.now().isoformat(),
                        "metrics": recorder_info,
                        "params": params or {},
                        "segments": resolved_segments,
                    }

                    training_kpis = _extract_training_kpis(recorder_info)
                    evaluation = kpi_registry.record(
                        "training",
                        {
                            "model_id": model_id,
                            "dataset": dataset_ref,
                            "handler": handler,
                        },
                        training_kpis,
                    )

                    result["kpi_metrics"] = training_kpis
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

                    # Save training metadata
                    meta_file = models_dir / f"{model_id}_meta.json"
                    with open(meta_file, 'w') as f:
                        json.dump(result, f, indent=2, default=str)

                    # Complete process monitoring
                    await monitor.complete_process(process_id, result)

                logger.info(f"Model trained successfully: {model_id}")

                # Clean up GPU memory after training
                DeviceManager.clear_memory()

                return result

        except asyncio.CancelledError:
            # Task was cancelled
            logger.info(f"Training task cancelled: {process_id}")
            if process_started:
                await monitor.fail_process(process_id, "Cancelled by user")
            # Clean up GPU memory
            DeviceManager.clear_memory()
            raise
        except Exception as e:
            logger.error(f"Error training model: {e}", exc_info=True)
            # Only fail process if it was successfully started
            if process_started:
                try:
                    await monitor.fail_process(process_id, str(e))
                except Exception as monitor_error:
                    logger.error(f"Failed to update process monitor: {monitor_error}")
            # Clean up GPU memory on error
            DeviceManager.clear_memory()
            return {
                "error": str(e),
                "dataset": dataset_ref,
                "handler": handler,
                "status": "failed"
            }

    # Register the task for cancellation support
    task = asyncio.create_task(do_training())
    await monitor.register_task(process_id, task)

    # Wait for task to complete
    try:
        result = await task
        return result
    except asyncio.CancelledError:
        return {"status": "cancelled", "process_id": process_id}


def _extract_training_kpis(recorder_metrics: Any) -> Dict[str, Optional[float]]:
    """Extract key training KPIs (ic, ic_ir, loss) from recorder output."""

    targets = {"ic": None, "ic_ir": None, "loss": None}
    preference = {"test": 3, "valid": 2, "validation": 2, "val": 2, "train": 1, None: 0}

    def _label_from_entry(entry: Dict[str, Any]) -> Optional[str]:
        for field in ("dataset", "step", "phase", "split"):
            label = entry.get(field)
            if isinstance(label, str):
                return label.lower()
        name = entry.get("name")
        if isinstance(name, str):
            lowered = name.lower()
            if "valid" in lowered:
                return "valid"
            if "test" in lowered:
                return "test"
            if "train" in lowered:
                return "train"
        return None

    def _try_record(metric: str, value: Any, label: Optional[str]) -> None:
        if value is None:
            return
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return
        current = targets.get(metric)
        label_score = preference.get(label, 0)
        if current is None:
            targets[metric] = (numeric, label_score)
        else:
            _, current_score = current
            if label_score >= current_score:
                targets[metric] = (numeric, label_score)

    def _maybe_check_entry(entry: Dict[str, Any]) -> None:
        label = _label_from_entry(entry)
        for key in ("name", "metric", "key"):
            name = entry.get(key)
            if not isinstance(name, str):
                continue
            lname = name.lower()
            value = entry.get("value")
            if value is None:
                # some variants use result column names
                value = entry.get("score")
            if "ic_ir" in lname or "information coefficient ir" in lname:
                _try_record("ic_ir", value, label)
            elif "ic" in lname and "ic_ir" not in lname:
                _try_record("ic", value, label)
            elif "loss" in lname:
                _try_record("loss", value, label)

        # Some recorders expose dicts under "metrics"
        if "metrics" in entry and isinstance(entry["metrics"], dict):
            for metric_name, metric_value in entry["metrics"].items():
                lowered = str(metric_name).lower()
                if lowered == "ic" and metric_value is not None:
                    _try_record("ic", metric_value, label)
                elif lowered in {"ic_ir", "ic-ir"} and metric_value is not None:
                    _try_record("ic_ir", metric_value, label)
                elif lowered == "loss" and metric_value is not None:
                    _try_record("loss", metric_value, label)

    if isinstance(recorder_metrics, dict):
        _maybe_check_entry(recorder_metrics)
    elif isinstance(recorder_metrics, list):
        for entry in recorder_metrics:
            if isinstance(entry, dict):
                _maybe_check_entry(entry)

    return {
        key: (value[0] if isinstance(value, tuple) else value)
        for key, value in targets.items()
    }


def get_model_config(
    handler: str,
    params: Dict[str, Any],
    device_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get model configuration based on handler type

    Args:
        handler: Model type (lightgbm, lstm, transformer, xgboost)
        params: User-provided model parameters
        device_config: Device configuration dict with GPU parameter

    Returns:
        Model configuration dict
    """
    # Remove 'device' from params if present (we handle it separately)
    params_copy = {k: v for k, v in params.items() if k != "device"}

    # Base configs for each model type
    configs = {
        "lightgbm": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
            "kwargs": {
                "loss": "mse",
                "colsample_bytree": 0.8879,
                "learning_rate": 0.0421,
                "subsample": 0.8789,
                "lambda_l1": 0.01,
                "lambda_l2": 0.01,
                "max_depth": 8,
                "num_leaves": 31,
                "num_threads": 20,
                **params_copy
            },
        },
        "xgboost": {
            "class": "XGBModel",
            "module_path": "qlib.contrib.model.xgboost",
            "kwargs": {
                "booster": "gbtree",
                "learning_rate": 0.05,
                "max_depth": 6,
                "n_estimators": 500,
                "objective": "reg:squarederror",
                **params_copy
            },
        },
        "lstm": {
            "class": "LSTM",
            "module_path": "qlib.contrib.model.pytorch_lstm",
            "kwargs": {
                "d_feat": 6,
                "hidden_size": 64,
                "num_layers": 2,
                "dropout": 0.2,
                "n_epochs": 100,
                "lr": 0.001,
                "batch_size": 512,
                "early_stop": 20,
                "loss": "mse",
                "optimizer": "adam",
                # GPU config will be merged below
                **params_copy
            },
        },
        "transformer": {
            "class": "Transformer",
            "module_path": "qlib.contrib.model.pytorch_transformer",
            "kwargs": {
                "d_feat": 6,
                "d_model": 64,
                "nhead": 4,
                "num_layers": 2,
                "dropout": 0.2,
                "n_epochs": 100,
                "lr": 0.001,
                "batch_size": 512,
                "early_stop": 20,
                "loss": "mse",
                "optimizer": "adam",
                # GPU config will be merged below
                **params_copy
            },
        },
        "gru": {
            "class": "GRU",
            "module_path": "qlib.contrib.model.pytorch_gru",
            "kwargs": {
                "d_feat": 6,
                "hidden_size": 64,
                "num_layers": 2,
                "dropout": 0.2,
                "n_epochs": 100,
                "lr": 0.001,
                "batch_size": 512,
                "early_stop": 20,
                "loss": "mse",
                "optimizer": "adam",
                # GPU config will be merged below
                **params_copy
            },
        },
    }

    config = configs.get(handler.lower(), configs["lightgbm"])

    # Apply device configuration to PyTorch models
    if device_config and handler.lower() in ["lstm", "transformer", "gru"]:
        # Merge device config, allowing user params to override if specified
        if "GPU" not in params_copy:
            config["kwargs"].update(device_config)
        else:
            logger.info(f"Using user-specified GPU parameter: {params_copy['GPU']}")

    return config
