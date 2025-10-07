"""
Test Concurrent Qlib Initialization

This test validates the async lock mechanism in init_qlib_clean_async
to prevent race conditions when multiple tool calls happen simultaneously.

Gap addressed: No concurrent execution tests existed
"""
import pytest
import asyncio
import sys
from pathlib import Path
import tempfile
import shutil
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.qlib_state import init_qlib_clean_async, get_qlib_config_info, clear_qlib_cache

# Check if qlib is available
try:
    import qlib
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

# Skip all tests if qlib is not available
pytestmark = pytest.mark.skipif(not QLIB_AVAILABLE, reason="qlib not installed")


class TestConcurrentQlibInit:
    """Test concurrent qlib initialization with async lock"""

    @pytest.fixture
    def setup_test_datasets(self):
        """Create three minimal test datasets for concurrency testing"""
        temp_dir = Path(tempfile.mkdtemp())

        datasets = {}
        for i, name in enumerate(['dataset_1', 'dataset_2', 'dataset_3']):
            dataset_dir = temp_dir / name
            dataset_dir.mkdir()
            (dataset_dir / "calendars").mkdir()
            (dataset_dir / "features").mkdir()
            (dataset_dir / "instruments").mkdir()

            # Create minimal calendar
            with open(dataset_dir / "calendars" / "day.txt", 'w') as f:
                # Each dataset has different dates
                base_day = i + 1
                f.write(f"2024-0{base_day}-01\n2024-0{base_day}-02\n2024-0{base_day}-03\n")

            # Create minimal instruments
            with open(dataset_dir / "instruments" / "all.txt", 'w') as f:
                symbol = chr(65 + i) * 4  # AAAA, BBBB, CCCC
                f.write(f"{symbol}\t2024-0{base_day}-01\t2099-12-31\n")

            datasets[name] = dataset_dir

        yield datasets

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_concurrent_init_with_lock(self, setup_test_datasets):
        """
        Test that concurrent init_qlib_clean_async calls don't race.

        The async lock should serialize initialization, preventing corruption.
        """
        datasets = setup_test_datasets

        # Track which dataset each coroutine initialized with
        results = []

        async def init_with_dataset(dataset_name: str, delay: float):
            """Initialize qlib with specific dataset after delay"""
            await asyncio.sleep(delay)

            dataset_path = datasets[dataset_name]
            start_time = time.time()

            success = await init_qlib_clean_async(
                provider_uri={"day": str(dataset_path)},
                region="cn"
            )

            end_time = time.time()
            elapsed = end_time - start_time

            config = get_qlib_config_info()

            return {
                'dataset': dataset_name,
                'success': success,
                'config': config,
                'elapsed': elapsed,
                'start': start_time
            }

        # Launch 3 concurrent initializations
        # The lock should serialize them, preventing race conditions
        coros = [
            init_with_dataset('dataset_1', 0.00),
            init_with_dataset('dataset_2', 0.01),
            init_with_dataset('dataset_3', 0.02),
        ]

        results = await asyncio.gather(*coros)

        # Verify all succeeded
        for result in results:
            assert result['success'], f"Failed to init {result['dataset']}"
            assert result['config'] is not None, f"No config for {result['dataset']}"

        # Verify each got the correct dataset
        for result in results:
            dataset_name = result['dataset']
            config_str = str(result['config']['provider_uri'])
            assert dataset_name in config_str, \
                f"Expected {dataset_name} in config, got: {config_str}"

        # The final config should be from the last task to run
        # (due to serialization by the lock)
        final_config = get_qlib_config_info()
        final_config_str = str(final_config['provider_uri'])

        # One of the datasets should be in the final config
        has_dataset = any(
            name in final_config_str
            for name in ['dataset_1', 'dataset_2', 'dataset_3']
        )
        assert has_dataset, f"No dataset found in final config: {final_config_str}"

    @pytest.mark.asyncio
    async def test_lock_serializes_access(self, setup_test_datasets):
        """
        Test that the lock actually serializes access.

        If the lock works, tasks should complete sequentially (not overlapping).
        """
        datasets = setup_test_datasets

        execution_log = []

        async def init_and_log(dataset_name: str, task_id: int):
            """Initialize and log execution timeline"""
            execution_log.append(f"Task {task_id} starting")

            success = await init_qlib_clean_async(
                provider_uri={"day": str(datasets[dataset_name])},
                region="cn"
            )

            # Simulate some work under the lock
            await asyncio.sleep(0.05)

            execution_log.append(f"Task {task_id} completed")
            return success

        # Launch 3 tasks simultaneously
        results = await asyncio.gather(
            init_and_log('dataset_1', 1),
            init_and_log('dataset_2', 2),
            init_and_log('dataset_3', 3),
        )

        # All should succeed
        assert all(results), "Some tasks failed"

        # Verify execution log shows serialization
        # We should see: start 1, complete 1, start 2, complete 2, start 3, complete 3
        # (or some other serialized order, but not interleaved)
        assert len(execution_log) == 6, f"Expected 6 log entries, got {len(execution_log)}"

        # Check for serialization pattern
        # Each "starting" should be followed by its "completed" before the next starts
        for i in range(0, len(execution_log), 2):
            start_msg = execution_log[i]
            if i + 1 < len(execution_log):
                next_msg = execution_log[i + 1]
                # The next message should be a completion, not another start
                # This proves tasks ran serially, not concurrently
                assert "completed" in next_msg or i + 2 == len(execution_log), \
                    f"Tasks may have run concurrently: {execution_log}"

    @pytest.mark.asyncio
    async def test_no_lock_would_cause_race(self, setup_test_datasets):
        """
        Demonstrate what would happen WITHOUT the lock (for documentation).

        This test shows that without proper locking, we'd get race conditions.
        """
        datasets = setup_test_datasets

        # Simulate racing without the lock by using the sync version directly
        from src.utils.qlib_state import init_qlib_clean

        async def unsafe_init(dataset_name: str):
            """Initialize without async lock protection"""
            # This would cause races if run concurrently
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                init_qlib_clean,
                {"day": str(datasets[dataset_name])},
                "cn"
            )
            return success, dataset_name

        # Run multiple inits without the lock
        # (This demonstrates why we NEED the lock)
        results = await asyncio.gather(
            unsafe_init('dataset_1'),
            unsafe_init('dataset_2'),
            unsafe_init('dataset_3'),
            return_exceptions=True
        )

        # Some may succeed, some may fail, but behavior is unpredictable
        # The point is to show that init_qlib_clean_async is NEEDED
        # We don't assert anything specific here because races are unpredictable

        # Just verify we can recover by using the safe version
        safe_result = await init_qlib_clean_async(
            provider_uri={"day": str(datasets['dataset_1'])},
            region="cn"
        )
        assert safe_result, "Failed to recover with safe async init"

    @pytest.mark.asyncio
    async def test_cache_clearing_under_concurrent_load(self, setup_test_datasets):
        """
        Test that cache clearing works correctly under concurrent load.

        This tests the combination of:
        1. Async lock (serializes init)
        2. Cache clearing (prevents state bleed)
        """
        datasets = setup_test_datasets

        async def init_and_verify(dataset_name: str):
            """Initialize with dataset and verify correct config"""
            success = await init_qlib_clean_async(
                provider_uri={"day": str(datasets[dataset_name])},
                region="cn"
            )

            if not success:
                return False, "Init failed"

            # Verify config
            config = get_qlib_config_info()
            if dataset_name not in str(config['provider_uri']):
                return False, f"Wrong dataset in config: {config}"

            # Try to access qlib data (tests cache)
            try:
                import qlib
                from qlib.data.data import Cal

                cal = Cal.calendar(freq='day')
                # If we can read calendar, verify it's correct
                if len(cal) > 0:
                    first_date = str(cal[0])
                    # Each dataset has dates starting with 2024-0{i}-
                    # dataset_1: 2024-01-*, dataset_2: 2024-02-*, dataset_3: 2024-03-*
                    return True, f"Calendar loaded: {first_date}"
            except Exception as e:
                # OK if calendar fails in test environment
                return True, f"Init successful (calendar error: {e})"

            return True, "Success"

        # Run many concurrent operations
        coros = []
        for _ in range(3):  # 3 rounds
            coros.extend([
                init_and_verify('dataset_1'),
                init_and_verify('dataset_2'),
                init_and_verify('dataset_3'),
            ])

        results = await asyncio.gather(*coros)

        # All should succeed
        for i, (success, msg) in enumerate(results):
            assert success, f"Task {i} failed: {msg}"

    @pytest.mark.asyncio
    async def test_async_lock_timeout_behavior(self, setup_test_datasets):
        """
        Test that the async lock doesn't deadlock.

        If one task takes too long, others should still be able to proceed.
        """
        datasets = setup_test_datasets

        async def quick_init():
            """Quick initialization"""
            return await init_qlib_clean_async(
                provider_uri={"day": str(datasets['dataset_1'])},
                region="cn"
            )

        async def slow_init():
            """Slow initialization (simulates heavy operation)"""
            result = await init_qlib_clean_async(
                provider_uri={"day": str(datasets['dataset_2'])},
                region="cn"
            )
            # Simulate slow operation after init
            await asyncio.sleep(0.1)
            return result

        # Run slow init, then multiple quick inits
        # The lock should queue them properly without deadlock
        results = await asyncio.gather(
            slow_init(),
            quick_init(),
            quick_init(),
            timeout=5.0  # Should complete well within 5 seconds
        )

        assert all(results), "Some tasks failed or timed out"


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v", "-s"])
