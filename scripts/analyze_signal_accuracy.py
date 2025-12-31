#!/usr/bin/env python3
"""
Analyze signal accuracy and prediction vs actual return relationship.
Helps understand if Sharpe < 0 is due to noise or model failure.
"""

import os
# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import qlib
from qlib.data import D
from qlib.utils import init_instance_by_config
from pathlib import Path
import json
import argparse
from datetime import datetime
import pickle

def load_config():
    with open("config/trading_params.json", "r") as f:
        return json.load(f)

def analyze_signals(start_time, end_time, model_path=None):
    config = load_config()
    data_path = "data/qlib/crypto_1h_future"
    
    # Initialize Qlib
    qlib.init(provider_uri=data_path, region="cn")
    
    # Get latest model if not provided
    if model_path is None:
        model_dir = Path("models/trained")
        model_files = sorted(model_dir.glob("alstm_*.pkl"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not model_files:
            print("No model found in models/trained")
            return
        model_path = model_files[0]
    
    print(f"Loading model: {model_path}")
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    
    # Prepare Dataset config (Alpha158)
    ds_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": "2023-01-01",
                    "end_time": end_time,
                    "fit_start_time": "2023-01-01",
                    "fit_end_time": "2024-01-01",
                    "instruments": "all",
                    "freq": "60min",
                },
            },
            "segments": {
                "test": [start_time, end_time],
            },
        },
    }
    
    dataset = init_instance_by_config(ds_config)
    test_df = dataset.prepare("test", col_set=["feature", "label"])
    
    if test_df.empty:
        print("Dataset is empty for the given period.")
        return

    features = test_df["feature"]
    labels = test_df["label"].iloc[:, 0]
    
    # DEBUG: Check features
    print(f"Total records: {len(test_df)}")
    print(f"Feature columns: {len(features.columns)}")
    print(f"Features NaN ratio: {features.isna().mean().mean():.2%}")
    
    # Fill NaNs - Crucial for RNNs!
    features_filled = features.fillna(0)
    
    print("Generating predictions...")
    # We can't easily replace features inside 'dataset' and call 'model.predict(dataset)'
    # because 'model.predict' inside Qlib usually calls 'dataset.prepare' again.
    # Instead, we'll try to use 'model.predict' on the DataFrame directly if the model supports it,
    # or manually prepare the data if we can.
    
    # For ALSTM (and most Qlib models), model.predict(dataset) is the standard way.
    # Let's hope the fillna(0) isn't needed if we provide enough lookback,
    # OR we try to predict on the filled features if we can bypass dataset.
    
    try:
        # Standard Qlib predict
        predictions = model.predict(dataset)
    except Exception as e:
        print(f"Prediction failed: {e}")
        return

    print(f"Predictions head:\n{predictions.head()}")
    print(f"Predictions tail:\n{predictions.tail()}")
    
    # Alignment
    df = pd.DataFrame({
        "pred": predictions,
        "actual": labels
    }).dropna()
    
    print(f"Valid records for analysis (after dropna): {len(df)}")
    
    if df.empty:
        print("ERROR: No valid aligned records found. All predictions or actuals were NaN.")
        return
        
    # Analysis
    ic = df["pred"].corr(df["actual"])
    rank_ic = df["pred"].corr(df["actual"], method="spearman")
    
    print(f"\n--- Signal Analysis [{start_time} to {end_time}] ---")
    print(f"Correlation (IC): {ic:.4f}")
    print(f"Rank Correlation (Rank IC): {rank_ic:.4f}")
    
    # Precision Analysis
    thresholds = [0.0, 0.1, 0.2, 0.3, 0.5]
    print("\nAccuracies by Threshold:")
    print("Threshold | Direction | Accuracy | Count | Avg Return")
    print("-" * 60)
    
    for t in thresholds:
        for side in ["Long", "Short"]:
            if side == "Long":
                sigs = df[df["pred"] > t]
                hit = (sigs["actual"] > 0).mean() if not sigs.empty else np.nan
            else:
                sigs = df[df["pred"] < -t]
                hit = (sigs["actual"] < 0).mean() if not sigs.empty else np.nan
                
            if not sigs.empty:
                avg_ret = sigs["actual"].mean()
                print(f"{t:<9} | {side:<9} | {hit:.2%}  | {len(sigs):<5} | {avg_ret:.4f}")

    # Visualization
    plt.figure(figsize=(15, 6))
    
    # 1. Scatter
    plt.subplot(1, 2, 1)
    plt.scatter(df["pred"], df["actual"], alpha=0.3, s=15, c=np.sign(df["actual"]), cmap="RdYlGn")
    plt.axhline(0, color='black', lw=1, alpha=0.5)
    plt.axvline(0, color='black', lw=1, alpha=0.5)
    plt.xlabel("Predicted Score")
    plt.ylabel("Actual Return")
    plt.title(f"Prediction vs Actual\nIC: {ic:.4f}, Rank IC: {rank_ic:.4f}")
    
    # 2. Score Hist
    plt.subplot(1, 2, 2)
    df["pred"].hist(bins=50, color='skyblue', edgecolor='black', alpha=0.7)
    plt.axvline(0, color='red', linestyle='--')
    plt.xlabel("Predicted Score")
    plt.ylabel("Frequency")
    plt.title(f"Score Distribution (N={len(df)})")
    
    log_file = f"logs/signal_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(log_file)
    plt.close()
    print(f"\nAnalysis plot saved to: {log_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-06-09", help="Start date")
    parser.add_argument("--end", default="2024-08-08", help="End date")
    parser.add_argument("--model", default=None, help="Path to model")
    args = parser.parse_args()
    analyze_signals(args.start, args.end, args.model)
