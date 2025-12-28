"""
Experiment management and recipe execution
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

# Global experiment registry
EXPERIMENTS_DB = {}


async def run_recipe(
    dataset: str,
    recipe: str,
    costs: str,
    rebalance: str,
    topk: int = 10,
    long_short: bool = False,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute an experiment recipe

    Args:
        dataset: Dataset name
        recipe: Recipe name (beginner_lightgbm, expert_ensemble, etc.)
        costs: Transaction costs level (low, medium, high)
        rebalance: Rebalancing frequency (weekly, monthly)
        params: Additional parameters

    Returns:
        Experiment results
    """
    try:
        from models.trainer import train_model
        from backtesting.engine import run_backtest

        run_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        logger.info(f"Starting experiment {run_id}: {recipe}")

        # Get recipe configuration
        recipe_config = get_recipe_config(recipe)

        # Merge custom params
        if params:
            recipe_config.update(params)

        # Create feature set for this experiment
        from data_pipeline.features import create_feature_set

        feature_handler = recipe_config.get("feature_handler", "alpha158")
        feature_set = await create_feature_set(
            dataset_ref=dataset,
            handler=feature_handler,
            params=recipe_config.get("feature_params", {})
        )

        # Train model(s)
        models = []
        for model_spec in recipe_config.get("models", [{"handler": "lightgbm"}]):
            model_result = await train_model(
                dataset_ref=dataset,
                feature_set_ref=feature_set["name"],
                handler=model_spec["handler"],
                params=model_spec.get("params", {}),
                segments=recipe_config.get("segments"),
            )
            models.append(model_result)

        # Run backtests
        backtest_results = []
        for model in models:
            if "model_id" in model:
                bt_result = await run_backtest(
                    model_id=model["model_id"],
                    dataset_ref=dataset,
                    costs=costs,
                    rebalance=rebalance,
                    funding=recipe_config.get("funding", False),
                    topk=topk,
                    long_short=long_short,
                    start_time=recipe_config.get("start_time"),
                    end_time=recipe_config.get("end_time"),
                    benchmark=recipe_config.get("benchmark"),
                )
                backtest_results.append(bt_result)

        # Aggregate results
        experiment_result = {
            "run_id": run_id,
            "recipe": recipe,
            "dataset": dataset,
            "costs": costs,
            "rebalance": rebalance,
            "status": "completed",
            "started_at": datetime.now().isoformat(),
            "models": models,
            "backtests": backtest_results,
            "tags": ["candidate"],
            "config": recipe_config
        }

        # Save experiment
        EXPERIMENTS_DB[run_id] = experiment_result

        project_root = Path(__file__).parent.parent.parent
        exp_dir = project_root / "experiments"
        exp_dir.mkdir(parents=True, exist_ok=True)

        exp_file = exp_dir / f"{run_id}.json"
        with open(exp_file, 'w') as f:
            json.dump(experiment_result, f, indent=2, default=str)

        logger.info(f"Experiment completed: {run_id}")
        return experiment_result

    except Exception as e:
        logger.error(f"Error running experiment: {e}", exc_info=True)
        return {
            "error": str(e),
            "run_id": run_id if 'run_id' in locals() else None,
            "status": "failed"
        }


async def tag_run(run_id: str, tags: List[str]) -> Dict[str, Any]:
    """
    Assign lifecycle tags to an experiment run

    Args:
        run_id: Experiment run ID
        tags: Tags to assign (candidate, promoted, archived)

    Returns:
        Updated experiment metadata
    """
    try:
        # Load experiment
        project_root = Path(__file__).parent.parent.parent
        exp_file = project_root / "experiments" / f"{run_id}.json"

        if not exp_file.exists():
            if run_id in EXPERIMENTS_DB:
                experiment = EXPERIMENTS_DB[run_id]
            else:
                return {"error": f"Experiment {run_id} not found"}
        else:
            with open(exp_file) as f:
                experiment = json.load(f)

        # Update tags
        experiment["tags"] = tags
        experiment["tagged_at"] = datetime.now().isoformat()

        # Save
        with open(exp_file, 'w') as f:
            json.dump(experiment, f, indent=2, default=str)

        EXPERIMENTS_DB[run_id] = experiment

        logger.info(f"Tagged experiment {run_id}: {tags}")
        return experiment

    except Exception as e:
        logger.error(f"Error tagging experiment: {e}", exc_info=True)
        return {"error": str(e), "run_id": run_id}


async def cancel_run(run_id: str, reason: str = "") -> Dict[str, Any]:
    """
    Cancel a running experiment

    Args:
        run_id: Experiment run ID
        reason: Cancellation reason

    Returns:
        Cancellation status
    """
    try:
        if run_id in EXPERIMENTS_DB:
            experiment = EXPERIMENTS_DB[run_id]
            experiment["status"] = "cancelled"
            experiment["cancelled_at"] = datetime.now().isoformat()
            experiment["cancel_reason"] = reason

            logger.info(f"Cancelled experiment {run_id}: {reason}")
            return experiment
        else:
            return {"error": f"Experiment {run_id} not found or not running"}

    except Exception as e:
        logger.error(f"Error cancelling experiment: {e}", exc_info=True)
        return {"error": str(e), "run_id": run_id}


def get_recipe_config(recipe: str) -> Dict[str, Any]:
    """Get predefined recipe configuration"""

    recipes = {
        "beginner_lightgbm": {
            "feature_handler": "alpha158",
            "models": [
                {"handler": "lightgbm", "params": {}}
            ],
            "description": "Simple LightGBM model with Alpha158 features"
        },
        "beginner_xgboost": {
            "feature_handler": "alpha158",
            "models": [
                {"handler": "xgboost", "params": {}}
            ],
            "description": "Simple XGBoost model with Alpha158 features"
        },
        "advanced_lstm": {
            "feature_handler": "alpha158",
            "models": [
                {"handler": "lstm", "params": {"hidden_size": 128, "num_layers": 3}}
            ],
            "description": "LSTM model for time series prediction"
        },
        "advanced_transformer": {
            "feature_handler": "alpha158",
            "models": [
                {"handler": "transformer", "params": {"d_model": 128, "nhead": 8}}
            ],
            "description": "Transformer model with attention mechanism"
        },
        "expert_ensemble": {
            "feature_handler": "alpha158",
            "models": [
                {"handler": "lightgbm", "params": {}},
                {"handler": "xgboost", "params": {}},
                {"handler": "lstm", "params": {}}
            ],
            "description": "Ensemble of multiple models"
        },
        "intraday_alpha360": {
            "feature_handler": "alpha360",
            "models": [
                {"handler": "lightgbm", "params": {"learning_rate": 0.01}}
            ],
            "description": "Intraday trading with Alpha360 features"
        }
    }

    return recipes.get(recipe, recipes["beginner_lightgbm"])
