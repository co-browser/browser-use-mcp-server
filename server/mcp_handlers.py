import asyncio
import json
import logging
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import mcp.types as types
from langchain_core.language_models import BaseLanguageModel
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from .browser import run_browser_task_async, task_store
from .config import CONFIG
from .event_store import InMemoryEventStore

logger = logging.getLogger(__name__)


def create_mcp_server(
    llm: BaseLanguageModel,
    window_width: int,
    window_height: int,
    locale: str,
) -> Server:
    """
    Create and configure an MCP server for browser interaction.
    """
    app = Server("browser_use")

    # Event Store in place for resumability
    event_store = InMemoryEventStore()
    session_manager = StreamableHTTPSessionManager(
        app=app,
        event_store=event_store,
        json_response=False,
    )

    @app.call_tool()
    async def call_tool(
        name: str, arguments: dict, request: Optional[Any] = None
    ) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:

        # Get MCP context
        ctx = app.request_context
        if not ctx:
            logger.error("MCP request context not found. Cannot send streamed updates.")
            return [
                types.TextContent(
                    type="text", text=json.dumps({"error": "MCP context unavailable"})
                )
            ]

        if name == "browser_use":
            if "url" not in arguments:
                raise ValueError("Missing required argument 'url'")
            if "action" not in arguments:
                raise ValueError("Missing required argument 'action'")

            task_id = str(uuid.uuid4())
            task_store[task_id] = {
                "id": task_id,
                "status": "pending",
                "url": arguments["url"],
                "action": arguments["action"],
                "created_at": datetime.now().isoformat(),
            }

            # CDP info is expected to be part of the 'arguments' dictionary
            cdp_target_id = arguments.get("cdp_target_id")
            cdp_url = arguments.get("cdp_url")

            if cdp_target_id or cdp_url:
                logger.info(
                    f"Using CDP info from tool arguments - Target ID: {cdp_target_id}, URL: {cdp_url}"
                )
            else:
                logger.warning(
                    "CDP info (cdp_target_id, cdp_url) not found in tool arguments. Will proceed without specific CDP target."
                )

            logger.info(
                f"Final CDP parameters for run_browser_task_async - Target ID: {cdp_target_id}, URL: {cdp_url}"
            )

            _task = asyncio.create_task(
                run_browser_task_async(
                    task_id=task_id,
                    url=arguments["url"],
                    action=arguments["action"],
                    llm=llm,
                    window_width=window_width,
                    window_height=window_height,
                    locale=locale,
                    cdp_target_id=cdp_target_id,
                    cdp_url=cdp_url,
                    ctx=ctx.session,
                    mcp_request_id=ctx.request_id,
                    event_loop=asyncio.get_event_loop(),
                )
            )

            if CONFIG["PATIENT_MODE"]:
                try:
                    await _task
                    task_data = task_store[task_id]
                    if task_data["status"] == "failed":
                        logger.error(
                            f"Task {task_id} failed: {task_data.get('error', 'Unknown error')}"
                        )
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(task_data, indent=2),
                        )
                    ]
                except Exception as e:
                    logger.error(f"Error in patient mode execution: {str(e)}")
                    traceback_str = traceback.format_exc()
                    task_store[task_id]["status"] = "failed"
                    task_store[task_id]["error"] = str(e)
                    task_store[task_id]["traceback"] = traceback_str
                    task_store[task_id]["end_time"] = datetime.now().isoformat()
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(task_store[task_id], indent=2),
                        )
                    ]
            else:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "task_id": task_id,
                                "status": "pending",
                                "message": "Browser task initiated. Logs and results will be streamed directly.",
                                "estimated_time": f"{CONFIG['DEFAULT_ESTIMATED_TASK_SECONDS']} seconds",
                                "resource_uri": f"resource://browser_task/{task_id}",
                            },
                            indent=2,
                        ),
                    )
                ]
        else:
            raise ValueError(f"Unknown tool: {name}")

    @app.list_tools()
    async def list_tools() -> List[types.Tool]:
        patient_mode = CONFIG["PATIENT_MODE"]
        tool_description = (
            "Performs a browser action. Logs and results are streamed. "
            "In patient mode, this tool call will wait for completion and return the final result along with streamed updates."
            if patient_mode
            else "Performs a browser action. A task ID is returned, and logs and results are streamed asynchronously."
        )
        return [
            types.Tool(
                name="browser_use",
                description=tool_description,
                inputSchema={
                    "type": "object",
                    "required": ["url", "action"],
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to navigate to",
                        },
                        "action": {
                            "type": "string",
                            "description": "Action to perform in the browser",
                        },
                    },
                },
            )
        ]

    @app.list_resources()
    async def list_resources() -> List[types.Resource]:
        resources = []
        for task_id, task_data in task_store.items():
            if task_data["status"] in ["completed", "failed"]:
                resources.append(
                    types.Resource(
                        uri=f"resource://browser_task/{task_id}",
                        title=f"Browser Task Result: {task_id[:8]}",
                        description=f"Result of browser task for URL: {task_data.get('url', 'unknown')}",
                    )
                )
        return resources

    @app.read_resource()
    async def read_resource(uri: str) -> List[types.ResourceContents]:
        if not uri.startswith("resource://browser_task/"):
            return [
                types.ResourceContents(
                    type="text",
                    text=json.dumps(
                        {"error": f"Invalid resource URI: {uri}"}, indent=2
                    ),
                )
            ]
        task_id = uri.replace("resource://browser_task/", "")
        if task_id not in task_store:
            return [
                types.ResourceContents(
                    type="text",
                    text=json.dumps({"error": f"Task not found: {task_id}"}, indent=2),
                )
            ]
        return [
            types.ResourceContents(
                type="text", text=json.dumps(task_store[task_id], indent=2)
            )
        ]
    return app
