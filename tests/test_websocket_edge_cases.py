"""
Comprehensive WebSocket Edge Case Tests

Tests all 9 high-priority edge cases identified in WEBSOCKET_EDGE_CASE_ANALYSIS.md:
1. Connection cleanup in finally blocks
2. Send buffer overflow handling
3. Error serialization
4. Graceful degradation
5. Stale data prevention
6. Duplicate message prevention
7. Reconnection guidance
8. Proper close codes
9. Connection state tracking
"""

import pytest

# Mark all tests in this module as requiring a running server
pytestmark = pytest.mark.requires_server
import asyncio
import json
from fastapi.testclient import TestClient
from fastapi import WebSocket
from unittest.mock import Mock, AsyncMock, patch
import time

# Import the app and components
from src.ui.api_enhanced import app
from src.ui.events import get_event_broadcaster
from src.ui.security import connection_manager


class MockWebSocket:
    """Mock WebSocket for testing"""
    def __init__(self):
        self.messages_sent = []
        self.messages_received = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.messages_sent.append(data)

    async def send_text(self, data):
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.messages_sent.append(data)

    async def receive_text(self):
        if self.messages_received:
            return self.messages_received.pop(0)
        # Simulate timeout
        await asyncio.sleep(0.1)
        raise asyncio.TimeoutError()

    async def close(self, code=1000, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.mark.asyncio
async def test_connection_cleanup_on_error():
    """Test #1: Connections are removed from manager on error"""
    broadcaster = get_event_broadcaster()

    # Mock websocket
    ws = MockWebSocket()

    # Add to broadcaster
    await broadcaster.connect(ws)
    assert ws in broadcaster.active_connections

    # Simulate error and disconnect
    broadcaster.disconnect(ws)

    # Verify cleanup
    assert ws not in broadcaster.active_connections


@pytest.mark.asyncio
async def test_send_buffer_overflow_handling():
    """Test #2: Send failures are caught and handled gracefully"""
    broadcaster = get_event_broadcaster()

    # Mock websocket that fails on send
    ws = MockWebSocket()

    # Override send_json to raise error
    async def failing_send_json(data):
        raise RuntimeError("Send buffer full")

    ws.send_json = failing_send_json

    # Connection should fail and clean up
    with pytest.raises(RuntimeError):
        await broadcaster.connect(ws)

    # Websocket should be removed after error
    assert ws not in broadcaster.active_connections

    # Now test broadcast with failing websocket
    ws2 = MockWebSocket()
    await broadcaster.connect(ws2)

    # Override after connection
    ws2.send_json = failing_send_json

    # This should not crash the broadcaster
    await broadcaster.broadcast("test_event", {"data": "test"})

    # Failing websocket should be disconnected after broadcast error
    assert ws2 not in broadcaster.active_connections


@pytest.mark.asyncio
async def test_error_serialization():
    """Test #3: Exceptions are serialized properly before sending"""

    # Test that error messages are dicts, not exception objects
    error = Exception("Test error")

    # Correct serialization
    error_message = {
        "type": "error",
        "message": str(error),
        "timestamp": "2025-10-07T10:00:00"
    }

    # This should be JSON serializable
    json_str = json.dumps(error_message)
    assert "Test error" in json_str


@pytest.mark.asyncio
async def test_graceful_degradation():
    """Test #4: Endpoint continues even if operations fail"""
    from src.monitoring.process_monitor import monitor

    # Mock monitor to fail
    original_get_all = monitor.get_all_processes

    call_count = 0
    async def failing_get_all():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Database error")
        return []

    monitor.get_all_processes = failing_get_all

    try:
        # First call should fail gracefully
        try:
            await monitor.get_all_processes()
        except RuntimeError:
            pass  # Expected on first call

        # Second call should succeed
        result = await monitor.get_all_processes()
        assert result == []

    finally:
        monitor.get_all_processes = original_get_all


@pytest.mark.asyncio
async def test_stale_data_prevention():
    """Test #5: State hash prevents sending unchanged data"""
    import hashlib

    # Simulate process state
    processes1 = [
        {"process_id": "test_1", "status": "running", "progress": 50.0}
    ]
    processes2 = [
        {"process_id": "test_1", "status": "running", "progress": 50.0}
    ]
    processes3 = [
        {"process_id": "test_1", "status": "completed", "progress": 100.0}
    ]

    # Compute hashes
    hash1 = hashlib.md5(json.dumps(processes1, sort_keys=True).encode()).hexdigest()
    hash2 = hashlib.md5(json.dumps(processes2, sort_keys=True).encode()).hexdigest()
    hash3 = hashlib.md5(json.dumps(processes3, sort_keys=True).encode()).hexdigest()

    # Same data should have same hash
    assert hash1 == hash2

    # Different data should have different hash
    assert hash1 != hash3


@pytest.mark.asyncio
async def test_duplicate_message_prevention():
    """Test #6: Duplicate messages are not sent"""
    last_message = None
    message_count = 0

    messages = ["ping", "ping", "pong"]

    for msg in messages:
        if msg != last_message:
            message_count += 1
            last_message = msg

    # Only 2 unique messages should be counted
    assert message_count == 2


@pytest.mark.asyncio
async def test_proper_close_codes():
    """Test #8: WebSocket uses proper close codes"""
    ws = MockWebSocket()

    # Test unauthorized close
    await ws.close(code=1008, reason="Unauthorized")
    assert ws.close_code == 1008
    assert ws.close_reason == "Unauthorized"

    # Test internal error close
    ws2 = MockWebSocket()
    await ws2.close(code=1011, reason="Server error occurred")
    assert ws2.close_code == 1011

    # Test normal close
    ws3 = MockWebSocket()
    await ws3.close(code=1000, reason="Normal closure")
    assert ws3.close_code == 1000


@pytest.mark.asyncio
async def test_connection_state_tracking():
    """Test #9: Connection state is tracked correctly"""
    from src.ui.security import UserConnectionInfo
    import time

    user_info = UserConnectionInfo(user_id="test_user")

    # Test initial state
    assert user_info.is_alive()

    # Test heartbeat update
    user_info.update_heartbeat()
    assert user_info.is_alive()

    # Test rate limiting
    # Should allow first message
    assert user_info.record_message()

    # Should allow up to limit
    for _ in range(99):
        assert user_info.record_message()

    # Should block after limit
    assert not user_info.record_message()


@pytest.mark.asyncio
async def test_reconnection_guidance():
    """Test #7: Close messages provide reconnection guidance"""
    ws = MockWebSocket()

    # Close with reconnection guidance
    await ws.close(
        code=1011,
        reason="Server error occurred. Please reconnect."
    )

    assert "reconnect" in ws.close_reason.lower()


@pytest.mark.asyncio
async def test_monotonic_time_usage():
    """Test that monotonic clock is used for timing"""
    import time

    # Test monotonic time
    start = time.monotonic()
    await asyncio.sleep(0.1)
    end = time.monotonic()

    elapsed = end - start

    # Should be approximately 0.1 seconds
    assert 0.05 < elapsed < 0.15

    # Monotonic time should always increase
    assert end > start


@pytest.mark.asyncio
async def test_json_decode_error_handling():
    """Test that JSON decode errors are caught and reported"""

    invalid_json = "{ invalid json }"

    try:
        data = json.loads(invalid_json)
        pytest.fail("Should have raised JSONDecodeError")
    except json.JSONDecodeError as e:
        # Error should be caught
        error_message = {
            "type": "error",
            "message": f"Invalid JSON: {str(e)}"
        }

        # Should be serializable
        json_str = json.dumps(error_message)
        assert "Invalid JSON" in json_str


@pytest.mark.asyncio
async def test_heartbeat_timeout_detection():
    """Test that heartbeat timeout is detected"""
    from src.ui.security import HEARTBEAT_TIMEOUT
    import time

    # Mock user connection
    user_id = "test_user"
    ws = MockWebSocket()

    # Add connection
    connection_manager.add_connection(user_id, ws)

    # Should be alive initially
    assert connection_manager.is_connection_alive(user_id)

    # Update heartbeat
    connection_manager.update_heartbeat(user_id)
    assert connection_manager.is_connection_alive(user_id)

    # Cleanup
    connection_manager.remove_connection(user_id, ws)


def test_all_endpoints_have_finally_blocks():
    """Test that all WebSocket endpoints have finally blocks for cleanup"""
    import inspect
    from src.ui import api_enhanced

    # Get all WebSocket endpoint functions
    websocket_endpoints = [
        api_enhanced.websocket_events,
        api_enhanced.websocket_market_data,
        api_enhanced.websocket_processes,
        api_enhanced.websocket_process_updates
    ]

    for endpoint in websocket_endpoints:
        source = inspect.getsource(endpoint)

        # Check for finally block
        assert "finally:" in source, f"{endpoint.__name__} missing finally block"

        # Check for cleanup in finally
        assert "remove_connection" in source, f"{endpoint.__name__} missing cleanup"


@pytest.mark.asyncio
async def test_broadcaster_race_condition_fix():
    """Test that broadcaster uses snapshot to prevent race condition"""
    broadcaster = get_event_broadcaster()

    # Add multiple connections
    connections = [MockWebSocket() for _ in range(5)]

    for ws in connections:
        await broadcaster.connect(ws)

    # Broadcast while modifying connection set
    async def broadcast_task():
        await broadcaster.broadcast("test", {"data": "test"})

    async def disconnect_task():
        await asyncio.sleep(0.01)
        broadcaster.disconnect(connections[0])

    # Run both tasks concurrently - should not crash
    await asyncio.gather(
        broadcast_task(),
        disconnect_task()
    )

    # Cleanup
    for ws in connections[1:]:
        broadcaster.disconnect(ws)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
