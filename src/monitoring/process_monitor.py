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
import logging
import time
from datetime import datetime
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


@dataclass
class ProcessInfo:
    """Complete information about a running process"""
    process_id: str
    process_type: str  # "download", "training", "backtest", "prediction"
    status: ProcessStatus
    metrics: ProcessMetrics = field(default_factory=ProcessMetrics)
    logs: List[ProcessLog] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "process_id": self.process_id,
            "process_type": self.process_type,
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
            },
            "logs": [
                {"timestamp": log.timestamp, "level": log.level, "message": log.message}
                for log in self.logs[-100:]  # Last 100 logs only
            ],
            "result": self.result,
            "error": self.error
        }


class ProcessMonitor:
    """
    Global process monitor - tracks all long-running processes
    Thread-safe, async-compatible
    """
    _instance = None
    _processes: Dict[str, ProcessInfo] = {}
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def start_process(
        self,
        process_id: str,
        process_type: str,
        total_steps: int = 0
    ) -> ProcessInfo:
        """Start tracking a new process - FAIL if already exists"""
        async with self._lock:
            if process_id in self._processes:
                raise ValueError(f"Process {process_id} already exists!")

            process = ProcessInfo(
                process_id=process_id,
                process_type=process_type,
                status=ProcessStatus.RUNNING,
                metrics=ProcessMetrics(
                    start_time=datetime.now().isoformat(),
                    total_steps=total_steps
                )
            )
            self._processes[process_id] = process

            await self._log(process_id, "INFO", f"Started {process_type} process")
            return process

    async def update_progress(
        self,
        process_id: str,
        progress_percent: float,
        current_step: str,
        completed_steps: Optional[int] = None
    ):
        """Update process progress"""
        async with self._lock:
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]
            process.metrics.progress_percent = progress_percent
            process.metrics.current_step = current_step

            if completed_steps is not None:
                process.metrics.completed_steps = completed_steps

            await self._log(process_id, "INFO", f"{current_step} ({progress_percent:.1f}%)")

    async def complete_process(
        self,
        process_id: str,
        result: Dict[str, Any]
    ):
        """Mark process as completed"""
        async with self._lock:
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]
            process.status = ProcessStatus.COMPLETED
            process.result = result
            process.metrics.end_time = datetime.now().isoformat()
            process.metrics.progress_percent = 100.0

            # Calculate duration
            if process.metrics.start_time:
                start = datetime.fromisoformat(process.metrics.start_time)
                end = datetime.fromisoformat(process.metrics.end_time)
                process.metrics.duration_seconds = (end - start).total_seconds()

            await self._log(process_id, "INFO", f"✓ Completed successfully in {process.metrics.duration_seconds:.2f}s")

    async def fail_process(
        self,
        process_id: str,
        error: str
    ):
        """Mark process as failed - NO FALLBACKS"""
        async with self._lock:
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]
            process.status = ProcessStatus.FAILED
            process.error = error
            process.metrics.end_time = datetime.now().isoformat()

            await self._log(process_id, "ERROR", f"✗ Failed: {error}")

    async def _log(
        self,
        process_id: str,
        level: str,
        message: str
    ):
        """Add log entry to process"""
        if process_id in self._processes:
            log = ProcessLog(
                timestamp=datetime.now().isoformat(),
                level=level,
                message=message
            )
            self._processes[process_id].logs.append(log)

            # Also log to Python logger
            log_func = getattr(logger, level.lower(), logger.info)
            log_func(f"[{process_id}] {message}")

    async def get_process(self, process_id: str) -> Optional[ProcessInfo]:
        """Get process info"""
        async with self._lock:
            return self._processes.get(process_id)

    async def get_all_processes(self) -> List[ProcessInfo]:
        """Get all processes"""
        async with self._lock:
            return list(self._processes.values())

    async def get_running_processes(self) -> List[ProcessInfo]:
        """Get only running processes"""
        async with self._lock:
            return [
                p for p in self._processes.values()
                if p.status == ProcessStatus.RUNNING
            ]

    async def cancel_process(self, process_id: str):
        """Cancel a running process"""
        async with self._lock:
            if process_id not in self._processes:
                raise ValueError(f"Process {process_id} not found!")

            process = self._processes[process_id]
            if process.status != ProcessStatus.RUNNING:
                raise ValueError(f"Process {process_id} is not running (status: {process.status.value})")

            process.status = ProcessStatus.CANCELLED
            process.metrics.end_time = datetime.now().isoformat()

            await self._log(process_id, "WARNING", "Process cancelled by user")


# Global monitor instance
monitor = ProcessMonitor()


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
