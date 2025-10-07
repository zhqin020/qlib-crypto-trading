"""
Comprehensive integration tests for ProcessMonitor

Tests monitor lifecycle, failure handling, concurrent processes,
cancellation, and log accumulation.
"""

import pytest
import asyncio
from datetime import datetime
from src.monitoring.process_monitor import (
    ProcessMonitor,
    ProcessStatus,
    ProcessInfo,
    ProcessMetrics,
    ProcessLog,
    monitor
)


@pytest.mark.asyncio
class TestProcessMonitorLifecycle:
    """Test complete process lifecycle: start → update → complete"""

    async def test_successful_process_lifecycle(self):
        """Test a process from start to successful completion"""
        # Start process
        process = await monitor.start_process(
            process_id="test_lifecycle_001",
            process_type="training",
            total_steps=5
        )

        # Verify initial state
        assert process.process_id == "test_lifecycle_001"
        assert process.process_type == "training"
        assert process.status == ProcessStatus.RUNNING
        assert process.metrics.total_steps == 5
        assert process.metrics.progress_percent == 0.0
        assert process.metrics.current_step == "Initializing"
        assert len(process.logs) == 1  # Start log

        # Update progress through steps
        await monitor.update_progress(
            process_id="test_lifecycle_001",
            progress_percent=20.0,
            current_step="Loading data",
            completed_steps=1
        )

        process = await monitor.get_process("test_lifecycle_001")
        assert process.metrics.progress_percent == 20.0
        assert process.metrics.current_step == "Loading data"
        assert process.metrics.completed_steps == 1
        assert len(process.logs) == 2

        await monitor.update_progress(
            process_id="test_lifecycle_001",
            progress_percent=60.0,
            current_step="Training model",
            completed_steps=3
        )

        process = await monitor.get_process("test_lifecycle_001")
        assert process.metrics.progress_percent == 60.0
        assert process.metrics.completed_steps == 3

        # Complete process
        result = {
            "model_id": "test_model_123",
            "accuracy": 0.95,
            "loss": 0.05
        }

        await monitor.complete_process(
            process_id="test_lifecycle_001",
            result=result
        )

        # Verify completed state
        process = await monitor.get_process("test_lifecycle_001")
        assert process.status == ProcessStatus.COMPLETED
        assert process.metrics.progress_percent == 100.0
        assert process.result == result
        assert process.metrics.duration_seconds is not None
        assert process.metrics.duration_seconds > 0
        assert process.metrics.end_time is not None

    async def test_process_start_fails_if_duplicate(self):
        """Test that starting a duplicate process raises error"""
        await monitor.start_process(
            process_id="test_duplicate",
            process_type="training"
        )

        # Try to start again with same ID
        with pytest.raises(ValueError, match="already exists"):
            await monitor.start_process(
                process_id="test_duplicate",
                process_type="training"
            )


@pytest.mark.asyncio
class TestProcessMonitorFailureHandling:
    """Test process failure handling: start → fail"""

    async def test_process_failure(self):
        """Test process failure with error message"""
        # Start process
        await monitor.start_process(
            process_id="test_failure_001",
            process_type="backtest",
            total_steps=3
        )

        # Update progress
        await monitor.update_progress(
            process_id="test_failure_001",
            progress_percent=33.0,
            current_step="Loading model",
            completed_steps=1
        )

        # Fail process
        error_msg = "Model file not found: model_123.pkl"
        await monitor.fail_process(
            process_id="test_failure_001",
            error=error_msg
        )

        # Verify failed state
        process = await monitor.get_process("test_failure_001")
        assert process.status == ProcessStatus.FAILED
        assert process.error == error_msg
        assert process.metrics.end_time is not None
        assert process.metrics.progress_percent == 33.0  # Stays at last progress

        # Check error log exists
        error_logs = [log for log in process.logs if log.level == "ERROR"]
        assert len(error_logs) > 0
        assert "Failed" in error_logs[-1].message

    async def test_update_nonexistent_process_fails(self):
        """Test that updating non-existent process raises error"""
        with pytest.raises(ValueError, match="not found"):
            await monitor.update_progress(
                process_id="nonexistent_process",
                progress_percent=50.0,
                current_step="Testing"
            )

    async def test_fail_nonexistent_process_fails(self):
        """Test that failing non-existent process raises error"""
        with pytest.raises(ValueError, match="not found"):
            await monitor.fail_process(
                process_id="nonexistent_process",
                error="Test error"
            )


