"""
Backtesting engine with crypto-specific features
"""

import logging
import json
import pickle
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


async def run_backtest(
    model_id: str,
    dataset_ref: str,
    costs: str,
    rebalance: str,
    funding: bool = False
) -> Dict[str, Any]:
    """
    Run backtest using trained model

    Args:
        model_id: Trained model ID
        dataset_ref: Dataset reference
        costs: Transaction costs level (low, medium, high)
        rebalance: Rebalancing frequency (weekly, monthly)
        funding: Include funding rate costs (for futures)

    Returns:
        Backtest results with performance metrics
    """
    try:
        from qlib.backtest import backtest as qlib_backtest, executor
        from qlib.contrib.strategy import TopkDropoutStrategy
        from qlib.contrib.evaluate import risk_analysis
        from qlib.utils import init_instance_by_config
        from ..utils.qlib_state import init_qlib_clean_async

        project_root = Path(__file__).parent.parent.parent
        models_dir = project_root / "models" / "trained"
        qlib_dir = project_root / "data" / "qlib" / dataset_ref

        # Validate dataset exists
        if not qlib_dir.exists():
            logger.error(f"Dataset directory not found: {qlib_dir}")
            return {
                "error": f"Dataset '{dataset_ref}' not found at {qlib_dir}",
                "status": "failed",
                "dataset": dataset_ref,
                "model_id": model_id
            }

        # Validate dataset has required structure
        if not (qlib_dir / "calendars").exists() and not (qlib_dir / "instruments").exists():
            logger.error(f"Dataset directory exists but appears empty: {qlib_dir}")
            return {
                "error": f"Dataset '{dataset_ref}' appears to be empty or invalid",
                "status": "failed",
                "dataset": dataset_ref,
                "model_id": model_id
            }

        # Initialize Qlib with clean cache (prevents state bleed)
        # Use async version for concurrency protection
        success = await init_qlib_clean_async(
            provider_uri=str(qlib_dir),
            region="cn",
            auto_mount=True
        )
        if not success:
            raise RuntimeError(f"Failed to initialize qlib for backtest: {model_id}")

        # Load model
        model_path = models_dir / f"{model_id}.pkl"
        if not model_path.exists():
            return {"error": f"Model {model_id} not found"}

        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        # Load model metadata
        meta_file = models_dir / f"{model_id}_meta.json"
        with open(meta_file) as f:
            model_meta = json.load(f)

        # Get transaction costs
        cost_config = get_cost_config(costs, funding)

        # Define trading strategy
        strategy_config = {
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy.signal_strategy",
            "kwargs": {
                "signal": model,
                "topk": 10,
                "n_drop": 2,
                "risk_degree": 0.95,
            },
        }

        # Define executor
        executor_config = {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": rebalance,
                "generate_portfolio_metrics": True,
                "verbose": False,
                **cost_config
            },
        }

        # Run backtest
        logger.info(f"Running backtest for model {model_id}...")

        portfolio_metric_dict, indicator_dict = qlib_backtest(
            start_time="2023-01-01",
            end_time="2024-12-31",
            strategy=strategy_config,
            executor=executor_config,
            benchmark="BTC_USDT",
        )

        # Calculate performance metrics
        analysis = calculate_crypto_metrics(portfolio_metric_dict, indicator_dict)

        # Create result summary
        result = {
            "model_id": model_id,
            "dataset": dataset_ref,
            "backtest_period": {
                "start": "2023-01-01",
                "end": "2024-12-31"
            },
            "config": {
                "costs": costs,
                "rebalance": rebalance,
                "funding": funding
            },
            "metrics": {
                "annualized_return": float(analysis.get("annualized_return", 0)),
                "information_ratio": float(analysis.get("information_ratio", 0)),
                "max_drawdown": float(analysis.get("max_drawdown", 0)),
                "sharpe_ratio": float(analysis.get("sharpe_ratio", 0)),
                "sortino_ratio": float(analysis.get("sortino_ratio", 0)),
                "calmar_ratio": float(analysis.get("calmar_ratio", 0)),
                "win_rate": float(analysis.get("win_rate", 0)),
                "total_trades": int(analysis.get("total_trades", 0))
            },
            "portfolio_curve": portfolio_metric_dict.get("excess_return_with_cost", []),
            "status": "completed",
            "completed_at": datetime.now().isoformat()
        }

        # Save backtest results
        bt_dir = project_root / "backtests"
        bt_dir.mkdir(parents=True, exist_ok=True)

        bt_file = bt_dir / f"{model_id}_backtest.json"
        with open(bt_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        logger.info(f"Backtest completed for {model_id}: Sharpe={result['metrics']['sharpe_ratio']:.3f}")
        return result

    except Exception as e:
        logger.error(f"Error running backtest: {e}", exc_info=True)
        return {
            "error": str(e),
            "model_id": model_id,
            "status": "failed"
        }


def get_cost_config(costs: str, funding: bool = False) -> Dict[str, Any]:
    """
    Get transaction cost configuration

    Crypto exchanges have different fee structures:
    - Maker/Taker fees
    - Funding rates (for futures)
    - Slippage (depends on liquidity)
    """

    cost_configs = {
        "low": {
            "trade_exchange": {"class": "Exchange", "kwargs": {
                "freq": "day",
                "min_cost": 0,
                "trade_unit": None,
                "deal_price": "close",
            }},
            "trade_cost": 0.0005,  # 0.05% (Binance maker fee)
            "slippage": 0.0001,    # 0.01% slippage
        },
        "medium": {
            "trade_exchange": {"class": "Exchange", "kwargs": {
                "freq": "day",
                "min_cost": 0,
                "trade_unit": None,
                "deal_price": "close",
            }},
            "trade_cost": 0.001,   # 0.1% (typical taker fee)
            "slippage": 0.0005,    # 0.05% slippage
        },
        "high": {
            "trade_exchange": {"class": "Exchange", "kwargs": {
                "freq": "day",
                "min_cost": 0,
                "trade_unit": None,
                "deal_price": "close",
            }},
            "trade_cost": 0.002,   # 0.2% (high fee tier)
            "slippage": 0.001,     # 0.1% slippage
        }
    }

    config = cost_configs.get(costs, cost_configs["medium"])

    # Add funding rate costs for futures (typically ±0.01% per 8 hours)
    if funding:
        config["funding_rate"] = 0.0001  # Daily equivalent

    return config


def calculate_crypto_metrics(portfolio_dict: Dict, indicator_dict: Dict) -> Dict[str, float]:
    """
    Calculate crypto-specific performance metrics

    Standard metrics:
    - Annualized return
    - Sharpe ratio
    - Max drawdown
    - Win rate

    Crypto-specific:
    - 24/7 adjusted metrics
    - Volatility-adjusted returns
    """
    try:
        # Extract returns series
        returns = pd.Series(portfolio_dict.get("excess_return_with_cost", []))

        if len(returns) == 0:
            return {}

        # Annualized return (365 days for crypto)
        total_return = (1 + returns).prod() - 1
        years = len(returns) / 365
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Sharpe ratio (24/7 adjustment)
        daily_vol = returns.std()
        sharpe_ratio = (returns.mean() / daily_vol) * np.sqrt(365) if daily_vol > 0 else 0

        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = (returns.mean() / downside_std) * np.sqrt(365) if downside_std > 0 else 0

        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())

        # Calmar ratio
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        # Win rate
        win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0

        # Information ratio
        excess_returns = returns
        tracking_error = excess_returns.std()
        information_ratio = (excess_returns.mean() / tracking_error) * np.sqrt(365) if tracking_error > 0 else 0

        return {
            "annualized_return": annualized_return,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
            "calmar_ratio": calmar_ratio,
            "win_rate": win_rate,
            "information_ratio": information_ratio,
            "total_trades": len(returns),
            "volatility": daily_vol * np.sqrt(365)
        }

    except Exception as e:
        logger.error(f"Error calculating metrics: {e}")
        return {}
