"""
Integration tests for CORD MCP stdio client and tool bridging.
"""

import sys
import pytest
from pathlib import Path
from cord.mcp.client import MCPStdioClient
from cord.mcp.manager import MCPWrappedTool


@pytest.mark.asyncio
async def test_mcp_stdio_lifecycle():
    mock_script = Path(__file__).parent / "mock_mcp_server.py"
    client = MCPStdioClient(
        name="mock",
        command=sys.executable,
        args=[str(mock_script)],
    )

    started = await client.start()
    assert started is True
    assert len(client.tools) == 1
    assert client.tools[0]["name"] == "echo_tool"

    # Test calling tool
    wrapped = MCPWrappedTool("mock", client, client.tools[0])
    res = await wrapped.execute(message="Testing MCP from CORD!")
    assert res.success is True
    assert "MOCK_ECHO: Testing MCP from CORD!" in res.output

    # Shutdown
    await client.stop()
