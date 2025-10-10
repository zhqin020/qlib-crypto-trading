"""
Backtesting engine with crypto-specific features
"""

import asyncio
import logging
import json
import pickle
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import uuid

from ..monitoring.process_monitor import monitor, ProcessStatus
from ..utils.datasets import load_snapshot_metadata
from ..utils.qlib_state import qlib_init_context

logger = logging.getLogger(__name__)

try:  # Optional dependency: qlib
    from qlib.backtest import backtest as _QLIB_backtest
except ImportError:  # pragma: no cover - executed when qlib is unavailable
    _QLIB_backtest = None


if _QLIB_backtest is not None:
    qlib_backtest = _QLIB_backtest
else:
    def qlib_backtest(*args, **kwargs):  # type: ignore[override]
        raise ModuleNotFoundError(
            "Qlib is required for backtesting workflows. Install qlib to enable this feature."
        )

    qlib_backtest._qlib_missing = True  # type: ignore[attr-defined]


async def run_backtest(
    model_id: str,
    dataset_ref: str,
    costs: str,
    rebalance: str,
    funding: bool = False,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    benchmark: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run backtest using trained model

    Args:
        model_id: Trained model ID
        dataset_ref: Dataset reference
        costs: Transaction costs level (low, medium, high)
        rebalance: Rebalancing frequency (weekly, monthly)
        funding: Include funding rate costs (for futures)
        start_time: Inclusive start date for the backtest window (YYYY-MM-DD)
        end_time: Inclusive end date for the backtest window (YYYY-MM-DD)
        benchmark: Benchmark instrument (e.g., BTC_USDT)

    Returns:
        Backtest results with performance metrics
    """
    # Generate process ID with timestamp to prevent collisions
    import time
    import asyncio
    process_id = f"backtest_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

    # Total steps: validation, init, load_model, config, run_backtest, calc_metrics, save
    total_steps = 7

    process_started = False

    # Create the actual work as a separate coroutine
    async def do_backtest():
        nonlocal process_started
        try:
            # Start process monitoring
            await monitor.start_process(process_id, "backtest", total_steps=total_steps)
            process_started = True

            # Check for cancellation
            process = await monitor.get_process(process_id)
            if process and process.status == ProcessStatus.CANCELLED:
                return {"status": "cancelled", "process_id": process_id}

            project_root = Path(__file__).parent.parent.parent
            models_dir = project_root / "models" / "trained"
            qlib_dir = project_root / "data" / "qlib" / dataset_ref

            # Step 1: Validate dataset
            await monitor.update_progress(process_id, 14.3, f"Validating dataset '{dataset_ref}'", 1)

            # Validate dataset exists
            if not qlib_dir.exists():
                logger.error(f"Dataset directory not found: {qlib_dir}")
                await monitor.fail_process(process_id, f"Dataset '{dataset_ref}' not found at {qlib_dir}")
                return {
                    "error": f"Dataset '{dataset_ref}' not found at {qlib_dir}",
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id
                }

            # Validate dataset has required structure
            if not (qlib_dir / "calendars").exists() and not (qlib_dir / "instruments").exists():
                logger.error(f"Dataset directory exists but appears empty: {qlib_dir}")
                await monitor.fail_process(process_id, f"Dataset '{dataset_ref}' appears to be empty or invalid")
                return {
                    "error": f"Dataset '{dataset_ref}' appears to be empty or invalid",
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id
                }

            # Load dataset metadata for defaults (if available)
            snapshot_meta = load_snapshot_metadata(qlib_dir)

            resolved_start = start_time or snapshot_meta.get("start_date")
            resolved_end = end_time or snapshot_meta.get("end_date")

            if not resolved_start or not resolved_end:
                error_msg = (
                    "Backtest requires start_time and end_time. Provide them in the request "
                    "or ensure snapshot_meta.json has start_date/end_date."
                )
                await monitor.fail_process(process_id, error_msg)
                return {
                    "error": error_msg,
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id,
                }

            try:
                start_ts = pd.Timestamp(resolved_start)
                end_ts = pd.Timestamp(resolved_end)
            except ValueError as parse_error:
                error_msg = f"Invalid backtest period: {parse_error}"
                await monitor.fail_process(process_id, error_msg)
                return {
                    "error": error_msg,
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id,
                }

            if start_ts > end_ts:
                error_msg = (
                    "Backtest start_time must be before or equal to end_time. "
                    f"Received start_time={start_ts.date()} end_time={end_ts.date()}"
                )
                await monitor.fail_process(process_id, error_msg)
                return {
                    "error": error_msg,
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id,
                }

            resolved_start_str = start_ts.strftime("%Y-%m-%d")
            resolved_end_str = end_ts.strftime("%Y-%m-%d")

            resolved_benchmark = benchmark or snapshot_meta.get("benchmark")
            if not resolved_benchmark:
                resolved_benchmark = "BTC_USDT"
                logger.info(
                    "No benchmark provided for dataset '%s'; defaulting to %s",
                    dataset_ref,
                    resolved_benchmark,
                )

            # Step 2: Initialize Qlib
            await monitor.update_progress(process_id, 28.6, f"Initializing Qlib with dataset '{dataset_ref}'", 2)

            # Initialize Qlib with clean cache (prevents state bleed)
            # Use async version for concurrency protection
            async with qlib_init_context(
                provider_uri=str(qlib_dir),
                region="cn",
                auto_mount=True
            ):
                # Check for cancellation after init
                process = await monitor.get_process(process_id)
                if process and process.status == ProcessStatus.CANCELLED:
                    return {"status": "cancelled", "process_id": process_id}

                # Step 3: Load model
                await monitor.update_progress(process_id, 42.9, f"Loading model '{model_id}'", 3)

                # Load model
                model_path = models_dir / f"{model_id}.pkl"
                if not model_path.exists():
                    await monitor.fail_process(process_id, f"Model {model_id} not found")
                    return {"error": f"Model {model_id} not found"}

                with open(model_path, 'rb') as f:
                    model = pickle.load(f)

                # Load model metadata
                meta_file = models_dir / f"{model_id}_meta.json"
                with open(meta_file) as f:
                    model_meta = json.load(f)

                # Step 4: Configure backtest
                await monitor.update_progress(
                    process_id,
                    57.1,
                    f"Configuring backtest (costs={costs}, rebalance={rebalance}, benchmark={resolved_benchmark})",
                    4,
                )

                # Get exchange cost configuration (NOT executor config)
                # This will be passed to backtest() via exchange_kwargs parameter
                exchange_kwargs = get_exchange_config(costs, funding)

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

                # Define executor (WITHOUT cost parameters - those go in exchange_kwargs)
                executor_config = {
                    "class": "SimulatorExecutor",
                    "module_path": "qlib.backtest.executor",
                    "kwargs": {
                        "time_per_step": rebalance,
                        "generate_portfolio_metrics": True,
                        "verbose": False,
                        # NOTE: Cost parameters (open_cost, close_cost, etc.) are passed
                        # via exchange_kwargs to backtest(), NOT here in executor config
                    },
                }

                # Check for cancellation before backtest
                process = await monitor.get_process(process_id)
                if process and process.status == ProcessStatus.CANCELLED:
                    return {"status": "cancelled", "process_id": process_id}

                # Step 5: Run backtest
                await monitor.update_progress(
                    process_id,
                    71.4,
                    f"Running backtest simulation ({resolved_start_str} to {resolved_end_str})",
                    5,
                )

                # Run backtest with exchange_kwargs
                logger.info(f"Running backtest for model {model_id} with costs={costs}...")

                def run_backtest_call():
                    return qlib_backtest(
                        start_time=resolved_start_str,
                        end_time=resolved_end_str,
                        strategy=strategy_config,
                        executor=executor_config,
                        benchmark=resolved_benchmark,
                        exchange_kwargs=exchange_kwargs,
                    )

                portfolio_metric_dict, indicator_dict = await asyncio.to_thread(run_backtest_call)

                # Step 6: Calculate metrics
                await monitor.update_progress(process_id, 85.7, f"Calculating performance metrics", 6)

                # Calculate performance metrics
                analysis = calculate_crypto_metrics(portfolio_metric_dict, indicator_dict)

                # Create result summary
                result = {
                    "model_id": model_id,
                    "dataset": dataset_ref,
                    "backtest_period": {
                        "start": resolved_start_str,
                        "end": resolved_end_str,
                    },
                    "config": {
                        "costs": costs,
                        "rebalance": rebalance,
                        "funding": funding,
                        "benchmark": resolved_benchmark,
                    },
                    "metrics": {
                        "annualized_return": float(analysis.get("annualized_return", 0)),
                        "information_ratio": float(analysis.get("information_ratio", 0)),
                        "max_drawdown": float(analysis.get("max_drawdown", 0)),
                        "sharpe_ratio": float(analysis.get("sharpe_ratio", 0)),
                        "sortino_ratio": float(analysis.get("sortino_ratio", 0)),
                        "calmar_ratio": float(analysis.get("calmar_ratio", 0)),
                        "win_rate": float(analysis.get("win_rate", 0)),
                        "total_trades": int(analysis.get("total_trades", 0)),
                    },
                    "portfolio_curve": portfolio_metric_dict.get("excess_return_with_cost", []),
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                }

            # Step 7: Save results
            await monitor.update_progress(process_id, 95.0, f"Saving backtest results", 7)

            # Save backtest results
            bt_dir = project_root / "backtests"
            bt_dir.mkdir(parents=True, exist_ok=True)

            bt_file = bt_dir / f"{model_id}_backtest.json"
            with open(bt_file, 'w') as f:
                json.dump(result, f, indent=2, default=str)

            # Complete process monitoring
            await monitor.complete_process(process_id, result)

            logger.info(f"Backtest completed for {model_id}: Sharpe={result['metrics']['sharpe_ratio']:.3f}")
            return result

        except asyncio.CancelledError:
            # Task was cancelled
            logger.info(f"Backtest task cancelled: {process_id}")
            if process_started:
                await monitor.fail_process(process_id, "Cancelled by user")
            raise
        except Exception as e:
            logger.error(f"Error running backtest: {e}", exc_info=True)
            # Only fail process if it was successfully started
            if process_started:
                try:
                    await monitor.fail_process(process_id, str(e))
                except Exception as monitor_error:
                    logger.error(f"Failed to update process monitor: {monitor_error}")
            return {
                "error": str(e),
                "model_id": model_id,
                "status": "failed"
            }

    # Register the task for cancellation support
    task = asyncio.create_task(do_backtest())
    await monitor.register_task(process_id, task)

    # Wait for task to complete
    try:
        result = await task
        return result
    except asyncio.CancelledError:
        return {"status": "cancelled", "process_id": process_id}


def get_exchange_config(costs: str, funding: bool = False) -> Dict[str, Any]:
    """
    Get exchange configuration for Qlib backtest.

    Uses correct Qlib Exchange parameters:
    - open_cost: Cost rate for opening positions
    - close_cost: Cost rate for closing positions
    - min_cost: Minimum transaction cost (0 for crypto)
    - impact_cost: Market impact/slippage cost

    Crypto exchanges have different fee structures:
    - Maker fees: Applied when adding liquidity (open_cost)
    - Taker fees: Applied when removing liquidity (close_cost)
    - Market impact: Price slippage from order size (impact_cost)

    Args:
        costs: Cost level - "low" (VIP tier), "medium" (standard), or "high" (conservative)
        funding: If True, log warning about funding rates (not natively supported)

    Returns:
        dict: Exchange configuration for backtest() function's exchange_kwargs parameter
    """

    cost_configs = {
        "low": {
            "freq": "day",
            "limit_threshold": None,      # No price limits for crypto
            "deal_price": "close",
            "open_cost": 0.0002,          # 0.02% - VIP maker fee (Binance VIP 1+)
            "close_cost": 0.0005,         # 0.05% - VIP taker fee
            "min_cost": 0,                # No minimum transaction cost for crypto
            "impact_cost": 0.00005,       # 0.005% - Low market impact (high liquidity)
        },
        "medium": {
            "freq": "day",
            "limit_threshold": None,
            "deal_price": "close",
            "open_cost": 0.0005,          # 0.05% - Standard maker fee (Binance)
            "close_cost": 0.001,          # 0.1% - Standard taker fee
            "min_cost": 0,
            "impact_cost": 0.0001,        # 0.01% - Moderate market impact
        },
        "high": {
            "freq": "day",
            "limit_threshold": None,
            "deal_price": "close",
            "open_cost": 0.001,           # 0.1% - Conservative maker fee
            "close_cost": 0.002,          # 0.2% - Conservative taker fee
            "min_cost": 0,
            "impact_cost": 0.0005,        # 0.05% - High market impact (low liquidity)
        }
    }

    config = cost_configs.get(costs, cost_configs["medium"])

    # Funding rates not natively supported by Qlib Exchange
    if funding:
        logger.warning(
            "Funding rate costs are not natively supported by Qlib Exchange. "
            "Consider implementing a custom Exchange subclass for futures funding rates. "
            "Typical perpetual funding rates: ±0.01% per 8 hours (±0.03% daily)"
        )

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
