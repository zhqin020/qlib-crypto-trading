#!/usr/bin/env python3
"""
Hyperparameter Tuning Script for Qlib Crypto Platform (Optuna Edition)
Uses Bayesian Optimization to find optimal parameters.
Supports parallel execution, PostgreSQL persistence, and resource optimization.
"""

import json
import subprocess
import re
import shutil
import time
import os
import optuna
import pandas as pd
from pathlib import Path
import logging
import argparse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/trading_params.json")
BACKUP_PATH = Path("config/trading_params.json.bak")
BEST_CONFIG_PATH = Path("config/trading_params.best.json")
HISTORY_PATH = Path("tuning_history.csv")
TMP_DIR = Path("tmp/tuning")

def setup_dirs():
    """Ensure temporary directories exist."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

def generate_wfv_folds(start_date="2023-01-01", end_date="2025-01-01", n_folds=3, ratio=(6, 1, 2), step_months=3):
    """Generate folds for Walk-Forward Validation using custom ratios."""
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    unit_days = 30
    folds = []
    
    for i in range(n_folds):
        f_start = start + relativedelta(months=i * step_months)
        
        d_train = ratio[0] * unit_days
        d_valid = ratio[1] * unit_days
        d_test = ratio[2] * unit_days
        
        train_end = f_start + timedelta(days=d_train)
        valid_start = train_end + timedelta(days=1)
        valid_end = valid_start + timedelta(days=d_valid)
        test_start = valid_end + timedelta(days=1)
        test_end = test_start + timedelta(days=d_test)
        
        if test_end > end:
            if test_start < end:
                test_end = end
            else:
                break
            
        folds.append({
            "train": [f_start.strftime("%Y-%m-%d"), train_end.strftime("%Y-%m-%d")],
            "valid": [valid_start.strftime("%Y-%m-%d"), valid_end.strftime("%Y-%m-%d")],
            "test": [test_start.strftime("%Y-%m-%d"), test_end.strftime("%Y-%m-%d")],
        })
    return folds

def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)

def save_config(config: Dict[str, Any], path: Path = CONFIG_PATH):
    with open(path, "w") as f:
        json.dump(config, f, indent=4)

def run_command(cmd, env_vars: Optional[Dict[str, str]] = None):
    """Run a shell command and return the result."""
    start_time = time.time()
    
    # Merge current environment with custom variables
    current_env = os.environ.copy()
    if env_vars:
        current_env.update(env_vars)
        
    result = subprocess.run(
        cmd, 
        shell=True, 
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Merge stderr into stdout
        text=True,
        env=current_env
    )
    duration = time.time() - start_time
    return result, duration

def parse_metrics(output):
    """Extract metrics from backtest output."""
    metrics = {
        "sharpe": -999.0,
        "annual_return": 0.0,
        "max_drawdown": 1.0,
        "sortino": -999.0,
        "calmar": -999.0,
        "win_rate": 0.0
    }
    
    # Sharpe Ratio
    sharpe_match = re.search(r"Sharpe Ratio:\s*([-\d.]+)", output)
    if not sharpe_match:
        sharpe_match = re.search(r"Sharpe=([-\d.]+)", output)
    if sharpe_match:
        metrics["sharpe"] = float(sharpe_match.group(1))
        
    # Annual Return
    return_match = re.search(r"Annualized Return:\s*([-\d.]+)%", output)
    if return_match:
        metrics["annual_return"] = float(return_match.group(1)) / 100.0
        
    # Max Drawdown
    mdd_match = re.search(r"Max Drawdown:\s*([-\d.]+)%", output)
    if mdd_match:
        metrics["max_drawdown"] = float(mdd_match.group(1)) / 100.0

    # Sortino Ratio
    sortino_match = re.search(r"Sortino Ratio:\s*([-\d.]+)", output)
    if sortino_match:
        metrics["sortino"] = float(sortino_match.group(1))

    # Calmar Ratio
    calmar_match = re.search(r"Calmar Ratio:\s*([-\d.]+)", output)
    if calmar_match:
        metrics["calmar"] = float(calmar_match.group(1))

    # Win Rate
    win_match = re.search(r"Win Rate:\s*([-\d.]+)%", output)
    if win_match:
        metrics["win_rate"] = float(win_match.group(1)) / 100.0
        
    return metrics

def calculate_composite_score(metrics):
    """Calculate Weighted Performance Score (WPS)"""
    # 1. Base Score Components
    sharpe_score = max(0, metrics["sharpe"]) * 0.40
    sortino_score = max(0, metrics["sortino"]) * 0.15
    calmar_score = max(0, metrics["calmar"]) * 0.10
    win_rate_score = (metrics["win_rate"] / 0.5) * 0.10
    
    composite = sharpe_score + sortino_score + calmar_score + win_rate_score
    
    # 2. Risk Penalties
    mdd = metrics["max_drawdown"]
    if mdd > 0.50:
        return -999.0 # Hard disqualify for 50% drawdown
    
    penalty = 0.0
    if mdd > 0.20:
        penalty = (mdd - 0.20) * 2.0 # -0.2 score for every 10% past 20% MDD
        
    return composite - penalty

def objective(trial, model_type, folds, base_config):
    """Optuna objective function."""
    trial_id = trial.number
    trial_config_path = TMP_DIR / f"config_{model_type}_{trial_id}.json"
    
    # Read tuning limits
    tuning_cfg = base_config.get("tuning", {})
    n_epochs = tuning_cfg.get("n_epochs", 20)
    early_stop = tuning_cfg.get("early_stop", 10)
    threads_per_job = str(tuning_cfg.get("max_threads_per_job", 2))
    hs_options = tuning_cfg.get("hidden_size_options", [32, 64])
    
    # 1. Define parameters based on model type
    params = {}
    if model_type == "lightgbm":
        params["learning_rate"] = trial.suggest_float("learning_rate", 0.005, 0.1, log=True)
        params["num_leaves"] = trial.suggest_int("num_leaves", 7, 127)
        params["lambda_l2"] = trial.suggest_float("lambda_l2", 1e-4, 10.0, log=True)
        params["max_depth"] = trial.suggest_int("max_depth", 3, 15)
        params["num_threads"] = int(threads_per_job)
    elif model_type == "xgboost":
        params["learning_rate"] = trial.suggest_float("learning_rate", 0.005, 0.1, log=True)
        params["max_depth"] = trial.suggest_int("max_depth", 3, 12)
        params["n_estimators"] = trial.suggest_int("n_estimators", 100, 1000)
        params["nthread"] = int(threads_per_job)
    elif model_type in ["lstm", "alstm"]:
        params["lr"] = trial.suggest_float("lr", 1e-5, 5e-3, log=True)
        params["dropout"] = trial.suggest_float("dropout", 0.1, 0.6)
        params["hidden_size"] = trial.suggest_categorical("hidden_size", hs_options)
        params["n_epochs"] = n_epochs
        params["early_stop"] = early_stop
        if model_type == "alstm":
            params["rnn_type"] = trial.suggest_categorical("rnn_type", ["GRU", "LSTM"])
    
    # 1.1 Strategy parameters tuning
    strat_params = {}
    strat_params["topk"] = trial.suggest_int("topk", 3, 5)
    strat_params["leverage"] = trial.suggest_int("leverage", 1, 3)
    strat_params["threshold"] = trial.suggest_float("threshold", 0.0, 0.5)
    
    # 2. Update config for this trial
    trial_config = base_config.copy()
    if "training" not in trial_config: trial_config["training"] = {}
    if "models" not in trial_config["training"]: trial_config["training"]["models"] = {}
    if model_type not in trial_config["training"]["models"]: trial_config["training"]["models"][model_type] = {}
    
    trial_config["training"]["models"][model_type].update(params)
    trial_config["training"]["model_type"] = model_type
    
    if "backtest" not in trial_config: trial_config["backtest"] = {}
    if "trading" not in trial_config["trading"]: trial_config["trading"] = {}
    trial_config["backtest"]["topk"] = strat_params["topk"]
    trial_config["trading"]["leverage"] = strat_params["leverage"]
    trial_config["trading"]["signal_threshold"] = strat_params["threshold"]
    
    save_config(trial_config, trial_config_path)
    
    # Environment variables for thread control
    env_vars = {
        "OMP_NUM_THREADS": threads_per_job,
        "MKL_NUM_THREADS": threads_per_job,
        "OPENBLAS_NUM_THREADS": threads_per_job,
        "VECLIB_MAXIMUM_THREADS": threads_per_job,
        "NUMEXPR_NUM_THREADS": threads_per_job
    }
    
    # 3. Iterate Folds
    all_metrics = []
    composite_scores = []
    
    logger.info(f"[Trial {trial_id}] Started with Model Params: {params} and Strat Params: {strat_params}")
    
    try:
        for i, fold in enumerate(folds):
            logger.info(f"[Trial {trial_id}] Fold {i+1}/{len(folds)} ({fold['test'][0]} to {fold['test'][1]})")
            
            # Train
            train_cmd = (f"{sys.executable} scripts/train_sample_model.py --config {trial_config_path} "
                         f"--model {model_type} "
                         f"--train-start {fold['train'][0]} --train-end {fold['train'][1]} "
                         f"--valid-start {fold['valid'][0]} --valid-end {fold['valid'][1]}")
            train_res, _ = run_command(train_cmd, env_vars=env_vars)
            if train_res.returncode != 0:
                logger.error(f"[Trial {trial_id}] Train FAIL on Fold {i+1}")
                composite_scores.append(-999.0)
                continue
                
            # Backtest
            bt_cmd = (f"{sys.executable} scripts/run_backtest.py --config {trial_config_path} "
                      f"--start {fold['test'][0]} --end {fold['test'][1]} "
                      f"--topk {strat_params['topk']} --leverage {strat_params['leverage']} "
                      f"--threshold {strat_params['threshold']}")
            bt_res, _ = run_command(bt_cmd, env_vars=env_vars)
            if bt_res.returncode != 0:
                logger.error(f"[Trial {trial_id}] BT FAIL on Fold {i+1}")
                composite_scores.append(-999.0)
                continue
                
            metrics = parse_metrics(bt_res.stdout)
            score = calculate_composite_score(metrics)
            all_metrics.append(metrics)
            composite_scores.append(score)
            logger.info(f"[Trial {trial_id}] Fold {i+1} Result -> Sharpe: {metrics['sharpe']:.2f}, Score: {score:.2f}")

        # Aggregate results
        if not composite_scores:
            return -999.0
            
        avg_score = sum(composite_scores) / len(composite_scores)
        avg_sharpe = sum(m["sharpe"] for m in all_metrics) / len(all_metrics) if all_metrics else -999.0
        
        logger.info(f"[Trial {trial_id}] Finished -> Avg Sharpe: {avg_sharpe:.3f}, Final WPS: {avg_score:.4f}")
        
        trial.set_user_attr("sharpe", avg_sharpe)
        trial.set_user_attr("max_drawdown", sum(m["max_drawdown"] for m in all_metrics) / len(all_metrics) if all_metrics else 1.0)
        
        return avg_score
    finally:
        if trial_config_path.exists():
            trial_config_path.unlink()

def get_storage_url(config: Dict[str, Any]) -> Optional[str]:
    """Build PostgreSQL storage URL from config."""
    db_cfg = config.get("database", {})
    if not db_cfg.get("use_db", False):
        return None
    
    user = db_cfg.get("user", "crypto_user")
    password = db_cfg.get("password", "crypto")
    host = db_cfg.get("host", "localhost")
    port = db_cfg.get("port", 5432)
    dbname = db_cfg.get("dbname", "qlib_crypto")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

def main():
    parser = argparse.ArgumentParser(description="Hyperparameter Tuning with Optuna (Parallel & Persistent)")
    parser.add_argument("--trials", type=int, default=20, help="Number of trials to run")
    parser.add_argument("--model", type=str, default=None, help="Model type to tune (lightgbm, xgboost, alstm, lstm)")
    parser.add_argument("--folds", type=int, default=3, help="Number of folds for Walk-Forward Validation")
    parser.add_argument("--n_jobs", type=int, default=1, help="Number of parallel trials (workers)")
    parser.add_argument("--study_name", type=str, default=None, help="Name of the Optuna study")
    args = parser.parse_args()

    setup_dirs()

    if not CONFIG_PATH.exists():
        logger.error(f"{CONFIG_PATH} not found")
        return

    # Backup configuration
    shutil.copy(CONFIG_PATH, BACKUP_PATH)
    logger.info(f"Backed up config to {BACKUP_PATH}")

    try:
        base_config = load_config()
        model_type = args.model or base_config.get("training", {}).get("model_type", "lightgbm")
        
        # Get Rolling Window Config
        rw_cfg = base_config.get("training", {}).get("rolling_window", {})
        n_folds = args.folds if args.folds != 3 else rw_cfg.get("n_folds", 3)
        fold_ratio = rw_cfg.get("fold_ratio", [6, 1, 2])
        step_months = rw_cfg.get("step_months", 3)

        # Get Data/Tuning range
        tr_start = base_config.get("training", {}).get("start_time", "2023-01-01")
        dt_end = base_config.get("data", {}).get("end_time")
        if not dt_end: # Default to now
            dt_end = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

        folds = generate_wfv_folds(
            start_date=tr_start,
            end_date=dt_end,
            n_folds=n_folds,
            ratio=fold_ratio,
            step_months=step_months
        )
        
        storage_url = get_storage_url(base_config)
        study_name = args.study_name or f"crypto_tuning_{model_type}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        logger.info(f"Starting Optuna Optimization with {len(folds)} Folds")
        logger.info(f"Model: {model_type.upper()}, Trials: {args.trials}, Parallel Workers: {args.n_jobs}")
        if storage_url:
            logger.info(f"Using persistence: {storage_url} (Study: {study_name})")
        
        study = optuna.create_study(
            study_name=study_name,
            storage=storage_url,
            direction="maximize",
            load_if_exists=True
        )
        
        study.optimize(
            lambda trial: objective(trial, model_type, folds, base_config), 
            n_trials=args.trials, 
            n_jobs=args.n_jobs
        )
        
        # Save results
        df = study.trials_dataframe()
        df.to_csv(HISTORY_PATH, index=False)
        logger.info(f"Tuning history saved to {HISTORY_PATH}")
        
        # Report Best
        print("\n" + "="*60)
        print("OPTIMIZATION COMPLETE (WPS Based)")
        print(f"Best Composite Score (WPS): {study.best_value:.4f}")
        
        best_trial = study.best_trial
        print(f"Best Sharpe Ratio: {best_trial.user_attrs.get('sharpe', 0):.3f}")
        print(f"Best Max Drawdown: {best_trial.user_attrs.get('max_drawdown', 0)*100:.2f}%")
        
        print("Best Parameters:")
        for k, v in study.best_params.items():
            print(f"  - {k}: {v}")
            
        # Update and save best config
        best_config = load_config(BACKUP_PATH) # Re-load from backup
        if "training" not in best_config: best_config["training"] = {}
        if "models" not in best_config["training"]: best_config["training"]["models"] = {}
        if model_type not in best_config["training"]["models"]: best_config["training"]["models"][model_type] = {}
        
        model_keys = ["learning_rate", "num_leaves", "lambda_l2", "max_depth", "n_estimators", "lr", "dropout", "hidden_size", "rnn_type"]
        best_model_params = {k: v for k, v in study.best_params.items() if k in model_keys}
        
        best_config["training"]["models"][model_type].update(best_model_params)
        best_config["training"]["model_type"] = model_type
        
        if "backtest" not in best_config: best_config["backtest"] = {}
        if "trading" not in best_config: best_config["trading"] = {}
        if "topk" in study.best_params:
            best_config["backtest"]["topk"] = int(study.best_params["topk"])
        if "leverage" in study.best_params:
            best_config["trading"]["leverage"] = int(study.best_params["leverage"])
        if "threshold" in study.best_params:
            best_config["trading"]["signal_threshold"] = study.best_params["threshold"]
            
        save_config(best_config, BEST_CONFIG_PATH)
        print(f"Best configuration saved to: {BEST_CONFIG_PATH}")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\nTuning interrupted by user.")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        # Restore original configuration
        if BACKUP_PATH.exists():
            shutil.copy(BACKUP_PATH, CONFIG_PATH)
            logger.info(f"Restored original configuration from {BACKUP_PATH}")

if __name__ == "__main__":
    main()
