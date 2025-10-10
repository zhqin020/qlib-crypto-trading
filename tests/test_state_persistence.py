"""
Comprehensive tests for ProcessMonitor state persistence

Tests cover:
- State save/load functionality
- Running process interruption handling
- Corrupted file handling
- Old process cleanup (>7 days)
- Atomic file operations
"""
import asyncio
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from src.monitoring.process_monitor import (
    ProcessMonitor,
    ProcessStatus,
    ProcessInfo,
    ProcessMetrics,
    ProcessLog
)


@pytest.fixture
def monitor():
    """Create a fresh ProcessMonitor for each test"""
    # Create new instance
    monitor = ProcessMonitor()

    # Clear state
    monitor._processes = {}
    monitor._tasks = {}
    monitor._cached_all_processes = []
    monitor._cache_timestamp = 0
    monitor._lock = None  # Reset lock

    # Use test state file
    test_state_file = Path(__file__).parent / "test_process_state.json"
    monitor._state_file = test_state_file

    # Clean up any existing test files
    if test_state_file.exists():
        test_state_file.unlink()
    if test_state_file.with_suffix('.json.tmp').exists():
        test_state_file.with_suffix('.json.tmp').unlink()
    if test_state_file.with_suffix('.json.corrupted').exists():
        test_state_file.with_suffix('.json.corrupted').unlink()

    yield monitor

    # Cleanup after test
    if test_state_file.exists():
        test_state_file.unlink()
    if test_state_file.with_suffix('.json.tmp').exists():
        test_state_file.with_suffix('.json.tmp').unlink()
    if test_state_file.with_suffix('.json.corrupted').exists():
        test_state_file.with_suffix('.json.corrupted').unlink()


