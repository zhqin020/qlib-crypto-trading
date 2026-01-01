"""
Enhanced FastAPI with real-time WebSocket support
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from contextlib import asynccontextmanager
import logging
from utils.logging_config import get_logger
import json
import asyncio
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from ui.events import get_event_broadcaster
from monitoring.process_monitor import monitor, ProcessInfo
from ui.security import (
    authenticate_websocket,
    connection_manager,
    check_message_size,
    MAX_MESSAGE_SIZE,
    HEARTBEAT_TIMEOUT,
    validate_api_key,
    create_ws_token,
)
from serving.oms import LocalOrderManager
from serving.schema import OrderSide
import os

logger = get_logger(__name__)


# Security validation helpers
def validate_dataset_name(name: str, max_length: int = 100) -> str:
    """
    Validate dataset name to prevent path traversal attacks.

    Args:
        name: Dataset name to validate
        max_length: Maximum allowed length (default: 100)

    Returns:
        Validated dataset name

    Raises:
        HTTPException: If name is invalid or contains malicious patterns
    """
    if not name:
        raise HTTPException(
            status_code=400,
            detail="Dataset name cannot be empty"
        )

    if len(name) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset name too long (max {max_length} characters)"
        )

    # Check for null bytes
    if '\x00' in name:
        raise HTTPException(
            status_code=400,
            detail="Dataset name contains invalid null byte"
        )

    # Check for path traversal patterns
    if '..' in name or '/' in name or '\\' in name:
        raise HTTPException(
            status_code=400,
            detail="Invalid dataset name: path traversal patterns not allowed"
        )

    # Whitelist: only alphanumeric, underscore, hyphen
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise HTTPException(
            status_code=400,
            detail="Dataset name must contain only alphanumeric characters, underscores, and hyphens"
        )

    return name


def validate_model_id(model_id: str, max_length: int = 200) -> str:
    """
    Validate model ID to prevent path traversal attacks.

    Args:
        model_id: Model ID to validate
        max_length: Maximum allowed length (default: 200)

    Returns:
        Validated model ID

    Raises:
        HTTPException: If model_id is invalid or contains malicious patterns
    """
    if not model_id:
        raise HTTPException(
            status_code=400,
            detail="Model ID cannot be empty"
        )

    if len(model_id) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Model ID too long (max {max_length} characters)"
        )

    # Check for null bytes
    if '\x00' in model_id:
        raise HTTPException(
            status_code=400,
            detail="Model ID contains invalid null byte"
        )

    # Check for path traversal patterns
    if '..' in model_id or '/' in model_id or '\\' in model_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid model ID: path traversal patterns not allowed"
        )

    return model_id


def validate_process_id(process_id: str, max_length: int = 100) -> str:
    """
    Validate process ID to prevent injection attacks.

    Args:
        process_id: Process ID to validate
        max_length: Maximum allowed length (default: 100)

    Returns:
        Validated process ID

    Raises:
        HTTPException: If process_id is invalid
    """
    if not process_id:
        raise HTTPException(
            status_code=400,
            detail="Process ID cannot be empty"
        )

    if len(process_id) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Process ID too long (max {max_length} characters)"
        )

    # Check for null bytes
    if '\x00' in process_id:
        raise HTTPException(
            status_code=400,
            detail="Process ID contains invalid null byte"
        )

    # Whitelist: only alphanumeric, underscore, hyphen
    if not re.match(r'^[a-zA-Z0-9_-]+$', process_id):
        raise HTTPException(
            status_code=400,
            detail="Process ID must contain only alphanumeric characters, underscores, and hyphens"
        )

    return process_id


def validate_path_safety(resolved_path: Path, allowed_base: Path) -> Path:
    """
    Verify that a resolved path is within the allowed base directory.

    Args:
        resolved_path: The resolved absolute path to validate
        allowed_base: The allowed base directory

    Returns:
        Validated path

    Raises:
        HTTPException: If path is outside allowed directory
    """
    try:
        # Resolve both paths to absolute
        resolved_path = resolved_path.resolve()
        allowed_base = allowed_base.resolve()

        # Check if resolved path is relative to allowed base
        resolved_path.relative_to(allowed_base)

        return resolved_path
    except ValueError:
        # relative_to() raises ValueError if path is not relative
        raise HTTPException(
            status_code=403,
            detail="Access denied: path is outside allowed directory"
        )


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup/shutdown)"""
    from utils.background_tasks import background_manager

    # Startup
    logger.info("Starting API server...")
    await background_manager.start()
    logger.info("Background tasks started")

    yield

    # Shutdown
    logger.info("Shutting down API server...")
    await background_manager.stop()
    logger.info("Background tasks stopped")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Qlib Crypto Trading Platform",
    description="AI-powered cryptocurrency trading platform with real-time updates",
    version="2.0.0",
    lifespan=lifespan
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


