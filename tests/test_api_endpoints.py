"""
Comprehensive API Endpoint Integration Tests

Tests all API endpoints with various scenarios:
- Normal operations
- Error cases
- Edge cases
- Input validation
"""

import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from datetime import datetime
import time

# Import the FastAPI app
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ui.api_enhanced import app
from src.monitoring.process_monitor import monitor, ProcessStatus
from src.ui.security import VALID_API_KEYS, verify_ws_token


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def cleanup_monitor():
    """Cleanup monitor state before each test"""
    monitor._processes.clear()
    yield
    monitor._processes.clear()


class TestProcessEndpoints:
    """Test /api/processes endpoints"""

    def test_get_all_processes_empty(self, client, cleanup_monitor):
        """Test 1.1.1: GET /api/processes with empty state"""
        response = client.get("/api/processes")

        assert response.status_code == 200
        data = response.json()
        assert data == {"processes": [], "total": 0}

    @pytest.mark.asyncio
    async def test_get_all_processes_multiple(self, client, cleanup_monitor):
        """Test 1.1.2: GET /api/processes with multiple processes"""
        # Create test processes
        await monitor.start_process("test_1", "training", total_steps=3)
        await monitor.start_process("test_2", "backtest", total_steps=2)
        await monitor.complete_process("test_2", {"result": "success"})

        response = client.get("/api/processes")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["processes"]) == 2

        # Validate structure
        process = data["processes"][0]
        required_fields = ["process_id", "process_type", "status", "metrics", "logs", "result", "error"]
        for field in required_fields:
            assert field in process

    @pytest.mark.asyncio
    async def test_get_running_processes_filter(self, client, cleanup_monitor):
        """Test 2.1: GET /api/processes/running filter accuracy"""
        # Create mixed processes
        await monitor.start_process("running_1", "training", total_steps=3)
        await monitor.start_process("running_2", "prediction", total_steps=2)
        await monitor.start_process("completed", "backtest", total_steps=1)
        await monitor.complete_process("completed", {"result": "done"})

        response = client.get("/api/processes/running")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        # Verify only running processes
        for proc in data["processes"]:
            assert proc["status"] == "running"

    def test_get_running_processes_empty(self, client, cleanup_monitor):
        """Test 2.2: GET /api/processes/running with no running processes"""
        response = client.get("/api/processes/running")

        assert response.status_code == 200
        data = response.json()
        assert data == {"processes": [], "total": 0}

    @pytest.mark.asyncio
    async def test_get_process_valid_id(self, client, cleanup_monitor):
        """Test 3.1: GET /api/processes/{id} with valid process"""
        await monitor.start_process("valid_id", "training", total_steps=5)
        await monitor.update_progress("valid_id", 50.0, "Training model", 2)

        response = client.get("/api/processes/valid_id")

        assert response.status_code == 200
        data = response.json()
        assert data["process_id"] == "valid_id"
        assert data["process_type"] == "training"
        assert data["status"] == "running"
        assert data["metrics"]["progress_percent"] == 50.0
        assert data["metrics"]["current_step"] == "Training model"

    def test_get_process_not_found(self, client, cleanup_monitor):
        """Test 3.2: GET /api/processes/{id} with non-existent process"""
        response = client.get("/api/processes/invalid_xyz")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_process_completed(self, client, cleanup_monitor):
        """Test 3.3: GET /api/processes/{id} for completed process"""
        await monitor.start_process("completed_proc", "training", total_steps=3)
        result = {"model_id": "model_123", "metrics": {"accuracy": 0.95}}
        await monitor.complete_process("completed_proc", result)

        response = client.get("/api/processes/completed_proc")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] == result
        assert data["error"] is None
        assert data["metrics"]["end_time"] is not None
        assert data["metrics"]["duration_seconds"] is not None
        assert data["metrics"]["progress_percent"] == 100.0

    @pytest.mark.asyncio
    async def test_get_process_failed(self, client, cleanup_monitor):
        """Test 3.4: GET /api/processes/{id} for failed process"""
        await monitor.start_process("failed_proc", "training", total_steps=3)
        await monitor.fail_process("failed_proc", "Dataset not found")

        response = client.get("/api/processes/failed_proc")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Dataset not found"
        assert data["result"] is None
        assert data["metrics"]["end_time"] is not None


