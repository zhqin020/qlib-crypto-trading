#!/usr/bin/env python
"""Test MCP server with stdio input"""
import subprocess
import json
import sys

# MCP initialization message
init_message = {
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

# Start the MCP server
proc = subprocess.Popen(
    ["/Users/chadwyatt/Code/trading/qlib-2/scripts/start_mcp_server.sh"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Send initialization
print("Sending initialization message...")
print(json.dumps(init_message))
proc.stdin.write(json.dumps(init_message) + "\n")
proc.stdin.flush()

# Try to read response
print("\nWaiting for response...")
try:
    import select
    import time

    # Wait a bit for response
    time.sleep(2)

    # Check if there's output
    output = proc.stdout.readline()
    if output:
        print("Response:", output)
        # Try to parse as JSON
        try:
            response = json.loads(output)
            print("Parsed response:", json.dumps(response, indent=2))
        except:
            print("Could not parse as JSON")
    else:
        print("No response received")

    # Check stderr
    if proc.stderr:
        errors = proc.stderr.read()
        if errors:
            print("\nStderr output:")
            print(errors)

except Exception as e:
    print(f"Error: {e}")
finally:
    proc.terminate()
    proc.wait(timeout=1)
