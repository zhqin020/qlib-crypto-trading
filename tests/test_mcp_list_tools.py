"""Test MCP server tools/list via direct API calls"""
import pytest
from src.mcp_server.server import list_tools


@pytest.mark.asyncio
async def test_tools_list_returns_data():
    """Test that tools/list returns a non-empty list"""
    tools = await list_tools()

    assert isinstance(tools, list), "list_tools() should return a list"
    assert len(tools) > 0, "Server should expose at least one tool"


@pytest.mark.asyncio
async def test_tools_have_required_fields():
    """Test that each tool has required name and description"""
    tools = await list_tools()

    for tool in tools:
        assert hasattr(tool, 'name'), f"Tool {tool} missing 'name' attribute"
        assert hasattr(tool, 'description'), f"Tool {tool} missing 'description' attribute"
        assert isinstance(tool.name, str), f"Tool name should be string, got {type(tool.name)}"
        assert len(tool.name) > 0, "Tool name should not be empty"


@pytest.mark.asyncio
async def test_tools_list_stability():
    """Test that tools/list returns consistent results across calls"""
    tools1 = await list_tools()
    tools2 = await list_tools()

    # Should return same number of tools
    assert len(tools1) == len(tools2), "tools/list should return consistent results"

    # Tool names should match
    names1 = sorted([t.name for t in tools1])
    names2 = sorted([t.name for t in tools2])
    assert names1 == names2, "Tool names should be consistent across calls"
