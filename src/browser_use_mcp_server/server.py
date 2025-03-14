"""
Core functionality for integrating browser-use with MCP.

This module provides the core components for integrating browser-use with the
Model-Control-Protocol (MCP) server. It supports browser automation via SSE transport.
"""

import os
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union, Awaitable

from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig, BrowserContext
import mcp.types as types
from mcp.server.lowlevel import Server

import logging
from dotenv import load_dotenv
import inspect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Task storage for async operations
task_store = {}

# Flag to track browser context health
browser_context_healthy = True


class MockContext:
    """Mock context for testing."""

    def __init__(self):
        pass


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self):
        pass

    # Define any necessary methods for testing here


def initialize_browser_context(
    chrome_path: Optional[str] = None,
    window_width: int = 1280,
    window_height: int = 1100,
    locale: str = "en-US",
    user_agent: Optional[str] = None,
    extra_chromium_args: Optional[List[str]] = None,
) -> BrowserContext:
    """
    Initialize the browser context with specified parameters.

    Args:
        chrome_path: Path to Chrome instance
        window_width: Browser window width
        window_height: Browser window height
        locale: Browser locale
        user_agent: Browser user agent
        extra_chromium_args: Additional arguments for Chrome

    Returns:
        Initialized BrowserContext
    """
    # Browser context configuration
    if not user_agent:
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36"
        )

    if not extra_chromium_args:
        extra_chromium_args = [
            "--no-sandbox",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--remote-debugging-port=9222",
        ]

    config = BrowserContextConfig(
        wait_for_network_idle_page_load_time=0.6,
        maximum_wait_page_load_time=1.2,
        minimum_wait_page_load_time=0.2,
        browser_window_size={"width": window_width, "height": window_height},
        locale=locale,
        user_agent=user_agent,
        highlight_elements=True,
        viewport_expansion=0,
    )

    # Initialize browser and context
    browser = Browser(
        config=BrowserConfig(
            chrome_instance_path=chrome_path or os.environ.get("CHROME_PATH"),
            extra_chromium_args=extra_chromium_args,
        )
    )

    return BrowserContext(browser=browser, config=config)


async def reset_browser_context(context: BrowserContext) -> None:
    """
    Reset the browser context to a clean state.

    Args:
        context: The browser context to reset
    """
    global browser_context_healthy

    try:
        logger.info("Resetting browser context...")

        # Check if browser is closed
        try:
            # Try a simple operation to check if browser is still alive
            if hasattr(context.browser, "new_context"):
                await context.browser.new_context()
                browser_context_healthy = True
                logger.info("Browser context reset successfully")
                return
        except Exception as e:
            logger.warning(f"Browser context appears to be closed: {e}")
            # Continue with reinitializing the browser

        # If we get here, we need to reinitialize the browser
        try:
            # Get the original configuration from the context if possible
            if hasattr(context, "config"):
                pass

            # Reinitialize the browser with the same configuration
            browser_config = BrowserConfig(
                chrome_path=os.environ.get("CHROME_PATH"),
                extra_chromium_args=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-dev-shm-usage",
                    "--remote-debugging-port=9222",
                ],
            )

            # Create a new browser instance
            browser = Browser(config=browser_config)
            await browser.initialize()

            # Create a new context with the same configuration as before
            context_config = BrowserContextConfig(
                wait_for_network_idle_page_load_time=0.6,
                maximum_wait_page_load_time=1.2,
                minimum_wait_page_load_time=0.2,
                browser_window_size={"width": 1280, "height": 1100},
                locale="en-US",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
                highlight_elements=True,
                viewport_expansion=0,
            )

            # Replace the old browser with the new one
            context.browser = browser
            context.config = context_config

            # Create a new browser context
            await context.browser.new_context(context_config)

            logger.info("Browser reinitialized successfully")
            browser_context_healthy = True
            return
        except Exception as e:
            logger.error(f"Failed to reinitialize browser: {e}")
            browser_context_healthy = False
            raise

    except Exception as e:
        browser_context_healthy = False
        logger.error(f"Failed to reset browser context: {e}")
        # Re-raise to allow caller to handle
        raise


