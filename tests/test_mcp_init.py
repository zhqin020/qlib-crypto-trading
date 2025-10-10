#!/usr/bin/env python3
"""
Test MCP Server Initialization

This script simulates what Claude Code does when connecting to the MCP server.
It will show exactly where the process hangs or what errors occur.
"""

import subprocess
import json
import sys
import time
import select
from pathlib import Path

def test_mcp_server():
    """Test the MCP server initialization"""

    print("=" * 60)
    print("MCP Server Initialization Test")
    print("=" * 60)

    # Start the server
    print("\n1. Starting MCP server...")
    print("   Command: python -m src.mcp_server")
    print("   CWD:", Path.cwd())

    try:
        proc = subprocess.Popen(
            [sys.executable, '-m', 'src.mcp_server'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            cwd=str(Path(__file__).parent)
        )
        print("   ✓ Process started (PID:", proc.pid, ")")
    except Exception as e:
        print(f"   ✗ Failed to start: {e}")
        return False

    # Give it a moment to initialize
    time.sleep(0.5)

    # Check if process died immediately
    if proc.poll() is not None:
        print(f"\n   ✗ Process died immediately with code {proc.returncode}")
        stderr = proc.stderr.read()
        if stderr:
            print("   STDERR:", stderr)
        return False

    print("   ✓ Process still running")

    # Send initialize request
    print("\n2. Sending initialize request...")
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }

    request_json = json.dumps(init_request)
    print(f"   Request: {request_json[:100]}...")

    try:
        proc.stdin.write(request_json + '\n')
        proc.stdin.flush()
        print("   ✓ Request sent")
    except Exception as e:
        print(f"   ✗ Failed to send: {e}")
        proc.kill()
        return False

    # Wait for response with timeout
    print("\n3. Waiting for response (5 second timeout)...")
    start_time = time.time()
    response_received = False

    while time.time() - start_time < 5:
        # Check if there's data to read
        if sys.platform != 'win32':
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if ready:
                try:
                    line = proc.stdout.readline()
                    if line:
                        print(f"\n   ✓ Response received after {time.time() - start_time:.2f}s")
                        print(f"   Response: {line[:200]}")

                        # Parse and validate
                        try:
                            response = json.loads(line)
                            if 'result' in response:
                                server_name = response['result'].get('serverInfo', {}).get('name', 'unknown')
                                print(f"   ✓ Server name: {server_name}")
                                response_received = True
                                break
                            elif 'error' in response:
                                print(f"   ✗ Server returned error: {response['error']}")
                                break
                        except json.JSONDecodeError as e:
                            print(f"   ✗ Invalid JSON response: {e}")
                            break
                except Exception as e:
                    print(f"   ✗ Error reading response: {e}")
                    break
        else:
            # Windows doesn't support select on pipes
            time.sleep(0.1)
            if proc.stdout.readable():
                line = proc.stdout.readline()
                if line:
                    print(f"\n   ✓ Response received")
                    print(f"   Response: {line[:200]}")
                    response_received = True
                    break

        # Check if process died
        if proc.poll() is not None:
            print(f"\n   ✗ Process died with code {proc.returncode}")
            stderr = proc.stderr.read()
            if stderr:
                print(f"   STDERR: {stderr}")
            break

    if not response_received:
        print(f"\n   ✗ No response after 5 seconds")
        print("\n4. Checking for stderr output...")

        # Try to get stderr
        try:
            proc.stdin.close()
            time.sleep(0.5)
            stderr = proc.stderr.read()
            if stderr:
                print(f"   STDERR:\n{stderr}")
            else:
                print("   No stderr output")
        except Exception as e:
            print(f"   Error reading stderr: {e}")

        # Kill the process
        print("\n5. Killing hung process...")
        proc.kill()
        proc.wait()
        print("   ✓ Process killed")
        return False

    # Clean up
    print("\n4. Cleaning up...")
    proc.kill()
    proc.wait()
    print("   ✓ Process terminated")

    print("\n" + "=" * 60)
    print("✓ MCP Server Initialization Test PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    # Change to project directory
    project_dir = Path(__file__).parent
    import os
    os.chdir(project_dir)

    success = test_mcp_server()
    sys.exit(0 if success else 1)
