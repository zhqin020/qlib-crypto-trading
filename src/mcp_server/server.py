"""
MCP Server Implementation for Qlib Crypto Trading Platform
"""

import asyncio
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
from mcp.server import Server
from mcp.types import Tool, TextContent, Resource
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("qlib-crypto-trading")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools"""
    return [
        # Data Management Tools
        Tool(
            name="data_create_snapshot",
            description="Build a PIT snapshot for a dataset/universe",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "description": "Dataset name"},
                    "calendar": {"type": "string", "description": "Calendar type (crypto_daily, crypto_hourly)"},
                    "start": {"type": "string", "format": "date", "nullable": True},
                    "end": {"type": "string", "format": "date", "nullable": True},
                },
                "required": ["dataset", "calendar"],
            },
        ),
        Tool(
            name="features_create_set",
            description="Create a feature set configuration (Alpha158/360/custom)",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_ref": {"type": "string"},
                    "handler": {"type": "string", "description": "Handler class name"},
                    "params": {"type": "object"},
                    "processors": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["dataset_ref", "handler"],
            },
        ),
        # Market Data Tools
        Tool(
            name="market_data_get_quote",
            description="Get real-time quote for a crypto symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Crypto symbol (e.g., BTC/USDT)"},
                    "provider": {"type": "string", "nullable": True, "description": "Data provider (binance, kraken, coinbase)"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="market_data_get_quotes_batch",
            description="Get real-time quotes for multiple symbols",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {"type": "array", "items": {"type": "string"}},
                    "provider": {"type": "string", "nullable": True},
                },
                "required": ["symbols"],
            },
        ),
        Tool(
            name="market_data_get_historical",
            description="Get historical price data for a symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "start_date": {"type": "string", "format": "date"},
                    "end_date": {"type": "string", "format": "date"},
                    "interval": {"type": "string", "default": "1d", "description": "Data interval (1m, 5m, 1h, 1d)"},
                    "provider": {"type": "string", "nullable": True},
                },
                "required": ["symbol", "start_date", "end_date"],
            },
        ),
        Tool(
            name="market_data_subscribe",
            description="Subscribe to real-time market data updates",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {"type": "array", "items": {"type": "string"}},
                    "fields": {"type": "array", "items": {"type": "string"}, "default": ["price"]},
                    "update_interval": {"type": "number", "default": 1},
                },
                "required": ["symbols"],
            },
        ),
        # Model Training Tools
        Tool(
            name="models_train",
            description="Train a model against a dataset + feature set",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_ref": {"type": "string"},
                    "feature_set_ref": {"type": "string"},
                    "handler": {"type": "string", "description": "Model handler (lightgbm, lstm, transformer)"},
                    "params": {"type": "object"},
                },
                "required": ["dataset_ref", "feature_set_ref", "handler"],
            },
        ),
        # Experiment Tools
        Tool(
            name="experiments_run_recipe",
            description="Execute an experiment recipe (Beginner or Expert mode)",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset": {"type": "string"},
                    "recipe": {"type": "string"},
                    "costs": {"type": "string", "enum": ["low", "medium", "high"]},
                    "rebalance": {"type": "string", "enum": ["weekly", "monthly"]},
                    "params": {"type": "object"},
                },
                "required": ["dataset", "recipe", "costs", "rebalance"],
            },
        ),
        # Backtesting Tools
        Tool(
            name="backtests_run",
            description="Run a backtest using a trained model and return performance metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_id": {"type": "string"},
                    "dataset_ref": {"type": "string"},
                    "costs": {"type": "string", "enum": ["low", "medium", "high"]},
                    "rebalance": {"type": "string", "enum": ["weekly", "monthly"]},
                    "funding": {"type": "boolean"},
                    "topk": {"type": "integer", "default": 10},
                    "long_short": {"type": "boolean", "default": false},
                },
                "required": ["model_id", "dataset_ref", "costs", "rebalance"],
            },
        ),
        Tool(
            name="experiments_tag",
            description="Assign lifecycle tags to a run (candidate/promoted/archived)",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["run_id", "tags"],
            },
        ),
        Tool(
            name="runs_cancel",
            description="Cancel a long-running job cooperatively",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["run_id"],
            },
        ),
        # Serving Tools
        Tool(
            name="serving_predict_today",
            description="Generate end-of-day predictions for the current trading session",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_id": {"type": "string"},
                    "dataset_ref": {"type": "string"},
                },
                "required": ["model_id", "dataset_ref"],
            },
        ),
        # Notification & Scheduling Tools
        Tool(
            name="notifications_dispatch",
            description="Send notifications (Teams/email) with templated payloads",
            inputSchema={
                "type": "object",
                "properties": {
                    "template_id": {"type": "string"},
                    "channels": {"type": "array", "items": {"type": "string"}},
                    "payload": {"type": "object"},
                },
                "required": ["template_id", "channels"],
            },
        ),
        Tool(
            name="schedules_create",
            description="Create or update a scheduled job via RRULE",
            inputSchema={
                "type": "object",
                "properties": {
                    "job": {"type": "string"},
                    "rrule": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["job", "rrule"],
            },
        ),
        # Knowledge Base Tool
        Tool(
            name="knowledge_describe_screen",
            description="Retrieve knowledge-base entries describing UI screens",
            inputSchema={
                "type": "object",
                "properties": {
                    "embedding": {"type": "array", "items": {"type": "number"}},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["embedding"],
            },
        ),
    ]


# Tool Handlers
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "data_create_snapshot":
            from data_pipeline.snapshot import create_snapshot
            result = await create_snapshot(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "features_create_set":
            from data_pipeline.features import create_feature_set
            result = await create_feature_set(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "market_data_get_quote":
            from data_pipeline.market_data import get_quote
            result = await get_quote(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "market_data_get_quotes_batch":
            from data_pipeline.market_data import get_quotes_batch
            result = await get_quotes_batch(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "market_data_get_historical":
            from data_pipeline.market_data import get_historical
            result = await get_historical(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "market_data_subscribe":
            from data_pipeline.market_data import subscribe
            result = await subscribe(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "models_train":
            from models.trainer import train_model
            result = await train_model(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "experiments_run_recipe":
            from models.experiments import run_recipe
            result = await run_recipe(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "backtests_run":
            from backtesting.engine import run_backtest
            result = await run_backtest(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "experiments_tag":
            from models.experiments import tag_run
            result = await tag_run(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "runs_cancel":
            from models.experiments import cancel_run
            result = await cancel_run(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "serving_predict_today":
            from serving.predictor import predict_today
            result = await predict_today(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "notifications_dispatch":
            from serving.notifications import dispatch_notification
            result = await dispatch_notification(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "schedules_create":
            from serving.scheduler import create_schedule
            result = await create_schedule(**arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "knowledge_describe_screen":
            result = {"message": "Knowledge base not yet implemented"}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources"""
    resources = []

    # List datasets
    if DATA_DIR.exists():
        for dataset_dir in (DATA_DIR / "processed").glob("*"):
            if dataset_dir.is_dir():
                resources.append(
                    Resource(
                        uri=f"dataset://{dataset_dir.name}",
                        name=f"Dataset: {dataset_dir.name}",
                        mimeType="application/json",
                    )
                )

    return resources


if __name__ == "__main__":
    import mcp.server.stdio
    mcp.server.stdio.stdio_server(app)
