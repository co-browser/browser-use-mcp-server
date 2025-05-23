import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Optional

import uvicorn
from mcp.server import Server as MCPCoreServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

# Imports from our refactored modules
from .browser import cleanup_old_tasks
from .config import CONFIG
from .custom_logging import TaskLogListHandler
from .event_store import InMemoryEventStore

logger = logging.getLogger(__name__)


def create_starlette_app(mcp_app: MCPCoreServer) -> Starlette:
    """Creates and configures the Starlette application for Streamable HTTP MCP."""

    event_store = InMemoryEventStore(
        max_events_per_stream=CONFIG["EVENT_STORE_MAX_EVENTS_PER_STREAM"]
    )
    streamable_http_session_manager = StreamableHTTPSessionManager(
        app=mcp_app,
        event_store=event_store,
        json_response=CONFIG["JSON_RESPONSE"],
    )

    async def handle_streamable_http_request(
        scope: Scope, receive: Receive, send: Send
    ) -> None:
        """ASGI handler for streamable HTTP connections using StreamableHTTPSessionManager."""
        await streamable_http_session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan_manager(app_instance: Starlette) -> AsyncIterator[None]:
        logger.info("Application lifespan startup sequence initiated...")
        # Validate essential configurations from CONFIG
        port = CONFIG.get("PORT", 8000)
        window_width = CONFIG["DEFAULT_WINDOW_WIDTH"]
        window_height = CONFIG["DEFAULT_WINDOW_HEIGHT"]
        task_expiry_minutes = CONFIG["DEFAULT_TASK_EXPIRY_MINUTES"]

        if not (0 < port <= 65535):
            logger.error(f"Invalid port number: {port}")
            raise ValueError(f"Invalid port number: {port}")
        if window_width <= 0 or window_height <= 0:
            logger.error(f"Invalid window dimensions: {window_width}x{window_height}")
            raise ValueError(
                f"Invalid window dimensions: {window_width}x{window_height}"
            )
        if task_expiry_minutes <= 0:
            logger.error(f"Invalid task expiry minutes: {task_expiry_minutes}")
            raise ValueError(f"Invalid task expiry minutes: {task_expiry_minutes}")

        # Schedule the background task for cleaning up old tasks
        cleanup_task = asyncio.create_task(cleanup_old_tasks())
        logger.info("Task cleanup process scheduled.")

        # Run the StreamableHTTPSessionManager
        async with streamable_http_session_manager.run():
            logger.info("StreamableHTTPSessionManager started.")
            try:
                yield  # Application is running
            finally:
                logger.info("Application shutting down...")
                # Cancel background tasks if they are still running
                if not cleanup_task.done():
                    cleanup_task.cancel()
                    try:
                        await cleanup_task
                    except asyncio.CancelledError:
                        logger.info("Task cleanup process cancelled successfully.")
                logger.info(
                    "StreamableHTTPSessionManager and other resources shut down."
                )

    starlette_app = Starlette(
        debug=True,
        routes=[
            Mount("/mcp_streamable", app=handle_streamable_http_request),
        ],
        lifespan=lifespan_manager,
    )

    return starlette_app


def run_server(starlette_app: Starlette, port: int, log_config: Optional[dict] = None):
    """Runs the Uvicorn server with the provided Starlette app."""
    # Default log_config for JSON logging if not provided
    # This replicates the JSON logging setup previously in server.py's main/run_uvicorn
    # The custom_logging.py module already configures root and uvicorn loggers.
    # Uvicorn's own log_config might override or supplement this.
    # For simplicity, we'll rely on the setup in custom_logging.py and uvicorn's default behavior
    # unless a specific uvicorn log_config is passed.

    # The log_config for uvicorn.run should ideally align with what custom_logging.py sets up.
    # If custom_logging.JSON_FORMATTER is used, uvicorn needs to be told to use it.
    # The setup_root_logger in custom_logging.py already adds a JSONFormatted StreamHandler to uvicorn loggers.
    # So, passing a log_config here might be redundant or cause conflicts if not carefully managed.
    # Let's ensure uvicorn uses the handlers set up by custom_logging.
    # We can pass `log_config=None` to uvicorn.run if our custom_logging.py sufficiently configures uvicorn loggers.
    # Or, construct a uvicorn-specific log_config that uses the shared JSON_FORMATTER.

    final_log_config = log_config
    if final_log_config is None:
        # This ensures uvicorn uses the handlers we configured in custom_logging.py
        # by not overriding them with its own default textual format. We tell it to use our existing handlers.
        final_log_config = {
            "version": 1,
            "disable_existing_loggers": False,  # Crucial to not disable our custom JSON loggers
            "handlers": {},
            "loggers": {
                "uvicorn": {
                    "handlers": [],
                    "level": "INFO",
                    "propagate": False,
                },  # Already handled by custom_logging
                "uvicorn.error": {"handlers": [], "level": "INFO", "propagate": False},
                "uvicorn.access": {"handlers": [], "level": "INFO", "propagate": False},
            },
        }
        # If relying purely on custom_logging.py, you might even pass log_config=None to uvicorn,
        # but explicitly defining it like above to *not* use uvicorn's default stream handlers is safer.

    uvicorn.run(
        starlette_app,
        host="0.0.0.0",
        port=port,
        log_config=final_log_config,  # Use the potentially modified log_config
        log_level="info",  # This sets the level for uvicorn's own log messages if not specified in log_config
    )
