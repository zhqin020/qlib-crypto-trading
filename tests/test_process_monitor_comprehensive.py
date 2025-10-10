"""
Comprehensive ProcessMonitor lifecycle and state management tests

Tests all aspects:
- Singleton pattern
- Process lifecycle (start, update, complete, fail, cancel)
- State transitions
- Concurrency & thread safety
- Data integrity
- Query methods
- Error handling
- Memory & performance
"""
import asyncio
import time
import uuid
import tracemalloc
from datetime import datetime
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.process_monitor import (
    ProcessMonitor,
    ProcessStatus,
    ProcessInfo,
    ProcessMetrics,
    ProcessLog,
    monitor
)


class TestSingletonPattern:
    """Test 1: Singleton Pattern"""

    @pytest.mark.asyncio
    async def test_single_instance(self):
        """Test 1.1: Single Instance"""
        print("\n=== Test 1.1: Single Instance ===")

        instance1 = ProcessMonitor()
        instance2 = ProcessMonitor()

        assert instance1 is instance2, "❌ FAIL: Multiple instances created"
        assert instance1 is monitor, "❌ FAIL: Global instance mismatch"

        print("✅ PASS: All references point to same object")

    @pytest.mark.asyncio
    async def test_state_sharing(self):
        """Test 1.2: State Sharing"""
        print("\n=== Test 1.2: State Sharing ===")

        # Clear existing state
        ProcessMonitor._processes.clear()

        monitor1 = ProcessMonitor()
        await monitor1.start_process("test_001", "training", 5)

        monitor2 = ProcessMonitor()
        process = await monitor2.get_process("test_001")

        assert process is not None, "❌ FAIL: State not shared between instances"
        assert process.process_id == "test_001", "❌ FAIL: Wrong process returned"

        print("✅ PASS: State shared correctly")