# Validation helper functions
def validate_dataset_exists(dataset_ref: str) -> Path:
    """
    Validate dataset exists and return its path.
    Includes security validation to prevent path traversal.

    Raises HTTPException if invalid or not found.
    """
    # First validate the dataset name format
    dataset_ref = validate_dataset_name(dataset_ref)

    project_root = Path(__file__).parent.parent.parent
    qlib_base = project_root / "data" / "qlib"
    qlib_dir = qlib_base / dataset_ref

    # Verify path safety
    validate_path_safety(qlib_dir, qlib_base)

    if not qlib_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset_ref}' not found. Available datasets can be fetched from GET /api/datasets"
        )

    if not qlib_dir.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Dataset '{dataset_ref}' is not a directory"
        )

    # Check required subdirectories
    required_dirs = ["calendars", "features", "instruments"]
    missing_dirs = [d for d in required_dirs if not (qlib_dir / d).exists()]
    if missing_dirs:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset '{dataset_ref}' is incomplete: missing {', '.join(missing_dirs)} director{'ies' if len(missing_dirs) > 1 else 'y'}"
        )

    return qlib_dir


def validate_model_exists(model_id: str) -> Path:
    """
    Validate model exists and return its path.
    Includes security validation to prevent path traversal.

    Raises HTTPException if invalid or not found.
    """
    # First validate the model_id format
    model_id = validate_model_id(model_id)

    project_root = Path(__file__).parent.parent.parent
    models_base = project_root / "models" / "trained"
    model_file = models_base / f"{model_id}.pkl"

    # Verify path safety
    validate_path_safety(model_file, models_base)

    if not model_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_id}' not found. Train a model first or check the model ID."
        )

    return model_file


# Request models
class DataDownloadRequest(BaseModel):
    symbols: List[str]
    start_date: str
    end_date: str
    interval: str = "1d"
    provider: str = "binance"
    market_type: str = "spot"

class TrainModelRequest(BaseModel):
    dataset: str = Field(..., min_length=1, max_length=100)
    feature_handler: str = Field(..., pattern="^(alpha158|alpha360)$")
    model_handler: str = Field(..., pattern="^(lightgbm|xgboost|lstm|transformer|gru)$")
    params: Optional[Dict[str, Any]] = None
    segments: Optional[Dict[str, Tuple[str, str]]] = None

    @field_validator('dataset')
    def validate_dataset(cls, v):
        # Prevent path traversal
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid dataset name: path traversal not allowed')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Dataset name must contain only alphanumeric characters, underscores, and hyphens')
        return v

    @field_validator('params')
    def validate_params(cls, v):
        if v is None:
            return {}
        # Limit params size to prevent excessive memory usage
        if len(json.dumps(v)) > 10000:  # 10KB limit
            raise ValueError('Parameters too large (max 10KB)')
        return v

    @field_validator('segments')
    def validate_segments(cls, v):
        if v is None:
            return None

        for key in ("train", "valid", "test"):
            if key not in v:
                raise ValueError(f"Segments must include '{key}' range")
            start, end = v[key]
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
                end_dt = datetime.strptime(end, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"Invalid {key} segment: {exc}") from exc
            if start_dt > end_dt:
                raise ValueError(f"Segment '{key}' start must be on or before end")

        return v

class BacktestRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=200)
    dataset: str = Field(..., min_length=1, max_length=100)
    start_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    benchmark: Optional[str] = Field(None, min_length=1, max_length=100)
    costs: str = Field(default="medium", pattern="^(low|medium|high)$")
    rebalance: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$")
    funding: bool = False
    topk: int = Field(default=10, ge=1, le=100)
    long_short: bool = False

    @field_validator('model_id')
    def validate_model_id(cls, v):
        # Prevent path traversal
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid model_id: path traversal not allowed')
        return v

    @field_validator('dataset')
    def validate_dataset(cls, v):
        # Prevent path traversal
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid dataset name: path traversal not allowed')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Dataset name must contain only alphanumeric characters, underscores, and hyphens')
        return v

    @field_validator('start_date', 'end_date')
    def validate_dates(cls, v, info):
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"Invalid {info.field_name.replace('_', ' ')}: {exc}")
        return v

class PredictionRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=200)
    dataset: str = Field(..., min_length=1, max_length=100)
    prediction_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator('model_id')
    def validate_model_id(cls, v):
        # Prevent path traversal
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid model_id: path traversal not allowed')
        return v

    @field_validator('dataset')
    def validate_dataset(cls, v):
        # Prevent path traversal
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid dataset name: path traversal not allowed')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Dataset name must contain only alphanumeric characters, underscores, and hyphens')
        return v

    @field_validator('prediction_date')
    def validate_prediction_date(cls, v):
        if v is None:
            return None
        try:
            date = datetime.strptime(v, "%Y-%m-%d")
            # Don't allow future dates beyond 1 year
            from datetime import timedelta
            if date > datetime.now() + timedelta(days=365):
                raise ValueError('Prediction date too far in future (max 1 year ahead)')
            return v
        except ValueError as e:
            if 'does not match format' in str(e):
                raise ValueError(f'Invalid date format. Expected YYYY-MM-DD')
            raise


class WebSocketTokenRequest(BaseModel):
    api_key: str = Field(..., min_length=10, max_length=256)


class WebSocketTokenResponse(BaseModel):
    token: str
    expires_at: datetime


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
    """
    WebSocket endpoint for real-time platform events

    Authentication: Requires API key in Authorization header or api_key query param
    Rate Limiting: 100 messages/minute per user
    Connection Limit: 10 concurrent connections per user
    Message Size: Max 1MB per message
    Heartbeat: 60s timeout
    """
    user_id = None

    # Authenticate connection
    try:
        user_id = await authenticate_websocket(websocket)
    except HTTPException as e:
        try:
            await websocket.close(code=1008, reason=e.detail)
        except:
            pass
        return

    # Add connection
    if not connection_manager.add_connection(user_id, websocket):
        try:
            await websocket.close(
                code=1008,
                reason=f"Maximum connections exceeded"
            )
        except:
            pass
        return

    # Register with broadcaster
    try:
        await broadcaster.connect(websocket)
    except Exception as e:
        logger.error(f"Failed to register with broadcaster: {e}")
        connection_manager.remove_connection(user_id, websocket)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
        return

    last_message = None  # Track for duplicate prevention

    try:
        while True:
            # Check heartbeat timeout
            if not connection_manager.is_connection_alive(user_id):
                logger.warning(f"Heartbeat timeout for user {user_id}")
                break

            # Keep connection alive and receive client messages
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0
                )

                # Check message size
                if not await check_message_size(data):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Message exceeds maximum size of {MAX_MESSAGE_SIZE} bytes",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Check rate limit
                if not connection_manager.check_rate_limit(user_id):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Rate limit exceeded. Max 100 messages per minute.",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Update heartbeat
                connection_manager.update_heartbeat(user_id)

                # Parse message
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type")

                    # Only send if changed (duplicate prevention)
                    if data != last_message:
                        if message_type == "ping":
                            await websocket.send_json({
                                "type": "pong",
                                "timestamp": datetime.now().isoformat()
                            })
                            last_message = data
                        else:
                            # Unknown message type - log but don't crash
                            logger.debug(f"Unknown message type from user {user_id}: {message_type}")

                except json.JSONDecodeError:
                    # Handle plain text for backward compatibility
                    if data == "ping" and data != last_message:
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                        last_message = data
                    else:
                        # Send error for invalid JSON
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Invalid JSON format. Expected JSON object or 'ping' text.",
                                "timestamp": datetime.now().isoformat()
                            })
                        except:
                            # If sending error fails, give up
                            break

            except asyncio.TimeoutError:
                # No message received, continue
                pass
            except Exception as e:
                logger.error(f"Error receiving message from user {user_id}: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected normally from /ws/events")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}", exc_info=True)
        try:
            await websocket.close(
                code=1011,
                reason="Server error occurred. Please reconnect."
            )
        except:
            pass
    finally:
        # Always cleanup
        broadcaster.disconnect(websocket)
        if user_id:
            connection_manager.remove_connection(user_id, websocket)

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


