#!/usr/bin/env python3
"""
Convert CSV data to Qlib format
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_pipeline.qlib_converter import convert_crypto_data


def main():
    """Convert CSV data to Qlib binary format"""

    print("Converting crypto data to Qlib format...")
    print()

    result = convert_crypto_data(
        csv_dir="data/raw",
        qlib_dir="data/qlib/crypto",
        freq="1d"
    )

    print("\nConversion Summary:")
    print(f"  Total files: {result['total_files']}")
    print(f"  Converted: {result['converted']}")
    print(f"  Failed: {result['failed']}")
    print(f"  Symbols: {', '.join(result['symbols'])}")
    print(f"  Output directory: {result['output_dir']}")
    print(f"  Calendar periods: {result['calendar_periods']}")

    if result['errors']:
        print("\nErrors:")
        for filename, error in result['errors']:
            print(f"  - {filename}: {error}")

    print("\nNext step:")
    print("  Train a model: python scripts/train_sample_model.py")


if __name__ == "__main__":
    main()