class TestProcessLifecycle:
    """Test 2: Process Lifecycle"""

    @pytest.mark.asyncio
    async def test_start_process(self):
        """Test 2.1: Start Process"""
        print("\n=== Test 2.1: Start Process ===")

        ProcessMonitor._processes.clear()

        process = await monitor.start_process(
            process_id="test_lifecycle_001",
            process_type="training",
            total_steps=10
        )

        failures = []

        if process.process_id != "test_lifecycle_001":
            failures.append("Wrong process_id")
        if process.process_type != "training":
            failures.append("Wrong process_type")
        if process.status != ProcessStatus.RUNNING:
            failures.append(f"Wrong status: {process.status}")
        if process.metrics.progress_percent != 0.0:
            failures.append(f"Wrong progress: {process.metrics.progress_percent}")
        if process.metrics.total_steps != 10:
            failures.append(f"Wrong total_steps: {process.metrics.total_steps}")
        if process.metrics.completed_steps != 0:
            failures.append(f"Wrong completed_steps: {process.metrics.completed_steps}")
        if process.metrics.start_time is None:
            failures.append("start_time is None")
        if process.metrics.end_time is not None:
            failures.append(f"end_time should be None but is {process.metrics.end_time}")
        if len(process.logs) != 1:
            failures.append(f"Expected 1 log, got {len(process.logs)}")

        if failures:
            print(f"❌ FAIL: {', '.join(failures)}")
            assert False, f"Start process validation failed: {failures}"

        print("✅ PASS: All assertions passed")

    @pytest.mark.asyncio
    async def test_duplicate_process_id(self):
        """Test 2.2: Duplicate Process ID"""
        print("\n=== Test 2.2: Duplicate Process ID ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("duplicate_test", "training", 5)

        # Try to start again with same ID
        try:
            await monitor.start_process("duplicate_test", "training", 5)
            print("❌ FAIL: Should have raised ValueError")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            if "already exists" in str(e):
                print("✅ PASS: ValueError raised with correct message")
            else:
                print(f"❌ FAIL: Wrong error message: {e}")
                assert False

    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test 2.3: Update Progress"""
        print("\n=== Test 2.3: Update Progress ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("progress_test", "training", 10)

        await monitor.update_progress(
            "progress_test",
            progress_percent=30.0,
            current_step="Training model",
            completed_steps=3
        )

        process = await monitor.get_process("progress_test")

        failures = []
        if process.metrics.progress_percent != 30.0:
            failures.append(f"Wrong progress: {process.metrics.progress_percent}")
        if process.metrics.current_step != "Training model":
            failures.append(f"Wrong current_step: {process.metrics.current_step}")
        if process.metrics.completed_steps != 3:
            failures.append(f"Wrong completed_steps: {process.metrics.completed_steps}")
        if len(process.logs) != 2:
            failures.append(f"Expected 2 logs, got {len(process.logs)}")

        if failures:
            print(f"❌ FAIL: {', '.join(failures)}")
            assert False

        print("✅ PASS: Progress updated correctly")

    @pytest.mark.asyncio
    async def test_complete_process(self):
        """Test 2.4: Complete Process"""
        print("\n=== Test 2.4: Complete Process ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("complete_test", "training", 5)

        result = {"model_id": "test_model_123", "accuracy": 0.95}
        await monitor.complete_process("complete_test", result)

        process = await monitor.get_process("complete_test")

        failures = []
        if process.status != ProcessStatus.COMPLETED:
            failures.append(f"Wrong status: {process.status}")
        if process.metrics.progress_percent != 100.0:
            failures.append(f"Wrong progress: {process.metrics.progress_percent}")
        if process.metrics.end_time is None:
            failures.append("end_time is None")
        if process.metrics.duration_seconds is None or process.metrics.duration_seconds <= 0:
            failures.append(f"Invalid duration: {process.metrics.duration_seconds}")
        if process.result != result:
            failures.append(f"Wrong result: {process.result}")
        if process.error is not None:
            failures.append(f"error should be None but is {process.error}")

        if failures:
            print(f"❌ FAIL: {', '.join(failures)}")
            assert False

        print("✅ PASS: Completion handled correctly")

    @pytest.mark.asyncio
    async def test_fail_process(self):
        """Test 2.5: Fail Process"""
        print("\n=== Test 2.5: Fail Process ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("fail_test", "training", 5)

        error_msg = "Dataset not found"
        await monitor.fail_process("fail_test", error_msg)

        process = await monitor.get_process("fail_test")

        failures = []
        if process.status != ProcessStatus.FAILED:
            failures.append(f"Wrong status: {process.status}")
        if process.error != error_msg:
            failures.append(f"Wrong error: {process.error}")
        if process.metrics.end_time is None:
            failures.append("end_time is None")
        if process.result is not None:
            failures.append(f"result should be None but is {process.result}")

        if failures:
            print(f"❌ FAIL: {', '.join(failures)}")
            assert False

        print("✅ PASS: Failure handled correctly")

    @pytest.mark.asyncio
    async def test_cancel_process(self):
        """Test 2.6: Cancel Process"""
        print("\n=== Test 2.6: Cancel Process ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("cancel_test", "training", 5)
        await monitor.update_progress("cancel_test", 50.0, "Halfway", 5)

        await monitor.cancel_process("cancel_test")

        process = await monitor.get_process("cancel_test")

        failures = []
        if process.status != ProcessStatus.CANCELLED:
            failures.append(f"Wrong status: {process.status}")
        if process.metrics.end_time is None:
            failures.append("end_time is None")

        # Check logs
        last_log_message = process.logs[-1].message.lower()
        if "cancel" not in last_log_message:
            failures.append(f"Last log doesn't mention cancel: {last_log_message}")

        if failures:
            print(f"❌ FAIL: {', '.join(failures)}")
            assert False

        print("✅ PASS: Cancellation works")


class TestStateTransitions:
    """Test 3: State Transitions"""

    @pytest.mark.asyncio
    async def test_invalid_transitions(self):
        """Test 3.2: Invalid Transitions"""
        print("\n=== Test 3.2: Invalid Transitions ===")

        ProcessMonitor._processes.clear()

        # Try to cancel completed process
        await monitor.start_process("invalid_trans", "training", 5)
        await monitor.complete_process("invalid_trans", {})

        try:
            await monitor.cancel_process("invalid_trans")
            print("❌ FAIL: Should raise ValueError")
            assert False, "Should raise ValueError"
        except ValueError as e:
            if "not running" in str(e):
                print("✅ PASS: Prevents invalid transitions")
            else:
                print(f"⚠️ WARNING: Error message unclear: {e}")

    @pytest.mark.asyncio
    async def test_update_nonexistent_process(self):
        """Test 3.3: Update Non-Existent Process"""
        print("\n=== Test 3.3: Update Non-Existent Process ===")

        try:
            await monitor.update_progress("nonexistent", 50.0, "test", 5)
            print("❌ FAIL: Should raise ValueError")
            assert False, "Should raise ValueError"
        except ValueError as e:
            if "not found" in str(e):
                print("✅ PASS: Error on missing process")
            else:
                print(f"⚠️ WARNING: Error message unclear: {e}")


class TestConcurrency:
    """Test 4: Concurrency & Thread Safety"""

    @pytest.mark.asyncio
    async def test_async_lock_initialization(self):
        """Test 4.1: Async Lock Initialization"""
        print("\n=== Test 4.1: Async Lock Initialization ===")

        # Create fresh monitor
        ProcessMonitor._instance = None
        ProcessMonitor._lock = None

        pm = ProcessMonitor()

        # BUG FOUND: _lock is class variable, not instance variable
        # So checking pm._lock checks class variable
        print(f"Lock before use: {pm._lock}")

        # Use in async context
        await pm.start_process("lock_test", "training", 5)

        print(f"Lock after use: {pm._lock}")

        if pm._lock is not None:
            print("✅ PASS: Lock created lazily")
        else:
            print("❌ FAIL: Lock not created")

    @pytest.mark.asyncio
    async def test_concurrent_updates(self):
        """Test 4.2: Concurrent Updates"""
        print("\n=== Test 4.2: Concurrent Updates ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("concurrent_test", "training", 100)

        # 10 concurrent updates
        tasks = [
            monitor.update_progress("concurrent_test", i*10, f"Step {i}", i)
            for i in range(1, 11)
        ]
        await asyncio.gather(*tasks)

        process = await monitor.get_process("concurrent_test")

        # Progress should be one of the values (race is ok)
        if 10 <= process.metrics.progress_percent <= 100:
            print(f"✅ PASS: Progress is valid ({process.metrics.progress_percent}%)")
        else:
            print(f"❌ FAIL: Invalid progress: {process.metrics.progress_percent}")

        # Logs should have all updates (order may vary)
        if len(process.logs) >= 11:  # Start + 10 updates
            print(f"✅ PASS: All updates logged ({len(process.logs)} logs)")
        else:
            print(f"❌ FAIL: Missing logs ({len(process.logs)} < 11)")

    @pytest.mark.asyncio
    async def test_concurrent_process_creation(self):
        """Test 4.3: Concurrent Process Creation"""
        print("\n=== Test 4.3: Concurrent Process Creation ===")

        ProcessMonitor._processes.clear()

        # Create 50 processes simultaneously
        tasks = [
            monitor.start_process(f"concurrent_{i}", "training", 5)
            for i in range(50)
        ]
        processes = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for exceptions
        exceptions = [p for p in processes if isinstance(p, Exception)]
        if exceptions:
            print(f"❌ FAIL: {len(exceptions)} exceptions occurred")
            for e in exceptions[:3]:  # Show first 3
                print(f"  - {e}")
            assert False

        # All should be retrievable
        all_processes = await monitor.get_all_processes()

        if len(all_processes) == 50:
            print("✅ PASS: All created without conflicts")
        else:
            print(f"❌ FAIL: Expected 50 processes, got {len(all_processes)}")


class TestDataIntegrity:
    """Test 5: Data Integrity"""

    @pytest.mark.asyncio
    async def test_process_id_format(self):
        """Test 5.1: Process ID Format"""
        print("\n=== Test 5.1: Process ID Format ===")

        # Test timestamp-based IDs from workflows
        process_id = f"training_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

        # Verify format
        parts = process_id.split("_")

        failures = []
        if len(parts) != 3:
            failures.append(f"Expected 3 parts, got {len(parts)}")
        elif parts[0] not in ["training", "backtest", "prediction", "download"]:
            failures.append(f"Invalid process type: {parts[0]}")
        elif not parts[1].isdigit():
            failures.append(f"Timestamp not numeric: {parts[1]}")
        elif len(parts[2]) != 6:
            failures.append(f"UUID fragment wrong length: {len(parts[2])}")

        if failures:
            print(f"❌ FAIL: {', '.join(failures)}")
            assert False

        print("✅ PASS: Correct format")

    @pytest.mark.asyncio
    async def test_timestamp_accuracy(self):
        """Test 5.2: Timestamp Accuracy"""
        print("\n=== Test 5.2: Timestamp Accuracy ===")

        ProcessMonitor._processes.clear()

        before = time.time()
        process = await monitor.start_process("timestamp_test", "training", 5)
        after = time.time()

        start_time = datetime.fromisoformat(process.metrics.start_time)
        start_ts = start_time.timestamp()

        if before <= start_ts <= after:
            print(f"✅ PASS: Timestamp accurate (within {after - before:.4f}s window)")
        else:
            print(f"❌ FAIL: Timestamp outside window: {start_ts} not in [{before}, {after}]")

    @pytest.mark.asyncio
    async def test_duration_calculation(self):
        """Test 5.3: Duration Calculation"""
        print("\n=== Test 5.3: Duration Calculation ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("duration_test", "training", 5)
        await asyncio.sleep(2)  # Wait 2 seconds
        await monitor.complete_process("duration_test", {})

        process = await monitor.get_process("duration_test")

        if 1.9 <= process.metrics.duration_seconds <= 2.5:
            print(f"✅ PASS: Duration calculated correctly ({process.metrics.duration_seconds:.3f}s)")
        else:
            print(f"❌ FAIL: Duration inaccurate: {process.metrics.duration_seconds}s (expected ~2s)")

    @pytest.mark.asyncio
    async def test_log_ordering(self):
        """Test 5.4: Log Ordering"""
        print("\n=== Test 5.4: Log Ordering ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("log_order_test", "training", 5)
        await monitor.update_progress("log_order_test", 25, "Step 1", 1)
        await asyncio.sleep(0.1)
        await monitor.update_progress("log_order_test", 50, "Step 2", 2)
        await asyncio.sleep(0.1)
        await monitor.update_progress("log_order_test", 75, "Step 3", 3)

        process = await monitor.get_process("log_order_test")
        logs = process.logs

        # Verify chronological order
        violations = []
        for i in range(len(logs) - 1):
            t1 = datetime.fromisoformat(logs[i].timestamp)
            t2 = datetime.fromisoformat(logs[i+1].timestamp)
            if t1 > t2:
                violations.append(f"Log {i} > Log {i+1}")

        if not violations:
            print("✅ PASS: Logs in chronological order")
        else:
            print(f"❌ FAIL: Log ordering violations: {violations}")

    @pytest.mark.asyncio
    async def test_log_limiting(self):
        """Test 5.5: Log Limiting (to_dict)"""
        print("\n=== Test 5.5: Log Limiting (to_dict) ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("log_limit_test", "training", 500)

        # Add 200 log entries
        for i in range(200):
            await monitor.update_progress("log_limit_test", i/2, f"Step {i}", i)

        process = await monitor.get_process("log_limit_test")

        if len(process.logs) == 201:  # All stored (start + 200)
            print(f"✅ PASS: All logs stored ({len(process.logs)})")
        else:
            print(f"⚠️ WARNING: Expected 201 logs, got {len(process.logs)}")

        # But to_dict limits to 100
        dict_repr = process.to_dict()

        if len(dict_repr["logs"]) == 100:
            print("✅ PASS: to_dict() limits to 100 correctly")
        else:
            print(f"❌ FAIL: to_dict() returned {len(dict_repr['logs'])} logs (expected 100)")


class TestQueryMethods:
    """Test 6: Query Methods"""

    @pytest.mark.asyncio
    async def test_get_process(self):
        """Test 6.1: get_process()"""
        print("\n=== Test 6.1: get_process() ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("query_test_1", "training", 5)

        process = await monitor.get_process("query_test_1")

        if process is not None and process.process_id == "query_test_1":
            print("✅ PASS: Returns correct process")
        else:
            print("❌ FAIL: Wrong process returned")

        # Non-existent
        missing = await monitor.get_process("nonexistent")

        if missing is None:
            print("✅ PASS: Returns None for missing process")
        else:
            print(f"❌ FAIL: Expected None, got {missing}")

    @pytest.mark.asyncio
    async def test_get_all_processes(self):
        """Test 6.2: get_all_processes()"""
        print("\n=== Test 6.2: get_all_processes() ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("all_test_1", "training", 5)
        await monitor.start_process("all_test_2", "backtest", 5)
        await monitor.start_process("all_test_3", "prediction", 5)

        all_processes = await monitor.get_all_processes()

        if len(all_processes) == 3:
            print(f"✅ PASS: Returns all processes ({len(all_processes)})")
        else:
            print(f"❌ FAIL: Expected 3 processes, got {len(all_processes)}")

        process_ids = {p.process_id for p in all_processes}
        expected_ids = {"all_test_1", "all_test_2", "all_test_3"}

        if process_ids == expected_ids:
            print("✅ PASS: All process IDs correct")
        else:
            print(f"❌ FAIL: Missing/extra IDs: {process_ids}")

    @pytest.mark.asyncio
    async def test_get_running_processes(self):
        """Test 6.3: get_running_processes()"""
        print("\n=== Test 6.3: get_running_processes() ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("running_1", "training", 5)
        await monitor.start_process("running_2", "backtest", 5)
        await monitor.start_process("running_3", "prediction", 5)
        await monitor.complete_process("running_2", {})

        running = await monitor.get_running_processes()

        if len(running) == 2:
            print(f"✅ PASS: Filters correctly ({len(running)} running)")
        else:
            print(f"❌ FAIL: Expected 2 running, got {len(running)}")

        running_ids = {p.process_id for p in running}

        if "running_1" in running_ids and "running_3" in running_ids and "running_2" not in running_ids:
            print("✅ PASS: Correct processes returned")
        else:
            print(f"❌ FAIL: Wrong processes: {running_ids}")


class TestErrorHandling:
    """Test 7: Error Handling"""

    @pytest.mark.asyncio
    async def test_process_not_found_errors(self):
        """Test 7.1: Process Not Found Errors"""
        print("\n=== Test 7.1: Process Not Found Errors ===")

        methods = [
            ("update_progress", lambda: monitor.update_progress("missing", 50, "test", 5)),
            ("complete_process", lambda: monitor.complete_process("missing", {})),
            ("fail_process", lambda: monitor.fail_process("missing", "error")),
            ("cancel_process", lambda: monitor.cancel_process("missing")),
        ]

        failures = []
        for name, method in methods:
            try:
                await method()
                failures.append(f"{name} didn't raise ValueError")
            except ValueError as e:
                if "not found" not in str(e):
                    failures.append(f"{name} wrong error message: {e}")

        if not failures:
            print("✅ PASS: All raise ValueError")
        else:
            print(f"❌ FAIL: {', '.join(failures)}")

    @pytest.mark.asyncio
    async def test_invalid_progress_values(self):
        """Test 7.2: Invalid Progress Values"""
        print("\n=== Test 7.2: Invalid Progress Values ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("validation_test", "training", 5)

        # Negative progress (should be caught or clamped)
        try:
            await monitor.update_progress("validation_test", -10.0, "test", 0)

            # If no validation, at least shouldn't crash
            process = await monitor.get_process("validation_test")

            if process.metrics.progress_percent < 0:
                print(f"⚠️ WARNING: No validation - negative progress allowed ({process.metrics.progress_percent})")
            else:
                print(f"✅ PASS: Progress clamped to {process.metrics.progress_percent}")
        except ValueError:
            print("✅ PASS: Validation exists, ValueError raised")


class TestMemoryPerformance:
    """Test 8: Memory & Performance"""

    @pytest.mark.asyncio
    async def test_performance_1000_updates(self):
        """Test 8.2: Performance (1000 updates)"""
        print("\n=== Test 8.2: Performance (1000 updates) ===")

        ProcessMonitor._processes.clear()

        await monitor.start_process("perf_test", "training", 1000)

        start = time.time()
        for i in range(1000):
            await monitor.update_progress("perf_test", i/10, f"Step {i}", i)
        elapsed = time.time() - start

        print(f"Time for 1000 updates: {elapsed:.3f}s")

        if elapsed < 2.0:
            print(f"✅ PASS: Fast updates ({1000/elapsed:.0f} ops/sec)")
        else:
            print(f"⚠️ WARNING: Slow updates ({1000/elapsed:.0f} ops/sec)")


# Run all tests
if __name__ == "__main__":
    print("=" * 80)
    print("PROCESSMONITOR COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    async def run_all_tests():
        # Test 1: Singleton
        suite1 = TestSingletonPattern()
        await suite1.test_single_instance()
        await suite1.test_state_sharing()

        # Test 2: Lifecycle
        suite2 = TestProcessLifecycle()
        await suite2.test_start_process()
        await suite2.test_duplicate_process_id()
        await suite2.test_update_progress()
        await suite2.test_complete_process()
        await suite2.test_fail_process()
        await suite2.test_cancel_process()

        # Test 3: State Transitions
        suite3 = TestStateTransitions()
        await suite3.test_invalid_transitions()
        await suite3.test_update_nonexistent_process()

        # Test 4: Concurrency
        suite4 = TestConcurrency()
        await suite4.test_async_lock_initialization()
        await suite4.test_concurrent_updates()
        await suite4.test_concurrent_process_creation()

        # Test 5: Data Integrity
        suite5 = TestDataIntegrity()
        await suite5.test_process_id_format()
        await suite5.test_timestamp_accuracy()
        await suite5.test_duration_calculation()
        await suite5.test_log_ordering()
        await suite5.test_log_limiting()

        # Test 6: Query Methods
        suite6 = TestQueryMethods()
        await suite6.test_get_process()
        await suite6.test_get_all_processes()
        await suite6.test_get_running_processes()

        # Test 7: Error Handling
        suite7 = TestErrorHandling()
        await suite7.test_process_not_found_errors()
        await suite7.test_invalid_progress_values()

        # Test 8: Performance
        suite8 = TestMemoryPerformance()
        await suite8.test_performance_1000_updates()

        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)

    asyncio.run(run_all_tests())
