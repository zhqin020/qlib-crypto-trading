"""
Enhanced FastAPI with real-time WebSocket support
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import json
import asyncio
from datetime import datetime

from .events import get_event_broadcaster
from ..monitoring.process_monitor import monitor, ProcessInfo

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Qlib Crypto Trading Platform",
    description="AI-powered cryptocurrency trading platform with real-time updates",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get event broadcaster
broadcaster = get_event_broadcaster()

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

try:
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
except:
    pass  # Static dir might not exist yet


# Request models
class DataDownloadRequest(BaseModel):
    symbols: List[str]
    start_date: str
    end_date: str
    interval: str = "1d"
    provider: str = "binance"

class TrainModelRequest(BaseModel):
    dataset: str
    feature_handler: str = "alpha158"
    model_handler: str = "lightgbm"
    params: Optional[Dict[str, Any]] = None

class BacktestRequest(BaseModel):
    model_id: str
    dataset: str
    costs: str = "medium"
    rebalance: str = "weekly"

class PredictionRequest(BaseModel):
    model_id: str
    dataset: str


# Process response models
class ProcessLogResponse(BaseModel):
    timestamp: str
    level: str
    message: str

class ProcessMetricsResponse(BaseModel):
    start_time: Optional[str]
    end_time: Optional[str]
    duration_seconds: Optional[float]
    progress_percent: float
    current_step: str
    total_steps: int
    completed_steps: int
    memory_mb: Optional[float]
    cpu_percent: Optional[float]

class ProcessResponse(BaseModel):
    process_id: str
    process_type: str
    status: str
    metrics: Dict[str, Any]
    logs: List[Dict[str, str]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


# WebSocket endpoint for real-time updates
@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for real-time platform events"""
    await broadcaster.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive client messages
            data = await websocket.receive_text()
            # Echo back or handle client commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        broadcaster.disconnect(websocket)


# Enhanced API endpoints with broadcasting
@app.get("/")
async def root():
    """Root endpoint - returns enhanced dashboard"""
    return FileResponse(STATIC_DIR / "index.html") if (STATIC_DIR / "index.html").exists() else HTMLResponse(content=get_enhanced_dashboard_html())


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "qlib-crypto-platform",
        "version": "2.0.0",
        "websocket_clients": len(broadcaster.active_connections)
    }


@app.get("/api/system/stats")
async def get_system_stats():
    """Get system statistics"""
    project_root = Path(__file__).parent.parent.parent

    # Count various resources
    models_count = len(list((project_root / "models" / "trained").glob("*_meta.json"))) if (project_root / "models" / "trained").exists() else 0
    backtests_count = len(list((project_root / "backtests").glob("*.json"))) if (project_root / "backtests").exists() else 0
    predictions_count = len(list((project_root / "predictions").glob("*.json"))) if (project_root / "predictions").exists() else 0
    experiments_count = len(list((project_root / "experiments").glob("*.json"))) if (project_root / "experiments").exists() else 0

    return {
        "models": models_count,
        "backtests": backtests_count,
        "predictions": predictions_count,
        "experiments": experiments_count,
        "websocket_clients": len(broadcaster.active_connections),
        "event_history": len(broadcaster.event_history)
    }


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
async def download_data(request: DataDownloadRequest, background_tasks: BackgroundTasks):
    """Download crypto market data"""
    from ..data_pipeline.market_data import download_crypto_universe

    # Notify start
    await broadcaster.broadcast_notification("info", f"Starting data download for {len(request.symbols)} symbols")

    async def download_task():
        try:
            result = await download_crypto_universe(
                symbols=request.symbols,
                start_date=request.start_date,
                end_date=request.end_date,
                interval=request.interval,
                provider=request.provider
            )
            await broadcaster.broadcast_data_update("download_complete", {
                "symbols": list(result.keys()),
                "count": len(result)
            })
            await broadcaster.broadcast_notification("success", f"Downloaded data for {len(result)} symbols")
        except Exception as e:
            await broadcaster.broadcast_notification("error", f"Download failed: {str(e)}")

    background_tasks.add_task(download_task)

    return {"status": "started", "symbols": request.symbols}


