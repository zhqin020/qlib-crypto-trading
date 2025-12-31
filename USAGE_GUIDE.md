# 📖 Qlib Crypto Trading Platform: Usage Guide

This guide covers the complete end-to-end workflow of the platform, from data acquisition to real-time predictions and the web dashboard.

## 📑 Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Data Pipeline](#2-data-pipeline)
3. [Model Training](#3-model-training)
4. [Backtesting](#4-backtesting)
5. [Serving & Predictions](#5-serving--predictions)
6. [Hyperparameter Tuning](#6-hyperparameter-tuning)
7. [Web Dashboard](#7-web-dashboard)
8. [MCP Server (Agentic Tool)](#8-mcp-server)

---

## 1. Prerequisites

### Environment Setup
The platform requires a Conda or Virtualenv environment with `qlib` and `pandas` installed.
```bash
# Recommended: Use the provided environment
conda activate qlib
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
```

### Configuration
Update `.env` for security and Redis settings:
```bash
WEBSOCKET_API_KEYS=your_key_here
PROCESS_MONITOR_REDIS_URL="" # Set to empty if Redis is not locally available
```

### Centralized Trading Parameters
Most trading parameters (symbols, interval, exchange, market type) are managed in `config/trading_params.json`.

#### Data & Backtest Config
```json
{
    "data": {
        "interval": "1h",
        "exchange": "binance",
        "market_type": "future",
        "symbols": ["BTC/USDT", "ETH/USDT", "..."]
    },
    "backtest": {
        "start_time": "2023-05-03",
        "end_time": "2025-01-01",
        "topk": 5
    }
}
```

#### Trading & Risk Config
```json
{
    "trading": {
        "direction": "long-short",
        "init_investment": 10000,
        "leverage": 1,
        "take_profit": 0.1,
        "stop_loss": -0.05
    }
}
```
*   `direction`: Supports `long`, `short`, and `long-short`.
*   `take_profit`/`stop_loss`: Percentage-based exit triggers.
*Note: Scripts will use these values as defaults unless overridden via command-line arguments.*

---

## 2. Data Pipeline

The data pipeline handles fetching OHLCV data and converting it into Qlib's high-performance binary format.

### Step A: Download Data
Download historical data from Binance (default) for a set of symbols.
```bash
# Download daily data (using defaults from config)
python scripts/download_sample_data.py --interval 1d

# Download hourly future data from Kraken
python scripts/download_sample_data.py --provider kraken --market-type future --interval 1h --start 2024-01-01
```

**Supported Market Types**: `spot` (default), `future`, `swap`, `margin`.

### Step B: Convert to Qlib Format
Convert the raw CSV files into a Qlib "Snapshot" using the 24/7 crypto calendar.
```bash
# Convert to 1d dataset (ref: crypto)
python scripts/convert_to_qlib.py --freq 1d

# Convert to 1h dataset (ref: crypto_1h)
python scripts/convert_to_qlib.py --freq 1h
```

---

## 3. Model Training
Train Machine Learning models using configurations defined in `config/trading_params.json`.

### Supported Models
- **LightGBM / XGBoost**: Efficient gradient boosting trees.
- **LSTM / Transformer**: Deep learning models for sequence modeling.

### Training Command
1. **Configure**: Set `training.model_type` in `config/trading_params.json` (e.g., `"model_type": "lstm"`).
2. **Train**:
```bash
# Auto-loads config and trains the specified model
python scripts/train_sample_model.py

# Or override via CLI
python scripts/train_sample_model.py --model xgboost
```
*The model and its metadata will be saved in `models/trained/`.*

---

## 4. Backtesting

Evaluate your models using crypto-specific performance metrics. The engine handles instrument name case-matching and frequency resolution automatically.

### Run Backtest
```bash
# Automatically finds and tests the LATEST trained model of the configured type
python scripts/run_backtest.py

# Or specify a model explicitly
python scripts/run_backtest.py <MODEL_ID>
```

### Key Metrics Tracked
- **Annualized Return**: 365-day basis.
- **Sharpe/Sortino Ratio**: Risk-adjusted performance.
- **Max Drawdown**: Worst peak-to-trough decline.
- **Calmar Ratio**: Return over Max DD.

---

## 5. Serving & Predictions

Generate signals for the current or a specific date.

### Generate Daily Predictions
```bash
python scripts/predict.py <MODEL_ID> --dataset crypto_1h
```
*Outputs a ranked list of instruments to trade based on the model's score.*

---

## 6. Hyperparameter Tuning

Optimize model performance using Bayesian Optimization (via Optuna) and a multi-factor scoring system.

### Optimization Logic (WPS)
The tuner calculates a **Weighted Performance Score (WPS)** to find balanced parameters:
- **Sharpe (40%)** + **Sortino (15%)** + **Calmar (10%)** + **Win Rate (10%)**.
- **Max Drawdown Penalty**: Heavy penalties for MDD > 20%. Disqualifies MDD > 50%.

### Tuning Commands
```bash
# Tune LightGBM for 20 trials (default model in config)
python scripts/tune_hyperparameters.py --trials 20

# Tune ALSTM for 50 trials (includes topk and leverage optimization)
python scripts/tune_hyperparameters.py --model alstm --trials 50
```

### Integrated Strategy Tuning
The tuner now optimizes not just model weights (learning rate, hidden size), but also **Strategy Parameters**:
- **topk**: Optimal number of assets to hold.
- **leverage**: Optimal leverage based on model confidence and risk tolerance.

### Outputs
- `config/trading_params.best.json`: The best parameter set found.
- `tuning_history.csv`: Full history of all trials with detailed metrics (Sortino, MDD, etc.).

---

## 7. Web Dashboard

### Start the Server
```bash
./scripts/start_server_enhanced.sh
```

### Dashboard Features
1. **Marketplace**: Live quotes and data downloads.
2. **Backtesting UI**: Trigger and visualize backtests with live progress bars.
3. **Process Monitor**: Real-time log streaming for long-running training/backtesting jobs.
4. **Authentication**: Secured via WebSocket API keys.

---

## 8. MCP Server (Agentic Tool)

The platform is a first-class citizen of the **Model Context Protocol (MCP)**, allowing AI agents (like Claude or Gemini) to control it directly.

### Start MCP Server
```bash
./scripts/start_mcp_server.sh
```

### Key MCP Tools
- `backtests_run`: Run a backtest job.
- `models_train`: Start a training session.
- `market_data_get_quote`: Fetch real-time prices.
- `data_create_snapshot`: Update the Qlib binary dataset.

---

## 🛠️ Troubleshooting
- **ModuleNotFoundError**: Ensure `export PYTHONPATH=$PYTHONPATH:$(pwd)/src` is run in your current shell.
- **Connection Refused (Redis)**: Set `PROCESS_MONITOR_REDIS_URL=""` in `.env` if you don't have Redis running.
- **Empty Backtest Results**: Check that your dataset frequency (1d vs 1h) matches your model's training frequency. The engine will try to auto-switch, but the data must exist in `data/qlib/`.
