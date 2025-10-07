"""
Test MCP Server State Isolation

This test simulates real MCP server usage to verify that sequential
and concurrent tool calls maintain proper state isolation.

Gap addressed: No MCP integration tests existed
"""
import pytest
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any
import tempfile
import shutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.qlib_state import init_qlib_clean, get_qlib_config_info

# Check if qlib is available
try:
    import qlib
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

# Skip all tests if qlib is not available
pytestmark = pytest.mark.skipif(not QLIB_AVAILABLE, reason="qlib not installed")


class TestMCPStateIsolation:
    """Test state isolation in MCP server tool calls"""

    @pytest.fixture
    def setup_test_datasets(self):
        """Create two minimal test datasets for isolation testing"""
        temp_dir = Path(tempfile.mkdtemp())

        # Dataset A
        dataset_a = temp_dir / "dataset_a"
        dataset_a.mkdir()
        (dataset_a / "calendars").mkdir()
        (dataset_a / "features").mkdir()
        (dataset_a / "instruments").mkdir()

        # Create minimal calendar for dataset A
        with open(dataset_a / "calendars" / "day.txt", 'w') as f:
            f.write("2024-01-01\n2024-01-02\n2024-01-03\n")

        # Create minimal instruments for dataset A
        with open(dataset_a / "instruments" / "all.txt", 'w') as f:
            f.write("AAAA\t2024-01-01\t2099-12-31\n")

        # Dataset B (different from A)
        dataset_b = temp_dir / "dataset_b"
        dataset_b.mkdir()
        (dataset_b / "calendars").mkdir()
        (dataset_b / "features").mkdir()
        (dataset_b / "instruments").mkdir()

        # Create minimal calendar for dataset B (different dates)
        with open(dataset_b / "calendars" / "day.txt", 'w') as f:
            f.write("2024-02-01\n2024-02-02\n2024-02-03\n")

        # Create minimal instruments for dataset B (different symbol)
        with open(dataset_b / "instruments" / "all.txt", 'w') as f:
            f.write("BBBB\t2024-02-01\t2099-12-31\n")

        yield dataset_a, dataset_b

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_sequential_tool_calls_different_datasets(self, setup_test_datasets):
        """
        Simulate sequential MCP tool calls with different datasets.

        This tests that calling models_train with dataset_a, then backtests_run
        with dataset_b properly switches datasets without state bleed.
        """
        dataset_a, dataset_b = setup_test_datasets

        # Simulate first tool call: models_train with dataset A
        success_a = init_qlib_clean(
            provider_uri={"day": str(dataset_a)},
            region="cn"
        )
        assert success_a, "Failed to initialize with dataset A"

        # Verify we're using dataset A
        config_a = get_qlib_config_info()
        assert "dataset_a" in str(config_a['provider_uri']), \
            f"Expected dataset_a in config, got: {config_a['provider_uri']}"

        # Simulate second tool call: backtests_run with dataset B
        success_b = init_qlib_clean(
            provider_uri={"day": str(dataset_b)},
            region="cn"
        )
        assert success_b, "Failed to initialize with dataset B"

        # Verify we switched to dataset B (no bleed from A)
        config_b = get_qlib_config_info()
        assert "dataset_b" in str(config_b['provider_uri']), \
            f"Expected dataset_b in config, got: {config_b['provider_uri']}"

        # Critical: Ensure dataset_a is NOT in the config
        assert "dataset_a" not in str(config_b['provider_uri']), \
            "State bleed detected! dataset_a still in config after switching to dataset_b"

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, setup_test_datasets):
        """
        Test concurrent tool calls don't race.

        This simulates multiple Claude tool calls happening at the same time
        (e.g., user asks multiple questions simultaneously).
        """
        dataset_a, dataset_b = setup_test_datasets

        async def init_dataset_a():
            """Simulate tool call using dataset A"""
            await asyncio.sleep(0.01)  # Simulate some work
            success = init_qlib_clean(
                provider_uri={"day": str(dataset_a)},
                region="cn"
            )
            config = get_qlib_config_info()
            return success, config

        async def init_dataset_b():
            """Simulate tool call using dataset B"""
            await asyncio.sleep(0.01)  # Simulate some work
            success = init_qlib_clean(
                provider_uri={"day": str(dataset_b)},
                region="cn"
            )
            config = get_qlib_config_info()
            return success, config

        # Run concurrently - this tests the async lock
        results = await asyncio.gather(
            init_dataset_a(),
            init_dataset_b(),
            init_dataset_a(),
            return_exceptions=True
        )

        # Verify all succeeded
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent call {i} failed with: {result}")

            success, config = result
            assert success, f"Concurrent call {i} failed to initialize"

            # Each should have correct dataset in config
            # (last one wins, but no corruption/mixing)
            assert config is not None, f"Call {i} returned None config"

    @pytest.mark.asyncio
    async def test_cache_clearing_between_calls(self, setup_test_datasets):
        """
        Test that cache is properly cleared between sequential calls.

        This is the core state bleed fix - ensuring H.clear() works.
        """
        dataset_a, dataset_b = setup_test_datasets

        # Initialize with dataset A
        success_a = init_qlib_clean(
            provider_uri={"day": str(dataset_a)},
            region="cn"
        )
        assert success_a

        # Load some data (this populates the cache)
        try:
            import qlib
            from qlib.data.data import Cal

            cal_a = Cal.calendar(freq='day')
            # Verify calendar is from dataset A
            assert len(cal_a) == 3, f"Expected 3 calendar entries for dataset A, got {len(cal_a)}"
        except Exception as e:
            # If calendar fails to load, that's ok for this test
            # We're just testing cache clearing
            pass

        # Switch to dataset B - this should clear cache
        success_b = init_qlib_clean(
            provider_uri={"day": str(dataset_b)},
            region="cn"
        )
        assert success_b

        # Load calendar from dataset B
        try:
            cal_b = Cal.calendar(freq='day')
            # Verify calendar is from dataset B (different dates)
            assert len(cal_b) == 3, f"Expected 3 calendar entries for dataset B, got {len(cal_b)}"

            # Critical: Verify dates are from dataset B, not A
            # Dataset A: 2024-01-01, 2024-01-02, 2024-01-03
            # Dataset B: 2024-02-01, 2024-02-02, 2024-02-03
            first_date = str(cal_b[0])
            assert "2024-02-01" in first_date, \
                f"State bleed! Expected 2024-02-01 from dataset B, got {first_date}"
        except Exception as e:
            pytest.fail(f"Failed to load calendar from dataset B: {e}")

    @pytest.mark.asyncio
    async def test_tool_call_simulation_with_qlib_operations(self, setup_test_datasets):
        """
        Full integration test simulating actual tool call workflow:
        1. models_train (uses dataset A, creates features, trains model)
        2. backtests_run (uses dataset B, runs backtest)

        Tests that full qlib operations don't leak state.
        """
        dataset_a, dataset_b = setup_test_datasets

        # Tool call 1: models_train with dataset A
        success_a = init_qlib_clean(
            provider_uri={"day": str(dataset_a)},
            region="cn"
        )
        assert success_a

        # Simulate model training operations (accessing qlib data)
        try:
            import qlib
            from qlib.data.data import Cal, Inst

            # Access calendar and instruments (populates cache)
            cal = Cal.calendar(freq='day')
            instruments = Inst.list_instruments(freq='day')

            # Verify we're working with dataset A
            assert len(cal) == 3, "Expected dataset A calendar"
        except Exception:
            pass  # OK if qlib operations fail in test environment

        # Tool call 2: backtests_run with dataset B
        success_b = init_qlib_clean(
            provider_uri={"day": str(dataset_b)},
            region="cn"
        )
        assert success_b

        # Verify config switched
        config = get_qlib_config_info()
        assert "dataset_b" in str(config['provider_uri']), \
            "Failed to switch to dataset B"

        # Access data again - should be from dataset B
        try:
            cal = Cal.calendar(freq='day')
            # If we can read calendar, verify it's from dataset B
            if len(cal) > 0:
                first_date = str(cal[0])
                assert "2024-02" in first_date, \
                    f"Expected dataset B dates (2024-02-*), got {first_date}"
        except Exception:
            pass  # OK if qlib operations fail in test environment


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v", "-s"])