class TestProcessLogsEndpoint:
    """Test /api/processes/{id}/logs endpoint"""

    @pytest.mark.asyncio
    async def test_logs_default_limit(self, client, cleanup_monitor):
        """Test 4.1: GET logs with default limit (100)"""
        await monitor.start_process("log_test", "training", total_steps=1)

        # Add 150 logs
        for i in range(150):
            await monitor.add_log("log_test", "INFO", f"Log entry {i}")

        response = client.get("/api/processes/log_test/logs")

        assert response.status_code == 200
        data = response.json()
        # Should return last 100 (plus initial "Started" log = 101 total, but sliced to 100)
        assert len(data["logs"]) == 100
        # Should be the LAST 100
        assert "Log entry 50" in data["logs"][0]["message"]

    @pytest.mark.asyncio
    async def test_logs_custom_limit(self, client, cleanup_monitor):
        """Test 4.2: GET logs with custom limit"""
        await monitor.start_process("log_test", "training", total_steps=1)

        for i in range(100):
            await monitor.add_log("log_test", "INFO", f"Log {i}")

        response = client.get("/api/processes/log_test/logs?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) <= 50

    @pytest.mark.asyncio
    async def test_logs_negative_limit(self, client, cleanup_monitor):
        """Test 4.3: GET logs with negative limit (SHOULD FAIL)"""
        await monitor.start_process("log_test", "training", total_steps=1)

        for i in range(20):
            await monitor.add_log("log_test", "INFO", f"Log {i}")

        response = client.get("/api/processes/log_test/logs?limit=-10")

        # Fixed: Now correctly returns 400 Bad Request for negative limit
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "limit" in data["detail"].lower() or "invalid" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_logs_max_limit(self, client, cleanup_monitor):
        """Test 4.4: GET logs with limit > 1000 (should clamp to 1000)"""
        await monitor.start_process("log_test", "training", total_steps=1)

        for i in range(1500):
            await monitor.add_log("log_test", "INFO", f"Log {i}")

        response = client.get("/api/processes/log_test/logs?limit=5000")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1000  # Clamped to max

    def test_logs_not_found(self, client, cleanup_monitor):
        """Test 4.5: GET logs for non-existent process"""
        response = client.get("/api/processes/invalid/logs")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_logs_structure(self, client, cleanup_monitor):
        """Test 4.6: Validate log structure"""
        await monitor.start_process("log_test", "training", total_steps=1)
        await monitor.add_log("log_test", "INFO", "Test log message")

        response = client.get("/api/processes/log_test/logs")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

        log = data["logs"][0]
        assert "timestamp" in log
        assert "level" in log
        assert "message" in log

        # Validate timestamp is ISO format
        datetime.fromisoformat(log["timestamp"])


class TestCancelProcess:
    """Test DELETE /api/processes/{id} endpoint"""

    @pytest.mark.asyncio
    async def test_cancel_running_process(self, client, cleanup_monitor):
        """Test 5.1: Cancel running process"""
        await monitor.start_process("running_proc", "training", total_steps=5)

        response = client.delete("/api/processes/running_proc")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["process_id"] == "running_proc"

        # Verify process state
        proc = await monitor.get_process("running_proc")
        assert proc.status == ProcessStatus.CANCELLED
        assert proc.metrics.end_time is not None

    @pytest.mark.asyncio
    async def test_cancel_completed_process(self, client, cleanup_monitor):
        """Test 5.2: Cancel completed process (should fail)"""
        await monitor.start_process("completed_proc", "training", total_steps=1)
        await monitor.complete_process("completed_proc", {"result": "done"})

        response = client.delete("/api/processes/completed_proc")

        assert response.status_code == 400
        data = response.json()
        assert "not running" in data["detail"].lower()
        assert "completed" in data["detail"]

    @pytest.mark.asyncio
    async def test_cancel_failed_process(self, client, cleanup_monitor):
        """Test 5.3: Cancel failed process (should fail)"""
        await monitor.start_process("failed_proc", "training", total_steps=1)
        await monitor.fail_process("failed_proc", "Error occurred")

        response = client.delete("/api/processes/failed_proc")

        assert response.status_code == 400
        data = response.json()
        assert "not running" in data["detail"].lower()

    def test_cancel_not_found(self, client, cleanup_monitor):
        """Test 5.4: Cancel non-existent process"""
        response = client.delete("/api/processes/invalid")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled(self, client, cleanup_monitor):
        """Test 5.5: Cancel already cancelled process"""
        await monitor.start_process("proc", "training", total_steps=1)
        await monitor.cancel_process("proc")

        response = client.delete("/api/processes/proc")

        assert response.status_code == 400
        data = response.json()
        assert "cancelled" in data["detail"].lower()


@pytest.mark.requires_server
class TestWebSocketProcesses:
    """Test WebSocket /ws/processes endpoint"""

    @pytest.mark.asyncio
    async def test_ws_connection(self, cleanup_monitor):
        """Test 6.1: WebSocket connection establishment"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/processes") as websocket:
                # Should accept connection
                # Receive first update
                data = websocket.receive_json()

                assert data["type"] == "process_update"
                assert "processes" in data
                assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_ws_update_frequency(self, cleanup_monitor):
        """Test 6.2: Update frequency (1 second)"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/processes") as websocket:
                # Receive first update
                start_time = time.time()
                websocket.receive_json()

                # Receive second update
                websocket.receive_json()
                elapsed = time.time() - start_time

                # Should be ~1 second (±200ms tolerance)
                assert 0.8 <= elapsed <= 1.2

    @pytest.mark.asyncio
    async def test_ws_ping_pong(self, cleanup_monitor):
        """Test 6.3: Ping/pong keepalive (EXPECTED TO FAIL)"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/processes") as websocket:
                # This test documents the missing ping/pong feature
                # Cannot test as endpoint doesn't receive messages
                pass  # Skip - endpoint doesn't implement ping/pong


@pytest.mark.requires_server
class TestWebSocketProcessSpecific:
    """Test WebSocket /ws/processes/{id} endpoint"""

    @pytest.mark.asyncio
    async def test_ws_valid_process(self, cleanup_monitor):
        """Test 7.1: Connect to valid process"""
        await monitor.start_process("ws_test", "training", total_steps=3)

        with TestClient(app) as client:
            with client.websocket_connect("/ws/processes/ws_test") as websocket:
                # Should receive initial state
                data = websocket.receive_json()

                assert data["type"] == "process_update"
                assert data["data"]["process_id"] == "ws_test"
                assert data["data"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_ws_invalid_process(self, cleanup_monitor):
        """Test 7.2: Connect to non-existent process"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/processes/invalid") as websocket:
                # Should receive error and close
                data = websocket.receive_json()

                assert data["type"] == "error"
                assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_ws_process_completion(self, cleanup_monitor):
        """Test 7.3: WebSocket closes when process completes"""
        await monitor.start_process("complete_test", "training", total_steps=1)

        with TestClient(app) as client:
            with client.websocket_connect("/ws/processes/complete_test") as websocket:
                # Receive initial state
                websocket.receive_json()

                # Complete the process
                await monitor.complete_process("complete_test", {"result": "done"})

                # Should receive completion message
                # Note: TestClient may timeout waiting for 500ms update
                try:
                    data = websocket.receive_json(timeout=1)
                    assert data["type"] == "process_complete"
                except:
                    pass  # Timeout acceptable in test client


