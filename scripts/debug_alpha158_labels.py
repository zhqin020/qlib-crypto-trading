#!/usr/bin/env python3
"""Check what Alpha158 handler produces for labels"""
import sys
import os
from pathlib import Path

os.environ['OMP_NUM_THREADS'] = '1'

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

if __name__ == '__main__':
    from utils.qlib_state import init_qlib_clean
    from qlib.utils import init_instance_by_config
    import json

    # Initialize qlib with clean cache
    qlib_dir = project_root / "data" / "qlib" / "crypto_multi_3year"
    success = init_qlib_clean(provider_uri=str(qlib_dir), region="cn")
    if not success:
        print(f"Failed to initialize qlib for dataset: {qlib_dir}")
        sys.exit(1)

    # Create Alpha158 handler with NO processors
    handler_config = {
        "class": "Alpha158",
        "module_path": "qlib.contrib.data.handler",
        "kwargs": {
            "start_time": "2022-01-01",
            "end_time": "2023-12-31",
            "fit_start_time": "2022-01-01",
            "fit_end_time": "2023-12-31",
            "instruments": "all",
            "infer_processors": [
                {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
                {"class": "Fillna", "kwargs": {"fields_group": "feature"}}
            ],
            "learn_processors": [
                {"class": "DropnaLabel"}
            ],
            "label": ["Ref($close, -1) / $close - 1"]
        }
    }

    handler = init_instance_by_config(handler_config)

    # Get dataset segments
    from qlib.data.dataset import DatasetH

    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": handler_config,
            "segments": {
                "train": ("2022-01-01", "2023-12-31"),  # FULL 2 years
            },
        },
    }

    dataset = init_instance_by_config(dataset_config)
    train_data = dataset.prepare("train")

    print("=" * 60)
    print("ALPHA158 OUTPUT (WITH PROCESSORS)")
    print("=" * 60)
    print(f"Shape: {train_data.shape}")
    print(f"\nAll columns:")
    print(train_data.columns.tolist())

    # Get label column - it's the last column
    label_col = train_data.columns[-1]

    print(f"\nLabel column: {label_col}")
    print(f"Label shape: {train_data[label_col].shape}")
    print(f"NaN count: {train_data[label_col].isna().sum()}")

    labels = train_data[label_col].dropna()
    print(f"\nNon-NaN labels: {len(labels)}")
    print(f"Mean: {labels.mean():.6f}")
    print(f"Std: {labels.std():.6f}")
    print(f"Min: {labels.min():.6f}")
    print(f"Max: {labels.max():.6f}")
    print(f"Unique values: {labels.nunique()}")

    print(f"\nFirst 20 labels:")
    print(labels.head(20))

    # Check by instrument
    print(f"\n\nBy instrument:")
    for inst in ['BTC', 'ETH', 'BNB', 'SOL', 'XRP']:
        inst_labels = train_data.loc[(slice(None), inst), label_col].dropna()
        if len(inst_labels) > 0:
            print(f"{inst}: {len(inst_labels)} samples, mean={inst_labels.mean():.6f}, std={inst_labels.std():.6f}")

    # Check feature variance
    print(f"\n\nFeature Statistics:")
    feature_cols = [c for c in train_data.columns if c != label_col]
    feature_data = train_data[feature_cols]

    print(f"Feature columns: {len(feature_cols)}")
    print(f"Features with 0 std: {(feature_data.std() == 0).sum()}")
    print(f"Features with NaN std: {feature_data.std().isna().sum()}")

    # Show constant features
    zero_std_features = feature_data.columns[feature_data.std() == 0].tolist()
    print(f"\nConstant features (std=0): {zero_std_features}")

    # Sample a few features to see their values
    print(f"\nSample feature values (first 10 rows, first 5 features):")
    print(feature_data.iloc[:10, :5])
