"""
Real-time prediction service
"""

import logging
import json
import pickle
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


async def predict_today(model_id: str, dataset_ref: str) -> Dict[str, Any]:
    """
    Generate predictions for current trading session

    Args:
        model_id: Trained model ID
        dataset_ref: Dataset reference

    Returns:
        Predictions with confidence scores
    """
    try:
        from qlib.data.dataset import DatasetH
        from qlib.utils import init_instance_by_config
        from ..utils.qlib_state import init_qlib_clean

        project_root = Path(__file__).parent.parent.parent
        models_dir = project_root / "models" / "trained"
        qlib_dir = project_root / "data" / "qlib" / dataset_ref

        # Validate dataset exists
        if not qlib_dir.exists():
            logger.error(f"Dataset directory not found: {qlib_dir}")
            return {
                "error": f"Dataset '{dataset_ref}' not found at {qlib_dir}",
                "status": "failed",
                "dataset": dataset_ref,
                "model_id": model_id
            }

        # Validate dataset has required structure
        if not (qlib_dir / "calendars").exists() and not (qlib_dir / "instruments").exists():
            logger.error(f"Dataset directory exists but appears empty: {qlib_dir}")
            return {
                "error": f"Dataset '{dataset_ref}' appears to be empty or invalid",
                "status": "failed",
                "dataset": dataset_ref,
                "model_id": model_id
            }

        # Initialize Qlib with clean cache (prevents state bleed)
        success = init_qlib_clean(
            provider_uri=str(qlib_dir),
            region="cn",
            auto_mount=True
        )
        if not success:
            raise RuntimeError(f"Failed to initialize qlib for predictions: {model_id}")

        # Load model
        model_path = models_dir / f"{model_id}.pkl"
        if not model_path.exists():
            return {"error": f"Model {model_id} not found"}

        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        # Load model metadata
        meta_file = models_dir / f"{model_id}_meta.json"
        with open(meta_file) as f:
            model_meta = json.load(f)

        # Get latest data for prediction
        today = datetime.now().strftime("%Y-%m-%d")

        # Load feature configuration
        config_dir = project_root / "config" / "features"
        feature_set_ref = model_meta.get("feature_set", "alpha158_crypto")
        feature_config_file = config_dir / f"{feature_set_ref}.json"

        if feature_config_file.exists():
            with open(feature_config_file) as f:
                feature_config = json.load(f)
            handler_config = feature_config["config"]
        else:
            from ..data_pipeline.features import get_alpha158_config
            handler_config = get_alpha158_config()

        # Update handler config for today's data
        handler_config["kwargs"]["start_time"] = today
        handler_config["kwargs"]["end_time"] = today

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

        dataset = init_instance_by_config(dataset_config)

        # Make predictions
        logger.info(f"Generating predictions for {today} using model {model_id}")
        predictions = model.predict(dataset)

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

        # Save predictions
        pred_dir = project_root / "predictions"
        pred_dir.mkdir(parents=True, exist_ok=True)

        pred_file = pred_dir / f"{model_id}_{today}.json"
        with open(pred_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        logger.info(f"Generated {len(top_predictions)} predictions for {today}")
        return result

    except Exception as e:
        logger.error(f"Error generating predictions: {e}", exc_info=True)
        return {
            "error": str(e),
            "model_id": model_id,
            "status": "failed"
        }


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
