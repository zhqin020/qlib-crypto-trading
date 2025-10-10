"""
ProcessMonitor Edge Cases and Race Condition Tests

Focus on:
- Singleton pattern edge cases
- Race conditions in lock initialization
- Class vs instance variable issues
- Memory cleanup (or lack thereof)
- Process ID collision scenarios
"""
import asyncio
import time
import threading
import uuid
from datetime import datetime
import sys
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.process_monitor import ProcessMonitor, ProcessStatus, monitor


class TestSingletonEdgeCases:
    """Deep dive into singleton pattern issues"""

    def test_singleton_across_threads(self):
        """CRITICAL BUG TEST: Singleton across threads"""
        print("\n=== Singleton Across Threads ===")

        # Reset
        ProcessMonitor.reset_instance()

        instances = []

        def create_instance():
            pm = ProcessMonitor()
            instances.append(pm)

        threads = [threading.Thread(target=create_instance) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should be same instance
        unique_instances = set(id(inst) for inst in instances)

        if len(unique_instances) == 1:
            print(f"✅ PASS: All threads got same instance")
        else:
            print(f"❌ CRITICAL BUG: {len(unique_instances)} different instances created!")
            print(f"   This breaks singleton guarantee in multi-threaded environments")

    async def test_singleton_race_condition_lock_init(self):
        """CRITICAL BUG TEST: Race condition in _get_lock()"""
        print("\n=== Race Condition in Lock Initialization ===")

        # Reset
        ProcessMonitor.reset_instance()

        pm = ProcessMonitor()

        # Simulate multiple coroutines calling _get_lock() simultaneously
        async def try_get_lock():
            return pm._get_lock()

        # 100 concurrent calls
        locks = await asyncio.gather(*[try_get_lock() for _ in range(100)])

        unique_locks = set(id(lock) for lock in locks)

        if len(unique_locks) == 1:
            print(f"✅ PASS: All got same lock (race not triggered)")
        else:
            print(f"❌ CRITICAL BUG: {len(unique_locks)} different locks created!")
            print(f"   Race condition in _get_lock() - not thread-safe!")

    async def test_class_vs_instance_variables(self):
        """BUG ANALYSIS: Class variables shared across instances"""
        print("\n=== Class vs Instance Variables ===")

        # Reset
        ProcessMonitor.reset_instance()

        pm1 = ProcessMonitor()
        pm2 = ProcessMonitor()

        # Both should be same instance (singleton)
        assert pm1 is pm2

        await pm1.start_process("test_1", "training", 5)

        # pm2 should see it (good)
        process = await pm2.get_process("test_1")

        if process is not None:
            print("✅ EXPECTED: State shared (singleton working)")
        else:
            print("❌ BUG: State not shared")

        # But here's the issue: if we reset _instance but not _processes...
        ProcessMonitor.reset_instance()
        pm3 = ProcessMonitor()  # New instance

        # Will pm3 see old processes?
        process_from_new = await pm3.get_process("test_1")

        if process_from_new is not None:
            print("⚠️ CRITICAL BUG: Class variable survives singleton reset!")
            print("   _processes is class variable, not tied to instance")
            print("   This can cause STATE BLEED between test runs")
        else:
            print("✅ PASS: Clean state")


class TestMemoryLeaks:
    """Test for unbounded memory growth"""

    async def test_no_cleanup_mechanism(self):
        """DESIGN FLAW: No way to cleanup old processes"""
        print("\n=== No Cleanup Mechanism ===")

        ProcessMonitor.reset_instance()

        # Create 10,000 processes
        for i in range(10000):
            await monitor.start_process(f"mem_test_{i}", "training", 5)
            await monitor.complete_process(f"mem_test_{i}", {})

        all_procs = await monitor.get_all_processes()

        if len(all_procs) == 10000:
            print(f"⚠️ CRITICAL DESIGN FLAW: All {len(all_procs)} processes retained in memory!")
            print("   No cleanup/expiry mechanism")
            print("   Long-running servers will accumulate unlimited process history")
            print("   Recommendation: Add max_processes limit or TTL cleanup")

        # Check memory size (rough estimate)
        import sys
        total_size = sys.getsizeof(monitor._processes)
        for proc in all_procs:
            total_size += sys.getsizeof(proc)

        print(f"   Estimated memory: {total_size / 1024 / 1024:.2f} MB")

    async def test_unbounded_log_growth(self):
        """DESIGN FLAW: Logs grow unbounded per process"""
        print("\n=== Unbounded Log Growth ===")

        ProcessMonitor.reset_instance()

        await monitor.start_process("log_bomb", "training", 100000)

        # Add 100,000 log entries
        for i in range(100000):
            await monitor.update_progress("log_bomb", i/1000, f"Step {i}", i)

        process = await monitor.get_process("log_bomb")

        if len(process.logs) > 10000:
            print(f"⚠️ CRITICAL BUG: Process has {len(process.logs)} log entries!")
            print("   No log rotation/limiting in ProcessInfo.logs")
            print("   to_dict() limits to 100, but in-memory storage is unbounded")
            print("   Recommendation: Limit logs list to max 1000 entries")


class TestProcessIDCollisions:
    """Test for potential process ID collisions"""

    async def test_timestamp_collision_potential(self):
        """MEDIUM RISK: Timestamp-based IDs could collide"""
        print("\n=== Process ID Collision Risk ===")

        # From workflows: f"training_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        # Millisecond precision + 6 hex chars (24 bits)

        # Generate IDs rapidly
        ids = set()
        for i in range(10000):
            process_id = f"training_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
            ids.add(process_id)

        if len(ids) == 10000:
            print(f"✅ PASS: No collisions in {len(ids)} IDs")
        else:
            collisions = 10000 - len(ids)
            print(f"⚠️ WARNING: {collisions} collisions detected!")
            print(f"   Collision rate: {collisions/10000*100:.2f}%")

        # But in same millisecond, collision possible
        # 6 hex chars = 16^6 = 16.7M possibilities
        # Birthday paradox: ~50% collision at sqrt(16.7M) = ~4000 IDs/ms
        print(f"   UUID fragment entropy: 16^6 = {16**6:,} possibilities")
        print(f"   Safe concurrent ops/ms: ~{int((16**6)**0.5):,} before 50% collision risk")


class TestStateTransitionEdgeCases:
    """Edge cases in state transitions"""

    async def test_complete_then_fail(self):
        """Can we fail a completed process?"""
        print("\n=== Complete Then Fail ===")

        ProcessMonitor.reset_instance()

        await monitor.start_process("state_test_1", "training", 5)
        await monitor.complete_process("state_test_1", {"success": True})

        # Try to fail it
        try:
            await monitor.fail_process("state_test_1", "Late failure")
            # If this succeeds, state machine is broken
            process = await monitor.get_process("state_test_1")
            print(f"❌ BUG: Completed process changed to {process.status.value}")
            print(f"   No state transition validation!")
        except ValueError:
            print("✅ PASS: State transition blocked")

    async def test_update_after_completion(self):
        """Can we update a completed process?"""
        print("\n=== Update After Completion ===")

        ProcessMonitor.reset_instance()

        await monitor.start_process("state_test_2", "training", 5)
        await monitor.complete_process("state_test_2", {"success": True})

        # Try to update progress
        try:
            await monitor.update_progress("state_test_2", 50.0, "Late update", 3)
            # If this succeeds, state machine is broken
            process = await monitor.get_process("state_test_2")
            print(f"❌ BUG: Completed process progress updated!")
            print(f"   Progress: {process.metrics.progress_percent}%")
            print(f"   No state validation in update_progress()")
        except ValueError:
            print("✅ PASS: Update blocked")


class TestConcurrencyRaceConditions:
    """Deep concurrency testing"""

    async def test_simultaneous_complete_and_fail(self):
        """Race: Complete and Fail called simultaneously"""
        print("\n=== Simultaneous Complete and Fail ===")

        ProcessMonitor.reset_instance()

        await monitor.start_process("race_test_1", "training", 5)

        # Race them
        results = await asyncio.gather(
            monitor.complete_process("race_test_1", {"success": True}),
            monitor.fail_process("race_test_1", "Failure"),
            return_exceptions=True
        )

        # One should succeed, one might error (depends on lock)
        process = await monitor.get_process("race_test_1")

        print(f"   Final status: {process.status.value}")
        print(f"   Result: {process.result}")
        print(f"   Error: {process.error}")

        # Whichever won is fine, but state should be consistent
        if process.status == ProcessStatus.COMPLETED:
            if process.result is not None and process.error is None:
                print("✅ PASS: Complete won, state consistent")
            else:
                print("❌ BUG: Inconsistent state (completed but has error)")
        elif process.status == ProcessStatus.FAILED:
            if process.error is not None and process.result is None:
                print("✅ PASS: Fail won, state consistent")
            else:
                print("❌ BUG: Inconsistent state (failed but has result)")

    async def test_lock_contention_deadlock(self):
        """Can we deadlock the lock?"""
        print("\n=== Lock Contention Test ===")

        ProcessMonitor.reset_instance()

        # Create many processes
        for i in range(10):
            await monitor.start_process(f"lock_test_{i}", "training", 5)

        # Hammer with concurrent operations
        async def random_ops():
            import random
            for _ in range(100):
                i = random.randint(0, 9)
                process_id = f"lock_test_{i}"
                op = random.choice([
                    lambda: monitor.update_progress(process_id, random.random()*100, "test", 0),
                    lambda: monitor.get_process(process_id),
                ])
                await op()

        start = time.time()
        await asyncio.gather(*[random_ops() for _ in range(10)])
        elapsed = time.time() - start

        print(f"   Completed 10,000 ops in {elapsed:.3f}s")

        if elapsed < 5.0:
            print(f"✅ PASS: No deadlock ({10000/elapsed:.0f} ops/sec)")
        else:
            print(f"⚠️ WARNING: Slow ({10000/elapsed:.0f} ops/sec) - possible contention")


class TestInputValidation:
    """Test for missing input validation"""

    async def test_negative_progress(self):
        """Can we set negative progress?"""
        print("\n=== Negative Progress ===")

        ProcessMonitor.reset_instance()

        await monitor.start_process("val_test_1", "training", 5)
        await monitor.update_progress("val_test_1", -100.0, "Negative", 0)

        process = await monitor.get_process("val_test_1")

        if process.metrics.progress_percent < 0:
            print(f"❌ BUG: Negative progress allowed ({process.metrics.progress_percent}%)")
            print("   Missing validation in update_progress()")
        else:
            print("✅ PASS: Progress validated/clamped")

    async def test_progress_over_100(self):
        """Can we set progress > 100?"""
        print("\n=== Progress Over 100 ===")

        ProcessMonitor.reset_instance()

        await monitor.start_process("val_test_2", "training", 5)
        await monitor.update_progress("val_test_2", 500.0, "Over", 0)

        process = await monitor.get_process("val_test_2")

        if process.metrics.progress_percent > 100:
            print(f"⚠️ BUG: Progress over 100 allowed ({process.metrics.progress_percent}%)")
        else:
            print("✅ PASS: Progress clamped to 100")

    async def test_completed_steps_exceeds_total(self):
        """Can completed_steps exceed total_steps?"""
        print("\n=== Completed Steps > Total ===")

        ProcessMonitor.reset_instance()

        await monitor.start_process("val_test_3", "training", 5)
        with pytest.raises(ValueError):
            await monitor.update_progress("val_test_3", 50.0, "Over", completed_steps=100)

        process = await monitor.get_process("val_test_3")

        if process.metrics.completed_steps > process.metrics.total_steps:
            print(f"⚠️ BUG: completed_steps ({process.metrics.completed_steps}) > total_steps ({process.metrics.total_steps})")
        else:
            print("✅ PASS: Steps validated")

    async def test_empty_process_id(self):
        """Can we create process with empty ID?"""
        print("\n=== Empty Process ID ===")

        ProcessMonitor.reset_instance()

        try:
            await monitor.start_process("", "training", 5)
            print("⚠️ BUG: Empty process ID allowed")
        except (ValueError, KeyError):
            print("✅ PASS: Empty ID rejected")

    async def test_none_process_type(self):
        """Can we create process with None type?"""
        print("\n=== None Process Type ===")

        try:
            await monitor.start_process("test", None, 5)
            process = await monitor.get_process("test")
            if process.process_type is None:
                print("⚠️ BUG: None process_type allowed")
        except (ValueError, TypeError):
            print("✅ PASS: None type rejected")


# Run all edge case tests
async def run_edge_case_tests():
    print("=" * 80)
    print("PROCESSMONITOR EDGE CASES & RACE CONDITIONS")
    print("=" * 80)

    # Singleton edge cases
    suite1 = TestSingletonEdgeCases()
    suite1.test_singleton_across_threads()
    await suite1.test_singleton_race_condition_lock_init()
    await suite1.test_class_vs_instance_variables()

    # Memory leaks
    suite2 = TestMemoryLeaks()
    await suite2.test_no_cleanup_mechanism()
    await suite2.test_unbounded_log_growth()

    # Process ID collisions
    suite3 = TestProcessIDCollisions()
    await suite3.test_timestamp_collision_potential()

    # State transitions
    suite4 = TestStateTransitionEdgeCases()
    await suite4.test_complete_then_fail()
    await suite4.test_update_after_completion()

    # Concurrency
    suite5 = TestConcurrencyRaceConditions()
    await suite5.test_simultaneous_complete_and_fail()
    await suite5.test_lock_contention_deadlock()

    # Input validation
    suite6 = TestInputValidation()
    await suite6.test_negative_progress()
    await suite6.test_progress_over_100()
    await suite6.test_completed_steps_exceeds_total()
    await suite6.test_empty_process_id()
    await suite6.test_none_process_type()

    print("\n" + "=" * 80)
    print("EDGE CASE TESTS COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_edge_case_tests())
pytestmark = pytest.mark.asyncio
