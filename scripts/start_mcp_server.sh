#!/bin/bash
# Start the MCP server

cd "$(dirname "$0")/.."

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "Starting MCP Server for Qlib Crypto Trading Platform..."
echo ""

python -m src.mcp_server.server
