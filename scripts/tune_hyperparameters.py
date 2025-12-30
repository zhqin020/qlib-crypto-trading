#!/usr/bin/env python3
"""
Hyperparameter Tuning Script for Qlib Crypto Platform (Optuna Edition)
Uses Bayesian Optimization to find optimal parameters.
"""

import json
import subprocess
import re
import shutil
import time
import optuna
import pandas as pd
from pathlib import Path
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/trading_params.json")
BACKUP_PATH = Path("config/trading_params.json.bak")
BEST_CONFIG_PATH = Path("config/trading_params.best.json")
HISTORY_PATH = Path("tuning_history.csv")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(config, path=CONFIG_PATH):
    with open(path, "w") as f:
        json.dump(config, f, indent=4)

def run_command(cmd):
    """Run a shell command and return the result."""
    start_time = time.time()
    result = subprocess.run(
        cmd, 
        shell=True, 
        capture_output=True, 
        text=True
    )
    duration = time.time() - start_time
    return result, duration

def parse_metrics(output):
    """Extract metrics from backtest output."""
    metrics = {
        "sharpe": -999.0,
        "annual_return": 0.0,
        "max_drawdown": 1.0
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
        
    return metrics

def objective(trial, model_type):
    """Optuna objective function."""
    
    # 1. Define parameters based on model type
    params = {}
    if model_type == "lightgbm":
        params["learning_rate"] = trial.suggest_float("learning_rate", 0.005, 0.1, log=True)
        params["num_leaves"] = trial.suggest_int("num_leaves", 7, 127)
        params["lambda_l2"] = trial.suggest_float("lambda_l2", 1e-4, 10.0, log=True)
        params["max_depth"] = trial.suggest_int("max_depth", 3, 15)
    elif model_type == "xgboost":
        params["learning_rate"] = trial.suggest_float("learning_rate", 0.005, 0.1, log=True)
        params["max_depth"] = trial.suggest_int("max_depth", 3, 12)
        params["n_estimators"] = trial.suggest_int("n_estimators", 100, 1000)
    elif model_type in ["lstm", "alstm"]:
        params["lr"] = trial.suggest_float("lr", 1e-5, 5e-3, log=True)
        params["dropout"] = trial.suggest_float("dropout", 0.1, 0.6)
        params["hidden_size"] = trial.suggest_categorical("hidden_size", [32, 64, 128])
        if model_type == "alstm":
            params["rnn_type"] = trial.suggest_categorical("rnn_type", ["GRU", "LSTM"])
    
    # 2. Update config
    current_config = load_config()
    if "training" not in current_config: current_config["training"] = {}
    if "models" not in current_config["training"]: current_config["training"]["models"] = {}
    if model_type not in current_config["training"]["models"]: current_config["training"]["models"][model_type] = {}
    
    current_config["training"]["models"][model_type].update(params)
    current_config["training"]["model_type"] = model_type
    save_config(current_config)
    
    # 3. Train
    print(f"\n   [Trial {trial.number}] Parameters: {params}")
    print(f"   Training...", end="", flush=True)
    train_res, train_time = run_command("python scripts/train_sample_model.py")
    if train_res.returncode != 0:
        print(f" FAILED (check logs)")
        return -999.0
    print(f" Done ({train_time:.1f}s)")
        
    # 4. Backtest
    print(f"   Backtesting...", end="", flush=True)
    bt_res, bt_time = run_command("python scripts/run_backtest.py")
    if bt_res.returncode != 0:
        print(f" FAILED")
        return -999.0
        
    metrics = parse_metrics(bt_res.stdout)
    print(f" Done ({bt_time:.1f}s) -> Sharpe: {metrics['sharpe']:.4f}")
    
    # Store metrics in trial user attributes
    trial.set_user_attr("annual_return", metrics["annual_return"])
    trial.set_user_attr("max_drawdown", metrics["max_drawdown"])
    
    return metrics["sharpe"]

def main():
    parser = argparse.ArgumentParser(description="Hyperparameter Tuning with Optuna")
    parser.add_argument("--trials", type=int, default=20, help="Number of trials to run")
    parser.add_argument("--model", type=str, default=None, help="Model type to tune (lightgbm, xgboost, alstm, lstm)")
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        logger.error(f"{CONFIG_PATH} not found")
        return

    # Backup configuration
    shutil.copy(CONFIG_PATH, BACKUP_PATH)
    logger.info(f"Backed up config to {BACKUP_PATH}")

    try:
        base_config = load_config()
        model_type = args.model or base_config.get("training", {}).get("model_type", "lightgbm")
        
        logger.info(f"Starting Optuna Optimization for Model: {model_type.upper()}")
        logger.info(f"Target trials: {args.trials}")
        
        study = optuna.create_study(direction="maximize")
        study.optimize(lambda trial: objective(trial, model_type), n_trials=args.trials)
        
        # Save results
        df = study.trials_dataframe()
        df.to_csv(HISTORY_PATH, index=False)
        logger.info(f"Tuning history saved to {HISTORY_PATH}")
        
        # Report Best
        print("\n" + "="*60)
        print("OPTIMIZATION COMPLETE")
        print(f"Best Sharpe Ratio: {study.best_value:.4f}")
        print("Best Parameters:")
        for k, v in study.best_params.items():
            print(f"  - {k}: {v}")
            
        # Update and save best config
        # We re-load the original config (from backup) to avoid trial-specific changes
        best_config = load_config()
        if "training" not in best_config: best_config["training"] = {}
        if "models" not in best_config["training"]: best_config["training"]["models"] = {}
        if model_type not in best_config["training"]["models"]: best_config["training"]["models"][model_type] = {}
        
        best_config["training"]["models"][model_type].update(study.best_params)
        best_config["training"]["model_type"] = model_type
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
            shutil.move(BACKUP_PATH, CONFIG_PATH)
            logger.info(f"Restored original configuration from {BACKUP_PATH}")

if __name__ == "__main__":
    main()
