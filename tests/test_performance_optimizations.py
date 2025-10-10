"""Test performance optimizations for monitoring system"""
import asyncio
import pytest
from datetime import datetime, timedelta

from src.monitoring.process_monitor import ProcessMonitor, monitor
from src.utils.background_tasks import BackgroundTaskManager


class TestProcessMonitorCaching:
    """Test caching optimizations in ProcessMonitor"""

    @pytest.mark.asyncio
    async def test_get_all_processes_caching(self):
        """Test that get_all_processes uses caching"""
        # Start a process
        await monitor.start_process("test_cache_1", "test", total_steps=1)

        # First call - should populate cache
        processes1 = await monitor.get_all_processes()
        cache_time1 = monitor._cache_timestamp

        # Second call immediately - should use cache
        processes2 = await monitor.get_all_processes()
        cache_time2 = monitor._cache_timestamp

        # Cache timestamp should be the same (cache hit)
        assert cache_time1 == cache_time2
        assert len(processes1) == len(processes2)

        # Wait for cache to expire (100ms TTL)
        await asyncio.sleep(0.15)

        # Third call - should refresh cache
        processes3 = await monitor.get_all_processes()
        cache_time3 = monitor._cache_timestamp

        # Cache timestamp should be different (cache miss)
        assert cache_time3 > cache_time2

        # Clean up
        await monitor.complete_process("test_cache_1", {"result": "success"})

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_state_change(self):
        """Test that cache is invalidated when process state changes"""
        # Get initial state
        processes1 = await monitor.get_all_processes()
        initial_count = len(processes1)

        # Add a new process
        await monitor.start_process("test_invalidate_1", "test", total_steps=1)

        # Cache should be invalidated, so next call should show new process
        processes2 = await monitor.get_all_processes()
        assert len(processes2) == initial_count + 1

        # Complete the process - should invalidate cache
        await monitor.complete_process("test_invalidate_1", {"result": "success"})

        # Verify cache was invalidated
        processes3 = await monitor.get_all_processes()
        # Count is still same, but status changed
        assert len(processes3) == initial_count + 1

    @pytest.mark.asyncio
    async def test_log_serialization_caching(self):
        """Test that ProcessInfo.to_dict() caches log serialization"""
        # Start a process
        await monitor.start_process("test_log_cache_1", "test", total_steps=1)

        # Get the process
        process = await monitor.get_process("test_log_cache_1")
        assert process is not None

        # First to_dict call - should populate log cache
        dict1 = process.to_dict()
        assert process._serialized_logs_cache is not None
        assert process._logs_cache_size == len(process.logs)

        # Second to_dict call - should use cached logs
        dict2 = process.to_dict()
        # Cache should be reused (same object reference)
        assert dict2["logs"] is dict1["logs"]

        # Add a new log
        await monitor.update_progress("test_log_cache_1", 50.0, "Testing", 1)

        # Third to_dict call - should re-serialize logs (cache invalidated)
        dict3 = process.to_dict()
        # Cache should be different (new serialization)
        assert dict3["logs"] is not dict2["logs"]

        # Clean up
        await monitor.complete_process("test_log_cache_1", {"result": "success"})


class TestCleanupOldProcesses:
    """Test cleanup of old processes"""

    @pytest.mark.asyncio
    async def test_cleanup_old_processes(self):
        """Test that old completed processes are cleaned up"""
        # Create and complete a process
        await monitor.start_process("test_cleanup_1", "test", total_steps=1)
        await monitor.complete_process("test_cleanup_1", {"result": "success"})

        # Verify it exists
        process = await monitor.get_process("test_cleanup_1")
        assert process is not None

        # Try to clean up (should not remove - too recent)
        removed = await monitor.cleanup_old_processes(max_age_hours=24)
        assert removed == 0

        # Verify still exists
        process = await monitor.get_process("test_cleanup_1")
        assert process is not None

        # Test cleanup with 0 hour age (should remove all completed)
        removed = await monitor.cleanup_old_processes(max_age_hours=0)
        assert removed >= 1

        # Verify it's gone
        process = await monitor.get_process("test_cleanup_1")
        assert process is None


class TestBackgroundTasks:
    """Test background task manager"""

    @pytest.mark.asyncio
    async def test_background_manager_lifecycle(self):
        """Test background manager starts and stops correctly"""
        manager = BackgroundTaskManager()

        # Start background tasks
        await manager.start()
        assert manager._running is True
        assert len(manager._tasks) > 0

        # Attempting to start again should warn
        await manager.start()  # Should log warning

        # Stop background tasks
        await manager.stop()
        assert manager._running is False
        assert len(manager._tasks) == 0


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Clean up all processes after each test"""
    yield
    # Clean up all processes
    all_processes = await monitor.get_all_processes()
    for process in all_processes:
        if process.status.value == "running":
            try:
                await monitor.cancel_process(process.process_id)
            except:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
