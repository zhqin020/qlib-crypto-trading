#!/usr/bin/env python3
"""
Run backtest for a trained model
"""

import argparse
import os
import asyncio
import sys
from pathlib import Path
import json

# Set Qlib version for setuptools-scm
os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging
logging.basicConfig(level=logging.INFO)

from backtesting.engine import run_backtest


def load_config(config_path: Path = None):
    """Load centralized trading parameters.
    If config_path is provided, use it; otherwise default to config/trading_params.json.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "trading_params.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


async def main():
    """Run backtest"""

    # First pass: parse only --config to load defaults
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("--config", default=None)
    conf_args, _ = conf_parser.parse_known_args()
    
    config = load_config(Path(conf_args.config) if conf_args.config else None)
    bt_config = config.get("backtest", {})
    tr_config = config.get("trading", {})

    # Second pass: parse everything
    parser = argparse.ArgumentParser(
        description="Run a backtest for a trained model using Qlib engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--config", default=None, help="Path to custom config JSON file (optional)")
    parser.add_argument("model_id", nargs="?", help="Model identifier (pickle filename without .pkl) to backtest. If omitted, uses the latest model of the type specified in config.")
    parser.add_argument("--dataset", default="crypto", help="Dataset reference to use for backtest (configured in Qlib)")
    parser.add_argument("--costs", default="medium", choices=["low", "medium", "high"], help="Transaction cost level: low (0.01%%), medium (0.05%%), high (0.1%%)")
    parser.add_argument("--rebalance", default=bt_config.get("rebalance", "weekly"), help="Rebalance frequency (weekly, monthly, daily, or N-day frequency like '5d')")
    parser.add_argument("--funding", action="store_true", help="Include funding rate costs (for futures/swap markets)")
    parser.add_argument("--start", dest="start_time", default=bt_config.get("start_time"), help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_time", default=bt_config.get("end_time"), help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--benchmark", default=bt_config.get("benchmark"), help="Benchmark instrument for relative performance (e.g., BTC/USDT)")
    parser.add_argument("--topk", type=int, default=bt_config.get("topk", 10), help="Number of assets to hold in the portfolio at any time")
    parser.add_argument("--long-short", action="store_true", help="Enable long-short trading (must be supported by the strategy)")
    parser.add_argument("--tp", type=float, default=tr_config.get("take_profit"), help="Take profit percentage (e.g., 0.1 for 10%%)")
    parser.add_argument("--sl", type=float, default=tr_config.get("stop_loss"), help="Stop loss percentage (e.g., -0.05 for -5%%)")
    parser.add_argument("--direction", default=tr_config.get("direction", "long"), choices=["long", "short", "long-short"], help="Trading directionality")
    parser.add_argument("--init-investment", type=float, default=tr_config.get("init_investment", 100000), help="Initial capital in USDT")
    parser.add_argument("--leverage", type=int, default=tr_config.get("leverage", 1), help="Leverage multiplier to apply to positions")
    parser.add_argument("--threshold", type=float, default=tr_config.get("signal_threshold", 0.0), help="Absolute score threshold. Scores below this are ignored (no confidence, no trade)")
    
    # Portfolio subset
    default_portfolio = bt_config.get("portfolios")
    if default_portfolio and isinstance(default_portfolio, list):
        default_portfolio_str = ",".join(default_portfolio)
    else:
        default_portfolio_str = None
    
    parser.add_argument("--instruments", default=default_portfolio_str, help="Comma-separated list of instruments to restrict the backtest window to. Defaults to all in dataset.")

    args = parser.parse_args()
    
    model_id = args.model_id
    
    # Auto-detect latest model if not provided
    if not model_id:
        training_cfg = config.get("training", {})
        target_type = training_cfg.get("model_type", "lightgbm")
        
        models_dir = Path(__file__).parent.parent / "models" / "trained"
        if not models_dir.exists():
            print(f"Error: Models directory not found at {models_dir}")
            sys.exit(1)
            
        # Find all .pkl files starting with target_type
        candidates = list(models_dir.glob(f"{target_type}_*.pkl"))
        if not candidates:
            print(f"Error: No trained models found for type '{target_type}'")
            print(f"  Please run: python scripts/train_sample_model.py")
            sys.exit(1)
            
        # Sort by modification time (newest first)
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        latest_model = candidates[0]
        model_id = latest_model.stem # remove .pkl
        print(f"Auto-selected latest {target_type} model: {model_id}")

    print(f"Running backtest for model: {model_id}")
    print()

    result = await run_backtest(
        model_id=model_id,
        dataset_ref=args.dataset,
        costs=args.costs,
        rebalance=args.rebalance,
        funding=args.funding,
        topk=args.topk,
        long_short=args.long_short,
        take_profit=args.tp,
        stop_loss=args.sl,
        direction=args.direction,
        init_investment=args.init_investment,
        leverage=args.leverage,
        signal_threshold=args.threshold,
        start_time=args.start_time,
        end_time=args.end_time,
        benchmark=args.benchmark,
        instruments=args.instruments.split(",") if args.instruments else None,
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
