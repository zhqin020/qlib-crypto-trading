#!/usr/bin/env python3
"""
Test WebSocket authentication on all 4 endpoints
"""

import asyncio
import json
import websockets
import pytest
from src.ui.security import generate_api_key, VALID_API_KEYS

# Mark all tests in this module as requiring a running server
pytestmark = pytest.mark.requires_server

# Test configuration
BASE_URL = "ws://localhost:5100"
ENDPOINTS = [
    "/ws/events",
    "/ws/processes",
    "/ws/processes/test_123",
    "/ws/market-data"
]


def get_valid_api_key():
    """Get a valid API key for testing"""
    if VALID_API_KEYS:
        return list(VALID_API_KEYS)[0]
    return "qlib_dev_key_change_in_production"


@pytest.mark.asyncio
async def test_websocket_no_auth():
    """Test that WebSocket connections without auth are rejected"""
    for endpoint in ENDPOINTS:
        url = f"{BASE_URL}{endpoint}"
        print(f"\nTesting {endpoint} without authentication...")

        try:
            async with websockets.connect(url) as ws:
                # Should not reach here - connection should be closed
                response = await asyncio.wait_for(ws.recv(), timeout=2)
                assert False, f"Expected connection to be rejected but got: {response}"
        except websockets.exceptions.ConnectionClosed as e:
            # Expected behavior
            print(f"✓ Connection rejected (code: {e.code})")
            assert e.code == 1008, f"Expected policy violation (1008) but got {e.code}"
        except asyncio.TimeoutError:
            assert False, "Connection timeout - expected immediate rejection"


@pytest.mark.asyncio
async def test_websocket_invalid_auth():
    """Test that WebSocket connections with invalid API key are rejected"""
    invalid_key = "invalid_key_12345"

    for endpoint in ENDPOINTS:
        url = f"{BASE_URL}{endpoint}?api_key={invalid_key}"
        print(f"\nTesting {endpoint} with invalid API key...")

        try:
            async with websockets.connect(url) as ws:
                # Should not reach here
                response = await asyncio.wait_for(ws.recv(), timeout=2)
                assert False, f"Expected connection to be rejected but got: {response}"
        except websockets.exceptions.ConnectionClosed as e:
            # Expected behavior
            print(f"✓ Invalid auth rejected (code: {e.code})")
            assert e.code == 1008, f"Expected policy violation (1008) but got {e.code}"
        except asyncio.TimeoutError:
            assert False, "Connection timeout - expected immediate rejection"


@pytest.mark.asyncio
async def test_websocket_valid_auth_query_param():
    """Test that WebSocket connections with valid API key (query param) are accepted"""
    api_key = get_valid_api_key()

    for endpoint in ENDPOINTS:
        if "{process_id}" in endpoint:
            # Skip parametrized endpoints for this test
            continue

        url = f"{BASE_URL}{endpoint}?api_key={api_key}"
        print(f"\nTesting {endpoint} with valid API key (query param)...")

        try:
            async with websockets.connect(url) as ws:
                # Send ping
                await ws.send(json.dumps({"type": "ping"}))

                # Should receive pong
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)

                print(f"✓ Connection accepted, received: {data}")
                assert data.get("type") == "pong", f"Expected pong but got {data}"

        except websockets.exceptions.ConnectionClosed as e:
            assert False, f"Connection unexpectedly closed: {e.code} - {e.reason}"
        except asyncio.TimeoutError:
            assert False, "Timeout waiting for pong response"


@pytest.mark.asyncio
async def test_websocket_valid_auth_header():
    """Test that WebSocket connections with valid API key (header) are accepted"""
    api_key = get_valid_api_key()
    headers = {"Authorization": f"Bearer {api_key}"}

    for endpoint in ENDPOINTS:
        if "{process_id}" in endpoint:
            # Skip parametrized endpoints for this test
            continue

        url = f"{BASE_URL}{endpoint}"
        print(f"\nTesting {endpoint} with valid API key (Authorization header)...")

        try:
            async with websockets.connect(url, extra_headers=headers) as ws:
                # Send ping
                await ws.send(json.dumps({"type": "ping"}))

                # Should receive pong
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)

                print(f"✓ Connection accepted, received: {data}")
                assert data.get("type") == "pong", f"Expected pong but got {data}"

        except websockets.exceptions.ConnectionClosed as e:
            assert False, f"Connection unexpectedly closed: {e.code} - {e.reason}"
        except asyncio.TimeoutError:
            assert False, "Timeout waiting for pong response"


