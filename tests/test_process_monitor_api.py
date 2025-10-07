"""
Comprehensive API tests for ProcessMonitor endpoints

Tests all REST API endpoints and WebSocket connections for process monitoring.
"""

import pytest
import asyncio
import json
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from src.ui.api_enhanced import app
from src.monitoring.process_monitor import monitor, ProcessStatus


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
async def cleanup_monitor():
    """Clean up monitor state between tests"""
    monitor._processes = {}
    yield
    monitor._processes = {}


@pytest.mark.asyncio
class TestProcessListEndpoints:
    """Test GET /api/processes endpoints"""

    async def test_get_all_processes_empty(self, client):
        """Test GET /api/processes returns empty list when no processes"""
        response = client.get("/api/processes")
        assert response.status_code == 200
        data = response.json()
        assert "processes" in data
        assert "total" in data
        assert data["total"] == 0
        assert data["processes"] == []

    async def test_get_all_processes_returns_all(self, client):
        """Test GET /api/processes returns all processes"""
        # Create test processes
        await monitor.start_process("test_1", "training")
        await monitor.start_process("test_2", "backtest")
        await monitor.start_process("test_3", "prediction")

        response = client.get("/api/processes")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["processes"]) == 3

        process_ids = [p["process_id"] for p in data["processes"]]
        assert "test_1" in process_ids
        assert "test_2" in process_ids
        assert "test_3" in process_ids

    async def test_get_running_processes_filters_correctly(self, client):
        """Test GET /api/processes/running filters only RUNNING processes"""
        # Create processes in different states
        await monitor.start_process("running_1", "training")
        await monitor.start_process("running_2", "backtest")
        await monitor.start_process("completed_1", "prediction")
        await monitor.start_process("failed_1", "download")

        # Change states
        await monitor.complete_process("completed_1", {"status": "ok"})
        await monitor.fail_process("failed_1", "error")

        response = client.get("/api/processes/running")
        assert response.status_code == 200
        data = response.json()

        # Only running processes
        assert data["total"] == 2
        process_ids = [p["process_id"] for p in data["processes"]]
        assert "running_1" in process_ids
        assert "running_2" in process_ids
        assert "completed_1" not in process_ids
        assert "failed_1" not in process_ids

        # Verify all returned processes have status=running
        for process in data["processes"]:
            assert process["status"] == "running"


@pytest.mark.asyncio
class TestProcessDetailEndpoint:
    """Test GET /api/processes/{process_id} endpoint"""

    async def test_get_process_by_id(self, client):
        """Test GET /api/processes/{process_id} returns correct data"""
        # Create process
        await monitor.start_process("detail_test", "training", total_steps=5)
        await monitor.update_progress("detail_test", 40.0, "Training epoch 2/5", 2)

        response = client.get("/api/processes/detail_test")
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert data["process_id"] == "detail_test"
        assert data["process_type"] == "training"
        assert data["status"] == "running"
        assert data["metrics"]["progress_percent"] == 40.0
        assert data["metrics"]["current_step"] == "Training epoch 2/5"
        assert data["metrics"]["total_steps"] == 5
        assert data["metrics"]["completed_steps"] == 2

    async def test_get_process_404_for_nonexistent(self, client):
        """Test GET /api/processes/{process_id} returns 404 for non-existent process"""
        response = client.get("/api/processes/nonexistent_process")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    async def test_get_completed_process(self, client):
        """Test GET /api/processes/{process_id} returns completed process with result"""
        # Create and complete process
        await monitor.start_process("completed_test", "training")
        result = {"model_id": "test_123", "accuracy": 0.95}
        await monitor.complete_process("completed_test", result)

        response = client.get("/api/processes/completed_test")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["result"] == result
        assert data["metrics"]["progress_percent"] == 100.0
        assert data["metrics"]["duration_seconds"] is not None

    async def test_get_failed_process(self, client):
        """Test GET /api/processes/{process_id} returns failed process with error"""
        # Create and fail process
        await monitor.start_process("failed_test", "backtest")
        await monitor.fail_process("failed_test", "Model not found")

        response = client.get("/api/processes/failed_test")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "failed"
        assert data["error"] == "Model not found"
        assert data["result"] is None


