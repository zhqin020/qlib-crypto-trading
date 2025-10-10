"""
Test that task cancellation properly stops the entire execution chain.
Tests the fix for the critical task cancellation gap in api_enhanced.py
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.monitoring.process_monitor import monitor, ProcessStatus


@pytest.mark.asyncio
async def test_task_registration_pattern():
    """Verify tasks are properly registered with ProcessMonitor"""
    process_id = "test_task_registration"

    # Create a simple async task
    async def sample_task():
        await asyncio.sleep(0.1)
        return {"status": "completed"}

    # Create and register task
    task = asyncio.create_task(sample_task())
    await monitor.register_task(process_id, task)

    # Verify task is registered
    assert process_id in monitor._tasks
    assert monitor._tasks[process_id] == task

    # Wait for task to complete
    result = await task
    assert result["status"] == "completed"

    # Cleanup
    if process_id in monitor._tasks:
        del monitor._tasks[process_id]


@pytest.mark.asyncio
async def test_task_cancellation_propagates():
    """Verify cancellation properly propagates through the task chain"""
    process_id = "test_cancellation"
    cancelled = False

    async def long_running_task():
        nonlocal cancelled
        try:
            await monitor.start_process(process_id, "test", total_steps=1)
            await asyncio.sleep(10)  # Long running task
            return {"status": "completed"}
        except asyncio.CancelledError:
            cancelled = True
            await monitor.add_log(process_id, "WARNING", "Process cancelled by user")
            raise

    # Create and register task
    task = asyncio.create_task(long_running_task())
    await monitor.register_task(process_id, task)

    # Give task time to start
    await asyncio.sleep(0.1)

    # Cancel the process
    await monitor.cancel_process(process_id)

    # Verify task was cancelled
    with pytest.raises(asyncio.CancelledError):
        await task

    assert cancelled, "Task should have caught CancelledError"

    # Verify process status
    process = await monitor.get_process(process_id)
    assert process.status == ProcessStatus.CANCELLED

    # Cleanup
    if process_id in monitor._processes:
        del monitor._processes[process_id]


@pytest.mark.asyncio
async def test_endpoint_pattern_matches_trainer():
    """Verify the API endpoint pattern matches the pattern in trainer.py"""
    from src.models.trainer import train_model
    import inspect

    # Get the source code of train_model
    source = inspect.getsource(train_model)

    # Verify it uses the proper pattern
    assert "asyncio.create_task" in source, "Should use asyncio.create_task"
    assert "await monitor.register_task" in source, "Should register task with monitor"
    assert "asyncio.CancelledError" in source, "Should handle cancellation"


@pytest.mark.asyncio
async def test_all_endpoints_use_correct_pattern():
    """Verify all API endpoints use asyncio.create_task instead of background_tasks.add_task"""
    import ast
    from pathlib import Path

    api_file = Path(__file__).parent.parent / "src" / "ui" / "api_enhanced.py"
    with open(api_file, 'r') as f:
        source = f.read()

    # Parse the source code
    tree = ast.parse(source)

    # Find all calls to background_tasks.add_task
    background_task_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if (isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'background_tasks' and
                    node.func.attr == 'add_task'):
                    background_task_calls.append(node)

    # Should be zero occurrences after the fix
    assert len(background_task_calls) == 0, \
        f"Found {len(background_task_calls)} calls to background_tasks.add_task - all should be replaced with asyncio.create_task"

    # Verify asyncio.create_task is used
    assert "asyncio.create_task" in source, "Should use asyncio.create_task"
    assert "await monitor.register_task" in source, "Should register tasks with monitor"


@pytest.mark.asyncio
async def test_cancellation_cleanup():
    """Verify that cancelled tasks are properly cleaned up"""
    process_id = "test_cleanup"

    async def task_to_cancel():
        try:
            await monitor.start_process(process_id, "test", total_steps=1)
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await monitor.fail_process(process_id, "Cancelled")
            raise

    # Create and register task
    task = asyncio.create_task(task_to_cancel())
    await monitor.register_task(process_id, task)

    # Give task time to start
    await asyncio.sleep(0.1)

    # Verify task is registered
    assert process_id in monitor._tasks

    # Cancel the process
    await monitor.cancel_process(process_id)

    # Verify task is removed from _tasks after cancellation
    assert process_id not in monitor._tasks, "Task should be removed from _tasks after cancellation"

    # Cleanup
    if process_id in monitor._processes:
        del monitor._processes[process_id]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
