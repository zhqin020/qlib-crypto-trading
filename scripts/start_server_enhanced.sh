#!/bin/bash
# Start the enhanced web API server with real-time WebSocket support

cd "$(dirname "$0")/.."

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   Qlib Crypto Trading Platform - Enhanced Live Dashboard      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Starting enhanced API server with real-time updates..."
echo ""
echo "📊 Dashboard:     http://localhost:5100"
echo "📖 API Docs:      http://localhost:5100/docs"
echo "🔌 WebSocket:     ws://localhost:5100/ws/events"
echo ""
echo "Features:"
echo "  ✓ Real-time activity feed"
echo "  ✓ Live MCP tool execution updates"
echo "  ✓ WebSocket event broadcasting"
echo "  ✓ Toast notifications"
echo "  ✓ Live statistics"
echo ""
echo "Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python -m uvicorn src.ui.api_enhanced:app --host 0.0.0.0 --port 5100 --reload
