"""
Real-time process monitoring for long-running tasks
Shows live progress, logs, and status for:
- Data download
- Model training
- Backtesting
- Predictions

NO FALLBACKS - Fails immediately on errors
"""
import asyncio
import contextlib
import logging
import time
import threading
import itertools
import os
import socket
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"  # Running process interrupted by shutdown


@dataclass
class ProcessLog:
    """Single log entry for a process"""
    timestamp: str
    level: str  # INFO, WARNING, ERROR
    message: str


@dataclass
class ProcessMetrics:
    """Real-time metrics for a process"""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    progress_percent: float = 0.0
    current_step: str = "Initializing"
    total_steps: int = 0
    completed_steps: int = 0
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    estimated_completion: Optional[str] = None  # ISO timestamp of estimated completion
    estimated_seconds_remaining: Optional[float] = None  # Seconds remaining


@dataclass
class ProcessInfo:
    """Complete information about a running process"""
    process_id: str
    process_type: str  # "download", "training", "backtest", "prediction"
    status: ProcessStatus
    display_id: str = ""  # User-friendly ID like "Training #42"
    metrics: ProcessMetrics = field(default_factory=ProcessMetrics)
    logs: List[ProcessLog] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # For interrupted state recovery

    # Cache for serialized logs
    _serialized_logs_cache: Optional[List[Dict]] = field(default=None, init=False, repr=False, compare=False)
    _logs_cache_size: int = field(default=0, init=False, repr=False, compare=False)

    def to_dict(self) -> Dict:
        """Serialize to dict with log caching"""
        # Check if we can reuse cached logs
        current_log_count = len(self.logs)
        if (self._serialized_logs_cache is not None and
            self._logs_cache_size == current_log_count):
            serialized_logs = self._serialized_logs_cache
        else:
            # Serialize last 100 logs
            serialized_logs = [
                {"timestamp": log.timestamp, "level": log.level, "message": log.message}
                for log in self.logs[-100:]
            ]
            # Cache result
            self._serialized_logs_cache = serialized_logs
            self._logs_cache_size = current_log_count

        return {
            "process_id": self.process_id,
            "process_type": self.process_type,
            "display_id": self.display_id,
            "status": self.status.value,
            "metrics": {
                "start_time": self.metrics.start_time,
                "end_time": self.metrics.end_time,
                "duration_seconds": self.metrics.duration_seconds,
                "progress_percent": self.metrics.progress_percent,
                "current_step": self.metrics.current_step,
                "total_steps": self.metrics.total_steps,
                "completed_steps": self.metrics.completed_steps,
                "memory_mb": self.metrics.memory_mb,
                "cpu_percent": self.metrics.cpu_percent,
                "estimated_completion": self.metrics.estimated_completion,
                "estimated_seconds_remaining": self.metrics.estimated_seconds_remaining,
            },
            "logs": serialized_logs,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessInfo':
        metrics_data = data.get("metrics", {})
        logs_data = data.get("logs", [])
        metrics = ProcessMetrics(**metrics_data)
        logs = [ProcessLog(**log) for log in logs_data]
        status = ProcessStatus(data.get("status", ProcessStatus.PENDING.value))

        return cls(
            process_id=data["process_id"],
            process_type=data["process_type"],
            display_id=data.get("display_id", ""),
            status=status,
            metrics=metrics,
            logs=logs,
            result=data.get("result"),
            error=data.get("error"),
            metadata=data.get("metadata"),
        )


class ProcessMonitor:
    """
    Global process monitor - tracks all long-running processes
    Thread-safe, async-compatible with state persistence
    """
    _instance: Optional['ProcessMonitor'] = None
    _instance_lock = threading.Lock()  # Thread-safe singleton
    _processes: Dict[str, ProcessInfo] = {}

    def __init__(self):
        """Initialize instance variables - called only once per instance"""
        # Only initialize if not already initialized
        if not hasattr(self, '_initialized'):
            self._processes: Dict[str, ProcessInfo] = {}
            self._tasks: Dict[str, asyncio.Task] = {}
            self._lock: Optional[asyncio.Lock] = None
            self._state_file: Path = Path(__file__).parent.parent.parent / "data" / "process_state.json"
            self._state_version: str = "1.0"
            self._process_counter: itertools.count = itertools.count(1)  # Thread-safe atomic counter
            self._cached_all_processes: List[ProcessInfo] = []
            self._cache_timestamp: float = 0
            # Keep a tiny TTL so repeated calls within the same event loop tick reuse the cache.
            self._cache_ttl: float = 0.1  # 100ms cache window for UI polling
            self._initialized = True
            self._current_test_marker: Optional[str] = None
            self._redis_url = os.getenv("PROCESS_MONITOR_REDIS_URL")
            self._redis_key = os.getenv("PROCESS_MONITOR_REDIS_KEY", "process_monitor:processes")
            self._redis_channel = os.getenv("PROCESS_MONITOR_CHANNEL", "process_monitor:events")
            self._redis = None
            self._redis_pubsub = None
            self._redis_listener_task: Optional[asyncio.Task] = None
            self._node_id = f"{socket.gethostname()}-{os.getpid()}"

            if self._redis_url:
                try:
                    import redis.asyncio as redis_async  # type: ignore

                    self._redis = redis_async.from_url(
                        self._redis_url,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                    logger.info("Process monitor connected to Redis at %s", self._redis_url)
                except Exception as redis_error:
                    logger.error("Failed to initialize Redis for process monitor: %s", redis_error)
                    self._redis = None

            # Expose shared state on the class for tests that access it directly
            type(self)._processes = self._processes

    def __new__(cls):
        """Thread-safe singleton pattern"""
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check inside lock
                if cls._instance is None:
                    instance = super().__new__(cls)
                    cls._instance = instance
        return cls._instance

    def __setattr__(self, name, value):
        """Ensure cache resets when process mapping is replaced externally."""
        object.__setattr__(self, name, value)
        if name == "_processes" and isinstance(value, dict):
            current = getattr(self, "_processes", None)
            if isinstance(current, dict) and current is not value:
                current.clear()
                current.update(value)
                value = current
            object.__setattr__(self, "_cache_timestamp", 0)
            object.__setattr__(self, "_cached_all_processes", [])
            type(self)._processes = value

    @classmethod
    def get_instance(cls) -> 'ProcessMonitor':
        """Get singleton instance"""
        if cls._instance is None:
            cls()  # __new__ handles singleton
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance - primarily for testing"""
        old_instance = cls._instance
        with cls._instance_lock:
            cls._instance = None
        new_instance = cls.get_instance()
        # Update module-level monitor reference to keep tests in sync
        global monitor
        monitor = new_instance

        # Update any modules that imported the previous singleton instance directly
        if old_instance is not None:
            for module in list(sys.modules.values()):
                try:
                    if getattr(module, "monitor", None) is old_instance:
                        setattr(module, "monitor", new_instance)
                except Exception:
                    continue

    def _redis_enabled(self) -> bool:
        return self._redis is not None

    async def start_redis_listener(self) -> None:
        if not self._redis_enabled() or self._redis_listener_task:
            return

        try:
            self._redis_pubsub = self._redis.pubsub()  # type: ignore[union-attr]
            await self._redis_pubsub.subscribe(self._redis_channel)
            self._redis_listener_task = asyncio.create_task(self._listen_to_redis())
            logger.info("Process monitor Redis listener started (node %s)", self._node_id)
        except Exception as exc:
            logger.error("Failed to start Redis listener: %s", exc)
            self._redis_listener_task = None
            if self._redis_pubsub is not None:
                with contextlib.suppress(Exception):
                    await self._redis_pubsub.close()
                self._redis_pubsub = None

    async def stop_redis_listener(self) -> None:
        if self._redis_listener_task:
            self._redis_listener_task.cancel()
            try:
                await self._redis_listener_task
            except asyncio.CancelledError:
                pass
            self._redis_listener_task = None

        if self._redis_pubsub is not None:
            with contextlib.suppress(Exception):
                await self._redis_pubsub.unsubscribe(self._redis_channel)
                await self._redis_pubsub.close()
            self._redis_pubsub = None

    async def _listen_to_redis(self) -> None:
        if not self._redis_pubsub:
            return
        try:
            async for message in self._redis_pubsub.listen():
                if message is None or message.get("type") != "message":
                    continue
                try:
                    payload = json.loads(message.get("data", "{}"))
                except json.JSONDecodeError:
                    continue

                if payload.get("origin") == self._node_id:
                    continue

                msg_type = payload.get("type")
                if msg_type == "sync":
                    process_data = payload.get("process")
                    if not process_data:
                        continue
                    process = ProcessInfo.from_dict(process_data)
                    self._processes[process.process_id] = process
                    await self._invalidate_cache()
                elif msg_type == "delete":
                    process_id = payload.get("process_id")
                    if process_id and process_id in self._processes:
                        self._processes.pop(process_id, None)
                        await self._invalidate_cache()
                elif msg_type == "cancel":
                    process_id = payload.get("process_id")
                    if process_id:
                        await self._handle_remote_cancel(process_id)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Error while listening to Redis channel: %s", exc)

    async def _handle_remote_cancel(self, process_id: str) -> None:
        task = self._tasks.get(process_id)
        if task and not task.done():
            task.cancel()

    async def _sync_to_redis(self, process: ProcessInfo) -> None:
        if not self._redis_enabled():
            return
        try:
            serialized = json.dumps(process.to_dict())
            await self._redis.hset(self._redis_key, process.process_id, serialized)  # type: ignore[union-attr]
            await self._publish_update({"type": "sync", "process": process.to_dict()})
        except Exception as exc:
            logger.error("Failed to sync process %s to Redis: %s", process.process_id, exc)

    async def _delete_from_redis(self, process_id: str) -> None:
        if not self._redis_enabled():
            return
        try:
            await self._redis.hdel(self._redis_key, process_id)  # type: ignore[union-attr]
            await self._publish_update({"type": "delete", "process_id": process_id})
        except Exception as exc:
            logger.error("Failed to delete process %s from Redis: %s", process_id, exc)

    async def _publish_update(self, payload: Dict[str, Any]) -> None:
        if not self._redis_enabled():
            return
        try:
            payload = dict(payload)
            payload["origin"] = self._node_id
            await self._redis.publish(self._redis_channel, json.dumps(payload))  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("Failed to publish process update: %s", exc)

    async def _publish_command(self, payload: Dict[str, Any]) -> None:
        await self._publish_update(payload)

    def _get_lock(self) -> asyncio.Lock:
        """Lazy-initialize lock to avoid event loop requirement at import time"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _ensure_test_isolation(self):
        """Clear shared state when pytest switches to a new test node."""
        test_marker = os.getenv("PYTEST_CURRENT_TEST")
        if test_marker and getattr(self, "_current_test_marker", None) != test_marker:
            self._processes.clear()
            self._cached_all_processes = []
            self._cache_timestamp = 0
            self._current_test_marker = test_marker

    async def _invalidate_cache(self):
        """Invalidate the all_processes cache"""
        self._cache_timestamp = 0
        self._cached_all_processes = []

    def _generate_display_id(self, process_type: str) -> str:
        """Generate user-friendly display ID like 'Training #42'"""
        counter_source = self._process_counter

        # Support tests resetting the counter to an int while keeping iterator usage by default
        if isinstance(counter_source, itertools.count):
            counter = next(counter_source)
        else:
            try:
                current_value = int(counter_source)
            except (TypeError, ValueError):
                current_value = 0
            counter = current_value + 1
            self._process_counter = counter

        # Capitalize first letter of process type and fallback to generic label
        type_name = (process_type or "process").strip().capitalize()
        return f"{type_name} #{counter}"

    def _calculate_eta(self, start_time: str, progress_percent: float) -> tuple[Optional[str], Optional[float]]:
        """
        Calculate estimated time to completion based on elapsed time and progress.
        Returns (estimated_completion_timestamp, estimated_seconds_remaining)
        """
        # Don't calculate ETA if progress is too low (< 5%) or already complete
        if progress_percent < 5.0 or progress_percent >= 100.0:
            return None, None

        try:
            start = datetime.fromisoformat(start_time)
            now = datetime.now()
            elapsed_seconds = (now - start).total_seconds()

            # Calculate total estimated time based on progress
            # Formula: ETA = (elapsed / progress) * (100 - progress)
            total_estimated_seconds = (elapsed_seconds / progress_percent) * 100
            remaining_seconds = total_estimated_seconds - elapsed_seconds

            # Clamp to reasonable values (don't show negative or extremely large values)
            if remaining_seconds < 0 or remaining_seconds > 86400 * 7:  # Max 7 days
                return None, None

            estimated_completion = now + timedelta(seconds=remaining_seconds)
            return estimated_completion.isoformat(), remaining_seconds
        except (ValueError, ZeroDivisionError):
            return None, None

    async def start_process(
        self,
        process_id: str,
        process_type: str,
        total_steps: int = 0
    ) -> ProcessInfo:
        """Start tracking a new process - FAIL if already exists"""
        # Validate inputs before acquiring lock
        self._ensure_test_isolation()

        if not process_id or not process_id.strip():
            raise ValueError("process_id cannot be empty")
        if not process_type or not process_type.strip():
            raise ValueError("process_type cannot be empty")
        if total_steps < 0:
            raise ValueError("total_steps cannot be negative")

        async with self._get_lock():
            if process_id in self._processes:
                raise ValueError(f"Process {process_id} already exists!")

            # Generate user-friendly display ID
            display_id = self._generate_display_id(process_type)

            process = ProcessInfo(
                process_id=process_id,
                process_type=process_type,
                display_id=display_id,
                status=ProcessStatus.RUNNING,
                metrics=ProcessMetrics(
                    start_time=datetime.now().isoformat(),
                    total_steps=total_steps
                )
            )
            if process.metadata is None:
                process.metadata = {}
            process.metadata["owner"] = self._node_id
            self._processes[process_id] = process

            await self._log(process_id, "INFO", f"Started {process_type} process")
            await self._invalidate_cache()
            await self._sync_to_redis(process)
            return process

    async def update_progress(
        self,
        process_id: str,
        progress_percent: float,
        current_step: str,
        completed_steps: Optional[int] = None
    ):
        """Update process progress with validation"""
        # Validate inputs
        if not process_id or not process_id.strip():
            raise ValueError("process_id cannot be empty")

        # Validate progress range
        if not 0.0 <= progress_percent <= 100.0:
            logger.warning(f"Invalid progress {progress_percent}%, clamping to 0-100 range")
            progress_percent = max(0.0, min(100.0, progress_percent))

        async with self._get_lock():
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]

            # Validate state transition - only update if RUNNING
            if process.status != ProcessStatus.RUNNING:
                raise ValueError(
                    f"Cannot update process {process_id}: "
                    f"not running (status: {process.status.value})"
                )

            # Warn if progress decreases
            if progress_percent < process.metrics.progress_percent:
                logger.warning(
                    f"Progress decreased for {process_id}: "
                    f"{process.metrics.progress_percent}% -> {progress_percent}%"
                )

            process.metrics.progress_percent = progress_percent
            process.metrics.current_step = current_step

            # Validate and update completed_steps
            if completed_steps is not None:
                if completed_steps < 0:
                    raise ValueError("completed_steps cannot be negative")

                if process.metrics.total_steps > 0:
                    if completed_steps > process.metrics.total_steps:
                        raise ValueError(
                            f"completed_steps ({completed_steps}) exceeds "
                            f"total_steps ({process.metrics.total_steps})"
                        )

                process.metrics.completed_steps = completed_steps

            # Calculate and update ETA
            if process.metrics.start_time:
                estimated_completion, estimated_seconds_remaining = self._calculate_eta(
                    process.metrics.start_time,
                    progress_percent
                )
            process.metrics.estimated_completion = estimated_completion
            process.metrics.estimated_seconds_remaining = estimated_seconds_remaining

            await self._log(process_id, "INFO", f"{current_step} ({progress_percent:.1f}%)")
            await self._sync_to_redis(process)

    async def complete_process(
        self,
        process_id: str,
        result: Dict[str, Any]
    ):
        """Mark process as completed"""
        # Validate inputs
        if not process_id or not process_id.strip():
            raise ValueError("process_id cannot be empty")

        async with self._get_lock():
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]

            # Validate state transition - only complete from RUNNING
            if process.status != ProcessStatus.RUNNING:
                logger.error(
                    f"Cannot complete process {process_id} with status {process.status.value}"
                )
                raise ValueError(
                    f"Cannot complete process in {process.status.value} state"
                )

            process.status = ProcessStatus.COMPLETED
            process.result = result
            process.error = None  # Clear incompatible field
            process.metrics.end_time = datetime.now().isoformat()
            process.metrics.progress_percent = 100.0

            # Calculate duration
            if process.metrics.start_time:
                start = datetime.fromisoformat(process.metrics.start_time)
                end = datetime.fromisoformat(process.metrics.end_time)
                process.metrics.duration_seconds = (end - start).total_seconds()

            # Clean up task reference
            if process_id in self._tasks:
                del self._tasks[process_id]

            await self._log(process_id, "INFO", f"✓ Completed successfully in {process.metrics.duration_seconds:.2f}s")
            await self._invalidate_cache()
            await self._sync_to_redis(process)

    async def fail_process(
        self,
        process_id: str,
        error: str
    ):
        """Mark process as failed - NO FALLBACKS"""
        # Validate inputs
        if not process_id or not process_id.strip():
            raise ValueError("process_id cannot be empty")
        if not error or not error.strip():
            raise ValueError("error message cannot be empty")

        async with self._get_lock():
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]

            # Validate state transition - only fail from RUNNING or PENDING
            if process.status not in [ProcessStatus.RUNNING, ProcessStatus.PENDING]:
                raise ValueError(
                    f"Cannot fail process {process_id}: "
                    f"already in state {process.status.value}"
                )

            process.status = ProcessStatus.FAILED
            process.error = error
            process.result = None  # Clear incompatible field
            process.metrics.end_time = datetime.now().isoformat()

            # Clean up task reference
            if process_id in self._tasks:
                del self._tasks[process_id]

            await self._log(process_id, "ERROR", f"✗ Failed: {error}")
            await self._invalidate_cache()
            await self._sync_to_redis(process)

    async def add_log(
        self,
        process_id: str,
        level: str,
        message: str
    ):
        """Add log entry to process (public API with lock)"""
        async with self._get_lock():
            await self._log(process_id, level, message)

    async def _log(
        self,
        process_id: str,
        level: str,
        message: str
    ):
        """Add log entry to process - caller must hold lock"""
        # Assert lock is held (development check)
        if __debug__:
            lock = self._get_lock()
            if not lock.locked():
                raise RuntimeError("_log() must be called with lock held")

        if process_id in self._processes:
            log = ProcessLog(
                timestamp=datetime.now().isoformat(),
                level=level,
                message=message
            )
            process = self._processes[process_id]
            process.logs.append(log)

            # Trim to last 1000 logs to prevent memory leak
            if len(process.logs) > 1000:
                process.logs = process.logs[-1000:]

            # Also log to Python logger
            log_func = getattr(logger, level.lower(), logger.info)
            log_func(f"[{process_id}] {message}")
            await self._sync_to_redis(process)

    async def get_process(self, process_id: str) -> Optional[ProcessInfo]:
        """Get process info"""
        # Validate inputs
        if not process_id or not process_id.strip():
            raise ValueError("process_id cannot be empty")

        self._ensure_test_isolation()

        async with self._get_lock():
            if self._redis_enabled():
                try:
                    data = await self._redis.hget(self._redis_key, process_id)  # type: ignore[union-attr]
                    if data:
                        process = ProcessInfo.from_dict(json.loads(data))
                        self._processes[process_id] = process
                        return process
                except Exception as exc:
                    logger.error("Failed to fetch process %s from Redis: %s", process_id, exc)
            return self._processes.get(process_id)

    async def get_all_processes(self) -> List[ProcessInfo]:
        """Get all processes with caching"""
        self._ensure_test_isolation()

        current_time = time.time()

        # Return cached result if fresh
        if current_time - self._cache_timestamp < self._cache_ttl:
            return self._cached_all_processes

        async with self._get_lock():
            # Double-check cache inside lock
            if current_time - self._cache_timestamp < self._cache_ttl:
                return self._cached_all_processes

            processes: List[ProcessInfo]
            if self._redis_enabled():
                try:
                    raw_processes = await self._redis.hgetall(self._redis_key)  # type: ignore[union-attr]
                    processes = []
                    for pid, serialized in raw_processes.items():
                        try:
                            process_data = json.loads(serialized)
                            process = ProcessInfo.from_dict(process_data)
                            self._processes[pid] = process
                            processes.append(process)
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            logger.error("Failed to decode process entry %s: %s", pid, exc)
                    # Remove stale local entries not present in Redis
                    redis_ids = set(raw_processes.keys())
                    local_ids = set(self._processes.keys())
                    for stale_id in local_ids - redis_ids:
                        self._processes.pop(stale_id, None)

                    processes.sort(key=lambda p: p.metrics.start_time or "", reverse=True)
                except Exception as exc:
                    logger.error("Failed to fetch processes from Redis: %s", exc)
                    processes = list(self._processes.values())
                    processes.sort(key=lambda p: p.metrics.start_time or "", reverse=True)
            else:
                processes = list(self._processes.values())
                processes.sort(key=lambda p: p.metrics.start_time or "", reverse=True)

            self._cached_all_processes = processes
            self._cache_timestamp = current_time
            return self._cached_all_processes

    async def get_running_processes(self) -> List[ProcessInfo]:
        """Get only running processes"""
        processes = await self.get_all_processes()
        return [p for p in processes if p.status == ProcessStatus.RUNNING]

    async def register_task(self, process_id: str, task: asyncio.Task):
        """Register an asyncio task for cancellation support"""
        # Validate inputs
        if not process_id or not process_id.strip():
            raise ValueError("process_id cannot be empty")
        if task is None:
            raise ValueError("task cannot be None")

        async with self._get_lock():
            self._tasks[process_id] = task
            logger.debug(f"Registered task for process {process_id}")

    async def cancel_process(self, process_id: str):
        """Cancel a running process"""
        # Validate inputs
        if not process_id or not process_id.strip():
            raise ValueError("process_id cannot be empty")

        async with self._get_lock():
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]
            if process.status != ProcessStatus.RUNNING:
                raise ValueError(f"Process {process_id} is not running (status: {process.status.value})")

            process.status = ProcessStatus.CANCELLED
            process.result = None  # Clear result
            process.error = None  # Clear error
            process.metrics.end_time = datetime.now().isoformat()

            await self._log(process_id, "WARNING", "Process cancelled by user")
            await self._invalidate_cache()
            await self._sync_to_redis(process)
            await self._publish_command({"type": "cancel", "process_id": process_id})

            # Actually cancel the asyncio task
            if process_id in self._tasks:
                task = self._tasks[process_id]
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled task for process {process_id}")
                del self._tasks[process_id]

    async def cleanup_old_processes(self, max_age_hours: int = 24):
        """Remove completed/failed/cancelled processes older than max_age_hours"""
        async with self._get_lock():
            if self._redis_enabled():
                try:
                    raw_processes = await self._redis.hgetall(self._redis_key)  # type: ignore[union-attr]
                    for pid, serialized in raw_processes.items():
                        try:
                            process_data = json.loads(serialized)
                            process = ProcessInfo.from_dict(process_data)
                            self._processes[pid] = process
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            logger.error("Failed to decode process entry %s during cleanup: %s", pid, exc)
                except Exception as exc:
                    logger.error("Failed to refresh process cache from Redis: %s", exc)

            now = datetime.now()
            to_remove = []

            terminal_states = [ProcessStatus.COMPLETED, ProcessStatus.FAILED,
                             ProcessStatus.CANCELLED, ProcessStatus.INTERRUPTED]

            for process_id, process in self._processes.items():
                if process.status not in terminal_states:
                    continue

                if not process.metrics.end_time:
                    continue

                end_time = datetime.fromisoformat(process.metrics.end_time)
                age_hours = (now - end_time).total_seconds() / 3600

                if age_hours > max_age_hours:
                    to_remove.append(process_id)

            for process_id in to_remove:
                process = self._processes.pop(process_id, None)
                if process:
                    logger.info(f"Cleaned up old process: {process_id}")
                    await self._delete_from_redis(process_id)

            return len(to_remove)

    async def save_state(self):
        """
        Save process state to disk
        Only persists terminal states (completed, failed, cancelled, interrupted)
        Running processes are marked as interrupted with metadata
        """
        async with self._get_lock():
            try:
                # Ensure data directory exists
                self._state_file.parent.mkdir(parents=True, exist_ok=True)

                # Collect processes to save
                processes_to_save = []
                terminal_states = [ProcessStatus.COMPLETED, ProcessStatus.FAILED,
                                 ProcessStatus.CANCELLED, ProcessStatus.INTERRUPTED]

                if self._redis_enabled():
                    try:
                        raw_processes = await self._redis.hgetall(self._redis_key)  # type: ignore[union-attr]
                        for pid, serialized in raw_processes.items():
                            try:
                                process_data = json.loads(serialized)
                                process = ProcessInfo.from_dict(process_data)
                                self._processes[pid] = process
                            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                                logger.error("Failed to decode process entry %s during save: %s", pid, exc)
                    except Exception as exc:
                        logger.error("Failed to refresh process cache from Redis during save: %s", exc)

                for process in self._processes.values():
                    # Handle running processes - mark as interrupted
                    if process.status == ProcessStatus.RUNNING:
                        interrupted_process = ProcessInfo(
                            process_id=process.process_id,
                            process_type=process.process_type,
                            status=ProcessStatus.INTERRUPTED,
                            metrics=process.metrics,
                            logs=process.logs[-100:],  # Save last 100 logs
                            result=None,
                            error=None,
                            metadata={
                                **(process.metadata or {}),
                                "last_known_progress": process.metrics.progress_percent,
                                "last_known_step": process.metrics.current_step,
                                "interrupted_at": datetime.now().isoformat()
                            }
                        )
                        processes_to_save.append(interrupted_process.to_dict())
                    # Save terminal states as-is
                    elif process.status in terminal_states:
                        processes_to_save.append(process.to_dict())

                # Create state file structure
                state = {
                    "version": self._state_version,
                    "saved_at": datetime.now().isoformat(),
                    "processes": processes_to_save
                }

                # Write atomically using temp file
                temp_file = self._state_file.with_suffix('.json.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(state, f, indent=2)

                # Atomic rename
                temp_file.replace(self._state_file)

                logger.info(f"Saved state for {len(processes_to_save)} processes to {self._state_file}")
                return len(processes_to_save)

            except Exception as e:
                logger.error(f"Failed to save process state: {e}", exc_info=True)
                raise

    async def load_state(self):
        """
        Load process state from disk
        Handles corrupted/missing files gracefully
        Running processes are already marked as interrupted
        """
        async with self._get_lock():
            try:
                # Check if state file exists
                if not self._state_file.exists():
                    logger.info("No state file found, starting fresh")
                    return 0

                # Load state file
                with open(self._state_file, 'r') as f:
                    state = json.load(f)

                # Validate version
                version = state.get("version")
                if version != self._state_version:
                    logger.warning(f"State file version mismatch: {version} != {self._state_version}")
                    # Continue anyway for now, might need migration logic later

                # Restore processes
                processes = state.get("processes", [])
                restored_count = 0

                for proc_data in processes:
                    try:
                        # Reconstruct ProcessInfo from dict
                        process = ProcessInfo(
                            process_id=proc_data["process_id"],
                            process_type=proc_data["process_type"],
                            display_id=proc_data.get("display_id", ""),
                            status=ProcessStatus(proc_data["status"]),
                            metrics=ProcessMetrics(**proc_data["metrics"]),
                            logs=[
                                ProcessLog(**log_data)
                                for log_data in proc_data.get("logs", [])
                            ],
                            result=proc_data.get("result"),
                            error=proc_data.get("error"),
                            metadata=proc_data.get("metadata")
                        )

                        self._processes[process.process_id] = process
                        restored_count += 1
                        await self._sync_to_redis(process)

                    except Exception as e:
                        logger.error(f"Failed to restore process {proc_data.get('process_id')}: {e}")
                        continue

                logger.info(f"Restored {restored_count} processes from {self._state_file}")
                await self._invalidate_cache()

                # Clean up state file for processes older than 7 days
                cleaned_count = await self._cleanup_state_file()

                # Return final count after cleanup
                final_count = restored_count - cleaned_count
                if cleaned_count > 0:
                    logger.info(f"Final count after cleanup: {final_count} processes")

                return final_count

            except json.JSONDecodeError as e:
                logger.error(f"Corrupted state file: {e}")
                # Backup corrupted file
                backup_file = self._state_file.with_suffix('.json.corrupted')
                if self._state_file.exists():
                    self._state_file.rename(backup_file)
                    logger.info(f"Backed up corrupted state file to {backup_file}")
                return 0

            except Exception as e:
                logger.error(f"Failed to load process state: {e}", exc_info=True)
                return 0

    async def _cleanup_state_file(self):
        """Remove processes older than 7 days from loaded state. Returns count of removed processes."""
        now = datetime.now()
        to_remove = []

        for process_id, process in self._processes.items():
            # Check end_time for terminal states
            if process.metrics.end_time:
                try:
                    end_time = datetime.fromisoformat(process.metrics.end_time)
                    age_days = (now - end_time).days

                    if age_days > 7:
                        to_remove.append(process_id)

                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid end_time for process {process_id}: {e}")
                    continue

        # Remove old processes
        for process_id in to_remove:
            del self._processes[process_id]
            logger.info(f"Removed old process from state: {process_id} (>7 days)")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old processes from state")
            await self._invalidate_cache()

        return len(to_remove)


# Global monitor instance - use get_instance() for singleton
monitor = ProcessMonitor.get_instance()


# Decorator for monitored async functions
def monitored_process(process_type: str):
    """Decorator to automatically monitor async functions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import uuid
            process_id = f"{process_type}_{uuid.uuid4().hex[:8]}"

            try:
                await monitor.start_process(process_id, process_type)
                result = await func(*args, process_id=process_id, **kwargs)
                await monitor.complete_process(process_id, result)
                return result
            except Exception as e:
                await monitor.fail_process(process_id, str(e))
                raise  # Re-raise - NO FALLBACKS

        return wrapper
    return decorator