async def check_browser_health(context: BrowserContext) -> bool:
    """
    Check if the browser context is healthy.

    Args:
        context: The browser context to check

    Returns:
        True if healthy, False otherwise
    """
    global browser_context_healthy

    # First, check if the browser context is already marked as unhealthy
    if not browser_context_healthy:
        logger.info("Browser context marked as unhealthy, attempting reset...")
        try:
            await reset_browser_context(context)
            logger.info("Browser context successfully reset")
            return True
        except Exception as e:
            logger.error(f"Failed to recover browser context: {e}")
            return False

    # Try a simple operation to check if browser is still alive
    try:
        # Check if browser is still responsive
        if hasattr(context.browser, "new_context"):
            # Just check if the method exists, don't actually call it
            browser_context_healthy = True
            logger.debug("Browser context appears healthy")
        else:
            # If the method doesn't exist, mark as unhealthy
            logger.warning("Browser context missing expected methods")
            browser_context_healthy = False
    except Exception as e:
        logger.warning(f"Error checking browser health: {e}")
        browser_context_healthy = False

    # If marked as unhealthy, try to reset
    if not browser_context_healthy:
        logger.info("Browser context appears unhealthy, attempting reset...")
        try:
            await reset_browser_context(context)
            logger.info("Browser context successfully reset")
            return True
        except Exception as e:
            logger.error(f"Failed to recover browser context: {e}")
            return False

    return True


async def run_browser_task_async(
    context: BrowserContext,
    llm: Any,
    task_id: str,
    url: str,
    action: str,
    custom_task_store: Optional[Dict[str, Any]] = None,
    step_callback: Optional[
        Callable[[Dict[str, Any], Dict[str, Any], int], Awaitable[None]]
    ] = None,
    done_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    task_expiry_minutes: int = 60,
    max_retries: int = 1,
) -> str:
    """
    Run a browser task asynchronously.

    Args:
        context: Browser context for the task
        llm: Language model to use for the agent
        task_id: Unique identifier for the task
        url: URL to navigate to
        action: Action description for the agent
        custom_task_store: Optional custom task store for tracking tasks
        step_callback: Optional callback for each step of the task
        done_callback: Optional callback for when the task is complete
        task_expiry_minutes: Minutes after which the task is considered expired
        max_retries: Maximum number of retries if the task fails due to browser issues

    Returns:
        Task ID
    """
    store = custom_task_store if custom_task_store is not None else task_store

    # Define steps for tracking progress
    store[task_id] = {
        "id": task_id,
        "url": url,
        "action": action,
        "status": "running",
        "start_time": datetime.now().isoformat(),
        "expiry_time": (
            datetime.now() + timedelta(minutes=task_expiry_minutes)
        ).isoformat(),
        "steps": [],
        "result": None,
        "error": None,
    }

    # Define default callbacks if not provided
    async def default_step_callback(browser_state, agent_output, step_number):
        """Default step callback that updates the task store."""
        store[task_id]["steps"].append(
            {
                "step": step_number,
                "browser_state": browser_state,
                "agent_output": agent_output,
                "timestamp": datetime.now().isoformat(),
            }
        )
        logger.info(f"Task {task_id}: Step {step_number} completed")

    async def default_done_callback(history):
        """Default done callback that updates the task store."""
        store[task_id]["status"] = "completed"
        store[task_id]["result"] = history
        store[task_id]["end_time"] = datetime.now().isoformat()
        logger.info(f"Task {task_id}: Completed successfully")

    step_cb = step_callback if step_callback is not None else default_step_callback
    done_cb = done_callback if done_callback is not None else default_done_callback

    retries = 0
    while retries <= max_retries:
        try:
            # Check and ensure browser health
            browser_healthy = await check_browser_health(context)
            if not browser_healthy:
                raise Exception("Browser context is unhealthy")

            # Create agent and run task
            try:
                # Inspect Agent class initialization parameters
                agent_params = inspect.signature(Agent.__init__).parameters
                logger.info(f"Agent init parameters: {list(agent_params.keys())}")

                # Adapt initialization based on available parameters
                agent_kwargs = {"context": context}

                if "llm" in agent_params:
                    agent_kwargs["llm"] = llm

                # Add task parameter which is required based on the error message
                if "task" in agent_params:
                    # Create a task that combines navigation and the action
                    task_description = f"First, navigate to {url}. Then, {action}"
                    agent_kwargs["task"] = task_description

                # Add browser and browser_context parameters if they're required
                if "browser" in agent_params:
                    agent_kwargs["browser"] = context.browser
                if "browser_context" in agent_params:
                    agent_kwargs["browser_context"] = context

                # Check for callbacks
                if "step_callback" in agent_params:
                    agent_kwargs["step_callback"] = step_cb
                if "done_callback" in agent_params:
                    agent_kwargs["done_callback"] = done_cb

                # Register callbacks with the new parameter names if the old ones don't exist
                if (
                    "step_callback" not in agent_params
                    and "register_new_step_callback" in agent_params
                ):
                    agent_kwargs["register_new_step_callback"] = step_cb
                if (
                    "done_callback" not in agent_params
                    and "register_done_callback" in agent_params
                ):
                    agent_kwargs["register_done_callback"] = done_cb

                # Check if all required parameters are set
                missing_params = []
                for param_name, param in agent_params.items():
                    if (
                        param.default == inspect.Parameter.empty
                        and param_name != "self"
                        and param_name not in agent_kwargs
                    ):
                        missing_params.append(param_name)

                if missing_params:
                    logger.error(
                        f"Missing required parameters for Agent: {missing_params}"
                    )
                    raise Exception(
                        f"Missing required parameters for Agent: {missing_params}"
                    )

                # Create agent with appropriate parameters
                agent = Agent(**agent_kwargs)

                # Launch task asynchronously
                # Don't pass any parameters to run() as they should already be set via init
                asyncio.create_task(agent.run())
                return task_id
            except Exception as agent_error:
                logger.error(f"Error creating Agent: {str(agent_error)}")
                raise Exception(f"Failed to create browser agent: {str(agent_error)}")

        except Exception as e:
            # Update task store with error
            store[task_id]["error"] = str(e)
            logger.error(f"Task {task_id}: Error - {str(e)}")

            # If we've reached max retries, mark as error and exit
            if retries >= max_retries:
                store[task_id]["status"] = "error"
                store[task_id]["end_time"] = datetime.now().isoformat()
                logger.error(f"Task {task_id}: Failed after {retries + 1} attempts")
                raise

            # Otherwise, try to reset the browser context and retry
            retries += 1
            logger.info(f"Task {task_id}: Retry attempt {retries}/{max_retries}")

            try:
                # Reset browser context before retrying
                await reset_browser_context(context)
                logger.info(f"Task {task_id}: Browser context reset for retry")
            except Exception as reset_error:
                logger.error(
                    f"Task {task_id}: Failed to reset browser context: {str(reset_error)}"
                )
                # Continue with retry even if reset fails

    # This should never be reached due to the raise in the loop
    return task_id