@app.post("/api/auth/ws-token", response_model=WebSocketTokenResponse)
async def issue_websocket_token(request: WebSocketTokenRequest):
    """Exchange an API key for a signed, short-lived WebSocket token."""
    user_id = validate_api_key(request.api_key)
    if not user_id:
        raise HTTPException(status_code=403, detail="Invalid API key")

    token, expires_at = create_ws_token(user_id)
    expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    return WebSocketTokenResponse(token=token, expires_at=expires_dt)


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
async def download_data(request: DataDownloadRequest):
    """Download crypto market data"""
    import uuid
    from data_pipeline.market_data import download_crypto_universe

    # Generate process ID
    process_id = f"download_{uuid.uuid4().hex[:8]}"

    # Notify start
    await broadcaster.broadcast_notification("info", f"Starting data download for {len(request.symbols)} symbols")

    async def download_task():
        try:
            await monitor.start_process(process_id, "download", total_steps=1)
            await monitor.update_progress(process_id, 10.0, f"Downloading {len(request.symbols)} symbols", 1)

            result = await download_crypto_universe(
                symbols=request.symbols,
                start_date=request.start_date,
                end_date=request.end_date,
                interval=request.interval,
                provider=request.provider,
                market_type=request.market_type
            )

            await monitor.complete_process(process_id, {
                "symbols": list(result.keys()),
                "count": len(result)
            })
            await broadcaster.broadcast_data_update("download_complete", {
                "symbols": list(result.keys()),
                "count": len(result)
            })
            await broadcaster.broadcast_notification("success", f"Downloaded data for {len(result)} symbols")
        except asyncio.CancelledError:
            logger.info(f"Download task cancelled: {process_id}")
            await monitor.fail_process(process_id, "Cancelled by user")
            raise
        except Exception as e:
            await monitor.fail_process(process_id, str(e))
            await broadcaster.broadcast_notification("error", f"Download failed: {str(e)}")

    # Create and register task for cancellation support
    task = asyncio.create_task(download_task())
    await monitor.register_task(process_id, task)

    return {"status": "started", "process_id": process_id, "symbols": request.symbols}


@app.post("/api/data/convert")
async def convert_data(dataset: str, freq: str = "1d"):
    """
    Convert CSV data to Qlib format with comprehensive security validation.

    Args:
        dataset: Dataset name (alphanumeric, underscore, hyphen only)
        freq: Frequency (default: "1d")

    Raises:
        HTTPException 400: Invalid dataset name or parameters
        HTTPException 403: Path traversal attempt detected
        HTTPException 500: Conversion failed
    """
    from data_pipeline.snapshot import create_snapshot

    # Validate dataset name to prevent path traversal
    dataset = validate_dataset_name(dataset)

    # Validate frequency parameter (whitelist)
    valid_freqs = ["1d", "1h", "4h", "1w", "1M"]
    if freq not in valid_freqs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frequency. Allowed values: {', '.join(valid_freqs)}"
        )

    # Verify path safety - ensure the resolved path is within data/qlib/
    project_root = Path(__file__).parent.parent.parent
    qlib_base = project_root / "data" / "qlib"
    dataset_path = qlib_base / dataset

    # Validate that resolved path is within allowed directory
    validate_path_safety(dataset_path, qlib_base)

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
async def train_model(request: TrainModelRequest):
    """Train a new model with comprehensive validation"""
    import uuid
    from models.trainer import train_model as train
    from data_pipeline.features import create_feature_set

    # Validate dataset exists before starting background task
    try:
        validate_dataset_exists(request.dataset)
    except HTTPException as e:
        # Return validation error immediately
        raise e

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

            if "error" in feature_set:
                await monitor.fail_process(process_id, feature_set["error"])
                await broadcaster.broadcast_notification("error", feature_set["error"])
                return

            await broadcaster.broadcast_model_update("creating", "in_progress", {"feature_set": feature_set["name"]})

            # Step 2: Train model
            await monitor.update_progress(process_id, 30.0, f"Training {request.model_handler} model", 2)
            result = await train(
                dataset_ref=request.dataset,
                feature_set_ref=feature_set["name"],
                handler=request.model_handler,
                params=request.params,
                segments=request.segments,
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
        except asyncio.CancelledError:
            logger.info(f"Training task cancelled: {process_id}")
            await monitor.fail_process(process_id, "Cancelled by user")
            raise
        except Exception as e:
            await monitor.fail_process(process_id, str(e))
            await broadcaster.broadcast_notification("error", f"Training error: {str(e)}")

    # Create and register task for cancellation support
    task = asyncio.create_task(train_task())
    await monitor.register_task(process_id, task)

    return {
        "status": "started",
        "process_id": process_id,
        "dataset": request.dataset,
        "feature_handler": request.feature_handler,
        "model_handler": request.model_handler,
        "message": f"Training {request.model_handler} model on {request.dataset} dataset"
    }


@app.get("/api/models/{model_id}")
async def get_model(model_id: str):
    """
    Get model details with comprehensive security validation.

    Args:
        model_id: Model identifier

    Raises:
        HTTPException 400: Invalid model_id format
        HTTPException 403: Path traversal attempt
        HTTPException 404: Model not found
    """
    # Validate model_id format (prevent path traversal)
    model_id = validate_model_id(model_id)

    project_root = Path(__file__).parent.parent.parent
    models_base = project_root / "models" / "trained"
    meta_file = models_base / f"{model_id}_meta.json"

    # Verify path safety
    validate_path_safety(meta_file, models_base)

    if not meta_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_id}' not found"
        )

    with open(meta_file) as f:
        return json.load(f)


