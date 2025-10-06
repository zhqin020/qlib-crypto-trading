#!/bin/bash
# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}/src"

# Send startup messages to stderr to keep stdout clean for MCP protocol
echo "Starting MCP Server for Qlib Crypto Trading Platform..." >&2

# Try to use venv python if it exists, otherwise fall back to system python3
if [ -f "${PROJECT_ROOT}/venv/bin/python3" ]; then
    "${PROJECT_ROOT}/venv/bin/python3" -m src.mcp_server
else
    python3 -m src.mcp_server
fi