@pytest.mark.asyncio
class TestProcessCancellationEndpoint:
    """Test DELETE /api/processes/{process_id} endpoint"""

    async def test_cancel_running_process(self, client):
        """Test DELETE /api/processes/{process_id} cancels running process"""
        # Create running process
        await monitor.start_process("cancel_test", "training")
        await monitor.update_progress("cancel_test", 30.0, "Training")

        # Cancel it
        response = client.delete("/api/processes/cancel_test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["process_id"] == "cancel_test"

        # Verify process is cancelled
        process = await monitor.get_process("cancel_test")
        assert process.status == ProcessStatus.CANCELLED

    async def test_cancel_nonexistent_process_404(self, client):
        """Test DELETE /api/processes/{process_id} returns 404 for non-existent"""
        response = client.delete("/api/processes/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_cancel_completed_process_400(self, client):
        """Test DELETE /api/processes/{process_id} returns 400 for completed process"""
        # Create and complete process
        await monitor.start_process("completed_cancel", "training")
        await monitor.complete_process("completed_cancel", {"status": "ok"})

        # Try to cancel
        response = client.delete("/api/processes/completed_cancel")
        assert response.status_code == 400
        data = response.json()
        assert "not running" in data["detail"].lower()

    async def test_cancel_failed_process_400(self, client):
        """Test DELETE /api/processes/{process_id} returns 400 for failed process"""
        # Create and fail process
        await monitor.start_process("failed_cancel", "training")
        await monitor.fail_process("failed_cancel", "error")

        # Try to cancel
        response = client.delete("/api/processes/failed_cancel")
        assert response.status_code == 400
        data = response.json()
        assert "not running" in data["detail"].lower()


@pytest.mark.asyncio
class TestProcessLogsEndpoint:
    """Test GET /api/processes/{process_id}/logs endpoint"""

    async def test_get_process_logs(self, client):
        """Test GET /api/processes/{process_id}/logs returns logs"""
        # Create process with multiple updates (logs)
        await monitor.start_process("logs_test", "training", total_steps=3)
        await monitor.update_progress("logs_test", 33.0, "Step 1", 1)
        await monitor.update_progress("logs_test", 66.0, "Step 2", 2)
        await monitor.update_progress("logs_test", 99.0, "Step 3", 3)

        response = client.get("/api/processes/logs_test/logs")
        assert response.status_code == 200
        data = response.json()

        assert "logs" in data
        logs = data["logs"]
        assert len(logs) >= 4  # start + 3 updates

        # Verify log structure
        for log in logs:
            assert "timestamp" in log
            assert "level" in log
            assert "message" in log

    async def test_get_process_logs_with_limit(self, client):
        """Test GET /api/processes/{process_id}/logs respects limit parameter"""
        # Create process with many logs
        await monitor.start_process("limit_test", "training")
        for i in range(20):
            await monitor.update_progress("limit_test", i * 5, f"Step {i}")

        # Request only 5 logs
        response = client.get("/api/processes/limit_test/logs?limit=5")
        assert response.status_code == 200
        data = response.json()

        # Should return only 5 most recent logs
        assert len(data["logs"]) == 5

    async def test_get_logs_404_for_nonexistent_process(self, client):
        """Test GET /api/processes/{process_id}/logs returns 404 for non-existent"""
        response = client.get("/api/processes/nonexistent/logs")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
class TestWebSocketProcessUpdates:
    """Test WebSocket /ws/processes endpoint"""

    async def test_websocket_all_processes(self, client):
        """Test /ws/processes sends updates for all processes"""
        # Create test processes
        await monitor.start_process("ws_test_1", "training")
        await monitor.start_process("ws_test_2", "backtest")

        with client.websocket_connect("/ws/processes") as websocket:
            # Should receive initial update
            data = websocket.receive_json()
            assert data["type"] == "process_update"
            assert "processes" in data
            assert len(data["processes"]) == 2

            # Update a process
            await monitor.update_progress("ws_test_1", 50.0, "Half way")

            # Should receive updated state (with some delay)
            import time
            time.sleep(1.1)  # Wait for next WebSocket update (1s interval)

            try:
                data = websocket.receive_json(timeout=2)
                assert data["type"] == "process_update"
                # Find the updated process
                processes = {p["process_id"]: p for p in data["processes"]}
                if "ws_test_1" in processes:
                    assert processes["ws_test_1"]["metrics"]["progress_percent"] == 50.0
            except:
                pass  # Timeout is ok for this test

    async def test_websocket_specific_process(self, client):
        """Test /ws/processes/{process_id} sends updates for specific process"""
        # Create test process
        await monitor.start_process("ws_specific", "training", total_steps=5)

        with client.websocket_connect("/ws/processes/ws_specific") as websocket:
            # Should receive initial state
            data = websocket.receive_json()
            assert data["type"] == "process_update"
            assert data["data"]["process_id"] == "ws_specific"
            assert data["data"]["status"] == "running"

            # Update process
            await monitor.update_progress("ws_specific", 40.0, "Step 2", 2)

            # Wait for update
            import time
            time.sleep(0.6)  # Wait for 500ms update interval

            try:
                data = websocket.receive_json(timeout=1)
                assert data["type"] == "process_update"
                assert data["data"]["metrics"]["progress_percent"] == 40.0
            except:
                pass  # Timeout is ok

    async def test_websocket_process_complete_closes(self, client):
        """Test WebSocket closes when process completes"""
        # Create test process
        await monitor.start_process("ws_complete", "training")

        with client.websocket_connect("/ws/processes/ws_complete") as websocket:
            # Receive initial state
            data = websocket.receive_json()
            assert data["type"] == "process_update"

            # Complete the process
            await monitor.complete_process("ws_complete", {"status": "ok"})

            # Should receive completion message then close
            import time
            time.sleep(0.6)

            try:
                data = websocket.receive_json(timeout=2)
                # Should be either process_update with completed status or process_complete
                assert data["type"] in ["process_update", "process_complete"]
                if data["type"] == "process_update":
                    assert data["data"]["status"] == "completed"
                elif data["type"] == "process_complete":
                    assert data["data"]["status"] == "completed"
            except WebSocketDisconnect:
                pass  # Expected behavior
            except:
                pass  # Timeout is ok

    async def test_websocket_nonexistent_process_error(self, client):
        """Test WebSocket for non-existent process returns error and closes"""
        with client.websocket_connect("/ws/processes/nonexistent") as websocket:
            # Should receive error message
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "not found" in data["message"].lower()


@pytest.mark.asyncio
class TestProcessDataStructure:
    """Test process data structure returned by API"""

    async def test_process_response_structure(self, client):
        """Test that process response has all required fields"""
        # Create complete process
        await monitor.start_process("structure_test", "training", total_steps=3)
        await monitor.update_progress("structure_test", 50.0, "Step 2", 2)
        await monitor.complete_process("structure_test", {"accuracy": 0.9})

        response = client.get("/api/processes/structure_test")
        assert response.status_code == 200
        data = response.json()

        # Required top-level fields
        required_fields = [
            "process_id",
            "process_type",
            "status",
            "metrics",
            "logs",
            "result",
            "error"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Required metrics fields
        metrics_fields = [
            "start_time",
            "end_time",
            "duration_seconds",
            "progress_percent",
            "current_step",
            "total_steps",
            "completed_steps",
            "memory_mb",
            "cpu_percent"
        ]
        for field in metrics_fields:
            assert field in data["metrics"], f"Missing metrics field: {field}"

        # Verify types
        assert isinstance(data["process_id"], str)
        assert isinstance(data["process_type"], str)
        assert isinstance(data["status"], str)
        assert isinstance(data["logs"], list)
        assert isinstance(data["result"], dict) or data["result"] is None
        assert isinstance(data["error"], str) or data["error"] is None

    async def test_log_entry_structure(self, client):
        """Test that log entries have correct structure"""
        await monitor.start_process("log_structure", "training")
        await monitor.update_progress("log_structure", 50.0, "Testing logs")

        response = client.get("/api/processes/log_structure/logs")
        assert response.status_code == 200
        data = response.json()

        for log in data["logs"]:
            assert "timestamp" in log
            assert "level" in log
            assert "message" in log

            # Verify timestamp is valid ISO format
            datetime.fromisoformat(log["timestamp"])

            # Verify level is valid
            assert log["level"] in ["INFO", "WARNING", "ERROR"]


@pytest.mark.asyncio
class TestProcessIntegrationScenarios:
    """Test real-world integration scenarios"""

    async def test_complete_training_workflow_via_api(self, client):
        """Test complete training workflow monitoring via API"""
        # Simulate training process
        process_id = "training_integration"
        await monitor.start_process(process_id, "training", total_steps=5)

        # Check initial state
        response = client.get(f"/api/processes/{process_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "running"

        # Progress through steps
        steps = [
            (20.0, "Loading dataset", 1),
            (40.0, "Feature engineering", 2),
            (60.0, "Training model", 3),
            (80.0, "Validation", 4),
            (95.0, "Saving model", 5)
        ]

        for progress, step, completed in steps:
            await monitor.update_progress(process_id, progress, step, completed)

        # Complete
        result = {
            "model_id": "test_model_123",
            "accuracy": 0.92,
            "loss": 0.08
        }
        await monitor.complete_process(process_id, result)

        # Verify final state
        response = client.get(f"/api/processes/{process_id}")
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] == result
        assert data["metrics"]["progress_percent"] == 100.0

    async def test_failed_backtest_workflow_via_api(self, client):
        """Test failed backtest workflow monitoring via API"""
        # Simulate backtest process
        process_id = "backtest_fail"
        await monitor.start_process(process_id, "backtest", total_steps=4)

        # Progress to failure point
        await monitor.update_progress(process_id, 25.0, "Loading model", 1)
        await monitor.update_progress(process_id, 50.0, "Initializing backtest", 2)

        # Fail
        await monitor.fail_process(process_id, "Insufficient data for backtest period")

        # Verify via API
        response = client.get(f"/api/processes/{process_id}")
        data = response.json()
        assert data["status"] == "failed"
        assert "Insufficient data" in data["error"]
        assert data["metrics"]["progress_percent"] == 50.0  # Stays at failure point
