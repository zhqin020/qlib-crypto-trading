#!/usr/bin/env python3
"""
Generate predictions using a trained model
"""

import os
import asyncio
import sys
from pathlib import Path

# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from serving.predictor import predict_today


async def main():
    """Generate predictions"""

    if len(sys.argv) < 2:
        print("Usage: python predict.py <model_id>")
        sys.exit(1)

    model_id = sys.argv[1]

    print(f"Generating predictions for model: {model_id}")
    print()

    result = await predict_today(
        model_id=model_id,
        dataset_ref="crypto"
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print(f"\nPredictions for {result['prediction_date']}:")
    print(f"Total symbols analyzed: {result['total_symbols']}")
    print()
    print("Top 10 Signals:")
    print(f"{'Rank':<6} {'Symbol':<15} {'Score':<10}")
    print("-" * 35)

    for pred in result['predictions'][:10]:
        print(f"{pred['rank']:<6} {pred['symbol']:<15} {pred['score']:<10.4f}")


if __name__ == "__main__":
    asyncio.run(main())