@pytest.mark.asyncio
async def test_websocket_message_size_limit():
    """Test that oversized messages are rejected"""
    api_key = get_valid_api_key()
    url = f"{BASE_URL}/ws/events?api_key={api_key}"

    print("\nTesting message size limit...")

    try:
        async with websockets.connect(url) as ws:
            # Send message larger than 1MB
            large_message = "x" * (2 * 1024 * 1024)  # 2MB
            await ws.send(large_message)

            # Should receive error
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)

            print(f"✓ Oversized message rejected: {data}")
            assert data.get("type") == "error", f"Expected error but got {data}"
            assert "exceeds maximum size" in data.get("message", ""), "Expected size limit error"

    except websockets.exceptions.ConnectionClosed as e:
        # Also acceptable - connection closed due to violation
        print(f"✓ Connection closed due to oversized message (code: {e.code})")
    except asyncio.TimeoutError:
        assert False, "Timeout waiting for error response"


@pytest.mark.asyncio
async def test_websocket_rate_limiting():
    """Test that rate limiting works (100 messages/minute)"""
    api_key = get_valid_api_key()
    url = f"{BASE_URL}/ws/events?api_key={api_key}"

    print("\nTesting rate limiting (sending 110 messages rapidly)...")

    try:
        async with websockets.connect(url) as ws:
            errors = 0

            # Send 110 messages rapidly
            for i in range(110):
                await ws.send("ping")

                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(response)

                    if data.get("type") == "error" and "Rate limit" in data.get("message", ""):
                        errors += 1
                        if errors == 1:
                            print(f"✓ Rate limit triggered after ~100 messages")
                except asyncio.TimeoutError:
                    pass  # No response yet

            assert errors > 0, "Expected rate limit errors but got none"
            print(f"✓ Rate limiting working ({errors} rate limit errors received)")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed during test: {e.code} - {e.reason}")


@pytest.mark.asyncio
async def test_websocket_connection_limit():
    """Test that connection limit per user works (max 10)"""
    api_key = get_valid_api_key()
    url = f"{BASE_URL}/ws/events?api_key={api_key}"

    print("\nTesting connection limit (attempting 12 concurrent connections)...")

    connections = []
    rejected = 0

    try:
        # Try to open 12 connections
        for i in range(12):
            try:
                ws = await websockets.connect(url)
                connections.append(ws)
                print(f"  Connection {i+1} opened")
            except websockets.exceptions.ConnectionClosed as e:
                rejected += 1
                print(f"  Connection {i+1} rejected (code: {e.code})")

        print(f"✓ Opened {len(connections)} connections, {rejected} rejected")
        assert len(connections) <= 10, f"Expected max 10 connections but got {len(connections)}"
        assert rejected >= 2, f"Expected at least 2 rejections but got {rejected}"

    finally:
        # Clean up connections
        for ws in connections:
            try:
                await ws.close()
            except:
                pass


def test_generate_api_key():
    """Test API key generation"""
    key1 = generate_api_key()
    key2 = generate_api_key()

    print(f"\nGenerated API keys:")
    print(f"  Key 1: {key1}")
    print(f"  Key 2: {key2}")

    assert key1.startswith("qlib_"), "Key should start with qlib_"
    assert len(key1) > 20, "Key should be long enough"
    assert key1 != key2, "Keys should be unique"
    print("✓ API key generation working correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Authentication Test Suite")
    print("=" * 60)
    print("\nNOTE: Server must be running at http://localhost:5100")
    print("Start server with: python3 -m src.ui.api_enhanced\n")

    # Run tests
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
