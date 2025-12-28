#!/usr/bin/env python3
"""
Run backtest for a trained model
"""

import argparse
import os
import asyncio
import sys
from pathlib import Path

# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging
logging.basicConfig(level=logging.INFO)

from backtesting.engine import run_backtest


async def main():
    """Run backtest"""

    parser = argparse.ArgumentParser(description="Run a backtest for a trained model")
    parser.add_argument("model_id", help="Model identifier to backtest")
    parser.add_argument("--dataset", default="crypto", help="Dataset reference (default: crypto)")
    parser.add_argument("--costs", default="medium", help="Cost level: low, medium, high")
    parser.add_argument("--rebalance", default="weekly", help="Rebalance frequency (e.g., weekly, monthly)")
    parser.add_argument("--funding", action="store_true", help="Include funding rate costs")
    parser.add_argument("--start", dest="start_time", help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_time", help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--benchmark", help="Benchmark instrument (e.g., BTC)")
    parser.add_argument("--topk", type=int, default=10, help="Number of assets to hold (default: 10)")
    parser.add_argument("--long-short", action="store_true", help="Enable long-short trading (if supported)")

    args = parser.parse_args()

    print(f"Running backtest for model: {args.model_id}")
    print()

    result = await run_backtest(
        model_id=args.model_id,
        dataset_ref=args.dataset,
        costs=args.costs,
        rebalance=args.rebalance,
        funding=args.funding,
        topk=args.topk,
        long_short=args.long_short,
        start_time=args.start_time,
        end_time=args.end_time,
        benchmark=args.benchmark,
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
