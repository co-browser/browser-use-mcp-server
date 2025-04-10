"""
Command line interface for browser-use-mcp-server.

This module provides a command-line interface for starting the browser-use MCP server.
It wraps the existing server functionality with a CLI.
"""

import json
import logging
import sys
from typing import Optional

import click
from pythonjsonlogger import jsonlogger

# Import directly from our package
from browser_use_mcp_server.server import main as server_main

# Configure logging for CLI
logger = logging.getLogger()
logger.handlers = []  # Remove any existing handlers
handler = logging.StreamHandler(sys.stderr)
formatter = jsonlogger.JsonFormatter(
    '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_error(message: str, error: Optional[Exception] = None):
    """Log error in JSON format to stderr"""
    error_data = {"error": message, "traceback": str(error) if error else None}
    print(json.dumps(error_data), file=sys.stderr)


@click.group()
def cli():
    """Browser-use MCP server command line interface."""


@cli.command()
@click.argument("subcommand")
@click.option("--port", default=8000, help="Port to listen on for SSE")
@click.option(
    "--proxy-port",
    default=None,
    type=int,
    help="Port for the proxy to listen on (when using stdio mode)",
)
@click.option("--chrome-path", default=None, help="Path to Chrome executable")
@click.option("--window-width", default=1280, help="Browser window width")
@click.option("--window-height", default=1100, help="Browser window height")
@click.option("--locale", default="en-US", help="Browser locale")
@click.option(
    "--task-expiry-minutes",
    default=60,
    help="Minutes after which tasks are considered expired",
)
@click.option(
    "--stdio", is_flag=True, default=False, help="Enable stdio mode with mcp-proxy"
)
def run(
    subcommand,
    port,
    proxy_port,
    chrome_path,
    window_width,
    window_height,
    locale,
    task_expiry_minutes,
    stdio,
):
    """Run the browser-use MCP server.

    SUBCOMMAND: should be 'server'
    """
    if subcommand != "server":
        log_error(f"Unknown subcommand: {subcommand}. Only 'server' is supported.")
        sys.exit(1)

    try:
        # We need to construct the command line arguments to pass to the server's Click command
        old_argv = sys.argv.copy()

        # Build a new argument list for the server command
        new_argv = [
            "server",  # Program name
            "--port",
            str(port),
        ]

        if chrome_path:
            new_argv.extend(["--chrome-path", chrome_path])

        if proxy_port is not None:
            new_argv.extend(["--proxy-port", str(proxy_port)])

        new_argv.extend(["--window-width", str(window_width)])
        new_argv.extend(["--window-height", str(window_height)])
        new_argv.extend(["--locale", locale])
        new_argv.extend(["--task-expiry-minutes", str(task_expiry_minutes)])

        if stdio:
            new_argv.append("--stdio")

        # Replace sys.argv temporarily
        sys.argv = new_argv

        # Run the server's command directly
        try:
            return server_main()
        finally:
            # Restore original sys.argv
            sys.argv = old_argv

    except Exception as e:
        log_error("Error starting server", e)
        sys.exit(1)


if __name__ == "__main__":
    cli()