@app.post("/api/data/convert")
async def convert_data(dataset: str, freq: str = "1d", background_tasks: BackgroundTasks = None):
    """Convert CSV data to Qlib format"""
    from ..data_pipeline.snapshot import create_snapshot

    await broadcaster.broadcast_notification("info", f"Converting dataset: {dataset}")

    try:
        result = await create_snapshot(
            dataset=dataset,
            calendar=f"crypto_{freq}"
        )

        await broadcaster.broadcast_data_update("conversion_complete", result)
        await broadcaster.broadcast_notification("success", f"Dataset '{dataset}' converted successfully")

        return result
    except Exception as e:
        await broadcaster.broadcast_notification("error", f"Conversion failed: {str(e)}")
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
async def train_model(request: TrainModelRequest, background_tasks: BackgroundTasks):
    """Train a new model"""
    import uuid
    from ..models.trainer import train_model as train
    from ..data_pipeline.features import create_feature_set

    # Generate process ID
    process_id = f"training_{uuid.uuid4().hex[:8]}"

    await broadcaster.broadcast_notification("info", f"Starting model training: {request.model_handler}")

    async def train_task():
        try:
            # Start process monitoring
            await monitor.start_process(process_id, "training", total_steps=3)

            # Step 1: Create feature set
            await monitor.update_progress(process_id, 10.0, "Creating feature set", 1)
            feature_set = await create_feature_set(
                dataset_ref=request.dataset,
                handler=request.feature_handler
            )

            await broadcaster.broadcast_model_update("creating", "in_progress", {"feature_set": feature_set["name"]})

            # Step 2: Train model
            await monitor.update_progress(process_id, 30.0, f"Training {request.model_handler} model", 2)
            result = await train(
                dataset_ref=request.dataset,
                feature_set_ref=feature_set["name"],
                handler=request.model_handler,
                params=request.params
            )

            if "error" not in result:
                # Step 3: Finalizing
                await monitor.update_progress(process_id, 90.0, "Saving model", 3)
                await monitor.complete_process(process_id, result)

                await broadcaster.broadcast_model_update(result["model_id"], "completed", result.get("metrics", {}))
                await broadcaster.broadcast_notification("success", f"Model {result['model_id']} trained successfully")
            else:
                await monitor.fail_process(process_id, result['error'])
                await broadcaster.broadcast_notification("error", f"Training failed: {result['error']}")
        except Exception as e:
            await monitor.fail_process(process_id, str(e))
            await broadcaster.broadcast_notification("error", f"Training error: {str(e)}")

    background_tasks.add_task(train_task)

    return {"status": "started", "process_id": process_id, "dataset": request.dataset, "model": request.model_handler}


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
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """Run backtest for a model"""
    import uuid
    from ..backtesting.engine import run_backtest as run_bt

    # Generate process ID
    process_id = f"backtest_{uuid.uuid4().hex[:8]}"

    await broadcaster.broadcast_notification("info", f"Starting backtest for model: {request.model_id}")

    async def backtest_task():
        try:
            # Start process monitoring
            await monitor.start_process(process_id, "backtest", total_steps=2)

            await broadcaster.broadcast_backtest_update(request.model_id, 0.0)
            await monitor.update_progress(process_id, 10.0, "Loading model and data", 1)

            result = await run_bt(
                model_id=request.model_id,
                dataset_ref=request.dataset,
                costs=request.costs,
                rebalance=request.rebalance
            )

            if "error" not in result:
                await monitor.update_progress(process_id, 90.0, "Calculating metrics", 2)
                await monitor.complete_process(process_id, result)

                await broadcaster.broadcast_backtest_update(request.model_id, 1.0, result.get("metrics", {}))
                await broadcaster.broadcast_notification("success", f"Backtest complete for {request.model_id}")
            else:
                await monitor.fail_process(process_id, result['error'])
                await broadcaster.broadcast_notification("error", f"Backtest failed: {result['error']}")
        except Exception as e:
            await monitor.fail_process(process_id, str(e))
            await broadcaster.broadcast_notification("error", f"Backtest error: {str(e)}")

    background_tasks.add_task(backtest_task)

    return {"status": "started", "process_id": process_id, "model_id": request.model_id}


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
async def generate_predictions(request: PredictionRequest, background_tasks: BackgroundTasks):
    """Generate predictions for today"""
    import uuid
    from ..serving.predictor import predict_today

    # Generate process ID
    process_id = f"prediction_{uuid.uuid4().hex[:8]}"

    await broadcaster.broadcast_notification("info", f"Generating predictions with model: {request.model_id}")

    async def predict_task():
        try:
            # Start process monitoring
            await monitor.start_process(process_id, "prediction", total_steps=2)

            await monitor.update_progress(process_id, 20.0, "Loading model", 1)

            result = await predict_today(
                model_id=request.model_id,
                dataset_ref=request.dataset
            )

            if "error" not in result:
                await monitor.update_progress(process_id, 80.0, "Generating predictions", 2)
                await monitor.complete_process(process_id, result)

                await broadcaster.broadcast_prediction_update(request.model_id, result.get("predictions", []))
                await broadcaster.broadcast_notification("success", f"Generated {len(result.get('predictions', []))} predictions")
            else:
                await monitor.fail_process(process_id, result['error'])
                await broadcaster.broadcast_notification("error", f"Prediction failed: {result['error']}")
        except Exception as e:
            await monitor.fail_process(process_id, str(e))
            await broadcaster.broadcast_notification("error", f"Prediction error: {str(e)}")

    background_tasks.add_task(predict_task)

    return {"status": "started", "process_id": process_id, "model_id": request.model_id}


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
    from ..data_pipeline.market_data import get_quote

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
            data = await websocket.receive_json()
            symbols = data.get("symbols", [])

            from ..data_pipeline.market_data import get_quotes_batch
            quotes = await get_quotes_batch(symbols)

            await websocket.send_json({
                "type": "quotes",
                "data": quotes
            })

            await asyncio.sleep(1)  # Rate limiting

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# Process monitoring endpoints
@app.get("/api/processes")
async def get_all_processes():
    """Get all tracked processes"""
    processes = await monitor.get_all_processes()
    return {
        "processes": [p.to_dict() for p in processes],
        "total": len(processes)
    }


