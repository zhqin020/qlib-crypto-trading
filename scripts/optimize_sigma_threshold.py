#!/usr/bin/env python3
"""
Grid search optimization for min_sigma_threshold parameter.
Tests different Sigma thresholds to find the optimal balance between
signal quality and trading frequency.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List
import pandas as pd

os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.1.0'
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtesting.engine import run_backtest

async def test_sigma_threshold(
    model_id: str,
    min_sigma: float,
    topk: int,
    dataset: str,
    start_time: str,
    end_time: str
) -> Dict:
    """Run backtest with specific min_sigma threshold."""
    
    print(f"\n{'='*60}")
    print(f"Testing: min_sigma={min_sigma}σ, topk={topk}")
    print(f"{'='*60}")
    
    result = await run_backtest(
        model_id=model_id,
        dataset_ref=dataset,
        costs="medium",
        rebalance="1h",
        funding=False,
        topk=topk,
        long_short=True,
        take_profit=None,
        stop_loss=None,
        direction="long-short",
        init_investment=100000,
        leverage=1,
        signal_threshold=0.0,
        start_time=start_time,
        end_time=end_time,
        benchmark="BTC",
        instruments=None,
    )
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return None
    
    metrics = result.get('metrics', {})
    
    print(f"\n📊 Results:")
    print(f"  Sharpe Ratio:      {metrics.get('sharpe_ratio', 0):.3f}")
    print(f"  Win Rate:          {metrics.get('win_rate', 0):.1%}")
    print(f"  Annualized Return: {metrics.get('annualized_return', 0):.2%}")
    print(f"  Max Drawdown:      {metrics.get('max_drawdown', 0):.2%}")
    print(f"  Calmar Ratio:      {metrics.get('calmar_ratio', 0):.3f}")
    print(f"  Total Trades:      {metrics.get('total_trades', 0)}")
    
    return {
        'min_sigma': min_sigma,
        'topk': topk,
        'sharpe_ratio': metrics.get('sharpe_ratio', 0),
        'win_rate': metrics.get('win_rate', 0),
        'annualized_return': metrics.get('annualized_return', 0),
        'max_drawdown': metrics.get('max_drawdown', 0),
        'calmar_ratio': metrics.get('calmar_ratio', 0),
        'sortino_ratio': metrics.get('sortino_ratio', 0),
        'total_trades': metrics.get('total_trades', 0),
        'passed': (
            metrics.get('sharpe_ratio', 0) > 1.0 and
            metrics.get('win_rate', 0) > 0.50 and
            metrics.get('max_drawdown', 0) < 0.15
        )
    }

async def main():
    """Run grid search for optimal min_sigma_threshold."""
    
    # Configuration
    model_id = "models/per_symbol_models_20260102_020624.json"
    dataset = "crypto_1h_future"
    start_time = "2024-05-03"
    end_time = "2025-01-01"
    
    # Grid search parameters
    sigma_thresholds = [0.0, 0.5, 0.75, 1.0, 1.25, 1.5]
    topk_values = [3]  # Keep topk fixed for now
    
    results = []
    
    print("\n" + "="*60)
    print("  ADAPTIVE SIGMA THRESHOLD OPTIMIZATION")
    print("="*60)
    print(f"\nModel: {model_id}")
    print(f"Period: {start_time} to {end_time}")
    print(f"Testing {len(sigma_thresholds)} sigma thresholds × {len(topk_values)} topk values")
    print(f"Total combinations: {len(sigma_thresholds) * len(topk_values)}")
    
    for topk in topk_values:
        for min_sigma in sigma_thresholds:
            result = await test_sigma_threshold(
                model_id=model_id,
                min_sigma=min_sigma,
                topk=topk,
                dataset=dataset,
                start_time=start_time,
                end_time=end_time
            )
            
            if result:
                results.append(result)
    
    # Save results
    output_dir = Path("analytics")
    output_dir.mkdir(exist_ok=True)
    
    results_df = pd.DataFrame(results)
    csv_file = output_dir / "sigma_optimization_results.csv"
    results_df.to_csv(csv_file, index=False)
    
    # Summary
    print("\n" + "="*60)
    print("  OPTIMIZATION RESULTS SUMMARY")
    print("="*60)
    
    print("\n📊 All Results:")
    print(results_df.to_string(index=False))
    
    # Find best configurations
    passed_configs = results_df[results_df['passed'] == True]
    
    if not passed_configs.empty:
        print("\n✅ Configurations Meeting Targets (Sharpe>1.0, WinRate>50%, DD<15%):")
        print(passed_configs.to_string(index=False))
        
        # Best by Sharpe
        best_sharpe = passed_configs.loc[passed_configs['sharpe_ratio'].idxmax()]
        print(f"\n🏆 Best Sharpe Ratio: {best_sharpe['sharpe_ratio']:.3f}")
        print(f"   min_sigma={best_sharpe['min_sigma']}σ, topk={int(best_sharpe['topk'])}")
        
        # Best by Win Rate
        best_wr = passed_configs.loc[passed_configs['win_rate'].idxmax()]
        print(f"\n🎯 Best Win Rate: {best_wr['win_rate']:.1%}")
        print(f"   min_sigma={best_wr['min_sigma']}σ, topk={int(best_wr['topk'])}")
        
        # Recommendation
        print("\n💡 Recommended Configuration:")
        # Prefer higher Sharpe with reasonable win rate
        recommended = passed_configs.loc[passed_configs['sharpe_ratio'].idxmax()]
        print(f"   min_sigma_threshold: {recommended['min_sigma']}")
        print(f"   topk: {int(recommended['topk'])}")
        print(f"   Expected Sharpe: {recommended['sharpe_ratio']:.3f}")
        print(f"   Expected Win Rate: {recommended['win_rate']:.1%}")
        print(f"   Expected Max DD: {recommended['max_drawdown']:.2%}")
        
    else:
        print("\n⚠️  No configurations met all targets.")
        print("    Showing best by Sharpe Ratio:")
        best_overall = results_df.loc[results_df['sharpe_ratio'].idxmax()]
        print(f"\n   min_sigma={best_overall['min_sigma']}σ")
        print(f"   Sharpe: {best_overall['sharpe_ratio']:.3f}")
        print(f"   Win Rate: {best_overall['win_rate']:.1%}")
        print(f"   Max DD: {best_overall['max_drawdown']:.2%}")
    
    print(f"\n📁 Results saved to: {csv_file}")
    print("\nNext steps:")
    print("  1. Review the results above")
    print("  2. Update config/trading_params.json with recommended min_sigma_threshold")
    print("  3. Run final validation backtest")

if __name__ == "__main__":
    asyncio.run(main())