@app.post("/api/backtests/run")
async def run_backtest(request: BacktestRequest):
    """Run backtest for a model with comprehensive validation"""
    import uuid
    from backtesting.engine import run_backtest as run_bt

    # Validate dataset exists
    try:
        validate_dataset_exists(request.dataset)
    except HTTPException as e:
        raise e

    # Validate model exists
    try:
        validate_model_exists(request.model_id)
    except HTTPException as e:
        raise e

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
                start_time=request.start_date,
                end_time=request.end_date,
                benchmark=request.benchmark,
                costs=request.costs,
                rebalance=request.rebalance,
                funding=request.funding,
                topk=request.topk,
                long_short=request.long_short,
            )

            if "error" not in result:
                await monitor.update_progress(process_id, 90.0, "Calculating metrics", 2)
                await monitor.complete_process(process_id, result)

                await broadcaster.broadcast_backtest_update(request.model_id, 1.0, result.get("metrics", {}))
                await broadcaster.broadcast_notification("success", f"Backtest complete for {request.model_id}")
            else:
                await monitor.fail_process(process_id, result['error'])
                await broadcaster.broadcast_notification("error", f"Backtest failed: {result['error']}")
        except asyncio.CancelledError:
            logger.info(f"Backtest task cancelled: {process_id}")
            await monitor.fail_process(process_id, "Cancelled by user")
            raise
        except Exception as e:
            await monitor.fail_process(process_id, str(e))
            await broadcaster.broadcast_notification("error", f"Backtest error: {str(e)}")

    # Create and register task for cancellation support
    task = asyncio.create_task(backtest_task())
    await monitor.register_task(process_id, task)

    return {
        "status": "started",
        "process_id": process_id,
        "model_id": request.model_id,
        "dataset": request.dataset,
        "costs": request.costs,
        "rebalance": request.rebalance,
        "message": f"Backtest started for model {request.model_id}"
    }


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
    """Generate predictions with comprehensive validation"""
    import uuid
    from serving.predictor import predict_today

    # Validate dataset exists
    try:
        validate_dataset_exists(request.dataset)
    except HTTPException as e:
        raise e

    # Validate model exists
    try:
        validate_model_exists(request.model_id)
    except HTTPException as e:
        raise e

    # Use provided date or today
    prediction_date = request.prediction_date or datetime.now().strftime("%Y-%m-%d")

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
        except asyncio.CancelledError:
            logger.info(f"Prediction task cancelled: {process_id}")
            await monitor.fail_process(process_id, "Cancelled by user")
            raise
        except Exception as e:
            await monitor.fail_process(process_id, str(e))
            await broadcaster.broadcast_notification("error", f"Prediction error: {str(e)}")

    # Create and register task for cancellation support
    task = asyncio.create_task(predict_task())
    await monitor.register_task(process_id, task)

    return {
        "status": "started",
        "process_id": process_id,
        "model_id": request.model_id,
        "dataset": request.dataset,
        "prediction_date": prediction_date,
        "message": f"Generating predictions for {prediction_date}"
    }


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
    from data_pipeline.market_data import get_quote

    try:
        result = await get_quote(symbol, provider)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    """
    WebSocket endpoint for real-time market data

    Authentication: Requires API key in Authorization header or api_key query param
    Rate Limiting: 100 messages/minute per user
    Connection Limit: 10 concurrent connections per user
    Message Size: Max 1MB per message
    Heartbeat: 60s timeout
    """
    user_id = None

    # Authenticate connection
    try:
        user_id = await authenticate_websocket(websocket)
    except HTTPException as e:
        try:
            await websocket.close(code=1008, reason=e.detail)
        except:
            pass
        return

    # Add connection
    if not connection_manager.add_connection(user_id, websocket):
        try:
            await websocket.close(code=1008, reason="Maximum connections exceeded")
        except:
            pass
        return

    # Accept connection explicitly
    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection for user {user_id}: {e}")
        connection_manager.remove_connection(user_id, websocket)
        return

    symbols = []
    last_symbols_state = None  # Track for duplicate detection

    try:
        while True:
            # Check heartbeat timeout
            if not connection_manager.is_connection_alive(user_id):
                logger.warning(f"Heartbeat timeout for user {user_id}")
                break

            # Check for client messages with short timeout
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=1.0
                )

                # Check message size
                if not await check_message_size(message):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Message exceeds maximum size of {MAX_MESSAGE_SIZE} bytes",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Check rate limit
                if not connection_manager.check_rate_limit(user_id):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Rate limit exceeded. Max 100 messages per minute.",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Update heartbeat
                connection_manager.update_heartbeat(user_id)

                try:
                    data = json.loads(message)
                    # Handle ping/pong keepalive
                    if data.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                    # Handle symbol subscription updates
                    elif "symbols" in data:
                        new_symbols = data.get("symbols", [])

                        # Validate symbols format
                        if isinstance(new_symbols, list) and all(isinstance(s, str) for s in new_symbols):
                            # Defensive copy to prevent race conditions
                            symbols = new_symbols.copy()
                            logger.info(f"User {user_id} subscribed to {len(symbols)} symbols")
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "symbols must be a list of strings",
                                "timestamp": datetime.now().isoformat()
                            })

                except json.JSONDecodeError as e:
                    # Handle plain text ping for backward compatibility
                    if message == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        # Send error response
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Invalid JSON: {str(e)}",
                                "timestamp": datetime.now().isoformat()
                            })
                        except:
                            # If sending error fails, continue
                            pass

            except asyncio.TimeoutError:
                pass  # No message, continue with updates
            except Exception as e:
                logger.error(f"Error receiving message from user {user_id}: {e}")
                break

            # Send quotes if symbols are subscribed and changed
            current_symbols_state = ",".join(sorted(symbols))
            if symbols and current_symbols_state != last_symbols_state:
                try:
                    from data_pipeline.market_data import get_quotes_batch
                    quotes = await get_quotes_batch(symbols)

                    try:
                        await websocket.send_json({
                            "type": "quotes",
                            "data": quotes,
                            "timestamp": datetime.now().isoformat()
                        })
                        last_symbols_state = current_symbols_state
                    except Exception as send_error:
                        logger.error(f"Failed to send quotes to user {user_id}: {send_error}")
                        # Don't break, continue trying

                except Exception as fetch_error:
                    logger.error(f"Failed to fetch quotes for user {user_id}: {fetch_error}")
                    # Graceful degradation - send error but continue operation
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Failed to fetch quotes: {str(fetch_error)}",
                            "timestamp": datetime.now().isoformat()
                        })
                    except:
                        # If even error send fails, continue
                        pass

            # Rate limiting
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected normally from /ws/market-data")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}", exc_info=True)
        try:
            await websocket.close(
                code=1011,
                reason="Server error occurred. Please reconnect."
            )
        except:
            pass
    finally:
        # Always cleanup
        if user_id:
            connection_manager.remove_connection(user_id, websocket)


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
    """Get specific process by ID with security validation"""
    # Validate process_id format (prevent injection)
    process_id = validate_process_id(process_id)

    process = await monitor.get_process(process_id)
    if not process:
        raise HTTPException(
            status_code=404,
            detail=f"Process '{process_id}' not found"
        )
    return process.to_dict()


