#!/bin/bash
# Start the web API server

cd "$(dirname "$0")/.."

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "Starting Qlib Crypto Trading Platform API..."
echo "API will be available at http://localhost:5100"
echo "API documentation at http://localhost:5100/docs"
echo ""

python -m uvicorn src.ui.api:app --host 0.0.0.0 --port 5100 --reload