def create_mcp_server(
    context: BrowserContext,
    llm: Any,
    custom_task_store: Optional[Dict[str, Any]] = None,
    task_expiry_minutes: int = 60,
) -> Server:
    """
    Create an MCP server with browser capabilities.

    Args:
        context: Browser context for the server
        llm: Language model to use for the agent
        custom_task_store: Optional custom task store for tracking tasks
        task_expiry_minutes: Minutes after which tasks are considered expired

    Returns:
        Configured MCP server
    """
    # Use provided task store or default
    store = custom_task_store if custom_task_store is not None else task_store

    # Create MCP server
    app = Server(name="browser-use-mcp-server")

    @app.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
        """
        Handle tool calls from the MCP client.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            List of content items
        """
        logger.info(f"Tool call received: {name} with arguments: {arguments}")

        if name == "mcp__browser_navigate":
            # Validate required arguments
            if "url" not in arguments:
                logger.error("URL argument missing in browser.navigate call")
                return [types.TextContent(type="text", text="Error: URL is required")]

            url = arguments["url"]
            action = arguments.get(
                "action", "Navigate to the given URL and tell me what you see."
            )

            logger.info(f"Navigation request to URL: {url} with action: {action}")

            # Generate unique task ID
            task_id = str(uuid.uuid4())

            try:
                # Run browser task
                await run_browser_task_async(
                    context=context,
                    llm=llm,
                    task_id=task_id,
                    url=url,
                    action=action,
                    custom_task_store=store,
                    task_expiry_minutes=task_expiry_minutes,
                )

                logger.info(f"Navigation task {task_id} started successfully")

                # Return a simpler response with just TextContent to avoid validation errors
                return [
                    types.TextContent(
                        type="text",
                        text=f"Navigating to {url}. Task {task_id} started successfully. Results will be available when task completes.",
                    )
                ]

            except Exception as e:
                logger.error(f"Error executing navigation task: {str(e)}")
                return [
                    types.TextContent(
                        type="text", text=f"Error navigating to {url}: {str(e)}"
                    )
                ]

        elif name == "mcp__browser_use":
            # Validate required arguments
            if "url" not in arguments:
                logger.error("URL argument missing in browser_use call")
                return [types.TextContent(type="text", text="Error: URL is required")]

            if "action" not in arguments:
                logger.error("Action argument missing in browser_use call")
                return [
                    types.TextContent(type="text", text="Error: Action is required")
                ]

            url = arguments["url"]
            action = arguments["action"]

            logger.info(f"Browser use request to URL: {url} with action: {action}")

            # Generate unique task ID
            task_id = str(uuid.uuid4())

            try:
                # Run browser task
                await run_browser_task_async(
                    context=context,
                    llm=llm,
                    task_id=task_id,
                    url=url,
                    action=action,
                    custom_task_store=store,
                    task_expiry_minutes=task_expiry_minutes,
                )

                logger.info(f"Browser task {task_id} started successfully")

                # Return task ID for async execution
                return [
                    types.TextContent(
                        type="text",
                        text=f"Task {task_id} started. Use mcp__browser_get_result with this task ID to get results when complete.",
                    )
                ]

            except Exception as e:
                logger.error(f"Error executing browser task: {str(e)}")
                return [
                    types.TextContent(
                        type="text", text=f"Error executing browser task: {str(e)}"
                    )
                ]

        elif name == "mcp__browser_get_result":
            # Validate required arguments
            if "task_id" not in arguments:
                logger.error("Task ID argument missing in browser_get_result call")
                return [
                    types.TextContent(type="text", text="Error: Task ID is required")
                ]

            task_id = arguments["task_id"]
            logger.info(f"Result request for task: {task_id}")

            # Check if task exists
            if task_id not in store:
                return [
                    types.TextContent(
                        type="text", text=f"Error: Task {task_id} not found"
                    )
                ]

            task = store[task_id]

            # Check task status
            if task["status"] == "error":
                return [types.TextContent(type="text", text=f"Error: {task['error']}")]

            if task["status"] == "running":
                # For running tasks, return the steps completed so far
                steps_text = "\n".join(
                    [
                        f"Step {s['step']}: {s['agent_output'].get('action', 'Unknown action')}"
                        for s in task["steps"]
                    ]
                )
                return [
                    types.TextContent(
                        type="text",
                        text=f"Task {task_id} is still running.\n\nSteps completed so far:\n{steps_text}",
                    )
                ]

            # For completed tasks, return the full result
            if task["result"]:
                # Format the result as text
                result_text = "Task completed successfully.\n\n"
                result_text += f"URL: {task['url']}\n\n"
                result_text += f"Action: {task['action']}\n\n"

                # Add final result if available
                if isinstance(task["result"], dict) and "text" in task["result"]:
                    result_text += f"Result: {task['result']['text']}\n\n"
                elif isinstance(task["result"], str):
                    result_text += f"Result: {task['result']}\n\n"
                else:
                    # Try to extract result from the last step
                    if task["steps"] and task["steps"][-1].get("agent_output"):
                        last_output = task["steps"][-1]["agent_output"]
                        if "done" in last_output and "text" in last_output["done"]:
                            result_text += f"Result: {last_output['done']['text']}\n\n"

                return [
                    types.TextContent(
                        type="text",
                        text=result_text,
                    )
                ]

            # Fallback for unexpected cases
            return [
                types.TextContent(
                    type="text",
                    text=f"Task {task_id} completed with status '{task['status']}' but no results are available.",
                )
            ]

        elif name == "mcp__browser_health":
            try:
                # Check browser health
                logger.info("Health check requested")
                healthy = await check_browser_health(context)
                status = "healthy" if healthy else "unhealthy"
                logger.info(f"Browser health status: {status}")
                return [
                    types.TextContent(type="text", text=f"Browser status: {status}")
                ]

            except Exception as e:
                logger.error(f"Error checking browser health: {str(e)}")
                return [
                    types.TextContent(
                        type="text", text=f"Error checking browser health: {str(e)}"
                    )
                ]

        elif name == "mcp__browser_reset":
            try:
                # Reset browser context
                logger.info("Browser reset requested")
                await reset_browser_context(context)
                logger.info("Browser context reset successful")
                return [
                    types.TextContent(
                        type="text", text="Browser context reset successfully"
                    )
                ]

            except Exception as e:
                logger.error(f"Error resetting browser context: {str(e)}")
                return [
                    types.TextContent(
                        type="text", text=f"Error resetting browser context: {str(e)}"
                    )
                ]

        else:
            logger.warning(f"Unknown tool requested: {name}")
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        """
        List available tools for the MCP client.

        Returns:
            List of available tools
        """
        try:
            logger.info("list_tools called - preparing to return tools")
            tools = [
                types.Tool(
                    name="mcp__browser_navigate",
                    description="Navigate to a URL and perform an action. This is a synchronous operation that will return when the task is complete.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL to navigate to",
                            },
                            "action": {
                                "type": "string",
                                "description": "The action to perform on the page",
                            },
                        },
                        "required": ["url"],
                    },
                ),
                types.Tool(
                    name="mcp__browser_use",
                    description="Performs a browser action asynchronously and returns a task ID. Use mcp__browser_get_result with the returned task ID to check the status and get results.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to navigate to",
                            },
                            "action": {
                                "type": "string",
                                "description": "Action to perform in the browser (e.g., 'Extract all headlines', 'Search for X')",
                            },
                        },
                        "required": ["url", "action"],
                    },
                ),
                types.Tool(
                    name="mcp__browser_get_result",
                    description="Gets the result of an asynchronous browser task. Use this to check the status of a task started with mcp__browser_use.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "ID of the task to get results for",
                            },
                        },
                        "required": ["task_id"],
                    },
                ),
                types.Tool(
                    name="mcp__browser_health",
                    description="Check browser health status and attempt recovery if needed",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                types.Tool(
                    name="mcp__browser_reset",
                    description="Force reset of the browser context to recover from errors",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            ]
            logger.info(f"Successfully prepared {len(tools)} tools")
            return tools
        except Exception as e:
            logger.error(f"Error in list_tools: {str(e)}")
            raise

    @app.list_resources()
    async def list_resources() -> list[types.Resource]:
        """
        List available resources for the MCP client.

        Returns:
            List of available resources
        """
        resources = []

        # Add all completed tasks as resources
        for task_id, task in store.items():
            if task["status"] in ["completed", "error"]:
                resources.append(
                    types.Resource(
                        uri=f"browser-task://{task_id}",
                        title=f"Browser Task: {task['url']}",
                        description=f"Status: {task['status']}",
                    )
                )

        return resources

    @app.read_resource()
    async def read_resource(uri: str) -> list[types.ResourceContents]:
        """
        Read resource content by URI.

        Args:
            uri: Resource URI

        Returns:
            Resource contents
        """
        # Extract task ID from URI
        if not uri.startswith("browser-task://"):
            return [types.ResourceContents(error="Invalid resource URI format")]

        task_id = uri[15:]  # Remove "browser-task://" prefix

        # Check if task exists
        if task_id not in store:
            return [types.ResourceContents(error=f"Task {task_id} not found")]

        task = store[task_id]

        # Check task status
        if task["status"] == "error":
            return [
                types.ResourceContents(
                    mimetype="text/plain",
                    contents=f"Error: {task['error']}",
                )
            ]

        if task["status"] == "running":
            # For running tasks, return the steps completed so far
            steps_text = "\n".join(
                [
                    f"Step {s['step']}: {s['agent_output'].get('action', 'Unknown action')}"
                    for s in task["steps"]
                ]
            )
            return [
                types.ResourceContents(
                    mimetype="text/plain",
                    contents=f"Task {task_id} is still running.\n\nSteps completed so far:\n{steps_text}",
                )
            ]

        # For completed tasks, return the full result
        if task["result"]:
            # Format the result as markdown
            result_text = "# Browser Task Report\n\n"
            result_text += f"URL: {task['url']}\n\n"
            result_text += f"Action: {task['action']}\n\n"
            result_text += f"Start Time: {task['start_time']}\n\n"
            result_text += f"End Time: {task['end_time']}\n\n"

            # Add steps
            result_text += "## Steps\n\n"
            for step in task["steps"]:
                result_text += f"### Step {step['step']}\n\n"
                result_text += f"Time: {step['timestamp']}\n\n"

                # Add agent output
                if "agent_output" in step and step["agent_output"]:
                    result_text += "#### Agent Output\n\n"
                    action = step["agent_output"].get("action", "Unknown action")
                    result_text += f"Action: {action}\n\n"

                    # Add agent thoughts if available
                    if "thought" in step["agent_output"]:
                        result_text += f"Thought: {step['agent_output']['thought']}\n\n"

                # Add browser state snapshot
                if "browser_state" in step and step["browser_state"]:
                    result_text += "#### Browser State\n\n"

                    # Add page title if available
                    if "page_title" in step["browser_state"]:
                        result_text += (
                            f"Page Title: {step['browser_state']['page_title']}\n\n"
                        )

                    # Add URL if available
                    if "url" in step["browser_state"]:
                        result_text += f"URL: {step['browser_state']['url']}\n\n"

                    # Add screenshot if available
                    if "screenshot" in step["browser_state"]:
                        result_text += (
                            "Screenshot available but not included in text output.\n\n"
                        )

            # Return formatted result
            return [
                types.ResourceContents(
                    mimetype="text/markdown",
                    contents=result_text,
                )
            ]

        # Fallback for unexpected cases
        return [
            types.ResourceContents(
                mimetype="text/plain",
                contents=f"Task {task_id} completed with status '{task['status']}' but no results are available.",
            )
        ]

    return app
