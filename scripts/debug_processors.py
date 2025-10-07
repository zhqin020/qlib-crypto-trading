#!/usr/bin/env python3
"""Debug what processors do to labels"""
import sys
import os
from pathlib import Path

os.environ['OMP_NUM_THREADS'] = '1'

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

if __name__ == '__main__':
    from utils.qlib_state import init_qlib_clean
    from qlib.data import D
    import numpy as np
    import pandas as pd

    # Initialize qlib with clean cache
    qlib_dir = project_root / "data" / "qlib" / "crypto_multi_3year"
    success = init_qlib_clean(provider_uri=str(qlib_dir), region="cn")
    if not success:
        print(f"Failed to initialize qlib for dataset: {qlib_dir}")
        sys.exit(1)

    # Get raw label data for all instruments
    instruments = ["BTC", "ETH", "BNB", "SOL", "XRP"]

    df_raw = D.features(
        instruments,
        ["Ref($close, -1) / $close - 1"],
        start_time="2022-01-01",
        end_time="2022-01-10"  # Just 10 days for debugging
    )

    print("RAW LABELS (before any processors):")
    print("=" * 60)
    print(df_raw)
    print(f"\nShape: {df_raw.shape}")
    print(f"Mean: {df_raw.mean().values[0]:.6f}")
    print(f"Std: {df_raw.std().values[0]:.6f}")
    print(f"NaN count: {df_raw.isna().sum().values[0]}")

    # Now apply RobustZScoreNorm to the labels
    print("\n\nAPPLYING RobustZScoreNorm:")
    print("=" * 60)

    from qlib.data.dataset.processor import RobustZScoreNorm

    # Get the label column name
    label_col = df_raw.columns[0]

    # Create processor
    proc = RobustZScoreNorm(fields_group="all", clip_outlier=True)

    # Fit and process
    proc.fit(df_raw)
    df_processed = proc(df_raw.copy())

    print(df_processed)
    print(f"\nShape: {df_processed.shape}")
    print(f"Mean: {df_processed.mean().values[0]:.6f}")
    print(f"Std: {df_processed.std().values[0]:.6f}")
    print(f"Unique values: {df_processed[label_col].nunique()}")

    # Check if all values are the same
    unique_vals = df_processed[label_col].dropna().unique()
    print(f"\nUnique label values after processing: {len(unique_vals)}")
    if len(unique_vals) <= 10:
        print(f"Values: {unique_vals}")
