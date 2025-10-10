#!/bin/bash
# Start the web API server

cd "$(dirname "$0")/.."

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
export PROCESS_MONITOR_REDIS_URL="${PROCESS_MONITOR_REDIS_URL:-redis://localhost:6379/1}"
export PROCESS_MONITOR_REDIS_KEY="${PROCESS_MONITOR_REDIS_KEY:-process_monitor:processes}"
export PROCESS_MONITOR_CHANNEL="${PROCESS_MONITOR_CHANNEL:-process_monitor:events}"
export DATA_REFRESH_ENABLED="${DATA_REFRESH_ENABLED:-false}"
export DATA_REFRESH_SYMBOLS="${DATA_REFRESH_SYMBOLS:-BTC/USDT,ETH/USDT,BNB/USDT}"
export DATA_REFRESH_INTERVAL="${DATA_REFRESH_INTERVAL:-1d}"
export DATA_REFRESH_LOOKBACK_DAYS="${DATA_REFRESH_LOOKBACK_DAYS:-30}"
export DATA_REFRESH_FREQUENCY_MINUTES="${DATA_REFRESH_FREQUENCY_MINUTES:-180}"
export DATA_REFRESH_PROVIDER="${DATA_REFRESH_PROVIDER:-binance}"
export DATA_REFRESH_DATASET="${DATA_REFRESH_DATASET:-crypto}"
export DATA_REFRESH_CALENDAR="${DATA_REFRESH_CALENDAR:-crypto_1d}"
export DATA_REFRESH_OUTPUT_DIR="${DATA_REFRESH_OUTPUT_DIR:-data/raw}"
export SETUPTOOLS_SCM_PRETEND_VERSION="${SETUPTOOLS_SCM_PRETEND_VERSION:-0.9.8}"

echo "Starting Qlib Crypto Trading Platform API..."
echo "API will be available at http://localhost:5100"
echo "API documentation at http://localhost:5100/docs"
echo ""

python -m uvicorn src.ui.api_enhanced:app --host 0.0.0.0 --port 5100 --reload