@app.get("/api/processes/running")
async def get_running_processes():
    """Get only running processes"""
    processes = await monitor.get_running_processes()
    return {
        "processes": [p.to_dict() for p in processes],
        "total": len(processes)
    }


@app.get("/api/processes/{process_id}")
async def get_process(process_id: str):
    """Get specific process by ID"""
    process = await monitor.get_process(process_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Process {process_id} not found")
    return process.to_dict()


@app.delete("/api/processes/{process_id}")
async def cancel_process(process_id: str):
    """Cancel a running process"""
    try:
        await monitor.cancel_process(process_id)
        return {"status": "cancelled", "process_id": process_id}
    except ValueError as e:
        error_msg = str(e)
        # Distinguish between 404 (not found) and 400 (invalid operation)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)


@app.get("/api/processes/{process_id}/logs")
async def get_process_logs(process_id: str, limit: int = 100):
    """
    Get logs for a specific process

    Args:
        process_id: Unique process identifier
        limit: Maximum number of logs to return (default: 100, max: 1000)

    Returns:
        {
            "logs": [
                {
                    "timestamp": "2025-10-07T10:00:00",
                    "level": "INFO",
                    "message": "Started training process"
                }
            ]
        }
    """
    process = await monitor.get_process(process_id)

    if not process:
        raise HTTPException(
            status_code=404,
            detail=f"Process '{process_id}' not found"
        )

    # Limit to max 1000 logs
    limit = min(limit, 1000)

    logs = [
        {
            "timestamp": log.timestamp,
            "level": log.level,
            "message": log.message
        }
        for log in process.logs[-limit:]
    ]

    return {"logs": logs}


@app.websocket("/ws/processes")
async def websocket_processes(websocket: WebSocket):
    """WebSocket endpoint for real-time process updates - ALL processes"""
    await websocket.accept()

    try:
        while True:
            # Send current process states
            processes = await monitor.get_all_processes()
            await websocket.send_json({
                "type": "process_update",
                "processes": [p.to_dict() for p in processes],
                "timestamp": datetime.now().isoformat()
            })

            # Wait before next update
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@app.websocket("/ws/processes/{process_id}")
async def websocket_process_updates(websocket: WebSocket, process_id: str):
    """
    WebSocket endpoint for real-time updates for a SPECIFIC process

    Sends process updates every 500ms while the process is running.
    Automatically closes when process completes, fails, or is cancelled.

    Protocol:
        Client -> Server: {"type": "ping"} (keepalive)
        Server -> Client: {
            "type": "process_update",
            "data": {
                "process_id": "training_abc123",
                "status": "running",
                "metrics": {...},
                "logs": [...],
                ...
            }
        }
        Server -> Client: {
            "type": "process_complete",
            "data": {...}
        } (then closes)

    Args:
        process_id: Unique process identifier
    """
    await websocket.accept()

    try:
        # First, verify process exists
        process = await monitor.get_process(process_id)
        if not process:
            await websocket.send_json({
                "type": "error",
                "message": f"Process '{process_id}' not found"
            })
            await websocket.close()
            return

        # Send initial state
        await websocket.send_json({
            "type": "process_update",
            "data": process.to_dict()
        })

        # Keep sending updates while process is running
        while True:
            # Check for client messages (keepalive, disconnect)
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.1
                )
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                pass  # No message, continue

            # Get latest process state
            process = await monitor.get_process(process_id)
            if not process:
                await websocket.send_json({
                    "type": "error",
                    "message": "Process no longer exists"
                })
                break

            # Send update
            await websocket.send_json({
                "type": "process_update",
                "data": process.to_dict()
            })

            # Check if process completed/failed/cancelled
            if process.status.value in ["completed", "failed", "cancelled"]:
                await websocket.send_json({
                    "type": "process_complete",
                    "data": process.to_dict()
                })
                break

            # Wait 500ms before next update
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from process {process_id}")
    except Exception as e:
        logger.error(f"WebSocket error for process {process_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


def get_enhanced_dashboard_html() -> str:
    """Return enhanced dashboard HTML with WebSocket support"""
    # This will be replaced by the React app
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Qlib Crypto Trading Platform</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
        <h1>Loading...</h1>
        <p>Enhanced dashboard loading. See /static/index.html</p>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5100)
