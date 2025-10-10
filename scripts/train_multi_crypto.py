#!/usr/bin/env python3
"""
Train a multi-asset crypto trading model using LightGBM
Standalone script to avoid multiprocessing issues with stdin
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import qlib
from qlib.workflow import R
from qlib.utils import init_instance_by_config
from qlib.workflow.record_temp import SignalRecord
import json
import pickle
from datetime import datetime
import uuid

def main():
    # Setup paths
    dataset_ref = "crypto_multi_3year"
    dataset_dir = project_root / "data" / "qlib" / dataset_ref
    models_dir = project_root / "models" / "trained"
    models_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Qlib cleanly
    from utils.qlib_state import init_qlib_clean
    from data_pipeline.crypto_calendar_provider import register_crypto_calendar

    print("🔧 Initializing Qlib...")
    register_crypto_calendar()
    init_qlib_clean(
        provider_uri={"day": str(dataset_dir), "1d": str(dataset_dir)},
        region="cn"
    )
    print("✅ Qlib initialized")

    # Generate model ID
    model_id = f"lightgbm_multi_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    print(f"📝 Model ID: {model_id}")

    # Load feature config with CSRankNorm (for multi-asset)
    config_file = project_root / "config" / "features" / "alpha158_crypto_3year.json"
    with open(config_file) as f:
        feature_config = json.load(f)

    # Remove CSRankNorm - it's causing all labels to be identical
    # CSRankNorm does cross-sectional ranking which doesn't work well for our use case
    feature_config["config"]["kwargs"]["learn_processors"] = [
        {"class": "DropnaLabel"}
    ]

    handler_config = feature_config["config"]
    handler_config["kwargs"]["fit_start_time"] = "2022-01-01"
    handler_config["kwargs"]["fit_end_time"] = "2023-12-31"

    # Model config - SINGLE THREADED to avoid multiprocessing issues
    model_config = {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "num_boost_round": 1000,
            "early_stopping_rounds": 50,
            "colsample_bytree": 0.8879,
            "learning_rate": 0.0421,
            "subsample": 0.8789,
            "lambda_l1": 205.6999,
            "lambda_l2": 580.9768,
            "max_depth": 8,
            "num_leaves": 210,
            "num_threads": 1,  # SINGLE THREAD - avoid multiprocessing issues
            "verbose": 100,
        },
    }

    # Dataset config
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": handler_config,
            "segments": {
                "train": ("2022-01-01", "2023-12-31"),  # 2 years training
                "valid": ("2024-01-01", "2024-06-30"),  # 6 months validation
                "test": ("2024-07-01", "2024-12-31"),   # 6 months test
            },
        },
    }

    print("🏋️  Training Multi-Asset LightGBM Model...")
    print("📊 Assets: BTC, ETH, BNB, SOL, XRP (5 cryptos)")
    print("📅 Training: 2022-2023 (2 years)")
    print("📅 Validation: 2024 H1")
    print("📅 Test: 2024 H2")
    print()

    # Train with MLflow tracking
    with R.start(experiment_name="crypto_multi_lightgbm", recorder_name=model_id):
        # Initialize
        model = init_instance_by_config(model_config)
        dataset = init_instance_by_config(dataset_config)

        # Check data
        train_data = dataset.prepare("train")
        print(f"✅ Training samples: {train_data.shape[0]}")
        print(f"✅ Features: {train_data.shape[1] - 1}")  # -1 for label
        print()

        # Train
        print("🔄 Training in progress...")
        model.fit(dataset)

        # Get results
        num_trees = model.model.num_trees()
        print(f"\n✅ Training complete!")
        print(f"🌳 Number of trees: {num_trees}")

        # Make predictions
        predictions = model.predict(dataset)

        # Record signals
        sr = SignalRecord(model, dataset, recorder=R.get_recorder())
        sr.generate()

        # Save model
        model_path = models_dir / f"{model_id}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)

        # Get metrics
        recorder_info = R.get_recorder().list_metrics()

        # Save metadata
        result = {
            "model_id": model_id,
            "handler": "lightgbm",
            "dataset": dataset_ref,
            "assets": ["BTC", "ETH", "BNB", "SOL", "XRP"],
            "num_assets": 5,
            "status": "completed",
            "num_trees": num_trees,
            "metrics": recorder_info,
            "trained_at": datetime.now().isoformat(),
        }

        meta_file = models_dir / f"{model_id}_meta.json"
        with open(meta_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n💾 Model saved: {model_path}")
        print(f"📄 Metadata saved: {meta_file}")

        # Success check
        if num_trees >= 100:
            print(f"\n🎉 SUCCESS! Model trained with {num_trees} boosting rounds")
            print(f"📈 Ready for backtesting on 5 cryptocurrencies")
            return 0
        elif num_trees > 10:
            print(f"\n⚠️  Model has {num_trees} trees (early stopped)")
            return 0
        else:
            print(f"\n❌ Training failed: only {num_trees} tree(s)")
            return 1

if __name__ == "__main__":
    sys.exit(main())
