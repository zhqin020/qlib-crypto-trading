#!/usr/bin/env python3
"""Check label distribution in the dataset"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from utils.qlib_state import init_qlib_clean
from qlib.utils import init_instance_by_config
import json
import numpy as np

# Initialize qlib with clean cache
qlib_dir = project_root / "data" / "qlib" / "crypto_multi_3year"
success = init_qlib_clean(provider_uri=str(qlib_dir), region="cn")
if not success:
    print(f"Failed to initialize qlib for dataset: {qlib_dir}")
    sys.exit(1)

# Load config - NO PROCESSORS
handler_config = {
    "class": "Alpha158",
    "module_path": "qlib.contrib.data.handler",
    "kwargs": {
        "start_time": "2022-01-01",
        "end_time": "2023-12-31",
        "fit_start_time": "2022-01-01",
        "fit_end_time": "2023-12-31",
        "instruments": "all",
        "infer_processors": [],  # NO PROCESSORS - check raw data
        "learn_processors": [],  # NO PROCESSORS
        "label": ["Ref($close, -1) / $close - 1"]
    }
}

handler = init_instance_by_config(handler_config)

# Get raw training data
from qlib.data.dataset import DatasetH

dataset_config = {
    "class": "DatasetH",
    "module_path": "qlib.data.dataset",
    "kwargs": {
        "handler": handler_config,
        "segments": {
            "train": ("2022-01-01", "2023-12-31"),
        },
    },
}

dataset = init_instance_by_config(dataset_config)
train_data = dataset.prepare("train")

print("=" * 60)
print("RAW TRAINING DATA (No Processors)")
print("=" * 60)
print(f"Shape: {train_data.shape}")
print(f"\nColumns: {train_data.columns.tolist()}")

# Get label column
label_col = [c for c in train_data.columns if 'LABEL' in str(c).upper()][0]
labels = train_data[label_col].dropna()

print(f"\nLabel column: {label_col}")
print(f"Total labels: {len(labels)}")
print(f"NaN labels: {train_data[label_col].isna().sum()}")
print(f"\nLabel Statistics:")
print(f"  Mean: {labels.mean():.6f}")
print(f"  Std:  {labels.std():.6f}")
print(f"  Min:  {labels.min():.6f}")
print(f"  Max:  {labels.max():.6f}")
print(f"  Unique values: {labels.nunique()}")

print(f"\nFirst 20 labels by asset:")
for asset in ['BTC', 'ETH', 'BNB', 'SOL', 'XRP']:
    asset_labels = train_data.loc[(slice(None), asset), label_col].head(10)
    if len(asset_labels) > 0:
        print(f"\n{asset}:")
        for idx, val in asset_labels.items():
            print(f"  {idx}: {val:.6f}")
