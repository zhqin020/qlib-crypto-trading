#!/usr/bin/env python3
"""
Train a sample model
"""

import os
import asyncio
import sys
from pathlib import Path

# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.trainer import train_model
from data_pipeline.features import create_feature_set
import json


def load_config():
    """Load centralized trading parameters"""
    config_path = Path(__file__).parent.parent / "config" / "trading_params.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


async def main():
    """Train a sample LightGBM model"""

    print("Training sample model...")
    print()

    config = load_config()
    data_cfg = config.get("data", {})
    interval = data_cfg.get("interval", "1h")
    market_type = data_cfg.get("market_type", "spot")
    mt_suffix = f"_{market_type}" if market_type != "spot" else ""
    dataset_ref = f"crypto_{interval}{mt_suffix}"

    # Create feature set
    print(f"Creating feature set for {dataset_ref}...")
    feature_set = await create_feature_set(
        dataset_ref=dataset_ref,
        handler="alpha158"
    )
    print(f"Feature set created: {feature_set['name']}")
    print()

    config = load_config()
    data_cfg = config.get("data", {})
    bt_cfg = config.get("backtest", {})
    
    interval = data_cfg.get("interval", "1h")
    market_type = data_cfg.get("market_type", "spot")
    
    # Construct dataset_ref with market_type suffix if not spot
    mt_suffix = f"_{market_type}" if market_type != "spot" else ""
    dataset_ref = f"crypto_{interval}{mt_suffix}"

    # Train model
    print("Training LightGBM model...")
    
    # Use config end dates for segments if available
    bt_start = bt_cfg.get("start_time", "2024-11-01")
    bt_end = bt_cfg.get("end_time", "2024-12-25")
    
    result = await train_model(
        dataset_ref=dataset_ref,
        feature_set_ref=feature_set["name"],
        handler="lightgbm",
        params={},
        segments={
            "train": ["2024-03-01", "2024-08-31"],
            "valid": ["2024-09-01", "2024-10-31"],
            "test": [bt_start, bt_end]
        }
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print("\nModel Training Complete!")
    print(f"  Model ID: {result['model_id']}")
    print(f"  Handler: {result['handler']}")
    print(f"  Dataset: {result['dataset']}")
    print(f"  Model path: {result['model_path']}")
    print(f"  Trained at: {result['trained_at']}")

    print("\nNext steps:")
    print(f"  1. Run backtest: python scripts/run_backtest.py {result['model_id']}")
    print(f"  2. Generate predictions: python scripts/predict.py {result['model_id']}")


if __name__ == "__main__":
    asyncio.run(main())
