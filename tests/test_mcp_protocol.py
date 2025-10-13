"""Test MCP server protocol handshake"""
import pytest
from src.mcp_server.server import list_tools, list_resources


@pytest.mark.asyncio
async def test_list_tools():
    """Test MCP server list_tools() method"""
    tools = await list_tools()

    # Verify tools were returned
    assert len(tools) > 0, "Expected at least one tool from MCP server"

    # Verify tool structure
    for tool in tools:
        assert hasattr(tool, 'name'), "Tool missing 'name' attribute"
        assert hasattr(tool, 'description'), "Tool missing 'description' attribute"
        assert tool.name, "Tool name should not be empty"


@pytest.mark.asyncio
async def test_list_resources():
    """Test MCP server list_resources() method"""
    resources = await list_resources()

    # Verify resources were returned
    assert isinstance(resources, list), "Expected list of resources"

    # Verify resource structure if any exist
    for resource in resources:
        assert hasattr(resource, 'uri'), "Resource missing 'uri' attribute"
        assert hasattr(resource, 'name'), "Resource missing 'name' attribute"


@pytest.mark.asyncio
async def test_protocol_integration():
    """Test complete MCP protocol handshake"""
    # Verify both tools and resources can be retrieved
    tools = await list_tools()
    resources = await list_resources()

    assert len(tools) > 0, "Server should expose at least one tool"
    assert isinstance(resources, list), "Resources should be a list"

    # Log for debugging (only shown on failure or with -v)
    print(f"\nMCP Server Status:")
    print(f"  Tools: {len(tools)}")
    print(f"  Resources: {len(resources)}")
