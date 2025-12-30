#!/usr/bin/env python3
"""
Convert CSV data to Qlib format
"""

import os
import sys
from pathlib import Path

# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_pipeline.official_qlib_converter import convert_crypto_data_official


import argparse
import json


def load_config():
    """Load centralized trading parameters"""
    config_path = Path(__file__).parent.parent / "config" / "trading_params.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

def main():
    """Convert CSV data to Qlib binary format"""

    config = load_config()
    data_cfg = config.get("data", {})
    default_freq = data_cfg.get("interval", "1d")

    parser = argparse.ArgumentParser(description="Convert CSV data to Qlib binary format")
    parser.add_argument("--freq", default=default_freq, help="Data frequency (1d, 1h, etc.)")
    parser.add_argument("--market-type", default=data_cfg.get("market_type", "spot"), help="Market type (spot, future, etc.)")
    
    args = parser.parse_args()
    
    qlib_dir_suffix = f"_{args.market_type}" if args.market_type != "spot" else ""
    qlib_dir = f"data/qlib/crypto_{args.freq}{qlib_dir_suffix}"
    
    # Allow override via cmd line
    parser.add_argument("--qlib_dir", default=qlib_dir, help="Output directory for Qlib data")
    # Re-parse to pick up qlib_dir if provided
    args = parser.parse_args()

    print(f"Converting crypto data to Qlib format (freq={args.freq}, market_type={args.market_type})...")
    print()

    result = convert_crypto_data_official(
        csv_dir="data/raw",
        qlib_dir=args.qlib_dir,
        freq=args.freq,
        market_type=args.market_type
    )

    print("\nConversion Summary:")
    print(f"  Status: {result.get('status', 'unknown')}")
    print(f"  Total files: {result.get('total_files', 'unknown')}")
    print(f"  Converted symbols: {', '.join(result.get('converted_symbols', []))}")
    print(f"  Output directory: {result.get('output_dir', 'unknown')}")

    if result.get('stderr'):
        print("\nOutput:")
        print(result.get('stderr', ''))

    print("\nNext step:")
    print("  Train a model: python scripts/train_sample_model.py")


if __name__ == "__main__":
    main()
