# 🚀 Quick Start Guide

Get up and running with the Qlib Crypto Trading Platform in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- 4GB RAM minimum
- Internet connection (for downloading data)

## Step 1: Installation (2 minutes)

```bash
# Clone or navigate to the project
cd qlib-2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create directory structure
make setup
```

## State Management

The platform automatically manages Qlib state. When working with multiple datasets:

```python
from utils.qlib_state import init_qlib_clean

# Each initialization clears previous state
init_qlib_clean(provider_uri="data/qlib/dataset_A", region="cn")
# ... work with dataset A ...

init_qlib_clean(provider_uri="data/qlib/dataset_B", region="cn")
# ... work with dataset B (no contamination from A)
```

**Features:**
- Automatic 24/7 crypto calendar registration
- Cache clearing prevents data bleed
- No manual state management needed

See [STATE_BLEED_FIX.md](STATE_BLEED_FIX.md) for technical details.

## Step 2: Download Sample Data (3 minutes)

Download historical data for top 10 cryptocurrencies:

```bash
make download-data
```

This downloads daily OHLCV data for BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, DOT, and MATIC from 2023-2024.

**Expected output:**
```
Downloading sample crypto data...
Symbols: BTC/USDT, ETH/USDT, BNB/USDT, ...
✓ Downloaded BTC/USDT: 731 records
✓ Downloaded ETH/USDT: 731 records
...
Data download complete!
```

## Step 3: Convert to Qlib Format (1 minute)

```bash
make convert
```

Converts CSV files to Qlib's optimized binary format with 24/7 crypto calendar.

**Expected output:**
```
Converting crypto data to Qlib format...
✓ Converted BTC_USDT: 731 records
✓ Converted ETH_USDT: 731 records
...
Converted: 10/10 successful
```

## Step 4: Train Your First Model (2-5 minutes)

```bash
make train
```

Trains a LightGBM model with Alpha158 features.

**Expected output:**
```
Creating feature set...
Feature set created: alpha158_crypto

Training LightGBM model...
Model Training Complete!
  Model ID: lightgbm_20241006_123456_abc123
  Handler: lightgbm
```

## Step 5: Run Backtest (1 minute)

```bash
python scripts/run_backtest.py lightgbm_20241006_123456_abc123
```

Replace with your actual model ID from Step 4.

**Expected output:**
```
Backtest Results:
  Annualized Return: 42.5%
  Sharpe Ratio: 1.85
  Max Drawdown: -18.2%
  Win Rate: 58.3%
```

## Step 6: Generate Predictions (30 seconds)

```bash
python scripts/predict.py lightgbm_20241006_123456_abc123
```

**Expected output:**
```
Top 10 Signals:
Rank   Symbol          Score
-----------------------------------
1      BTC_USDT        0.0523
2      SOL_USDT        0.0412
3      ETH_USDT        0.0389
...
```

## 🎉 Success!

You've just:
- ✅ Downloaded crypto market data
- ✅ Converted it to Qlib format
- ✅ Trained an AI model
- ✅ Backtested the strategy
- ✅ Generated trading signals

## What's Next?

### Start the Web Interface

```bash
make api
```

Visit http://localhost:5100 for the dashboard and API docs.

### Try Different Models

```bash
# LSTM model
python scripts/train_sample_model.py --model lstm

# Transformer model
python scripts/train_sample_model.py --model transformer

# Ensemble of models
python scripts/run_experiment.py --recipe expert_ensemble
```

### Use the MCP Server

```bash
make mcp
```

Configure your MCP client (like Claude Desktop) to use the server.

### Run with Docker

```bash
make docker-up
```

Starts API, MCP server, PostgreSQL, and Redis.

## Common Issues

### "No module named 'qlib'"

```bash
pip install pyqlib
```

### "No CSV files found"

Make sure you ran `make download-data` first.

### Model training fails

Check you have enough RAM (4GB minimum) and the data was converted successfully.

### Import errors

Ensure you're in the virtual environment:
```bash
source venv/bin/activate
```

## Need Help?

- Full documentation: See [README.md](README.md)
- API docs: http://localhost:5100/docs
- Issues: GitHub Issues

## Quick Reference

```bash
# Data pipeline
make download-data    # Download crypto data
make convert          # Convert to Qlib format

# Training
make train           # Train default model

# Services
make api             # Start web API
make mcp             # Start MCP server

# Testing
make test            # Run tests

# Docker
make docker-up       # Start all services
make docker-down     # Stop services

# Cleanup
make clean           # Remove cache files
make clean-all       # Remove everything
```

Happy trading! 🚀