@app.delete("/api/processes/{process_id}")
async def cancel_process(process_id: str):
    """Cancel a running process with security validation"""
    # Validate process_id format (prevent injection)
    process_id = validate_process_id(process_id)

    try:
        await monitor.cancel_process(process_id)
        return {
            "status": "cancelled",
            "process_id": process_id,
            "message": f"Process '{process_id}' has been cancelled"
        }
    except ValueError as e:
        error_msg = str(e)
        # Distinguish between 404 (not found) and 400 (invalid operation)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=404,
                detail=f"Process '{process_id}' not found"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel process: {error_msg}"
            )


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
    # Validate process_id format (prevent injection)
    process_id = validate_process_id(process_id)

    # Validate limit parameter
    if limit < 1:
        raise HTTPException(
            status_code=400,
            detail="Limit must be at least 1"
        )
    if limit > 1000:
        # Clamp to maximum instead of failing
        limit = 1000

    process = await monitor.get_process(process_id)

    if not process:
        raise HTTPException(
            status_code=404,
            detail=f"Process '{process_id}' not found"
        )

    # Return limited logs (most recent)
    logs = [
        {
            "timestamp": log.timestamp,
            "level": log.level,
            "message": log.message
        }
        for log in process.logs[-limit:]
    ]

    return {
        "logs": logs,
        "total_logs": len(process.logs),
        "returned_logs": len(logs)
    }


