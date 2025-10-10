#!/usr/bin/env python
"""Test MCP server tools/list request"""
import subprocess
import json
import time

# Start the MCP server
proc = subprocess.Popen(
    ["/Users/chadwyatt/Code/trading/qlib-2/scripts/start_mcp_server.sh"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Initialize
init_message = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }
}

print("1. Initializing...")
proc.stdin.write(json.dumps(init_message) + "\n")
proc.stdin.flush()
init_response = proc.stdout.readline()
print(f"Init response: {init_response}")

# Send initialized notification
initialized_notification = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized"
}
print("\n2. Sending initialized notification...")
proc.stdin.write(json.dumps(initialized_notification) + "\n")
proc.stdin.flush()

# Request tools list
tools_request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
}
print("\n3. Requesting tools list...")
proc.stdin.write(json.dumps(tools_request) + "\n")
proc.stdin.flush()

# Read response
time.sleep(0.5)
tools_response = proc.stdout.readline()
print(f"\nTools response: {tools_response}")

if tools_response:
    try:
        data = json.loads(tools_response)
        if "result" in data and "tools" in data["result"]:
            print(f"\nFound {len(data['result']['tools'])} tools:")
            for tool in data['result']['tools']:
                print(f"  - {tool['name']}: {tool.get('description', 'N/A')}")
    except Exception as e:
        print(f"Error parsing: {e}")

proc.terminate()
proc.wait(timeout=1)