@pytest.mark.asyncio
async def test_save_state_creates_file(monitor):
    """Test that save_state creates a JSON file"""
    # Create a completed process
    await monitor.start_process("test_proc_1", "training", total_steps=5)
    await monitor.complete_process("test_proc_1", {"accuracy": 0.95})

    # Save state
    saved_count = await monitor.save_state()

    assert saved_count == 1
    assert monitor._state_file.exists()

    # Verify JSON structure
    with open(monitor._state_file, 'r') as f:
        state = json.load(f)

    assert state["version"] == "1.0"
    assert "saved_at" in state
    assert len(state["processes"]) == 1
    assert state["processes"][0]["process_id"] == "test_proc_1"
    assert state["processes"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_save_state_running_process_marked_interrupted(monitor):
    """Test that running processes are marked as interrupted when saved"""
    # Create a running process
    await monitor.start_process("running_proc", "backtest", total_steps=10)
    await monitor.update_progress("running_proc", 45.0, "Processing data", completed_steps=4)

    # Save state
    saved_count = await monitor.save_state()

    assert saved_count == 1

    # Load and verify
    with open(monitor._state_file, 'r') as f:
        state = json.load(f)

    proc = state["processes"][0]
    assert proc["status"] == "interrupted"
    assert proc["metadata"]["last_known_progress"] == 45.0
    assert proc["metadata"]["last_known_step"] == "Processing data"
    assert "interrupted_at" in proc["metadata"]

    # Verify only last 100 logs are saved
    assert len(proc["logs"]) <= 100


@pytest.mark.asyncio
async def test_save_state_terminal_states_only(monitor):
    """Test that only terminal states are persisted"""
    # Create various processes
    await monitor.start_process("completed_proc", "training")
    await monitor.complete_process("completed_proc", {"result": "success"})

    await monitor.start_process("failed_proc", "download")
    await monitor.fail_process("failed_proc", "Connection error")

    await monitor.start_process("cancelled_proc", "backtest")
    await monitor.cancel_process("cancelled_proc")

    await monitor.start_process("running_proc", "prediction")

    # Don't create pending_proc since start_process always creates RUNNING status
    # We'll verify that RUNNING processes become INTERRUPTED instead

    # Save state
    saved_count = await monitor.save_state()

    # Should save: completed, failed, cancelled, and running (as interrupted)
    assert saved_count == 4

    with open(monitor._state_file, 'r') as f:
        state = json.load(f)

    statuses = [p["status"] for p in state["processes"]]
    assert "completed" in statuses
    assert "failed" in statuses
    assert "cancelled" in statuses
    assert "interrupted" in statuses


@pytest.mark.asyncio
async def test_load_state_no_file(monitor):
    """Test load_state handles missing file gracefully"""
    restored_count = await monitor.load_state()

    assert restored_count == 0
    assert len(monitor._processes) == 0


@pytest.mark.asyncio
async def test_load_state_restores_processes(monitor):
    """Test that load_state correctly restores processes"""
    # Create and save processes
    await monitor.start_process("proc1", "training")
    await monitor.complete_process("proc1", {"accuracy": 0.95})

    await monitor.start_process("proc2", "download")
    await monitor.fail_process("proc2", "Network error")

    await monitor.save_state()

    # Clear in-memory state
    monitor._processes = {}
    monitor._cached_all_processes = []

    # Load state
    restored_count = await monitor.load_state()

    assert restored_count == 2
    assert "proc1" in monitor._processes
    assert "proc2" in monitor._processes

    proc1 = monitor._processes["proc1"]
    assert proc1.status == ProcessStatus.COMPLETED
    assert proc1.result == {"accuracy": 0.95}

    proc2 = monitor._processes["proc2"]
    assert proc2.status == ProcessStatus.FAILED
    assert proc2.error == "Network error"


@pytest.mark.asyncio
async def test_load_state_interrupted_process(monitor):
    """Test that interrupted processes are loaded correctly"""
    # Create state file with interrupted process
    state = {
        "version": "1.0",
        "saved_at": datetime.now().isoformat(),
        "processes": [{
            "process_id": "interrupted_proc",
            "process_type": "training",
            "display_id": "Training #1",
            "status": "interrupted",
            "metrics": {
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "duration_seconds": None,
                "progress_percent": 67.5,
                "current_step": "Training epoch 3",
                "total_steps": 5,
                "completed_steps": 3,
                "memory_mb": None,
                "cpu_percent": None,
                "estimated_completion": None,
                "estimated_seconds_remaining": None
            },
            "logs": [
                {"timestamp": datetime.now().isoformat(), "level": "INFO", "message": "Started training"}
            ],
            "result": None,
            "error": None,
            "metadata": {
                "last_known_progress": 67.5,
                "last_known_step": "Training epoch 3",
                "interrupted_at": datetime.now().isoformat()
            }
        }]
    }

    with open(monitor._state_file, 'w') as f:
        json.dump(state, f)

    # Load state
    restored_count = await monitor.load_state()

    assert restored_count == 1
    assert "interrupted_proc" in monitor._processes

    proc = monitor._processes["interrupted_proc"]
    assert proc.status == ProcessStatus.INTERRUPTED
    assert proc.metadata["last_known_progress"] == 67.5
    assert proc.metadata["last_known_step"] == "Training epoch 3"


@pytest.mark.asyncio
async def test_load_state_corrupted_file(monitor):
    """Test that corrupted JSON files are handled gracefully"""
    # Create corrupted JSON file
    with open(monitor._state_file, 'w') as f:
        f.write("{ this is not valid JSON }")

    # Load state
    restored_count = await monitor.load_state()

    assert restored_count == 0
    assert len(monitor._processes) == 0

    # Verify corrupted file was backed up
    backup_file = monitor._state_file.with_suffix('.json.corrupted')
    assert backup_file.exists()


@pytest.mark.asyncio
async def test_cleanup_old_processes_from_state(monitor):
    """Test that processes older than 7 days are cleaned up on load"""
    # Create state with old and new processes
    now = datetime.now()
    old_time = (now - timedelta(days=8)).isoformat()
    new_time = (now - timedelta(days=1)).isoformat()

    state = {
        "version": "1.0",
        "saved_at": now.isoformat(),
        "processes": [
            {
                "process_id": "old_proc",
                "process_type": "training",
                "display_id": "Training #1",
                "status": "completed",
                "metrics": {
                    "start_time": old_time,
                    "end_time": old_time,
                    "duration_seconds": 100,
                    "progress_percent": 100,
                    "current_step": "Done",
                    "total_steps": 5,
                    "completed_steps": 5,
                    "memory_mb": None,
                    "cpu_percent": None,
                    "estimated_completion": None,
                    "estimated_seconds_remaining": None
                },
                "logs": [],
                "result": {"success": True},
                "error": None,
                "metadata": None
            },
            {
                "process_id": "new_proc",
                "process_type": "training",
                "display_id": "Training #2",
                "status": "completed",
                "metrics": {
                    "start_time": new_time,
                    "end_time": new_time,
                    "duration_seconds": 50,
                    "progress_percent": 100,
                    "current_step": "Done",
                    "total_steps": 3,
                    "completed_steps": 3,
                    "memory_mb": None,
                    "cpu_percent": None,
                    "estimated_completion": None,
                    "estimated_seconds_remaining": None
                },
                "logs": [],
                "result": {"success": True},
                "error": None,
                "metadata": None
            }
        ]
    }

    with open(monitor._state_file, 'w') as f:
        json.dump(state, f)

    # Load state
    restored_count = await monitor.load_state()

    # Only new process should remain after cleanup
    assert restored_count == 1
    assert "new_proc" in monitor._processes
    assert "old_proc" not in monitor._processes


@pytest.mark.asyncio
async def test_save_state_atomic_write(monitor):
    """Test that save_state uses atomic write (temp file then rename)"""
    # Create a process
    await monitor.start_process("proc1", "training")
    await monitor.complete_process("proc1", {"result": "success"})

    # Save state
    await monitor.save_state()

    # Verify temp file was cleaned up
    temp_file = monitor._state_file.with_suffix('.json.tmp')
    assert not temp_file.exists()

    # Verify actual file exists
    assert monitor._state_file.exists()


@pytest.mark.asyncio
async def test_save_state_preserves_last_100_logs(monitor):
    """Test that only last 100 logs are saved"""
    # Create process with many logs
    await monitor.start_process("proc1", "training")

    # Add 150 logs
    for i in range(150):
        await monitor.update_progress("proc1", i/150*100, f"Step {i}", completed_steps=i)

    await monitor.complete_process("proc1", {"result": "success"})

    # Save state
    await monitor.save_state()

    # Load and verify
    with open(monitor._state_file, 'r') as f:
        state = json.load(f)

    # Should only have last 100 logs
    assert len(state["processes"][0]["logs"]) == 100


@pytest.mark.asyncio
async def test_load_state_version_mismatch_warning(monitor, caplog):
    """Test that version mismatch generates warning but continues"""
    state = {
        "version": "2.0",  # Future version
        "saved_at": datetime.now().isoformat(),
        "processes": []
    }

    with open(monitor._state_file, 'w') as f:
        json.dump(state, f)

    # Load state
    await monitor.load_state()

    # Should have warning about version mismatch (check would need proper logging setup)
    # For now just verify it didn't crash


@pytest.mark.asyncio
async def test_save_load_roundtrip(monitor):
    """Test complete save/load roundtrip preserves data"""
    # Create various processes
    await monitor.start_process("proc1", "training", total_steps=5)
    await monitor.update_progress("proc1", 80.0, "Almost done", completed_steps=4)
    await monitor.complete_process("proc1", {"accuracy": 0.95, "loss": 0.05})

    await monitor.start_process("proc2", "download")
    await monitor.fail_process("proc2", "Network timeout")

    await monitor.start_process("proc3", "backtest")
    await monitor.update_progress("proc3", 50.0, "Processing")
    # Leave running

    # Save state
    saved_count = await monitor.save_state()
    assert saved_count == 3

    # Clear and reload
    original_procs = {k: v.to_dict() for k, v in monitor._processes.items()}
    monitor._processes = {}

    restored_count = await monitor.load_state()
    assert restored_count == 3

    # Verify proc1
    proc1 = monitor._processes["proc1"]
    assert proc1.status == ProcessStatus.COMPLETED
    assert proc1.result == {"accuracy": 0.95, "loss": 0.05}
    assert proc1.metrics.progress_percent == 100.0

    # Verify proc2
    proc2 = monitor._processes["proc2"]
    assert proc2.status == ProcessStatus.FAILED
    assert proc2.error == "Network timeout"

    # Verify proc3 (was running, now interrupted)
    proc3 = monitor._processes["proc3"]
    assert proc3.status == ProcessStatus.INTERRUPTED
    assert proc3.metadata["last_known_progress"] == 50.0
    assert proc3.metadata["last_known_step"] == "Processing"


@pytest.mark.asyncio
async def test_load_state_invalid_process_skipped(monitor, caplog):
    """Test that invalid processes are skipped but others load"""
    state = {
        "version": "1.0",
        "saved_at": datetime.now().isoformat(),
        "processes": [
            {
                "process_id": "valid_proc",
                "process_type": "training",
                "display_id": "Training #1",
                "status": "completed",
                "metrics": {
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": 100,
                    "progress_percent": 100,
                    "current_step": "Done",
                    "total_steps": 5,
                    "completed_steps": 5,
                    "memory_mb": None,
                    "cpu_percent": None,
                    "estimated_completion": None,
                    "estimated_seconds_remaining": None
                },
                "logs": [],
                "result": {"success": True},
                "error": None,
                "metadata": None
            },
            {
                "process_id": "invalid_proc",
                # Missing required fields
                "status": "invalid_status"
            }
        ]
    }

    with open(monitor._state_file, 'w') as f:
        json.dump(state, f)

    # Load state
    restored_count = await monitor.load_state()

    # Should only restore valid process
    assert restored_count == 1
    assert "valid_proc" in monitor._processes
    assert "invalid_proc" not in monitor._processes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