@app.websocket("/ws/processes")
async def websocket_processes(websocket: WebSocket):
    """
    WebSocket endpoint for real-time process updates - ALL processes (optimized)

    Authentication: Requires API key in Authorization header or api_key query param
    Rate Limiting: 100 messages/minute per user
    Connection Limit: 10 concurrent connections per user
    Message Size: Max 1MB per message
    Heartbeat: 60s timeout
    """
    user_id = None

    # Authenticate connection
    try:
        user_id = await authenticate_websocket(websocket)
    except HTTPException as e:
        try:
            await websocket.close(code=1008, reason=e.detail)
        except:
            pass
        return

    # Add connection
    if not connection_manager.add_connection(user_id, websocket):
        try:
            await websocket.close(code=1008, reason="Maximum connections exceeded")
        except:
            pass
        return

    # Accept connection explicitly
    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection for user {user_id}: {e}")
        connection_manager.remove_connection(user_id, websocket)
        return

    import time
    import hashlib

    # Track last update to avoid redundant sends
    last_state_hash = None
    last_update_time = time.monotonic()  # Use monotonic clock

    def compute_state_hash(processes):
        """Compute hash of all process states to detect changes"""
        state_str = json.dumps([
            (p.process_id, p.status.value, p.metrics.progress_percent)
            for p in processes
        ], sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()

    try:
        while True:
            # Check heartbeat timeout
            if not connection_manager.is_connection_alive(user_id):
                logger.warning(f"Heartbeat timeout for user {user_id}")
                break

            # Check for client messages (ping/pong keepalive)
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.1
                )

                # Check message size
                if not await check_message_size(message):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Message exceeds maximum size of {MAX_MESSAGE_SIZE} bytes",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Check rate limit
                if not connection_manager.check_rate_limit(user_id):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Rate limit exceeded. Max 100 messages per minute.",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Update heartbeat
                connection_manager.update_heartbeat(user_id)

                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError:
                    # Handle plain text ping
                    if message == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
            except asyncio.TimeoutError:
                pass  # No message, continue with updates
            except Exception as e:
                logger.error(f"Error receiving message from user {user_id}: {e}")
                break

            # Send current process states
            try:
                processes = await monitor.get_all_processes()
                current_time = time.monotonic()

                # Compute state hash to detect actual changes
                current_hash = compute_state_hash(processes)

                # Only send if state changed or 5 seconds passed (cache invalidation)
                if current_hash != last_state_hash or (current_time - last_update_time) > 5.0:
                    try:
                        await websocket.send_json({
                            "type": "process_update",
                            "processes": [p.to_dict() for p in processes],
                            "timestamp": datetime.now().isoformat()
                        })
                        last_state_hash = current_hash
                        last_update_time = current_time
                    except Exception as send_error:
                        logger.error(f"Failed to send process update to user {user_id}: {send_error}")
                        # Don't break, continue trying

            except Exception as fetch_error:
                logger.error(f"Failed to get processes for user {user_id}: {fetch_error}")
                # Graceful degradation - send error but continue
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to retrieve process data",
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    pass

            # Wait before next update
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected normally from /ws/processes")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}", exc_info=True)
        try:
            await websocket.close(
                code=1011,
                reason="Server error occurred. Please reconnect."
            )
        except:
            pass
    finally:
        # Always cleanup
        if user_id:
            connection_manager.remove_connection(user_id, websocket)


