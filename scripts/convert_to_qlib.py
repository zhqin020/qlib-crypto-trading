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

def main():
    """Convert CSV data to Qlib binary format"""

    parser = argparse.ArgumentParser(description="Convert CSV data to Qlib binary format")
    parser.add_argument("--freq", default="1d", help="Data frequency (1d, 1h, etc.)")
    parser.add_argument("--qlib_dir", default="data/qlib/crypto", help="Output directory for Qlib data")
    args = parser.parse_args()

    print(f"Converting crypto data to Qlib format (freq={args.freq})...")
    print()

    result = convert_crypto_data_official(
        csv_dir="data/raw",
        qlib_dir=args.qlib_dir,
        freq=args.freq
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
