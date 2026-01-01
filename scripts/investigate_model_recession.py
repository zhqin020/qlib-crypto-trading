#!/usr/bin/env python3
"""
Investigation Script: Model Recession Analysis
analyzes the performance of the best model (Trial 56) across different valid/test periods
to identify market regimes where the strategy fails.
"""

import subprocess
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path
import re
import json

CONFIG_PATH = "config/trial_56.json"
MODEL_TYPE = "alstm"
TRAIN_START = "2023-01-01"
TRAIN_END = "2024-01-01"  # Train on 1 year
FULL_TEST_START = "2024-01-01"
FULL_TEST_END = "2025-01-01"

def run_cmd(cmd):
    """Run command and return output"""
    print(f"[EXEC] {cmd}")
    process = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return process.stdout, process.returncode

def parse_metrics(output):
    """Extract metrics from backtest output."""
    metrics = {
        "Annualized Return": "N/A",
        "Sharpe Ratio": "N/A",
        "Max Drawdown": "N/A",
        "Win Rate": "N/A"
    }
    
    ar_match = re.search(r"Annualized Return:\s*([-\d.]+)%", output)
    if ar_match: metrics["Annualized Return"] = ar_match.group(1) + "%"
    
    sr_match = re.search(r"Sharpe Ratio:\s*([-\d.]+)", output)
    if sr_match: metrics["Sharpe Ratio"] = sr_match.group(1)
    
    mdd_match = re.search(r"Max Drawdown:\s*([-\d.]+)%", output)
    if mdd_match: metrics["Max Drawdown"] = mdd_match.group(1) + "%"
    
    wr_match = re.search(r"Win Rate:\s*([-\d.]+)%", output)
    if wr_match: metrics["Win Rate"] = wr_match.group(1) + "%"
    
    return metrics

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, help="Skip training and use existing model ID")
    parser.add_argument("--skip-train", action="store_true", help="Skip training phase")
    args = parser.parse_args()

    print("🚀 Starting Model Recession Investigation...")
    
    model_id = args.model
    
    # 1. Train the Model (if needed)
    if not model_id and not args.skip_train:
        print("\n--- Phase 1: Training Model (Trial 56 Params) ---")
        train_cmd = (f"{sys.executable} scripts/train_sample_model.py --config {CONFIG_PATH} "
                     f"--model {MODEL_TYPE} "
                     f"--train-start {TRAIN_START} --train-end {TRAIN_END} "
                     f"--valid-start {FULL_TEST_START} --valid-end {FULL_TEST_END}") 
        
        out, rc = run_cmd(train_cmd)
        if rc != 0:
            print("❌ Training failed!")
            print(out)
            sys.exit(1)
            
        # Extract Model ID
        model_id_match = re.search(r"Model saved to .*?/(alstm_.*?).pkl", out)
        if not model_id_match:
            print("⚠️ Could not parse model ID from output, finding latest...")
            models_dir = Path("models/trained")
            candidates = list(models_dir.glob(f"{MODEL_TYPE}_*.pkl"))
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            model_id = candidates[0].stem
        else:
            model_id = model_id_match.group(1)
        print(f"✅ Model Trained: {model_id}")
    elif not model_id:
         # Find latest if skipping train
        models_dir = Path("models/trained")
        candidates = list(models_dir.glob(f"{MODEL_TYPE}_*.pkl"))
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        model_id = candidates[0].stem
        print(f"✅ Using Latest Model: {model_id}")

    
    # 2. Segmented Backtesting
    print("\n--- Phase 2: Segmented Backtesting (Quarterly) ---")
    
    segments = [
        ("Q1 2024", "2024-01-01", "2024-03-31"),
        ("Q2 2024", "2024-04-01", "2024-06-30"),
        ("Q3 2024", "2024-07-01", "2024-09-30"),
        ("Q4 2024", "2024-10-01", "2024-12-31"),
    ]
    
    results = []
    
    for name, start, end in segments:
        print(f"Testing {name} ({start} -> {end})...")
        bt_cmd = (f"{sys.executable} scripts/run_backtest.py {model_id} --config {CONFIG_PATH} "
                  f"--start {start} --end {end}")
        
        out, rc = run_cmd(bt_cmd)
        if rc != 0:
            print(f"❌ Backtest failed for {name}")
            continue
            
        metrics = parse_metrics(out)
        metrics["Period"] = name
        results.append(metrics)
    
    # 3. Report
    print("\n" + "="*60)
    print(f"📊 INVESTIGATION REPORT: Trial 56 Analysis")
    print(f"Model ID: {model_id}")
    print("="*60)
    
    df = pd.DataFrame(results)
    # Reorder columns
    cols = ["Period", "Annualized Return", "Sharpe Ratio", "Max Drawdown", "Win Rate"]
    df = df[cols]
    
    # Use to_string() instead of to_markdown() to avoid tabulate dependency
    print(df.to_string(index=False))
    print("="*60)
    
    # Detect Recession
    print("\n🔍 FINDINGS:")
    for _, row in df.iterrows():
        try:
            ar_str = row['Annualized Return'].replace('%', '')
            if ar_str == "N/A": continue
            ar = float(ar_str)
            
            if ar < 0:
                print(f" - ⚠️ NEGATIVE PERFORMANCE in {row['Period']} (Return: {row['Annualized Return']})")
                print(f"   Potential Cause: Bear/Chop regime mismatch.")
        except Exception as e:
            print(f"Error parsing row: {e}")

if __name__ == "__main__":
    main()
