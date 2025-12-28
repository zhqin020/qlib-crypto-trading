"""
FastAPI REST API for the trading platform
"""

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import importlib
import logging
from utils.logging_config import get_logger
import json
from datetime import datetime, timezone

from .security import validate_api_key, create_ws_token

logger = get_logger(__name__)


def _import_module(module_path: str):
    """Import module supporting both 'pkg' and 'src.pkg' styles."""
    try:
        return importlib.import_module(module_path)
    except ImportError as first_error:
        try:
            return importlib.import_module(f"src.{module_path}")
        except ImportError:
            raise first_error

app = FastAPI(
    title="Qlib Crypto Trading Platform",
    description="AI-powered cryptocurrency trading platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class DataDownloadRequest(BaseModel):
    symbols: List[str]
    start_date: str
    end_date: str
    interval: str = "1d"
    provider: str = "binance"

class TrainModelRequest(BaseModel):
    dataset: str
    feature_handler: str
    model_handler: str
    params: Optional[Dict[str, Any]] = None
    segments: Optional[Dict[str, Tuple[str, str]]] = None

class BacktestRequest(BaseModel):
    model_id: str
    dataset: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    benchmark: Optional[str] = None
    costs: str = "medium"
    rebalance: str = "weekly"
    funding: bool = False

class PredictionRequest(BaseModel):
    model_id: str
    dataset: str


class WebSocketTokenRequest(BaseModel):
    api_key: str


class WebSocketTokenResponse(BaseModel):
    token: str
    expires_at: datetime


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint - returns dashboard HTML"""
    return HTMLResponse(content=get_dashboard_html(), status_code=200)


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "qlib-crypto-platform"}


@app.post("/api/auth/ws-token", response_model=WebSocketTokenResponse)
async def issue_websocket_token(request: WebSocketTokenRequest):
    """Exchange an API key for a signed WebSocket token."""
    user_id = validate_api_key(request.api_key)
    if not user_id:
        raise HTTPException(status_code=403, detail="Invalid API key")

    token, expires_at = create_ws_token(user_id)
    expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    return WebSocketTokenResponse(token=token, expires_at=expires_dt)


@app.get("/api/datasets")
async def list_datasets():
    """List available datasets"""
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "qlib"

    if not data_dir.exists():
        return {"datasets": []}

    datasets = []
    for dataset_dir in data_dir.iterdir():
        if dataset_dir.is_dir():
            meta_file = dataset_dir / "snapshot_meta.json"
            if meta_file.exists():
                with open(meta_file) as f:
                    meta = json.load(f)
                datasets.append(meta)
            else:
                datasets.append({"name": dataset_dir.name})

    return {"datasets": datasets}


@app.post("/api/data/download")
async def download_data(request: DataDownloadRequest):
    """Download crypto market data"""
    download_crypto_universe = _import_module("data_pipeline.market_data").download_crypto_universe

    try:
        result = await download_crypto_universe(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            interval=request.interval,
            provider=request.provider
        )
        return {"status": "success", "symbols": list(result.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/convert")
async def convert_data(dataset: str, freq: str = "1d"):
    """Convert CSV data to Qlib format"""
    create_snapshot = _import_module("data_pipeline.snapshot").create_snapshot

    try:
        result = await create_snapshot(
            dataset=dataset,
            calendar=f"crypto_{freq}"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models")
async def list_models():
    """List trained models"""
    project_root = Path(__file__).parent.parent.parent
    models_dir = project_root / "models" / "trained"

    if not models_dir.exists():
        return {"models": []}

    models = []
    for meta_file in models_dir.glob("*_meta.json"):
        with open(meta_file) as f:
            meta = json.load(f)
            models.append(meta)

    return {"models": models}


@app.post("/api/models/train")
async def train_model(request: TrainModelRequest):
    """Train a new model"""
    train = _import_module("models.trainer").train_model
    create_feature_set = _import_module("data_pipeline.features").create_feature_set

    try:
        # Create feature set
        feature_set = await create_feature_set(
            dataset_ref=request.dataset,
            handler=request.feature_handler
        )

        if "error" in feature_set:
            raise HTTPException(status_code=400, detail=feature_set["error"])

        # Train model
        result = await train(
            dataset_ref=request.dataset,
            feature_set_ref=feature_set["name"],
            handler=request.model_handler,
            params=request.params,
            segments=request.segments,
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models/{model_id}")
async def get_model(model_id: str):
    """Get model details"""
    project_root = Path(__file__).parent.parent.parent
    meta_file = project_root / "models" / "trained" / f"{model_id}_meta.json"

    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    with open(meta_file) as f:
        return json.load(f)


@app.post("/api/backtests/run")
async def run_backtest(request: BacktestRequest):
    """Run backtest for a model"""
    run_bt = _import_module("backtesting.engine").run_backtest

    try:
        result = await run_bt(
            model_id=request.model_id,
            dataset_ref=request.dataset,
            start_time=request.start_date,
            end_time=request.end_date,
            benchmark=request.benchmark,
            costs=request.costs,
            rebalance=request.rebalance,
            funding=request.funding
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtests")
async def list_backtests():
    """List backtest results"""
    project_root = Path(__file__).parent.parent.parent
    bt_dir = project_root / "backtests"

    if not bt_dir.exists():
        return {"backtests": []}

    backtests = []
    for bt_file in bt_dir.glob("*_backtest.json"):
        with open(bt_file) as f:
            backtests.append(json.load(f))

    return {"backtests": backtests}


@app.post("/api/predictions/generate")
async def generate_predictions(request: PredictionRequest):
    """Generate predictions for today"""
    predict_today = _import_module("serving.predictor").predict_today

    try:
        result = await predict_today(
            model_id=request.model_id,
            dataset_ref=request.dataset
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/predictions")
async def list_predictions():
    """List recent predictions"""
    project_root = Path(__file__).parent.parent.parent
    pred_dir = project_root / "predictions"

    if not pred_dir.exists():
        return {"predictions": []}

    predictions = []
    for pred_file in sorted(pred_dir.glob("*.json"), reverse=True)[:20]:
        with open(pred_file) as f:
            predictions.append(json.load(f))

    return {"predictions": predictions}


@app.get("/api/experiments")
async def list_experiments():
    """List experiments"""
    project_root = Path(__file__).parent.parent.parent
    exp_dir = project_root / "experiments"

    if not exp_dir.exists():
        return {"experiments": []}

    experiments = []
    for exp_file in exp_dir.glob("*.json"):
        with open(exp_file) as f:
            experiments.append(json.load(f))

    return {"experiments": experiments}


@app.get("/api/market-data/quote/{symbol}")
async def get_quote(symbol: str, provider: str = "binance"):
    """Get real-time quote"""
    get_quote = _import_module("data_pipeline.market_data").get_quote

    try:
        result = await get_quote(symbol, provider)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket endpoint for real-time market data"""
    await websocket.accept()

    try:
        while True:
            # Receive subscription request
            data = await websocket.receive_json()
            symbols = data.get("symbols", [])

            # Send initial data
            get_quotes_batch = _import_module("data_pipeline.market_data").get_quotes_batch
            quotes = await get_quotes_batch(symbols)

            await websocket.send_json({
                "type": "quotes",
                "data": quotes
            })

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()


def get_dashboard_html() -> str:
    """Return dashboard HTML"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Qlib Crypto Trading Platform</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                margin-bottom: 30px;
            }
            h1 {
                color: #667eea;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            .subtitle {
                color: #666;
                font-size: 1.2em;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .card {
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                transition: transform 0.3s, box-shadow 0.3s;
            }
            .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 40px rgba(0,0,0,0.15);
            }
            .card h2 {
                color: #333;
                margin-bottom: 15px;
                font-size: 1.5em;
            }
            .card p {
                color: #666;
                line-height: 1.6;
                margin-bottom: 15px;
            }
            .button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 1em;
                font-weight: 600;
                transition: opacity 0.3s;
            }
            .button:hover {
                opacity: 0.9;
            }
            .endpoint {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }
            .method {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
                margin-right: 10px;
            }
            .get { background: #61affe; color: white; }
            .post { background: #49cc90; color: white; }
            .ws { background: #fca130; color: white; }
            .feature-list {
                list-style: none;
                padding: 0;
            }
            .feature-list li {
                padding: 10px 0;
                border-bottom: 1px solid #eee;
            }
            .feature-list li:before {
                content: "✓ ";
                color: #667eea;
                font-weight: bold;
                margin-right: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Qlib Crypto Trading Platform</h1>
                <p class="subtitle">AI-Powered Cryptocurrency Trading & Research Platform</p>
            </div>

            <div class="grid">
                <div class="card">
                    <h2>📊 Features</h2>
                    <ul class="feature-list">
                        <li>Multi-exchange data acquisition</li>
                        <li>Advanced ML models (LightGBM, LSTM, Transformer)</li>
                        <li>Comprehensive backtesting</li>
                        <li>Real-time predictions</li>
                        <li>MCP server integration</li>
                        <li>24/7 crypto calendar support</li>
                    </ul>
                </div>

                <div class="card">
                    <h2>🔌 API Endpoints</h2>
                    <div class="endpoint">
                        <span class="method get">GET</span>/api/health
                    </div>
                    <div class="endpoint">
                        <span class="method get">GET</span>/api/datasets
                    </div>
                    <div class="endpoint">
                        <span class="method post">POST</span>/api/data/download
                    </div>
                    <div class="endpoint">
                        <span class="method post">POST</span>/api/models/train
                    </div>
                    <div class="endpoint">
                        <span class="method post">POST</span>/api/backtests/run
                    </div>
                    <div class="endpoint">
                        <span class="method ws">WS</span>/ws/market-data
                    </div>
                </div>

                <div class="card">
                    <h2>🎯 Quick Start</h2>
                    <p><strong>1. Download Data:</strong></p>
                    <code style="display:block;background:#f8f9fa;padding:10px;border-radius:5px;margin:10px 0;">
                        POST /api/data/download<br>
                        {"symbols": ["BTC/USDT"], "start_date": "2023-01-01", "end_date": "2024-12-31"}
                    </code>

                    <p><strong>2. Train Model:</strong></p>
                    <code style="display:block;background:#f8f9fa;padding:10px;border-radius:5px;margin:10px 0;">
                        POST /api/models/train<br>
                        {"dataset": "crypto", "model_handler": "lightgbm"}
                    </code>
                </div>
            </div>

            <div class="card">
                <h2>📖 Documentation</h2>
                <p>For full API documentation, visit <a href="/docs" style="color:#667eea;font-weight:600;">/docs</a> (Interactive Swagger UI)</p>
                <p>For MCP integration, see the MCP server documentation in the project README</p>
                <button class="button" onclick="window.location.href='/docs'">View API Docs</button>
            </div>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5100)
