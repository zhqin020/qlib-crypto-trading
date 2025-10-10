"""
Test UX improvements: User-friendly Process IDs and ETA calculation
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.monitoring.process_monitor import ProcessMonitor, ProcessStatus


class TestProcessIDGeneration:
    """Test user-friendly process ID generation"""

    @pytest.fixture
    def monitor(self):
        """Create fresh monitor for each test"""
        monitor = ProcessMonitor()
        # Reset counter to ensure consistent test results
        monitor._process_counter = 0
        return monitor

    def test_display_id_format(self, monitor):
        """Test display ID follows 'Type #N' format"""
        display_id = monitor._generate_display_id("training")
        assert display_id == "Training #1"
        assert display_id.startswith("Training #")

    def test_display_id_increments(self, monitor):
        """Test counter increments for each process"""
        id1 = monitor._generate_display_id("training")
        id2 = monitor._generate_display_id("training")
        id3 = monitor._generate_display_id("backtest")

        assert id1 == "Training #1"
        assert id2 == "Training #2"
        assert id3 == "Backtest #3"

    def test_display_id_capitalizes(self, monitor):
        """Test process type is capitalized"""
        assert monitor._generate_display_id("training") == "Training #1"
        assert monitor._generate_display_id("backtest") == "Backtest #2"
        assert monitor._generate_display_id("prediction") == "Prediction #3"
        assert monitor._generate_display_id("download") == "Download #4"

    @pytest.mark.asyncio
    async def test_start_process_includes_display_id(self, monitor):
        """Test that start_process generates and includes display_id"""
        process = await monitor.start_process(
            process_id="test_123",
            process_type="training",
            total_steps=5
        )

        assert process.display_id == "Training #1"
        assert process.display_id != ""
        assert process.process_id == "test_123"

    @pytest.mark.asyncio
    async def test_display_id_in_serialization(self, monitor):
        """Test display_id is included in to_dict()"""
        process = await monitor.start_process(
            process_id="test_456",
            process_type="backtest"
        )

        process_dict = process.to_dict()
        assert "display_id" in process_dict
        assert process_dict["display_id"] == "Backtest #1"


class TestETACalculation:
    """Test estimated time to completion calculation"""

    @pytest.fixture
    def monitor(self):
        return ProcessMonitor()

    def test_eta_at_50_percent(self, monitor):
        """Test ETA calculation at 50% progress"""
        # Process started 10 seconds ago, now at 50%
        start_time = (datetime.now() - timedelta(seconds=10)).isoformat()
        eta_ts, eta_sec = monitor._calculate_eta(start_time, 50.0)

        assert eta_sec is not None
        assert 8 <= eta_sec <= 12  # Should be around 10 seconds remaining (±2s for test execution time)

    def test_eta_at_25_percent(self, monitor):
        """Test ETA calculation at 25% progress"""
        # Process started 10 seconds ago, now at 25%
        start_time = (datetime.now() - timedelta(seconds=10)).isoformat()
        eta_ts, eta_sec = monitor._calculate_eta(start_time, 25.0)

        assert eta_sec is not None
        # Total time = 10s / 0.25 = 40s, remaining = 40s - 10s = 30s
        assert 28 <= eta_sec <= 32

    def test_eta_not_calculated_below_threshold(self, monitor):
        """Test ETA not calculated when progress < 5%"""
        start_time = datetime.now().isoformat()

        # Progress too low
        eta_ts, eta_sec = monitor._calculate_eta(start_time, 0.0)
        assert eta_sec is None

        eta_ts, eta_sec = monitor._calculate_eta(start_time, 4.9)
        assert eta_sec is None

        # Just above threshold should calculate
        start_time = (datetime.now() - timedelta(seconds=1)).isoformat()
        eta_ts, eta_sec = monitor._calculate_eta(start_time, 5.0)
        assert eta_sec is not None

    def test_eta_not_calculated_when_complete(self, monitor):
        """Test ETA not calculated when progress >= 100%"""
        start_time = datetime.now().isoformat()

        eta_ts, eta_sec = monitor._calculate_eta(start_time, 100.0)
        assert eta_sec is None

        eta_ts, eta_sec = monitor._calculate_eta(start_time, 99.9)
        assert eta_sec is not None  # Should still calculate

    def test_eta_timestamp_format(self, monitor):
        """Test ETA timestamp is valid ISO format"""
        start_time = (datetime.now() - timedelta(seconds=10)).isoformat()
        eta_ts, eta_sec = monitor._calculate_eta(start_time, 50.0)

        assert eta_ts is not None
        # Should be parseable as datetime
        parsed = datetime.fromisoformat(eta_ts)
        assert parsed > datetime.now()  # Should be in the future

    def test_eta_handles_edge_cases(self, monitor):
        """Test ETA handles edge cases gracefully"""
        # Invalid start time
        eta_ts, eta_sec = monitor._calculate_eta("invalid", 50.0)
        assert eta_sec is None

        # Zero progress (division by zero)
        start_time = datetime.now().isoformat()
        eta_ts, eta_sec = monitor._calculate_eta(start_time, 0.0)
        assert eta_sec is None

        # Extremely long ETA (> 7 days) should return None
        start_time = (datetime.now() - timedelta(days=1)).isoformat()
        eta_ts, eta_sec = monitor._calculate_eta(start_time, 0.1)
        assert eta_sec is None  # Would be > 7 days

    @pytest.mark.asyncio
    async def test_eta_updated_on_progress(self, monitor):
        """Test ETA is calculated and updated on progress updates"""
        process = await monitor.start_process(
            process_id="test_eta",
            process_type="training"
        )

        # Initially no ETA (progress = 0%)
        assert process.metrics.estimated_seconds_remaining is None

        # Wait a moment then update progress
        await asyncio.sleep(0.1)
        await monitor.update_progress(
            process_id="test_eta",
            progress_percent=10.0,
            current_step="Step 1"
        )

        # Should have ETA now
        process = await monitor.get_process("test_eta")
        assert process.metrics.estimated_seconds_remaining is not None
        assert process.metrics.estimated_completion is not None

        # ETA should be positive
        assert process.metrics.estimated_seconds_remaining > 0

    @pytest.mark.asyncio
    async def test_eta_in_serialization(self, monitor):
        """Test ETA fields are included in to_dict()"""
        process = await monitor.start_process(
            process_id="test_serialize",
            process_type="training"
        )

        await asyncio.sleep(0.1)
        await monitor.update_progress(
            process_id="test_serialize",
            progress_percent=10.0,
            current_step="Step 1"
        )

        process_dict = process.to_dict()
        metrics = process_dict["metrics"]

        assert "estimated_completion" in metrics
        assert "estimated_seconds_remaining" in metrics
        assert metrics["estimated_seconds_remaining"] is not None


class TestFullWorkflow:
    """Test complete UX improvements workflow"""

    @pytest.fixture
    def monitor(self):
        monitor = ProcessMonitor()
        monitor._process_counter = 0
        return monitor

    @pytest.mark.asyncio
    async def test_complete_process_lifecycle(self, monitor):
        """Test full process lifecycle with both improvements"""
        # Start process
        process = await monitor.start_process(
            process_id="workflow_test",
            process_type="training",
            total_steps=10
        )

        # Verify display ID
        assert process.display_id == "Training #1"

        # Update progress and check ETA
        await asyncio.sleep(0.1)
        await monitor.update_progress(
            process_id="workflow_test",
            progress_percent=20.0,
            current_step="Step 2",
            completed_steps=2
        )

        process = await monitor.get_process("workflow_test")
        assert process.metrics.estimated_seconds_remaining is not None

        # Serialize and verify all fields
        process_dict = process.to_dict()
        assert process_dict["display_id"] == "Training #1"
        assert process_dict["metrics"]["estimated_seconds_remaining"] is not None
        assert process_dict["metrics"]["estimated_completion"] is not None

        # Complete process
        await monitor.complete_process(
            process_id="workflow_test",
            result={"accuracy": 0.95}
        )

        process = await monitor.get_process("workflow_test")
        assert process.status == ProcessStatus.COMPLETED
        assert process.metrics.progress_percent == 100.0

    @pytest.mark.asyncio
    async def test_multiple_processes_unique_ids(self, monitor):
        """Test multiple concurrent processes get unique display IDs"""
        processes = []
        for i in range(5):
            process = await monitor.start_process(
                process_id=f"process_{i}",
                process_type="training" if i % 2 == 0 else "backtest"
            )
            processes.append(process)

        # Verify unique IDs
        display_ids = [p.display_id for p in processes]
        assert len(display_ids) == len(set(display_ids))  # All unique

        # Verify format
        assert display_ids[0] == "Training #1"
        assert display_ids[1] == "Backtest #2"
        assert display_ids[2] == "Training #3"
        assert display_ids[3] == "Backtest #4"
        assert display_ids[4] == "Training #5"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
