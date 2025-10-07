"""
Model training system supporting multiple ML algorithms
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from ..monitoring.process_monitor import monitor, ProcessStatus

logger = logging.getLogger(__name__)


async def train_model(
    dataset_ref: str,
    feature_set_ref: str,
    handler: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Train a model against dataset and feature set

    Args:
        dataset_ref: Dataset reference/path
        feature_set_ref: Feature set configuration reference
        handler: Model type (lightgbm, lstm, transformer, xgboost)
        params: Model-specific parameters

    Returns:
        Training result with model_id and metrics
    """
    # Generate process ID
    process_id = f"training_{uuid.uuid4().hex[:8]}"

    # Total steps: validation, init, model_gen, dataset_load, training, prediction, save, record
    total_steps = 8

    try:
        # Start process monitoring
        await monitor.start_process(process_id, "training", total_steps=total_steps)

        from qlib.workflow import R
        from qlib.workflow.record_temp import SignalRecord
        from qlib.utils import init_instance_by_config
        from ..utils.qlib_state import init_qlib_clean_async

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

        # Step 2: Initialize Qlib
        await monitor.update_progress(process_id, 25.0, f"Initializing Qlib with dataset '{dataset_ref}'", 2)

        # Initialize Qlib with clean cache (prevents state bleed)
        # Use async version for concurrency protection
        success = await init_qlib_clean_async(
            provider_uri=str(qlib_dir),
            region="cn",
            expression_cache=None,
            dataset_cache=None,
        )
        if not success:
            await monitor.fail_process(process_id, f"Failed to initialize qlib for dataset: {dataset_ref}")
            raise RuntimeError(f"Failed to initialize qlib for dataset: {dataset_ref}")

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
            from ..data_pipeline.features import get_alpha158_config
            handler_config = get_alpha158_config()

        # Get model configuration
        model_config = get_model_config(handler, params or {})

        # Define dataset configuration
        dataset_config = {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": handler_config,
                "segments": {
                    "train": ("2020-01-01", "2022-12-31"),
                    "valid": ("2023-01-01", "2023-06-30"),
                    "test": ("2023-07-01", "2024-12-31"),
                },
            },
        }

        # Step 4: Load dataset
        await monitor.update_progress(process_id, 50.0, f"Loading dataset '{dataset_ref}'", 4)

        # Initialize experiment
        with R.start(experiment_name=f"crypto_{handler}", recorder_name=model_id):
            # Initialize model
            model = init_instance_by_config(model_config)

            # Initialize dataset
            dataset = init_instance_by_config(dataset_config)

            # Step 5: Train model
            await monitor.update_progress(process_id, 62.5, f"Training {handler} model '{model_id}'", 5)

            # Train model
            logger.info(f"Training {handler} model: {model_id}")
            model.fit(dataset)

            # Step 6: Generate predictions
            await monitor.update_progress(process_id, 75.0, f"Generating predictions for validation", 6)

            # Make predictions
            predictions = model.predict(dataset)

            # Record signals
            sr = SignalRecord(model, dataset, recorder=R.get_recorder())
            sr.generate()

            # Step 7: Save model
            await monitor.update_progress(process_id, 87.5, f"Saving model to disk", 7)

            # Save model
            model_path = models_dir / f"{model_id}.pkl"
            import pickle
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)

            # Step 8: Record results
            await monitor.update_progress(process_id, 95.0, f"Recording training results", 8)

            # Get recorder info
            recorder_info = R.get_recorder().list_metrics()

            result = {
                "model_id": model_id,
                "handler": handler,
                "dataset": dataset_ref,
                "feature_set": feature_set_ref,
                "status": "completed",
                "model_path": str(model_path),
                "trained_at": datetime.now().isoformat(),
                "metrics": recorder_info,
                "params": params or {}
            }

            # Save training metadata
            meta_file = models_dir / f"{model_id}_meta.json"
            with open(meta_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)

            # Complete process monitoring
            await monitor.complete_process(process_id, result)

            logger.info(f"Model trained successfully: {model_id}")
            return result

    except Exception as e:
        logger.error(f"Error training model: {e}", exc_info=True)
        await monitor.fail_process(process_id, str(e))
        return {
            "error": str(e),
            "dataset": dataset_ref,
            "handler": handler,
            "status": "failed"
        }


def get_model_config(handler: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Get model configuration based on handler type"""

    configs = {
        "lightgbm": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
            "kwargs": {
                "loss": "mse",
                "colsample_bytree": 0.8879,
                "learning_rate": 0.0421,
                "subsample": 0.8789,
                "lambda_l1": 205.6999,
                "lambda_l2": 580.9768,
                "max_depth": 8,
                "num_leaves": 210,
                "num_threads": 20,
                **params
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
                **params
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
                "GPU": 0,
                **params
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
                "GPU": 0,
                **params
            },
        },
    }

    return configs.get(handler.lower(), configs["lightgbm"])