@pytest.mark.asyncio
class TestConcurrentProcessTracking:
    """Test concurrent process tracking (multiple processes at once)"""

    async def test_multiple_concurrent_processes(self):
        """Test tracking multiple processes simultaneously"""
        # Start 3 concurrent processes
        process_ids = []
        for i in range(3):
            process_id = f"concurrent_test_{i}"
            process_ids.append(process_id)
            await monitor.start_process(
                process_id=process_id,
                process_type=f"type_{i}",
                total_steps=5
            )

        # Verify all processes are tracked
        all_processes = await monitor.get_all_processes()
        concurrent_processes = [p for p in all_processes if p.process_id in process_ids]
        assert len(concurrent_processes) == 3

        # Update each process independently
        for i, process_id in enumerate(process_ids):
            await monitor.update_progress(
                process_id=process_id,
                progress_percent=(i + 1) * 25.0,
                current_step=f"Step {i}",
                completed_steps=i
            )

        # Verify each has different progress
        for i, process_id in enumerate(process_ids):
            process = await monitor.get_process(process_id)
            assert process.metrics.progress_percent == (i + 1) * 25.0
            assert process.metrics.completed_steps == i

        # Complete first process
        await monitor.complete_process(
            process_id=process_ids[0],
            result={"status": "success"}
        )

        # Fail second process
        await monitor.fail_process(
            process_id=process_ids[1],
            error="Test failure"
        )

        # Verify running processes only shows third
        running = await monitor.get_running_processes()
        running_ids = [p.process_id for p in running]
        assert process_ids[2] in running_ids
        assert process_ids[0] not in running_ids
        assert process_ids[1] not in running_ids

    async def test_get_running_processes_filters_correctly(self):
        """Test that get_running_processes only returns RUNNING processes"""
        # Create processes in different states
        await monitor.start_process("running_1", "training")
        await monitor.start_process("running_2", "backtest")
        await monitor.start_process("will_complete", "prediction")
        await monitor.start_process("will_fail", "download")

        # Complete and fail some
        await monitor.complete_process("will_complete", {"status": "ok"})
        await monitor.fail_process("will_fail", "error")

        # Get running processes
        running = await monitor.get_running_processes()
        running_ids = [p.process_id for p in running]

        assert "running_1" in running_ids
        assert "running_2" in running_ids
        assert "will_complete" not in running_ids
        assert "will_fail" not in running_ids


@pytest.mark.asyncio
class TestProcessCancellation:
    """Test process cancellation"""

    async def test_cancel_running_process(self):
        """Test cancelling a running process"""
        # Start process
        await monitor.start_process(
            process_id="test_cancel_001",
            process_type="training",
            total_steps=10
        )

        # Update progress
        await monitor.update_progress(
            process_id="test_cancel_001",
            progress_percent=40.0,
            current_step="Training epoch 4/10"
        )

        # Cancel process
        await monitor.cancel_process("test_cancel_001")

        # Verify cancelled state
        process = await monitor.get_process("test_cancel_001")
        assert process.status == ProcessStatus.CANCELLED
        assert process.metrics.end_time is not None
        assert process.metrics.progress_percent == 40.0  # Stays at last progress

        # Check cancel log exists
        cancel_logs = [log for log in process.logs if "cancelled" in log.message.lower()]
        assert len(cancel_logs) > 0

    async def test_cancel_nonexistent_process_fails(self):
        """Test that cancelling non-existent process raises error"""
        with pytest.raises(ValueError, match="not found"):
            await monitor.cancel_process("nonexistent_cancel")

    async def test_cancel_completed_process_fails(self):
        """Test that cancelling completed process raises error"""
        # Start and complete process
        await monitor.start_process("completed_cancel", "training")
        await monitor.complete_process("completed_cancel", {"status": "ok"})

        # Try to cancel
        with pytest.raises(ValueError, match="not running"):
            await monitor.cancel_process("completed_cancel")

    async def test_cancel_failed_process_fails(self):
        """Test that cancelling failed process raises error"""
        # Start and fail process
        await monitor.start_process("failed_cancel", "training")
        await monitor.fail_process("failed_cancel", "error")

        # Try to cancel
        with pytest.raises(ValueError, match="not running"):
            await monitor.cancel_process("failed_cancel")


