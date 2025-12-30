#!/usr/bin/env python3
"""
Hyperparameter Tuning Script for Qlib Crypto Platform
Automatically searches for optimal parameters by running training and backtesting loops.
"""

import itertools
import json
import subprocess
import re
import shutil
import time
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# 1. Define Search Space
# ==========================================
# Only model-specific parameters will be tuned.
# Modify lists to expand search space.
SEARCH_SPACE = {
    "lightgbm": {
        "learning_rate": [0.01, 0.05],
        "num_leaves": [15, 31],
        "lambda_l2": [0.01, 0.1]
    },
    "xgboost": {
        "learning_rate": [0.01, 0.05],
        "max_depth": [4, 6],
        "n_estimators": [300, 500]
    },
    "lstm": {
        "lr": [0.001, 0.0001],
        "hidden_size": [64, 128],
        "dropout": [0.2, 0.4]
    },
    "alstm": {
        "lr": [0.001, 0.0001],
        "dropout": [0.2, 0.4],
        "rnn_type": ["GRU", "LSTM"]
    }
}

CONFIG_PATH = Path("config/trading_params.json")
BACKUP_PATH = Path("config/trading_params.json.bak")
BEST_CONFIG_PATH = Path("config/trading_params.best.json")

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

def parse_sharpe(output):
    """Extract Sharpe Ratio from backtest output."""
    # Matches "Sharpe Ratio: 0.597" or "Sharpe=0.597"
    match = re.search(r"Sharpe Ratio:\s*([-\d.]+)", output)
    if match:
        return float(match.group(1))
    
    match = re.search(r"Sharpe=([-\d.]+)", output)
    if match:
        return float(match.group(1))
    return -999.0

def main():
    if not CONFIG_PATH.exists():
        logger.error(f"{CONFIG_PATH} not found")
        return

    # 1. Backup configuration
    shutil.copy(CONFIG_PATH, BACKUP_PATH)
    logger.info(f"Backed up config to {BACKUP_PATH}")

    try:
        base_config = load_config()
        
        # Determine model type to tune (from current config)
        training_cfg = base_config.get("training", {})
        model_type = training_cfg.get("model_type", "lightgbm")
        
        # Allow override? For now, stick to config.
        # Ensure we have a search space
        if model_type not in SEARCH_SPACE:
            logger.warning(f"No search space defined for '{model_type}'. Defaulting to 'lightgbm' search space.")
            model_type = "lightgbm"
            
        space = SEARCH_SPACE[model_type]
        keys = list(space.keys())
        values = list(space.values())
        combinations = list(itertools.product(*values))
        
        logger.info(f"Starting Grid Search for Model: {model_type.upper()}")
        logger.info(f"Parameters to tune: {keys}")
        logger.info(f"Total combinations: {len(combinations)}")
        print("-" * 60)
        
        best_sharpe = -float('inf')
        best_params = None
        results = []
        
        # 2. Iterate through combinations
        for i, combo in enumerate(combinations):
            params = dict(zip(keys, combo))
            step_str = f"[{i+1}/{len(combinations)}]"
            print(f"{step_str} Testing Params: {params}")
            
            # Update configuration logic for nested structure
            current_config = load_config()
            if "training" not in current_config:
                current_config["training"] = {}
            if "models" not in current_config["training"]:
                current_config["training"]["models"] = {}
            if model_type not in current_config["training"]["models"]:
                current_config["training"]["models"][model_type] = {}
                
            # Update specific model params
            current_config["training"]["models"][model_type].update(params)
            
            # Ensure model_type is set correctly
            current_config["training"]["model_type"] = model_type
            
            save_config(current_config)
            
            # A. Training Phase
            print(f"       Training...", end="", flush=True)
            train_res, train_time = run_command("python scripts/train_sample_model.py")
            
            if train_res.returncode != 0:
                print(f" \033[91mFAILED\033[0m")
                logger.error(f"Training failed:\n{train_res.stderr[-500:]}")
                continue
            else:
                print(f" Done ({train_time:.1f}s)")
                
            # B. Backtesting Phase
            print(f"       Backtesting...", end="", flush=True)
            # Run without args to let it auto-pick the latest model we just trained
            bt_res, bt_time = run_command("python scripts/run_backtest.py")
            
            if bt_res.returncode != 0:
                print(f" \033[91mFAILED\033[0m")
                logger.error(f"Backtest failed:\n{bt_res.stderr[-500:]}")
                continue
            
            sharpe = parse_sharpe(bt_res.stdout)
            print(f" Done ({bt_time:.1f}s) -> Sharpe: \033[1m{sharpe:.4f}\033[0m")
            
            # Record result
            results.append({
                "params": params,
                "sharpe": sharpe
            })
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params
                print(f"       \033[92m>>> NEW BEST FOUND! <<<\033[0m")
                
                # Save best config to a separate file
                save_config(current_config, BEST_CONFIG_PATH)

        # 3. Report Results
        print("=" * 60)
        print("Tuning Complete")
        print(f"Best Sharpe Ratio: {best_sharpe:.4f}")
        print(f"Best Parameters: {best_params}")
        print(f"Best configuration saved to: {BEST_CONFIG_PATH}")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\nTuning interrupted by user.")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        # 4. Restore original configuration
        if BACKUP_PATH.exists():
            shutil.move(BACKUP_PATH, CONFIG_PATH)
            logger.info(f"Restored original configuration from {BACKUP_PATH}")

if __name__ == "__main__":
    main()
