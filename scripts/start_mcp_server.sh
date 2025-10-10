#!/bin/bash
# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}/src"
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

# Send startup messages to stderr to keep stdout clean for MCP protocol
echo "Starting MCP Server for Qlib Crypto Trading Platform..." >&2

# Try to use venv python if it exists, otherwise fall back to system python3
if [ -f "${PROJECT_ROOT}/venv/bin/python3" ]; then
    "${PROJECT_ROOT}/venv/bin/python3" -m src.mcp_server
else
    python3 -m src.mcp_server
fi
