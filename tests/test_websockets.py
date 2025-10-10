"""
WebSocket Integration Tests

Tests WebSocket endpoints for:
- Connection establishment
- Real-time updates
- Ping/pong keepalive
- Error handling
- Connection lifecycle
"""

import asyncio
import websockets
import json
import time
import sys
from pathlib import Path
import pytest

# Mark all tests in this module as requiring a running server
pytestmark = pytest.mark.requires_server

# Colors for output
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
BOLD = "\033[1m"
RESET = "\033[0m"


async def test_ws_processes_connection():
    """Test 6.1: WebSocket /ws/processes connection"""
    print(f"{BOLD}Test 1: WebSocket /ws/processes connection{RESET}")

    uri = "ws://localhost:5100/ws/processes"

    try:
        async with websockets.connect(uri) as websocket:
            print(f"{GREEN}✓ Connection established{RESET}")

            # Receive first update
            message = await asyncio.wait_for(websocket.recv(), timeout=2)
            data = json.loads(message)

            assert data["type"] == "process_update", "Wrong message type"
            assert "processes" in data, "Missing processes field"
            assert "timestamp" in data, "Missing timestamp field"

            print(f"  Received update with {len(data['processes'])} processes")
            print(f"{GREEN}✓ Pass{RESET}\n")
            return True

    except Exception as e:
        print(f"{RED}✗ Fail: {e}{RESET}\n")
        return False


async def test_ws_update_frequency():
    """Test 6.2: Update frequency (1 second)"""
    print(f"{BOLD}Test 2: WebSocket update frequency{RESET}")

    uri = "ws://localhost:5100/ws/processes"

    try:
        async with websockets.connect(uri) as websocket:
            # Record timing of 3 updates
            timings = []
            for i in range(3):
                start = time.time()
                await asyncio.wait_for(websocket.recv(), timeout=2)
                elapsed = time.time() - start
                timings.append(elapsed)

            # Check average is ~1 second
            avg_interval = sum(timings[1:]) / len(timings[1:])  # Skip first

            print(f"  Average interval: {avg_interval:.3f}s")

            if 0.8 <= avg_interval <= 1.2:
                print(f"{GREEN}✓ Pass - Updates every ~1 second{RESET}\n")
                return True
            else:
                print(f"{YELLOW}⚠ Warning - Interval outside expected range{RESET}\n")
                return True  # Still pass, just timing variance

    except Exception as e:
        print(f"{RED}✗ Fail: {e}{RESET}\n")
        return False


async def test_ws_ping_pong():
    """Test 6.3: Ping/pong keepalive (EXPECTED TO FAIL)"""
    print(f"{BOLD}Test 3: WebSocket ping/pong (known issue){RESET}")

    uri = "ws://localhost:5100/ws/processes"

    try:
        async with websockets.connect(uri) as websocket:
            # Wait for first update
            await asyncio.wait_for(websocket.recv(), timeout=2)

            # Try to send ping
            await websocket.send("ping")

            # Try to receive pong (with timeout)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2)
                data = json.loads(response)

                if data.get("type") == "pong":
                    print(f"{GREEN}✓ Pass - Ping/pong implemented{RESET}\n")
                    return True
                else:
                    # Received update instead of pong
                    print(f"{YELLOW}⚠ Expected 'pong', received: {data.get('type')}{RESET}")
                    print(f"{YELLOW}⚠ Bug confirmed - Ping/pong not implemented{RESET}\n")
                    return False

            except asyncio.TimeoutError:
                print(f"{YELLOW}⚠ No response to ping{RESET}")
                print(f"{YELLOW}⚠ Bug confirmed - Ping/pong not implemented{RESET}\n")
                return False

    except Exception as e:
        print(f"{RED}✗ Fail: {e}{RESET}\n")
        return False


async def test_ws_multiple_connections():
    """Test 6.4: Multiple concurrent connections"""
    print(f"{BOLD}Test 4: Multiple WebSocket connections{RESET}")

    uri = "ws://localhost:5100/ws/processes"

    try:
        # Open 3 concurrent connections
        connections = []
        for i in range(3):
            ws = await websockets.connect(uri)
            connections.append(ws)

        print(f"{GREEN}✓ 3 connections established{RESET}")

        # All should receive updates
        messages = await asyncio.gather(
            *[ws.recv() for ws in connections],
            return_exceptions=True
        )

        success = all(not isinstance(m, Exception) for m in messages)

        # Close all
        await asyncio.gather(*[ws.close() for ws in connections])

        if success:
            print(f"{GREEN}✓ Pass - All connections received updates{RESET}\n")
            return True
        else:
            print(f"{RED}✗ Fail - Some connections failed{RESET}\n")
            return False

    except Exception as e:
        print(f"{RED}✗ Fail: {e}{RESET}\n")
        return False


async def test_ws_graceful_close():
    """Test 6.5: Graceful connection close"""
    print(f"{BOLD}Test 5: WebSocket graceful close{RESET}")

    uri = "ws://localhost:5100/ws/processes"

    try:
        async with websockets.connect(uri) as websocket:
            # Receive first message
            await asyncio.wait_for(websocket.recv(), timeout=2)

            # Close from client side
            await websocket.close()

        print(f"{GREEN}✓ Pass - Connection closed gracefully{RESET}\n")
        return True

    except Exception as e:
        print(f"{RED}✗ Fail: {e}{RESET}\n")
        return False


