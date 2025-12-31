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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Merge stderr into stdout
        text=True
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
    
    # 1.1 Strategy parameters tuning
    strat_params = {}
    strat_params["topk"] = trial.suggest_int("topk", 3, 10)
    strat_params["leverage"] = trial.suggest_int("leverage", 1, 3)
    
    # 2. Update config
    current_config = load_config()
    if "training" not in current_config: current_config["training"] = {}
    if "models" not in current_config["training"]: current_config["training"]["models"] = {}
    if model_type not in current_config["training"]["models"]: current_config["training"]["models"][model_type] = {}
    
    current_config["training"]["models"][model_type].update(params)
    current_config["training"]["model_type"] = model_type
    
    # Update backtest/trading sections
    if "backtest" not in current_config: current_config["backtest"] = {}
    if "trading" not in current_config: current_config["trading"] = {}
    current_config["backtest"]["topk"] = strat_params["topk"]
    current_config["trading"]["leverage"] = strat_params["leverage"]
    
    save_config(current_config)
    
    # 3. Train
    print(f"\n   [Trial {trial.number}] Model Params: {params}")
    print(f"   [Trial {trial.number}] Strat Params: {strat_params}")
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
    if metrics["sharpe"] == -999.0:
        logger.warning(f"Failed to parse metrics for trial {trial.number}. Output tail: {bt_res.stdout[-200:]}")
        
    wps_score = calculate_composite_score(metrics)
    print(f" Done ({bt_time:.1f}s) -> Sharpe: {metrics['sharpe']:.3f}, WPS: {wps_score:.4f}")
    
    # Store metrics in trial user attributes
    trial.set_user_attr("sharpe", metrics["sharpe"])
    trial.set_user_attr("annual_return", metrics["annual_return"])
    trial.set_user_attr("max_drawdown", metrics["max_drawdown"])
    trial.set_user_attr("sortino", metrics["sortino"])
    trial.set_user_attr("calmar", metrics["calmar"])
    trial.set_user_attr("win_rate", metrics["win_rate"])
    
    return wps_score

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
        print("OPTIMIZATION COMPLETE (WPS Based)")
        print(f"Best Composite Score (WPS): {study.best_value:.4f}")
        
        # Extract additional attributes for the best trial
        best_trial = study.best_trial
        print(f"Best Sharpe Ratio: {best_trial.user_attrs.get('sharpe', 0):.3f}")
        print(f"Best Max Drawdown: {best_trial.user_attrs.get('max_drawdown', 0)*100:.2f}%")
        
        print("Best Parameters:")
        for k, v in study.best_params.items():
            print(f"  - {k}: {v}")
            
        # Update and save best config
        # We re-load the original config (from backup) to avoid trial-specific changes
        best_config = load_config()
        if "training" not in best_config: best_config["training"] = {}
        if "models" not in best_config["training"]: best_config["training"]["models"] = {}
        if model_type not in best_config["training"]["models"]: best_config["training"]["models"][model_type] = {}
        
        # Candidate model keys to filter from study.best_params
        model_keys = ["learning_rate", "num_leaves", "lambda_l2", "max_depth", "n_estimators", "lr", "dropout", "hidden_size", "rnn_type"]
        best_model_params = {k: v for k, v in study.best_params.items() if k in model_keys}
        
        best_config["training"]["models"][model_type].update(best_model_params)
        best_config["training"]["model_type"] = model_type
        
        # Update strategy bests
        if "backtest" not in best_config: best_config["backtest"] = {}
        if "trading" not in best_config: best_config["trading"] = {}
        if "topk" in study.best_params:
            best_config["backtest"]["topk"] = study.best_params["topk"]
        if "leverage" in study.best_params:
            best_config["trading"]["leverage"] = study.best_params["leverage"]
            
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
