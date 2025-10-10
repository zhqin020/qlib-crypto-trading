"""
Test WebSocket ping/pong keepalive functionality
"""
import pytest

# Mark all tests in this module as requiring a running server
pytestmark = pytest.mark.requires_server
import json
from fastapi.testclient import TestClient

from src.ui.api_enhanced import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_ws_market_data_ping_pong(client):
    """Test /ws/market-data ping/pong keepalive with JSON"""
    with client.websocket_connect("/ws/market-data") as websocket:
        # Send ping as JSON
        websocket.send_json({"type": "ping"})

        # Should receive pong
        response = websocket.receive_json()
        assert response["type"] == "pong"


def test_ws_market_data_plain_ping(client):
    """Test /ws/market-data plain text ping"""
    with client.websocket_connect("/ws/market-data") as websocket:
        # Send plain text ping
        websocket.send_text("ping")

        # Should receive pong
        response = websocket.receive_json()
        assert response["type"] == "pong"


def test_ws_processes_ping_pong(client):
    """Test /ws/processes ping/pong keepalive with JSON"""
    with client.websocket_connect("/ws/processes") as websocket:
        # Send ping as JSON
        websocket.send_json({"type": "ping"})

        # Should receive pong
        response = websocket.receive_json()
        assert response["type"] == "pong"


def test_ws_processes_plain_ping(client):
    """Test /ws/processes plain text ping"""
    with client.websocket_connect("/ws/processes") as websocket:
        # Send plain text ping
        websocket.send_text("ping")

        # Should receive pong
        response = websocket.receive_json()
        assert response["type"] == "pong"


def test_ws_market_data_invalid_json(client):
    """Test /ws/market-data handles invalid JSON gracefully"""
    with client.websocket_connect("/ws/market-data") as websocket:
        # Send invalid JSON
        websocket.send_text("{invalid json}")

        # Connection should still be alive - send ping
        websocket.send_text("ping")

        # Should receive pong
        response = websocket.receive_json()
        assert response["type"] == "pong"


def test_ws_processes_invalid_json(client):
    """Test /ws/processes handles invalid JSON gracefully"""
    with client.websocket_connect("/ws/processes") as websocket:
        # Send invalid JSON
        websocket.send_text("{invalid json}")

        # Connection should still be alive - send ping
        websocket.send_json({"type": "ping"})

        # Should receive pong (might receive process_update first due to timing)
        response = websocket.receive_json()
        # If we get a process_update first, get the next message
        if response["type"] == "process_update":
            response = websocket.receive_json()
        assert response["type"] == "pong"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