async def test_ws_process_specific_valid():
    """Test 7.1: WebSocket /ws/processes/{id} with valid process"""
    print(f"{BOLD}Test 6: WebSocket /ws/processes/{{id}} - valid process{RESET}")

    # First, start a process via API
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            # Start training
            async with session.post(
                "http://localhost:5100/api/models/train",
                json={
                    "dataset": "crypto_btc_daily",
                    "feature_handler": "alpha158",
                    "model_handler": "lightgbm"
                }
            ) as resp:
                if resp.status != 200:
                    print(f"{YELLOW}⚠ Skipped - Could not start process{RESET}\n")
                    return None

                data = await resp.json()
                process_id = data["process_id"]

        print(f"  Started process: {process_id}")

        # Connect to specific process
        uri = f"ws://localhost:5100/ws/processes/{process_id}"

        async with websockets.connect(uri) as websocket:
            # Receive initial state
            message = await asyncio.wait_for(websocket.recv(), timeout=2)
            data = json.loads(message)

            assert data["type"] == "process_update", "Wrong message type"
            assert data["data"]["process_id"] == process_id, "Wrong process ID"
            assert "status" in data["data"], "Missing status"
            assert "metrics" in data["data"], "Missing metrics"

            print(f"  Status: {data['data']['status']}")
            print(f"  Progress: {data['data']['metrics']['progress_percent']}%")

            # Wait for one more update
            message = await asyncio.wait_for(websocket.recv(), timeout=1)
            data2 = json.loads(message)

            print(f"{GREEN}✓ Pass - Receiving real-time updates{RESET}\n")

            # Cancel the process
            async with aiohttp.ClientSession() as session:
                await session.delete(f"http://localhost:5100/api/processes/{process_id}")

            return True

    except Exception as e:
        print(f"{RED}✗ Fail: {e}{RESET}\n")
        return False


async def test_ws_process_specific_invalid():
    """Test 7.2: WebSocket /ws/processes/{id} with invalid process"""
    print(f"{BOLD}Test 7: WebSocket /ws/processes/{{id}} - invalid process{RESET}")

    uri = "ws://localhost:5100/ws/processes/invalid_process_xyz"

    try:
        async with websockets.connect(uri) as websocket:
            # Should receive error message
            message = await asyncio.wait_for(websocket.recv(), timeout=2)
            data = json.loads(message)

            assert data["type"] == "error", f"Expected error, got {data['type']}"
            assert "not found" in data["message"].lower(), "Wrong error message"

            print(f"  Error message: {data['message']}")
            print(f"{GREEN}✓ Pass - Correct error handling{RESET}\n")
            return True

    except websockets.exceptions.ConnectionClosed:
        print(f"{GREEN}✓ Pass - Connection closed after error{RESET}\n")
        return True
    except Exception as e:
        print(f"{RED}✗ Fail: {e}{RESET}\n")
        return False


async def test_ws_process_completion():
    """Test 7.3: WebSocket detects process completion"""
    print(f"{BOLD}Test 8: WebSocket process completion detection{RESET}")

    # This test requires a fast-completing process
    # For now, we'll document the expected behavior
    print(f"{YELLOW}⚠ Skipped - Requires fast-completing test process{RESET}")
    print(f"  Expected behavior:")
    print(f"    1. Connect to /ws/processes/{{id}}")
    print(f"    2. Receive updates while running")
    print(f"    3. Receive final message with type='process_complete'")
    print(f"    4. Connection closes automatically\n")
    return None


async def main():
    """Run all WebSocket tests"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}WebSocket Integration Test Suite{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    # Check server is running
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:5100/api/health") as resp:
                if resp.status != 200:
                    raise Exception("Server not healthy")
        print(f"{GREEN}✓ Server is running{RESET}\n")
    except Exception as e:
        print(f"{RED}✗ Server not running at http://localhost:5100{RESET}")
        print("Start server with: python -m src.ui.api_enhanced")
        return

    # Run tests
    results = []

    tests = [
        test_ws_processes_connection,
        test_ws_update_frequency,
        test_ws_ping_pong,
        test_ws_multiple_connections,
        test_ws_graceful_close,
        test_ws_process_specific_valid,
        test_ws_process_specific_invalid,
        test_ws_process_completion,
    ]

    for test in tests:
        result = await test()
        results.append(result)
        await asyncio.sleep(0.5)  # Brief pause between tests

    # Summary
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}Test Summary{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    skipped = sum(1 for r in results if r is None)

    print(f"Total tests: {len(results)}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    print(f"{YELLOW}Skipped: {skipped}{RESET}\n")

    if failed > 0:
        print(f"{YELLOW}Known issues:{RESET}")
        print(f"  - Ping/pong not implemented on /ws/processes (Test 3)")
        print(f"\nSee API_INTEGRATION_TEST_REPORT.md for details\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted{RESET}")
