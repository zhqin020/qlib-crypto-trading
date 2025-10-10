#!/usr/bin/env python
"""Test MCP server protocol handshake"""
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mcp_server.server import app

async def test_protocol():
    """Test the MCP protocol handshake"""

    # Get tools
    print("Testing list_tools()...")
    tools = await app.list_tools()
    print(f"\nFound {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")

    # Get resources
    print("\n\nTesting list_resources()...")
    resources = await app.list_resources()
    print(f"Found {len(resources)} resources:")
    for resource in resources:
        print(f"  - {resource.uri}: {resource.name}")

if __name__ == "__main__":
    asyncio.run(test_protocol())
