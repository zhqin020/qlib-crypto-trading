"""
Feature set creation and management
Supports Alpha158, Alpha360, and custom feature sets
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from .validation import (
    validate_dataset_name,
    validate_handler,
    ValidationError
)

logger = logging.getLogger(__name__)


# Alpha158 features configuration
ALPHA158_FIELDS = [
    "$close", "$open", "$high", "$low", "$volume",
    "$vwap",  # Volume weighted average price
]

ALPHA158_LABELS = ["Ref($close, -1) / $close - 1"]


def get_alpha158_config() -> Dict[str, Any]:
    """Get Alpha158 feature configuration"""
    return {
        "class": "Alpha158",
        "module_path": "qlib.contrib.data.handler",
        "kwargs": {
            "start_time": None,
            "end_time": None,
            "fit_start_time": None,
            "fit_end_time": None,
            "instruments": "all",
            "infer_processors": [
                {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
                {"class": "Fillna", "kwargs": {"fields_group": "feature"}}
            ],
            "learn_processors": [
                {"class": "DropnaLabel"},
                {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}}
            ],
            "label": ALPHA158_LABELS
        }
    }


def get_alpha360_config() -> Dict[str, Any]:
    """Get Alpha360 feature configuration (for intraday)"""
    return {
        "class": "Alpha360",
        "module_path": "qlib.contrib.data.handler",
        "kwargs": {
            "start_time": None,
            "end_time": None,
            "fit_start_time": None,
            "fit_end_time": None,
            "instruments": "all",
            "infer_processors": [
                {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
                {"class": "Fillna", "kwargs": {"fields_group": "feature"}}
            ],
            "learn_processors": [
                {"class": "DropnaLabel"},
                {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}}
            ]
        }
    }


async def create_feature_set(
    dataset_ref: str,
    handler: str,
    params: Optional[Dict[str, Any]] = None,
    processors: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Create a feature set configuration

    Args:
        dataset_ref: Reference to dataset
        handler: Handler type (alpha158, alpha360, custom)
        params: Custom parameters for handler
        processors: Data processors to apply

    Returns:
        Feature set metadata

    Raises:
        ValidationError: If input validation fails
    """
    try:
        # Validate inputs
        dataset_ref = validate_dataset_name(dataset_ref)
        handler = validate_handler(handler)

        # Validate params if provided
        if params is not None and not isinstance(params, dict):
            raise ValidationError("Parameters must be a dictionary")

        # Validate processors if provided
        if processors is not None:
            if not isinstance(processors, list):
                raise ValidationError("Processors must be a list")
            if len(processors) > 50:
                raise ValidationError("Too many processors (max 50)")
            for processor in processors:
                if not isinstance(processor, dict):
                    raise ValidationError("Each processor must be a dictionary")

        logger.info(f"Creating feature set: dataset={dataset_ref}, handler={handler}")

        project_root = Path(__file__).parent.parent.parent
        config_dir = project_root / "config" / "features"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Select base configuration
        if handler.lower() == "alpha158":
            config = get_alpha158_config()
        elif handler.lower() == "alpha360":
            config = get_alpha360_config()
        else:
            # Custom handler
            config = {
                "class": handler,
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {}
            }

        # Merge custom parameters
        if params:
            config["kwargs"].update(params)

        # Override processors if provided
        if processors:
            config["kwargs"]["infer_processors"] = processors

        # Create feature set metadata
        feature_set = {
            "name": f"{handler}_{dataset_ref}",
            "dataset": dataset_ref,
            "handler": handler,
            "config": config,
            "created_at": str(pd.Timestamp.now()),
            "status": "ready"
        }

        # Save configuration
        config_file = config_dir / f"{feature_set['name']}.json"
        with open(config_file, 'w') as f:
            json.dump(feature_set, f, indent=2)

        logger.info(f"Feature set created: {feature_set['name']}")
        return feature_set

    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        return {"error": f"Invalid input: {str(e)}", "dataset": dataset_ref}
    except Exception as e:
        logger.error(f"Error creating feature set: {e}", exc_info=True)
        return {"error": str(e), "dataset": dataset_ref}


# For the import at top of file
import pandas as pd
