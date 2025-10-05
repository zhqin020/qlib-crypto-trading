#!/usr/bin/env python3
"""
Train a sample model
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.trainer import train_model
from data_pipeline.features import create_feature_set


async def main():
    """Train a sample LightGBM model"""

    print("Training sample model...")
    print()

    # Create feature set
    print("Creating feature set...")
    feature_set = await create_feature_set(
        dataset_ref="crypto",
        handler="alpha158"
    )
    print(f"Feature set created: {feature_set['name']}")
    print()

    # Train model
    print("Training LightGBM model...")
    result = await train_model(
        dataset_ref="crypto",
        feature_set_ref=feature_set["name"],
        handler="lightgbm",
        params={}
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