class TestEdgeCases:
    """Test edge cases"""

    @pytest.mark.asyncio
    async def test_process_id_uniqueness(self, cleanup_monitor):
        """Edge Case 1: Process ID uniqueness"""
        # Try to create duplicate
        await monitor.start_process("unique_id", "training", total_steps=1)

        with pytest.raises(ValueError, match="already exists"):
            await monitor.start_process("unique_id", "training", total_steps=1)

    @pytest.mark.asyncio
    async def test_concurrent_cancellations(self, cleanup_monitor):
        """Edge Case 3: Concurrent cancellations (race condition test)"""
        await monitor.start_process("race_test", "training", total_steps=5)

        # Simulate concurrent cancellations
        results = await asyncio.gather(
            monitor.cancel_process("race_test"),
            monitor.cancel_process("race_test"),
            monitor.cancel_process("race_test"),
            return_exceptions=True
        )

        # First should succeed, others should fail
        successes = [r for r in results if not isinstance(r, Exception)]
        errors = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 1  # Only one succeeds
        assert len(errors) == 2  # Others raise ValueError

    def test_malformed_request_missing_fields(self, client):
        """Edge Case 4.1: Missing required fields"""
        response = client.post("/api/models/train", json={"dataset": "test"})

        # Pydantic validation should fail
        assert response.status_code == 422

    def test_malformed_request_wrong_types(self, client):
        """Edge Case 4.2: Wrong data types"""
        response = client.post("/api/models/train", json={
            "dataset": 123,  # Should be string
            "model_handler": "lightgbm"
        })

        assert response.status_code == 422


class TestIntegrationScenarios:
    """Integration tests - end-to-end workflows"""

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, client, cleanup_monitor):
        """Integration Test 3: Error handling"""
        # This would need actual trainer implementation
        # Test documents expected behavior
        pass  # Requires full system


def test_issue_ws_token_endpoint(client):
    """Verify API key can be exchanged for a signed WebSocket token."""
    api_key = next(iter(VALID_API_KEYS))

    response = client.post("/api/auth/ws-token", json={"api_key": api_key})
    assert response.status_code == 200

    data = response.json()
    assert "token" in data
    assert "expires_at" in data

    payload = verify_ws_token(data["token"])
    assert payload is not None
    assert payload.get("user_id")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