@pytest.mark.asyncio
class TestLogAccumulation:
    """Test log accumulation and management"""

    async def test_logs_accumulate_correctly(self):
        """Test that logs accumulate throughout process lifecycle"""
        process_id = "test_logs_001"
        await monitor.start_process(process_id, "training", total_steps=5)

        initial_logs = (await monitor.get_process(process_id)).logs
        assert len(initial_logs) == 1  # Start log

        # Add multiple updates
        for i in range(5):
            await monitor.update_progress(
                process_id=process_id,
                progress_percent=(i + 1) * 20.0,
                current_step=f"Step {i + 1}",
                completed_steps=i + 1
            )

        # Complete process
        await monitor.complete_process(process_id, {"status": "success"})

        # Check log count
        final_process = await monitor.get_process(process_id)
        assert len(final_process.logs) == 7  # 1 start + 5 updates + 1 complete

        # Verify log order (chronological)
        timestamps = [log.timestamp for log in final_process.logs]
        assert timestamps == sorted(timestamps)

    async def test_logs_limited_to_100_in_output(self):
        """Test that to_dict() only returns last 100 logs"""
        process_id = "test_log_limit"
        await monitor.start_process(process_id, "training")

        # Add 150 log entries
        for i in range(150):
            await monitor.update_progress(
                process_id=process_id,
                progress_percent=min(i / 150 * 100, 99.0),
                current_step=f"Step {i}"
            )

        process = await monitor.get_process(process_id)
        process_dict = process.to_dict()

        # Process stores all logs, but to_dict limits to 100
        assert len(process.logs) > 100
        assert len(process_dict["logs"]) == 100

    async def test_log_levels(self):
        """Test different log levels are captured correctly"""
        process_id = "test_log_levels"
        await monitor.start_process(process_id, "training")

        # Start creates INFO log
        # Update creates INFO log
        await monitor.update_progress(process_id, 50.0, "Half way")

        # Fail creates ERROR log
        await monitor.fail_process(process_id, "Test error")

        process = await monitor.get_process(process_id)
        log_levels = [log.level for log in process.logs]

        assert "INFO" in log_levels
        assert "ERROR" in log_levels

    async def test_log_timestamps_are_iso_format(self):
        """Test that log timestamps are valid ISO format strings"""
        process_id = "test_timestamps"
        await monitor.start_process(process_id, "training")
        await monitor.update_progress(process_id, 50.0, "Testing")

        process = await monitor.get_process(process_id)

        for log in process.logs:
            # Should be parseable as ISO datetime
            datetime.fromisoformat(log.timestamp)

    async def test_process_to_dict_format(self):
        """Test that process.to_dict() returns correct structure"""
        process_id = "test_dict_format"
        await monitor.start_process(process_id, "training", total_steps=3)
        await monitor.update_progress(process_id, 33.0, "Step 1", 1)
        await monitor.complete_process(process_id, {"accuracy": 0.95})

        process = await monitor.get_process(process_id)
        process_dict = process.to_dict()

        # Verify structure
        assert "process_id" in process_dict
        assert "process_type" in process_dict
        assert "status" in process_dict
        assert "metrics" in process_dict
        assert "logs" in process_dict
        assert "result" in process_dict
        assert "error" in process_dict

        # Verify metrics structure
        metrics = process_dict["metrics"]
        assert "start_time" in metrics
        assert "end_time" in metrics
        assert "duration_seconds" in metrics
        assert "progress_percent" in metrics
        assert "current_step" in metrics
        assert "total_steps" in metrics
        assert "completed_steps" in metrics

        # Verify types
        assert isinstance(process_dict["status"], str)
        assert isinstance(process_dict["logs"], list)
        assert isinstance(process_dict["result"], dict)


@pytest.fixture(autouse=True)
async def cleanup_monitor():
    """Clean up monitor state between tests"""
    # Reset monitor processes before each test
    monitor._processes = {}
    yield
    # Clean up after test
    monitor._processes = {}
