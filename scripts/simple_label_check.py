#!/usr/bin/env python3
"""Simple label check using direct Qlib data loading - NO multiprocessing"""
import sys
import os
from pathlib import Path

# Disable multiprocessing for Alpha158 features
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

if __name__ == '__main__':
    from utils.qlib_state import init_qlib_clean
    from qlib.data import D

    # Initialize qlib with clean cache
    qlib_dir = project_root / "data" / "qlib" / "crypto_multi_3year"
    success = init_qlib_clean(provider_uri=str(qlib_dir), region="cn")
    if not success:
        print(f"Failed to initialize qlib for dataset: {qlib_dir}")
        sys.exit(1)

    # Load label expression directly
    instruments = ["BTC", "ETH", "BNB", "SOL", "XRP"]

    print("Checking raw label formula: Ref($close, -1) / $close - 1")
    print("=" * 60)

    for inst in instruments:
        # Load close prices
        df = D.features(
            [inst],
            ["$close", "Ref($close, -1)", "Ref($close, -1) / $close - 1"],
            start_time="2022-01-01",
            end_time="2022-01-31"
        )

        print(f"\n{inst} (Jan 2022 - first month):")
        print(df.head(10))

        # Calculate stats
        label_col = df.columns[2]  # "Ref($close, -1) / $close - 1"
        labels = df[label_col].dropna()

        if len(labels) > 0:
            print(f"\nStats for {inst}:")
            print(f"  Mean: {labels.mean():.6f}")
            print(f"  Std:  {labels.std():.6f}")
            print(f"  Min:  {labels.min():.6f}")
            print(f"  Max:  {labels.max():.6f}")
