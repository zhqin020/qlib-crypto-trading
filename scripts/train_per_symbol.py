#!/usr/bin/env python3
"""
Train Per-Symbol Models for Crypto
"""

import os
import asyncio
import sys
from pathlib import Path
import json
import argparse
from datetime import datetime

# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.1.0'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.trainer import train_model
from data_pipeline.features import create_feature_set

def load_config(config_path: Path = None):
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "trading_params.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

async def train_per_symbol(symbols, args, config):
    training_cfg = config.get("training", {})
    bt_cfg = config.get("backtest", {})
    data_cfg = config.get("data", {})
    
    interval = data_cfg.get("interval", "1h")
    market_type = data_cfg.get("market_type", "spot")
    mt_suffix = f"_{market_type}" if market_type != "spot" else ""
    dataset_ref = f"crypto_{interval}{mt_suffix}"
    
    # Use standard features (no embedding for per-symbol)
    feature_handler = training_cfg.get("feature_handler", "alpha158")
    feature_set_name = f"{feature_handler}_{dataset_ref}"
    
    print(f"Checking feature set: {feature_set_name}")
    # Ensure feature set exists
    await create_feature_set(dataset_ref=dataset_ref, handler=feature_handler, instrument_embedding=False)

    model_type = args.model
    model_params = training_cfg.get("models", {}).get(model_type, {}).copy()
    
    # Date segments
    bt_start = bt_cfg.get("start_time", "2024-05-03")
    bt_end = bt_cfg.get("end_time", "2025-01-01")
    
    results = {}
    
    for symbol in symbols:
        print(f"\n{'='*40}")
        print(f"🚀 Training model for {symbol}...")
        print(f"{'='*40}")
        
        # Clean symbol for Qlib
        qlib_symbol = symbol.split('/')[0]
        
        params = model_params.copy()
        params["instruments"] = [qlib_symbol]
        params["device"] = args.device
        
        # Add a hint in the model name/recorder if possible, 
        # but trainer.py generates its own model_id.
        # We'll rely on the meta.json mapping.
        
        try:
            result = await train_model(
                dataset_ref=dataset_ref,
                feature_set_ref=feature_set_name,
                handler=model_type,
                params=params,
                segments={
                    "train": [args.train_start, args.train_end],
                    "valid": [args.valid_start, args.valid_end],
                    "test": [bt_start, bt_end]
                }
            )
            
            if "error" in result:
                print(f"❌ Error training {symbol}: {result['error']}")
            else:
                print(f"✅ Trained {symbol}: {result['model_id']}")
                results[symbol] = result
        except Exception as e:
            print(f"💥 Exception training {symbol}: {e}")

    # Save summary mapping
    summary = {
        "timestamp": datetime.now().isoformat(),
        "model_type": model_type,
        "symbols": results
    }
    
    summary_file = Path(__file__).parent.parent / "models" / f"per_symbol_models_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n🎉 Per-symbol training complete. Summary saved to: {summary_file}")
    return summary_file

async def main():
    parser = argparse.ArgumentParser(description="Train per-symbol models")
    parser.add_argument("--model", default="alstm", choices=["lightgbm", "xgboost", "lstm", "alstm", "gru"])
    parser.add_argument("--symbols", default="BTC,ETH,SOL,AVAX,DOT", help="Comma separated symbols")
    parser.add_argument("--train-start", default="2023-05-10", help="Training period start date")
    parser.add_argument("--train-end", default="2023-11-06", help="Training period end date")
    parser.add_argument("--valid-start", default="2023-11-07", help="Validation period start date")
    parser.add_argument("--valid-end", default="2023-12-07", help="Validation period end date")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--config", default=None)
    
    args = parser.parse_args()
    config = load_config(Path(args.config) if args.config else None)
    
    symbols = [s.strip() for s in args.symbols.split(",")]
    await train_per_symbol(symbols, args, config)

if __name__ == "__main__":
    asyncio.run(main())
