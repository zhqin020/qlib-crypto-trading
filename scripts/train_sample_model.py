#!/usr/bin/env python3
"""
Train a sample model
"""

import os
import asyncio
import sys
from pathlib import Path
import json
import argparse

# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.trainer import train_model
from data_pipeline.features import create_feature_set


def load_config(config_path: Path = None):
    """Load centralized trading parameters.
    If config_path is provided, use it; otherwise default to config/trading_params.json.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "trading_params.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


async def main():
    """Train a sample model"""

    # First pass: parse only --config to load defaults
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("--config", default=None)
    conf_args, _ = conf_parser.parse_known_args()
    
    config = load_config(Path(conf_args.config) if conf_args.config else None)
    
    # Load default model from config
    training_cfg = config.get("training", {})
    default_model = training_cfg.get("model_type", "lightgbm")
    
    parser = argparse.ArgumentParser(
        description="Train a machine learning model for crypto price prediction",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--model", default=default_model, choices=["lightgbm", "xgboost", "lstm", "transformer", "alstm", "gru"], help="Model architecture type")
    parser.add_argument("--config", default=None, help="Path to custom configuration JSON file")
    parser.add_argument("--embedding", action="store_true", help="Enable instrument embedding (append HashInstrumentProcessor)")
    
    # Date segments
    parser.add_argument("--train-start", default="2023-05-10", help="Training period start date")
    parser.add_argument("--train-end", default="2023-11-06", help="Training period end date")
    parser.add_argument("--valid-start", default="2023-11-07", help="Validation period start date")
    parser.add_argument("--valid-end", default="2023-12-07", help="Validation period end date")
    
    # Hardware
    parser.add_argument("--device", default="auto", help="Execution device: auto, cpu, cuda, or cuda:N")
    
    args = parser.parse_args()
    
    model_type = args.model
    # Re-load config in case it changed (though it shouldn't have from the first pass)
    config = load_config(Path(args.config) if args.config else None)
    
    print(f"Training sample model with {model_type}...")
    if args.embedding:
        print("  -> Instrument Embedding Enabled")
    print()

    data_cfg = config.get("data", {})
    bt_cfg = config.get("backtest", {})
    training_cfg = config.get("training", {})
    
    interval = data_cfg.get("interval", "1h")
    market_type = data_cfg.get("market_type", "spot")
    mt_suffix = f"_{market_type}" if market_type != "spot" else ""
    dataset_ref = f"crypto_{interval}{mt_suffix}"

    # Create feature set
    print(f"Creating feature set for {dataset_ref}...")
    feature_set = await create_feature_set(
        dataset_ref=dataset_ref,
        handler=training_cfg.get("feature_handler", "alpha158"),
        instrument_embedding=args.embedding
    )
    print(f"Feature set created: {feature_set['name']}")
    print()

    # Prepare training parameters
    # 1. Get model-specific parameters
    model_params = training_cfg.get("models", {}).get(model_type, {})
    
    # 2. Start with a copy of these params
    params = model_params.copy()
    
    # 3. Add global training options (excluding structural keys)
    for k, v in training_cfg.items():
        if k not in ["model_type", "feature_handler", "models"]:
            params[k] = v
            
    # Ensure device is set
    params["device"] = args.device

    # Update params for embedding
    if args.embedding:
        if "d_feat" in params:
            params["d_feat"] = int(params["d_feat"]) + 1
        params["use_embedding"] = True
        # For LightGBM/XGBoost - categorical features
        # The ID is the last feature (index 158 if 0-based and orig size is 158)
        # But d_feat is size. so last index is d_feat - 1 (after increment)
        if model_type in ["lightgbm", "xgboost"]:
             # Assuming standard 158 features, the new one is at index 158.
             # We should probably get d_feat or assume 158.
             # LightGBM expects `categorical_feature`
             # We can handle this logic in trainer.py or here.
             # Let's just set the flag here.
             pass

    # Train model
    print(f"Training {model_type} model...")
    
    # Use config end dates for segments if available
    bt_start = bt_cfg.get("start_time", "2024-11-01")
    bt_end = bt_cfg.get("end_time", "2024-12-25")
    
    result = await train_model(
        dataset_ref=dataset_ref,
        feature_set_ref=feature_set["name"],
        handler=model_type,
        params=params,
        segments={
            "train": [args.train_start, args.train_end],
            "valid": [args.valid_start, args.valid_end],
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
