#!/usr/bin/env python3
"""
Train precision-tuned crypto models based on research findings
Goal: Build simple but effective crypto trading models that exceed baseline
Target: Sharpe ratio >2.0, Max Drawdown <15%
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.trainer import train_model


async def train_crypto_optimized_models():
    """Train all precision-tuned crypto models"""

    # Load crypto-specific configurations
    config_file = Path(__file__).parent.parent / "config" / "crypto_model_tuning.json"
    with open(config_file) as f:
        config = json.load(f)

    results = []

    print("\n" + "="*80)
    print("TRAINING PRECISION-TUNED CRYPTO MODELS")
    print("Goal: Sharpe Ratio >2.0, Max Drawdown <15%")
    print("="*80 + "\n")

    # Train Tier 1 models (proven for crypto)
    tier_1_models = [
        ("lightgbm", config["precision_tuned_models"]["lightgbm_crypto_optimized"]),
        ("lstm", config["precision_tuned_models"]["lstm_crypto_optimized"]),
        ("gru", config["precision_tuned_models"]["gru_crypto_optimized"]),
        ("xgboost", config["precision_tuned_models"]["xgboost_crypto_optimized"]),
    ]

    for model_name, model_config in tier_1_models:
        print(f"\n{'='*80}")
        print(f"Training: {model_name.upper()}")
        print(f"Description: {model_config['description']}")
        print(f"{'='*80}\n")

        try:
            result = await train_model(
                dataset_ref="crypto_btc_daily",
                feature_set_ref="alpha158",
                handler=model_config["model_type"],
                params=model_config["params"]
            )

            if "error" in result:
                print(f"❌ FAILED: {result['error']}\n")
                results.append({
                    "model": model_name,
                    "status": "failed",
                    "error": result['error']
                })
            else:
                print(f"✅ SUCCESS: {result['model_id']}")
                print(f"   Metrics: {result.get('metrics', 'N/A')}\n")
                results.append({
                    "model": model_name,
                    "status": "success",
                    "model_id": result['model_id'],
                    "metrics": result.get('metrics', {})
                })

        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)}\n")
            results.append({
                "model": model_name,
                "status": "exception",
                "error": str(e)
            })

    # Save results
    results_file = Path(__file__).parent.parent / "models" / "training_results.json"
    results_file.parent.mkdir(exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": str(Path(__file__).parent.parent),
            "goal": "Sharpe >2.0, MaxDD <15%",
            "results": results
        }, f, indent=2, default=str)

    print("\n" + "="*80)
    print("TRAINING SUMMARY")
    print("="*80)
    for r in results:
        status_icon = "✅" if r["status"] == "success" else "❌"
        print(f"{status_icon} {r['model'].upper()}: {r['status']}")

    print(f"\nResults saved to: {results_file}")
    return results


if __name__ == "__main__":
    asyncio.run(train_crypto_optimized_models())
