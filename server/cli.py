"""
Browser Use MCP Server (CLI Interface)

This module provides the command-line interface for the Browser Use MCP server.
It orchestrates the setup and launch of the server components which are now
refactored into separate modules for better organization and adherence to the
Single Responsibility Principle.
"""

import logging
import os
import sys
import threading
import time
from typing import Optional

import click
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp.server.sse import SseServerTransport

load_dotenv() 

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)
PARENT_DIR = os.path.dirname(SERVER_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(
        0, PARENT_DIR
    )

from . import custom_logging
from .config import CONFIG
from .mcp_handlers import create_mcp_server
from .web_setup import create_starlette_app, run_server

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--port",
    default=8000,
    help="Port to listen on for SSE",
    type=int,
    show_default=True,
)
@click.option(
    "--proxy-port",
    default=None,
    type=int,
    help="Port for mcp-proxy to listen on. Activates proxy mode. If --stdio is also used, this port is for client connections to proxy.",
)
@click.option("--chrome-path", default=None, help="Path to Chrome executable", type=str)
@click.option(
    "--window-width",
    default=None,
    type=int,
    help="Browser window width (overrides config)",
)
@click.option(
    "--window-height",
    default=None,
    type=int,
    help="Browser window height (overrides config)",
)
@click.option(
    "--locale", default=None, help="Browser locale (overrides config)", type=str
)
@click.option(
    "--task-expiry-minutes",
    default=None,
    type=int,
    help="Minutes after which tasks are considered expired (overrides config)",
)
@click.option(
    "--stdio",
    is_flag=True,
    default=False,
    help="Enable mcp-proxy stdio mode (for chaining with other tools). Implies proxy mode.",
    show_default=True,
)
@click.option(
    "--json-response",
    is_flag=True,
    default=False,
    help="For StreamableHTTP: Enable plain JSON responses instead of SSE streams.",
    show_default=True,
)
@click.option(
    "--event-store-max-events-per-stream",
    default=None,
    type=int,
    help="For StreamableHTTP (InMemoryEventStore): Max events per session.",
    show_default=True,
)
def main(
    port: int,
    proxy_port: Optional[int],
    chrome_path: Optional[str],
    window_width: Optional[int],
    window_height: Optional[int],
    locale: Optional[str],
    task_expiry_minutes: Optional[int],
    stdio: bool,
    json_response: bool,
    event_store_max_events_per_stream: Optional[int],
) -> int:
    """
    Run the browser-use MCP server, orchestrating components from refactored modules.
    """
    logger.info("Initializing server with CLI arguments and configuration...")

    # Update global CONFIG with CLI parameters if they are provided
    if window_width is not None:
        CONFIG["DEFAULT_WINDOW_WIDTH"] = window_width
    if window_height is not None:
        CONFIG["DEFAULT_WINDOW_HEIGHT"] = window_height
    if locale is not None:
        CONFIG["DEFAULT_LOCALE"] = locale
    if task_expiry_minutes is not None:
        CONFIG["DEFAULT_TASK_EXPIRY_MINUTES"] = task_expiry_minutes
    CONFIG["PORT"] = port  

    CONFIG["JSON_RESPONSE"] = json_response
    if event_store_max_events_per_stream is not None:
        CONFIG["EVENT_STORE_MAX_EVENTS_PER_STREAM"] = event_store_max_events_per_stream

    if chrome_path:
        os.environ["CHROME_PATH"] = chrome_path
        logger.info(f"Using Chrome path explicitly set to: {chrome_path}")
    elif os.environ.get("CHROME_PATH"):
        logger.info(
            f"Using Chrome path from environment variable: {os.environ.get('CHROME_PATH')}"
        )
    else:
        logger.info(
            "No Chrome path specified (CLI or env), Playwright will use its default."
        )

    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
        logger.info(f"Language model initialized: {llm.model_name}")
    except Exception as e:
        logger.error(f"Failed to initialize Language Model: {e}")
        return 1

    mcp_app = create_mcp_server(
        llm=llm,
        window_width=CONFIG["DEFAULT_WINDOW_WIDTH"],
        window_height=CONFIG["DEFAULT_WINDOW_HEIGHT"],
        locale=CONFIG["DEFAULT_LOCALE"],
    )
    logger.info("MCP server instance configured.")

    starlette_app = create_starlette_app(mcp_app=mcp_app)
    logger.info("Starlette application with StreamableHTTP support created.")

    actual_proxy_port = proxy_port
    if stdio and actual_proxy_port is None:
        # If stdio is on and no specific proxy-port for client connections, mcp-proxy might not listen on a TCP port for clients.
        # It would primarily use stdin/stdout for communication with another tool.
        # We might still define a default if we expect clients to connect TO the proxy, even in stdio mode.
        # For now, let's assume if proxy_port is None in stdio, it means no external client port for the proxy.
        logger.info("--stdio mode enabled. mcp-proxy will use stdin/stdout.")
    elif stdio and actual_proxy_port is not None:
        logger.info(
            f"--stdio mode enabled. mcp-proxy will use stdin/stdout and also listen on port {actual_proxy_port} for SSE clients."
        )

    enable_proxy_mode = stdio or (proxy_port is not None)

    if enable_proxy_mode:
        import subprocess

        uvicorn_thread = threading.Thread(
            target=run_server, args=(starlette_app, port, None), daemon=True
        )
        uvicorn_thread.start()
        logger.info(
            f"Uvicorn server (for MCP StreamableHTTP) starting on port {port} in a background thread."
        )
        time.sleep(2)  # Brief pause for Uvicorn to initialize

        proxy_command_args = ["mcp-proxy"]
        # Target URL for mcp-proxy changed to /mcp_streamable (or your chosen path for StreamableHTTPSessionManager)
        # This assumes StreamableHTTPSessionManager handles GET requests on its base path for establishing the stream if json_response=False
        proxy_target_url = f"http://localhost:{port}/mcp_streamable"

        if stdio:
            proxy_command_args.append(proxy_target_url)
        else:
            proxy_command_args.append(proxy_target_url)

        if actual_proxy_port:
            proxy_command_args.extend(
                ["--sse-port", str(actual_proxy_port)]
            )

        proxy_command_args.extend(["--allow-origin", "*"])

        logger.info(f"Starting mcp-proxy with command: {' '.join(proxy_command_args)}")
        if actual_proxy_port and not stdio:
            logger.info(
                f"mcp-proxy expected to be accessible for clients on port {actual_proxy_port}."
            )
        elif stdio and actual_proxy_port:
            logger.info(
                f"mcp-proxy in stdio mode, also listening for clients on {actual_proxy_port}."
            )
        elif stdio:
            logger.info(
                "mcp-proxy in stdio mode, connected to another process via stdin/stdout."
            )

        try:
            # Bandit B603: subprocess_popen_with_shell_equals_true - not used here, shell=False is default
            # Bandit B607: start_process_with_partial_path - mcp-proxy should be in PATH
            proxy_process = subprocess.Popen(proxy_command_args)  # nosec B603 B607
            proxy_process.wait()
            logger.info(
                f"mcp-proxy process (PID: {proxy_process.pid}) has exited with code {proxy_process.returncode}."
            )
        except FileNotFoundError:
            logger.error(
                "mcp-proxy command not found. Please ensure it is installed and in your system PATH."
            )
            return 1
        except Exception as e:
            logger.error(f"An error occurred while running mcp-proxy: {e}")
            return 1
        finally:
            if uvicorn_thread.is_alive():
                logger.info(
                    "mcp-proxy exited. Uvicorn (daemon thread) will terminate when main thread exits."
                )
    else:
        logger.info(
            f"Running in direct StreamableHTTP mode on port {port}. mcp-proxy is not active."
        )
        run_server(starlette_app, port, None)

    logger.info("Server shutdown sequence initiated or main process ended.")
    return 0


if __name__ == "__main__":
    main()
