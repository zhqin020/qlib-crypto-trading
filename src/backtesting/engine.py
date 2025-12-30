"""
Backtesting engine with crypto-specific features
"""

import asyncio
import logging
from utils.logging_config import get_logger
import json
import pickle
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd
import numpy as np
import uuid
import warnings

from analytics.investment_kpis import kpi_registry
from monitoring.process_monitor import monitor, ProcessStatus
from utils.datasets import load_snapshot_metadata
from utils.qlib_state import qlib_init_context

logger = get_logger(__name__)

try:  # Optional dependency: qlib
    from qlib.backtest import backtest as _QLIB_backtest
    from qlib.utils import init_instance_by_config as _QLIB_init_instance_by_config
except ImportError:  # pragma: no cover - executed when qlib is unavailable
    _QLIB_backtest = None
    _QLIB_init_instance_by_config = None


if _QLIB_backtest is not None:
    qlib_backtest = _QLIB_backtest
else:
    def qlib_backtest(*args, **kwargs):  # type: ignore[override]
        raise ModuleNotFoundError(
            "Qlib is required for backtesting workflows. Install qlib to enable this feature."
        )

    qlib_backtest._qlib_missing = True  # type: ignore[attr-defined]

if _QLIB_init_instance_by_config is not None:
    init_instance_by_config = _QLIB_init_instance_by_config
else:
    def init_instance_by_config(*args, **kwargs):  # type: ignore[override]
        raise ModuleNotFoundError(
            "Qlib utilities are required for workflows. Install qlib to enable this feature."
        )

    init_instance_by_config._qlib_missing = True  # type: ignore[attr-defined]


