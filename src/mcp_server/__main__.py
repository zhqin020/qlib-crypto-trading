"""MCP Server entry point

This allows running the MCP server as:
    python -m src.mcp_server

Or via the MCP config in Claude.
"""
import asyncio
import sys
import logging
from utils.logging_config import get_logger
import mcp.server.stdio

from .server import app

# Logging is configured via utils.logging_config on import
logger = get_logger(__name__)


async def main():
    """Run the MCP server with stdio transport"""
    logger.info("MCP Server starting...")
    logger.info(f"Python version: {sys.version}")

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.info("Stdio server created successfully")
            init_options = app.create_initialization_options()
            logger.info("Starting server.run()...")
            await app.run(
                read_stream,
                write_stream,
                init_options,
                raise_exceptions=True
            )
            logger.info("Server.run() completed")
    except Exception as e:
        logger.error(f"MCP Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