@app.websocket("/ws/processes/{process_id}")
async def websocket_process_updates(websocket: WebSocket, process_id: str):
    """
    WebSocket endpoint for real-time updates for a SPECIFIC process

    Sends process updates every 500ms while the process is running.
    Automatically closes when process completes, fails, or is cancelled.

    Authentication: Requires API key in Authorization header or api_key query param
    Rate Limiting: 100 messages/minute per user
    Connection Limit: 10 concurrent connections per user
    Message Size: Max 1MB per message
    Heartbeat: 60s timeout

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
    user_id = None

    # Authenticate connection
    try:
        user_id = await authenticate_websocket(websocket)
    except HTTPException as e:
        try:
            await websocket.close(code=1008, reason=e.detail)
        except:
            pass
        return

    # Add connection
    if not connection_manager.add_connection(user_id, websocket):
        try:
            await websocket.close(code=1008, reason="Maximum connections exceeded")
        except:
            pass
        return

    # Validate process_id
    try:
        process_id = validate_process_id(process_id)
    except HTTPException as e:
        try:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": e.detail,
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=1008, reason=e.detail)
        except:
            pass
        if user_id:
            connection_manager.remove_connection(user_id, websocket)
        return

    # Accept connection explicitly
    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"Failed to accept WebSocket connection for user {user_id}: {e}")
        connection_manager.remove_connection(user_id, websocket)
        return

    try:
        # First, verify process exists
        process = await monitor.get_process(process_id)
        if not process:
            await websocket.send_json({
                "type": "error",
                "message": f"Process '{process_id}' not found",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=1008, reason="Process not found")
            connection_manager.remove_connection(user_id, websocket)
            return

        # Send initial state
        await websocket.send_json({
            "type": "process_update",
            "data": process.to_dict(),
            "timestamp": datetime.now().isoformat()
        })

        # Keep sending updates while process is running
        while True:
            # Check heartbeat timeout
            if not connection_manager.is_connection_alive(user_id):
                logger.warning(f"Heartbeat timeout for user {user_id}")
                break

            # Check for client messages (keepalive, disconnect)
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.1
                )

                # Check message size
                if not await check_message_size(message):
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Message exceeds maximum size of {MAX_MESSAGE_SIZE} bytes",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Check rate limit
                if not connection_manager.check_rate_limit(user_id):
                    await websocket.send_json({
                        "type": "error",
                        "message": "Rate limit exceeded. Max 100 messages per minute.",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # Update heartbeat
                connection_manager.update_heartbeat(user_id)

                # Parse message with error handling
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from user {user_id} for process {process_id}: {message[:100]}")
                    # Send error but continue
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Invalid JSON format: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        })
                    except:
                        pass

            except asyncio.TimeoutError:
                pass  # No message, continue
            except Exception as e:
                logger.error(f"Error receiving message from user {user_id}: {e}")
                break

            # Get latest process state
            try:
                process = await monitor.get_process(process_id)
                if not process:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Process no longer exists",
                        "timestamp": datetime.now().isoformat()
                    })
                    break

                # Send update
                try:
                    await websocket.send_json({
                        "type": "process_update",
                        "data": process.to_dict(),
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as send_error:
                    logger.error(f"Failed to send update to user {user_id}: {send_error}")
                    # Don't break, continue trying

                # Check if process completed/failed/cancelled
                if process.status.value in ["completed", "failed", "cancelled"]:
                    try:
                        await websocket.send_json({
                            "type": "process_complete",
                            "data": process.to_dict(),
                            "timestamp": datetime.now().isoformat()
                        })
                        # Give client time to receive final message
                        await asyncio.sleep(0.2)
                    except Exception as complete_error:
                        logger.error(f"Failed to send completion message: {complete_error}")
                    break

            except Exception as fetch_error:
                logger.error(f"Failed to get process {process_id}: {fetch_error}")
                # Graceful degradation
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Failed to retrieve process data",
                        "timestamp": datetime.now().isoformat()
                    })
                except:
                    pass

            # Wait 500ms before next update
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected normally from process {process_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}, process {process_id}: {e}", exc_info=True)
        try:
            # Serialize exception properly
            error_message = {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(error_message)
        except:
            pass
    finally:
        # Always cleanup
        if user_id:
            connection_manager.remove_connection(user_id, websocket)
        try:
            await websocket.close(
                code=1000,
                reason="Process monitoring complete"
            )
        except:
            pass


# -------------------------------------------------------------------------
# OMS / Live Trading Endpoints
# -------------------------------------------------------------------------

# Helper to get OMS instance
def get_oms() -> LocalOrderManager:
    db_url = os.getenv("DATABASE_URL", "postgresql://crypto_user:crypto@localhost:5432/qlib_crypto")
    # Fix for local development when .env contains docker-compose service name
    if "@postgres" in db_url:
        db_url = db_url.replace("@postgres", "@localhost")
    return LocalOrderManager(db_url)

@app.get("/api/live/account")
async def get_live_account(account_name: str = "OKX_Paper"):
    """Get live execution account details"""
    oms = get_oms()
    session = oms.Session()
    try:
        account = oms._get_account(session)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return {
            "id": str(account.id),
            "name": account.name,
            "balance": account.balance,
            "equity": account.equity,
            "updated_at": account.updated_at
        }
    finally:
        session.close()

@app.get("/api/live/positions")
async def get_live_positions(account_name: str = "OKX_Paper"):
    """Get open positions"""
    oms = get_oms()
    session = oms.Session()
    try:
        account = oms._get_account(session)
        if not account:
            return []
            
        positions = []
        for p in account.positions:
            positions.append({
                "symbol": p.symbol,
                "amount": p.amount,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "value": p.amount * p.current_price
            })
        return positions
    finally:
        session.close()

@app.get("/api/live/orders")
async def get_live_orders(account_name: str = "OKX_Paper", limit: int = 50):
    """Get recent orders"""
    oms = get_oms()
    session = oms.Session()
    from serving.schema import Order
    try:
        account = oms._get_account(session)
        if not account:
            return []
            
        orders_query = session.query(Order).filter_by(account_id=account.id)\
            .order_by(Order.created_at.desc()).limit(limit).all()
            
        return [{
            "id": str(o.id),
            "symbol": o.symbol,
            "side": o.side.value,
            "type": o.type,
            "amount": o.amount,
            "price": o.price,
            "fee": o.fee,
            "status": o.status.value,
            "created_at": o.created_at
        } for o in orders_query]
    finally:
        session.close()

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