async def run_backtest(
    model_id: str,
    dataset_ref: str,
    costs: str,
    rebalance: str,
    funding: bool = False,
    topk: int = 10,
    long_short: bool = False,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    benchmark: Optional[str] = None,
    instruments: Optional[List[str]] = None,
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
        instruments: List of instruments to include in backtest (default: all)

    Returns:
        Backtest results with performance metrics
    """
    # Generate process ID with timestamp to prevent collisions
    import time
    import asyncio
    process_id = f"backtest_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

    # Total steps: validation, init, load_model, config, run_backtest, calc_metrics, save
    total_steps = 7

    # Map human-readable frequency strings to Qlib format
    freq_map = {
        "weekly": "week",
        "monthly": "month",
        "daily": "day",
        "1h": "60min",
        "hourly": "60min"
    }
    resolved_rebalance = freq_map.get(rebalance, rebalance)

    process_started = False

    # Create the actual work as a separate coroutine
    async def do_backtest():
        nonlocal process_started, dataset_ref
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

            # Pre-load model metadata to resolve frequency correctly
            model_meta_file = models_dir / f"{model_id}_meta.json"
            if not model_meta_file.exists():
                logger.warning(f"Metadata for model {model_id} not found at {model_meta_file}. Using defaults.")
                model_meta = {}
            else:
                with open(model_meta_file) as f:
                    model_meta = json.load(f)

            # Check if we should automatically switch dataset based on model
            if dataset_ref == "crypto" and model_meta.get("dataset") == "crypto_1h":
                logger.info("Auto-switching to 'crypto_1h' dataset to match model training frequency.")
                dataset_ref = "crypto_1h"
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
                    "model_id": model_id,
                }

            # Validate dataset has required structure
            if not (qlib_dir / "calendars").exists() and not (qlib_dir / "instruments").exists():
                logger.error(f"Dataset directory exists but appears empty: {qlib_dir}")
                await monitor.fail_process(process_id, f"Dataset '{dataset_ref}' appears to be empty or invalid")
                return {
                    "error": f"Dataset '{dataset_ref}' appears to be empty or invalid",
                    "status": "failed",
                    "dataset": dataset_ref,
                    "model_id": model_id,
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
                resolved_benchmark = "BTC"
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

                # Step 4: Configure backtest
                await monitor.update_progress(
                    process_id,
                    57.1,
                    f"Configuring backtest (costs={costs}, rebalance={rebalance}, benchmark={resolved_benchmark})",
                    4,
                )

                # Resolve frequency for handler and exchange
                dataset_freq = snapshot_meta.get("frequency", model_meta.get("dataset_freq", "1d"))
                qlib_handler_freq = freq_map.get(dataset_freq, "day")
                logger.info(f"Resolved dataset frequency: {dataset_freq} -> {qlib_handler_freq}")

                # Get exchange cost configuration (NOT executor config)
                # This will be passed to backtest() via exchange_kwargs parameter
                exchange_kwargs = get_exchange_config(costs, funding, qlib_handler_freq)

                # Get handler configuration from model metadata
                config_dir = project_root / "config" / "features"
                feature_set_ref = model_meta.get("feature_set", "alpha158_crypto")
                feature_config_file = config_dir / f"{feature_set_ref}.json"

                if feature_config_file.exists():
                    with open(feature_config_file) as f:
                        feature_config = json.load(f)
                    handler_config = feature_config["config"]
                else:
                    from data_pipeline.features import get_alpha158_config
                    handler_config = get_alpha158_config()

                # Override instruments if provided
                if instruments:
                    # Qlib expects symbols without /USDT in many providers, 
                    # but our converter uses lowercase and no slash.
                    # Standardizing to what the Qlib data path contains.
                    clean_instruments = [i.split('/')[0].lower() for i in instruments]
                    handler_config["kwargs"]["instruments"] = clean_instruments
                    logger.info(f"Backtest limited to {len(clean_instruments)} instruments: {clean_instruments}")

                # Add fit range from model metadata to handler config
                fit_range = model_meta.get("segments", {}).get("train")
                if fit_range and "kwargs" in handler_config:
                    if handler_config["kwargs"].get("fit_start_time") is None:
                        handler_config["kwargs"]["fit_start_time"] = fit_range[0]
                    if handler_config["kwargs"].get("fit_end_time") is None:
                        handler_config["kwargs"]["fit_end_time"] = fit_range[1]
                
                if "kwargs" not in handler_config:
                    handler_config["kwargs"] = {}
                handler_config["kwargs"]["freq"] = qlib_handler_freq
                logger.info(f"Using frequency '{qlib_handler_freq}' for backtest handler")

                # Define dataset for signal prediction
                # Generate predictions first to avoid signal type issues in qlib_backtest
                await monitor.update_progress(process_id, 64.3, f"Generating predictions for backtest", 4)

                prediction_dataset_config = {
                    "class": "DatasetH",
                    "module_path": "qlib.data.dataset",
                    "kwargs": {
                        "handler": handler_config,
                        "segments": {
                            "test": (resolved_start_str, resolved_end_str)
                        },
                    },
                }
                
                # Use standardized dataset for progress reporting
                await monitor.update_progress(process_id, 64.3, f"Generating predictions ({dataset_ref})", 4)
                
                prediction_dataset = await asyncio.to_thread(init_instance_by_config, prediction_dataset_config)
                predictions = await asyncio.to_thread(model.predict, prediction_dataset)
                
                # Standardize Predictions: Force instrument names to UPPERCASE to match Exchange/all.txt
                # This is CRITICAL because Qlib's Exchange is case-sensitive on Linux.
                if not predictions.empty:
                    try:
                        # Standardize index names and force uppercase on 'instrument' level
                        # Note: predictions can be a Series or DataFrame
                        idx = predictions.index
                        if isinstance(idx, pd.MultiIndex):
                            name_list = [n.lower() if n else "" for n in idx.names]
                            if 'instrument' in name_list:
                                inst_idx = name_list.index('instrument')
                                # Rebuild index with uppercase instruments
                                predictions.index = idx.set_levels(
                                    idx.levels[inst_idx].astype(str).str.upper(), 
                                    level=inst_idx
                                )
                                logger.info(f"Standardized instruments in predictions to UPPERCASE (Level: {idx.names[inst_idx]})")
                    except Exception as e:
                        logger.warning(f"Could not standardize prediction index: {e}")

                logger.info(f"Generated predictions: shape={predictions.shape}")
                if not predictions.empty:
                    # Count non-zero non-nan values
                    valid_mask = predictions.notna() & (predictions != 0)
                    non_nan_count = valid_mask.values.sum() if hasattr(valid_mask, 'values') else valid_mask.sum()
                    unique_vals = predictions.nunique()
                    logger.info(f"Predictions statistics:\nTotal: {len(predictions)}\nValid: {non_nan_count}\nUnique values: {unique_vals}")
                    
                    if non_nan_count == 0:
                        logger.error("ALL predictions are NaN or zero! Strategy will result in an empty portfolio.")
                    elif unique_vals < 2:
                        logger.warning("All predictions have the SAME value. Strategy cannot rank instruments.")
                        
                    logger.info(f"Predictions sample:\n{predictions.head()}")
                else:
                    logger.warning("Predictions dataframe is EMPTY!")

                # Define trading strategy with pre-calculated predictions
                if long_short:
                    # For long-short, we use a custom or tailored WeightStrategy if needed,
                    # but since Qlib's TopkDropout is long-only, we'll note the limitation
                    # or switch to a basic signal selection if possible.
                    # For now, let's keep TopkDropout but allow topk to be set.
                    logger.warning("LongShortStrategy support is limited; using TopkDropout on both ends is not standard.")
                
                strategy_config = {
                    "class": "TopkDropoutStrategy",
                    "module_path": "qlib.contrib.strategy.signal_strategy",
                    "kwargs": {
                        "signal": predictions,
                        "topk": topk,
                        "n_drop": max(1, topk // 5),
                        "risk_degree": 0.95,
                    },
                }

                # Define executor (WITHOUT cost parameters - those go in exchange_kwargs)
                executor_config = {
                    "class": "SimulatorExecutor",
                    "module_path": "qlib.backtest.executor",
                    "kwargs": {
                        "time_per_step": qlib_handler_freq,
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

                # Pre-fetch benchmark to avoid resampling issues in Qlib
                # provide a returns series directly to avoid Qlib's internal frequency resolution errors
                benchmark_to_pass = resolved_benchmark
                try:
                    from qlib.data import D
                    
                    # 1. Clean the benchmark symbol (e.g., BTC/USDT -> BTC)
                    # Use uppercase and strip common suffixes
                    base_symbol = resolved_benchmark.split('/')[0].split('_')[0].upper()
                    
                    # 2. Try several fallback options
                    targets = []
                    if base_symbol: targets.append(base_symbol)
                    if resolved_benchmark != base_symbol: targets.append(resolved_benchmark)
                    if "BTC" not in targets: targets.append("BTC")
                    if "ETH" not in targets: targets.append("ETH")
                    
                    # Also try the first instrument in the dataset as a last resort
                    try:
                        all_insts = await asyncio.to_thread(D.instruments, market='all')
                        first_inst = next(iter(all_insts)) if all_insts else None
                        if first_inst and first_inst not in targets:
                            targets.append(first_inst)
                    except:
                        pass

                    found_df = None
                    final_target = None
                    for target in targets:
                        try:
                            df = await asyncio.to_thread(
                                D.features, 
                                [target], 
                                ['$close'], 
                                start_time=resolved_start_str, 
                                end_time=resolved_end_str, 
                                freq=qlib_handler_freq
                            )
                            if not df.empty:
                                found_df = df
                                final_target = target
                                break
                        except:
                            continue

                    if found_df is not None and not found_df.empty:
                        # Convert price to returns for Qlib benchmark configuration
                        # This works best with Qlib's internal account logic
                        benchmark_series = found_df['$close'].groupby(level='datetime').first()
                        benchmark_returns = benchmark_series.sort_index().pct_change().fillna(0)
                        benchmark_to_pass = pd.Series(benchmark_returns)
                        logger.info(f"Using pre-fetched benchmark '{final_target}' ({len(benchmark_to_pass)} points)")
                    else:
                        # Fallback: if we can't find ANY data for ANY target, 
                        # create a zero-return series to avoid Qlib's problematic string-based resolution
                        logger.warning(f"Could not find data for any benchmark targets {targets}. Using zero returns.")
                        if not predictions.empty:
                            dates = predictions.index.get_level_values('datetime').unique().sort_values()
                            benchmark_to_pass = pd.Series(0.0, index=dates)
                        else:
                            benchmark_to_pass = resolved_benchmark # Last resort fallback to string
                except Exception as b_err:
                    logger.warning(f"Error resolving benchmark: {b_err}. Falling back to string '{resolved_benchmark}'.")
                    benchmark_to_pass = resolved_benchmark

                def run_backtest_call():
                    # Suppress benign Qlib warnings and noisy logs inside the backtest call
                    qlib_logger = logging.getLogger("qlib")
                    old_level = qlib_logger.level
                    qlib_logger.setLevel(logging.WARNING)
                    
                    try:
                        with warnings.catch_warnings():
                            warnings.filterwarnings("ignore", message=".*common_infra is not set.*")
                            return qlib_backtest(
                                start_time=resolved_start_str,
                                end_time=resolved_end_str,
                                strategy=strategy_config,
                                executor=executor_config,
                                benchmark=benchmark_to_pass,
                                exchange_kwargs=exchange_kwargs,
                            )
                    finally:
                        qlib_logger.setLevel(old_level)

                portfolio_metric_dict, indicator_dict = await asyncio.to_thread(run_backtest_call)
                
                # Extract positions to generate order history
                positions_df = None
                for freq in ['1day', '1d', 'day', '1week', 'week', '60min', '1h']:
                    if freq in portfolio_metric_dict:
                        val = portfolio_metric_dict[freq]
                        if isinstance(val, tuple):
                            positions_df = val[1]
                        break
                
                orders = []
                if positions_df is not None:
                    try:
                        orders = extract_backtest_orders(positions_df)
                        logger.info(f"Extracted {len(orders)} orders from backtest history")
                    except Exception as e:
                        logger.warning(f"Failed to extract orders: {e}")

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
                        "topk": topk,
                        "long_short": long_short,
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
                    "orders": orders,
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                }

                evaluation = kpi_registry.record(
                    "backtest",
                    {
                        "model_id": model_id,
                        "dataset": dataset_ref,
                        "benchmark": resolved_benchmark,
                        "period": {
                            "start": resolved_start_str,
                            "end": resolved_end_str,
                        },
                    },
                    result["metrics"],
                )

                result["kpi_evaluation"] = evaluation.to_dict()
                result["deployment_ready"] = evaluation.passed

                log_level = "INFO" if evaluation.passed else "WARNING"
                if evaluation.breaches:
                    breach_summary = ", ".join(
                        f"{b['metric']}->{b.get('actual')}" for b in evaluation.breaches
                    )
                    message = f"Investment KPI check failed: {breach_summary}"
                else:
                    message = "Investment KPI check passed"

                await monitor.add_log(process_id, log_level, message)

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


def get_exchange_config(costs: str, funding: bool = False, freq: str = "day") -> Dict[str, Any]:
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
            "freq": freq,
            "limit_threshold": None,      # No price limits for crypto
            "deal_price": "close",
            "open_cost": 0.0002,          # 0.02% - VIP maker fee (Binance VIP 1+)
            "close_cost": 0.0005,         # 0.05% - VIP taker fee
            "min_cost": 0,                # No minimum transaction cost for crypto
            "impact_cost": 0.00005,       # 0.005% - Low market impact (high liquidity)
        },
        "medium": {
            "freq": freq,
            "limit_threshold": None,
            "deal_price": "close",
            "open_cost": 0.0005,          # 0.05% - Standard maker fee (Binance)
            "close_cost": 0.001,          # 0.1% - Standard taker fee
            "min_cost": 0,
            "impact_cost": 0.0001,        # 0.01% - Moderate market impact
        },
        "high": {
            "freq": freq,
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
    Calculate crypto-specific performance metrics from Qlib output
    """
    try:
        # Extract the report dataframe (usually keyed by frequency, e.g., '1day' or '1week')
        report_df = None
        for freq in ['1day', '1d', 'day', '1week', 'week']:
            if freq in portfolio_dict:
                report_df = portfolio_dict[freq]
                break
        
        if report_df is None:
            # Fallback to first available key if any
            if portfolio_dict:
                first_key = list(portfolio_dict.keys())[0]
                report_df = portfolio_dict[first_key]
            else:
                return {}

        # Handle tuple return (report_df, positions_df)
        if isinstance(report_df, tuple):
            report_df = report_df[0]

        if report_df is None or report_df.empty:
            return {}
        # 'return' is the strategy return
        if 'return' in report_df.columns:
            returns = report_df['return']
        elif 'excess_return_with_cost' in report_df.columns:
            returns = report_df['excess_return_with_cost']
        else:
            # Try to find any column with 'return' in name
            return_cols = [c for c in report_df.columns if 'return' in c.lower()]
            if return_cols:
                returns = report_df[return_cols[0]]
            else:
                return {}

        if len(returns) == 0:
            return {}

        # Annualized return (365 days for crypto)
        total_return = (1 + returns).prod() - 1
        
        # Determine frequency for annualization
        # For daily crypto, we use 365. For weekly, we use 52.
        # Check frequency of index if possible, or use heuristic
        annualization_factor = 365
        if len(returns) > 1:
            # Check gap between first two indices
            if hasattr(returns.index, 'freq') and returns.index.freq == 'W':
                annualization_factor = 52
            elif (returns.index[1] - returns.index[0]).days >= 6:
                annualization_factor = 52

        years = len(returns) / annualization_factor
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Sharpe ratio
        daily_vol = returns.std()
        sharpe_ratio = (returns.mean() / daily_vol) * np.sqrt(annualization_factor) if daily_vol > 0 else 0

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


def extract_backtest_orders(positions_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Extract trade orders from Qlib positions DataFrame.
    
    Qlib positions_df typically has MultiIndex [datetime, instrument] 
    and columns like ['count', 'price', 'weight', ...].
    """
    if positions_df is None or positions_df.empty:
        return []

    orders = []
    
    try:
        # Standardize the index and columns
        df = positions_df.copy()
        
        # Ensure index names are correct
        if df.index.names != ['datetime', 'instrument']:
            # Try to fix if they are just swapped or mismatched
            if 'datetime' in df.index.names and 'instrument' in df.index.names:
                df = df.reorder_levels(['datetime', 'instrument'])
            else:
                # If index is not multi-index or levels are unnamed, this might fail
                return []

        # We need 'count' (quantity) and 'price'
        if 'count' not in df.columns:
            return []
            
        # Get list of unique instruments
        instruments = df.index.get_level_values('instrument').unique()
        
        for inst in instruments:
            inst_df = df.xs(inst, level='instrument').sort_index()
            # Calculate difference in count to find trades
            # Qlib count is the units held AFTER the trade at that timestamp
            inst_df['prev_count'] = inst_df['count'].shift(1).fillna(0)
            inst_df['trade_size'] = inst_df['count'] - inst_df['prev_count']
            
            # Filter rows where a trade occurred
            trades = inst_df[inst_df['trade_size'].abs() > 1e-10].copy()
            
            for dt, row in trades.iterrows():
                side = "BUY" if row['trade_size'] > 0 else "SELL"
                orders.append({
                    "datetime": dt.isoformat(),
                    "symbol": inst,
                    "side": side,
                    "amount": abs(float(row['trade_size'])),
                    "price": float(row['price']) if 'price' in row else 0.0,
                    "value": abs(float(row['trade_size'] * (row['price'] if 'price' in row else 0.0))),
                })
        
        # Sort orders by datetime
        orders.sort(key=lambda x: x['datetime'])
        
    except Exception as e:
        logging.error(f"Error in extract_backtest_orders: {e}")
        
    return orders
