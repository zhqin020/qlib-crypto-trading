#!/usr/bin/env python3
"""
Run backtest for a trained model
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backtesting.engine import run_backtest


async def main():
    """Run backtest"""

    if len(sys.argv) < 2:
        print("Usage: python run_backtest.py <model_id>")
        sys.exit(1)

    model_id = sys.argv[1]

    print(f"Running backtest for model: {model_id}")
    print()

    result = await run_backtest(
        model_id=model_id,
        dataset_ref="crypto",
        costs="medium",
        rebalance="weekly",
        funding=False
    )

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print("\nBacktest Results:")
    print(f"  Model ID: {result['model_id']}")
    print(f"  Dataset: {result['dataset']}")
    print(f"  Period: {result['backtest_period']['start']} to {result['backtest_period']['end']}")
    print()
    print("Performance Metrics:")
    metrics = result['metrics']
    print(f"  Annualized Return: {metrics['annualized_return']:.2%}")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
    print(f"  Sortino Ratio: {metrics['sortino_ratio']:.3f}")
    print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"  Calmar Ratio: {metrics['calmar_ratio']:.3f}")
    print(f"  Win Rate: {metrics['win_rate']:.2%}")
    print(f"  Total Trades: {metrics['total_trades']}")


if __name__ == "__main__":
    asyncio.run(main())
