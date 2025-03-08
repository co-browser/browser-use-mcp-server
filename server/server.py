import anyio
import click
import asyncio
import uuid
import os
from datetime import datetime
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
import mcp.types as types
from mcp.server.lowlevel import Server
from dotenv import load_dotenv
import json
import logging
from browser_use.browser.context import BrowserContextConfig, BrowserContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Browser context configuration
config = BrowserContextConfig(
    wait_for_network_idle_page_load_time=0.6,
    maximum_wait_page_load_time=1.2,
    minimum_wait_page_load_time=0.2,
    browser_window_size={"width": 1280, "height": 1100},
    locale="en-US",
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
    highlight_elements=True,
    viewport_expansion=0,
)

# Initialize browser and context
browser = Browser(
    config=BrowserConfig(
        chrome_instance_path=os.environ.get("CHROME_PATH"),
    )
)
context = BrowserContext(browser=browser, config=config)

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

# Flag to track browser context health
browser_context_healthy = True

# Task storage for async operations
task_store = {}


async def reset_browser_context():
    """Reset the browser context to a clean state."""
    global context, browser, browser_context_healthy

    logger.info("Resetting browser context")
    try:
        # Try to close the existing context
        try:
            await context.close()
        except Exception as e:
            logger.warning(f"Error closing browser context: {str(e)}")

        # Create a new context
        context = BrowserContext(browser=browser, config=config)
        browser_context_healthy = True
        logger.info("Browser context reset successfully")
    except Exception as e:
        logger.error(f"Failed to reset browser context: {str(e)}")
        browser_context_healthy = False
        # If we can't reset the context, try to reset the browser
        try:
            await browser.close()
            browser = Browser()
            context = BrowserContext(browser=browser, config=config)
            browser_context_healthy = True
            logger.info("Browser reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset browser: {str(e)}")
            browser_context_healthy = False


async def check_browser_health():
    """Check if the browser context is healthy."""
    global browser_context_healthy

    if not browser_context_healthy:
        await reset_browser_context()
        return browser_context_healthy

    try:
        # Simple health check - try to get the current page
        await context.get_current_page()
        return True
    except Exception as e:
        logger.warning(f"Browser health check failed: {str(e)}")
        browser_context_healthy = False
        await reset_browser_context()
        return browser_context_healthy


async def run_browser_task_async(task_id, url, action):
    """Run a browser task asynchronously and store the result."""
    try:
        # Update task status to running
        task_store[task_id]["status"] = "running"
        task_store[task_id]["start_time"] = datetime.now().isoformat()
        task_store[task_id]["progress"] = {
            "current_step": 0,
            "total_steps": 0,
            "steps": [],
        }

        # Reset browser context to ensure a clean state
        await reset_browser_context()

        # Check browser health
        if not await check_browser_health():
            task_store[task_id]["status"] = "failed"
            task_store[task_id]["end_time"] = datetime.now().isoformat()
            task_store[task_id][
                "error"
            ] = "Browser context is unhealthy and could not be reset"
            return

        # Define step callback function with the correct signature
        async def step_callback(browser_state, agent_output, step_number):
            # Update progress in task store
            task_store[task_id]["progress"]["current_step"] = step_number
            task_store[task_id]["progress"]["total_steps"] = max(
                task_store[task_id]["progress"]["total_steps"], step_number
            )

            # Add step info with minimal details
            step_info = {"step": step_number, "time": datetime.now().isoformat()}

            # Add goal if available
            if agent_output and hasattr(agent_output, "current_state"):
                if hasattr(agent_output.current_state, "next_goal"):
                    step_info["goal"] = agent_output.current_state.next_goal

            # Add to progress steps
            task_store[task_id]["progress"]["steps"].append(step_info)

            # Log progress
            logger.info(f"Task {task_id}: Step {step_number} completed")

        # Define done callback function with the correct signature
        async def done_callback(history):
            # Log completion
            logger.info(f"Task {task_id}: Completed with {len(history.history)} steps")

            # Add final step
            current_step = task_store[task_id]["progress"]["current_step"] + 1
            task_store[task_id]["progress"]["steps"].append(
                {
                    "step": current_step,
                    "time": datetime.now().isoformat(),
                    "status": "completed",
                }
            )

        # Use the existing browser context with callbacks
        agent = Agent(
            task=f"First, navigate to {url}. Then, {action}",
            llm=llm,
            browser_context=context,
            register_new_step_callback=step_callback,
            register_done_callback=done_callback,
        )

        # Run the agent
        ret = await agent.run(max_steps=10)

        # Get the final result
        final_result = ret.final_result()

        # Check if we have a valid result
        if final_result and hasattr(final_result, "raise_for_status"):
            final_result.raise_for_status()
            result_text = str(final_result.text)
        else:
            result_text = (
                str(final_result) if final_result else "No final result available"
            )

        # Gather essential information from the agent history
        is_successful = ret.is_successful()
        has_errors = ret.has_errors()
        errors = ret.errors()
        urls_visited = ret.urls()
        action_names = ret.action_names()
        extracted_content = ret.extracted_content()
        steps_taken = ret.number_of_steps()

        # Create a focused response with the most relevant information for an LLM
        response_data = {
            "final_result": result_text,
            "success": is_successful,
            "has_errors": has_errors,
            "errors": [str(err) for err in errors if err],
            "urls_visited": [str(url) for url in urls_visited if url],
            "actions_performed": action_names,
            "extracted_content": extracted_content,
            "steps_taken": steps_taken,
        }

        # Store the result
        task_store[task_id]["status"] = "completed"
        task_store[task_id]["end_time"] = datetime.now().isoformat()
        task_store[task_id]["result"] = response_data

    except Exception as e:
        logger.error(f"Error in async browser task: {str(e)}")
        import traceback

        tb = traceback.format_exc()

        # Mark the browser context as unhealthy
        global browser_context_healthy
        browser_context_healthy = False

        # Store the error
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["end_time"] = datetime.now().isoformat()
        task_store[task_id]["error"] = str(e)
        task_store[task_id]["traceback"] = tb

    finally:
        # Always try to reset the browser context to a clean state after use
        try:
            current_page = await context.get_current_page()
            await current_page.goto("about:blank")
        except Exception as e:
            logger.warning(f"Error resetting page state: {str(e)}")
            browser_context_healthy = False


@click.command()
@click.option("--port", default=8000, help="Port to listen on for SSE")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
def main(port: int, transport: str) -> int:
    load_dotenv()
    app = Server("browser_use")

    @app.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        global browser_context_healthy

        # Handle different tool types
        if name == "browser_use":
            # Check required arguments
            if "url" not in arguments:
                raise ValueError("Missing required argument 'url'")
            if "action" not in arguments:
                raise ValueError("Missing required argument 'action'")

            # Generate a task ID
            task_id = str(uuid.uuid4())

            # Initialize task in store
            task_store[task_id] = {
                "id": task_id,
                "status": "pending",
                "url": arguments["url"],
                "action": arguments["action"],
                "created_at": datetime.now().isoformat(),
            }

            # Start task in background
            asyncio.create_task(
                run_browser_task_async(task_id, arguments["url"], arguments["action"])
            )

            # Estimate task duration
            estimated_seconds = 60  # Default estimate of 60 seconds

            # Return task ID immediately with explicit sleep instruction
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "task_id": task_id,
                            "status": "pending",
                            "message": f"Browser task started. Please wait for {estimated_seconds} seconds, then check the result using browser_get_result or the resource URI. Always wait exactly 5 seconds between status checks.",
                            "estimated_time": f"{estimated_seconds} seconds",
                            "resource_uri": f"resource://browser_task/{task_id}",
                            "sleep_command": "sleep 5",
                            "instruction": "Use the terminal command 'sleep 5' to wait 5 seconds between status checks. IMPORTANT: Always use exactly 5 seconds, no more and no less.",
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "browser_get_result":
            # Get result of async task
            if "task_id" not in arguments:
                raise ValueError("Missing required argument 'task_id'")

            task_id = arguments["task_id"]

            if task_id not in task_store:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": "Task not found", "task_id": task_id}, indent=2
                        ),
                    )
                ]

            # Get the current task data
            task_data = task_store[task_id].copy()

            # If task is still running, add simple guidance
            if task_data["status"] == "running":
                # Add a simple next check suggestion
                progress = task_data.get("progress", {})
                current_step = progress.get("current_step", 0)

                if current_step > 0:
                    # Simple message based on current step
                    task_data["message"] = (
                        f"Task is running (step {current_step}). Wait 5 seconds before checking again."
                    )
                    task_data["sleep_command"] = "sleep 5"
                    task_data["instruction"] = (
                        "Use the terminal command 'sleep 5' to wait 5 seconds before checking again. IMPORTANT: Always use exactly 5 seconds, no more and no less."
                    )
                else:
                    task_data["message"] = (
                        "Task is starting. Wait 5 seconds before checking again."
                    )
                    task_data["sleep_command"] = "sleep 5"
                    task_data["instruction"] = (
                        "Use the terminal command 'sleep 5' to wait 5 seconds before checking again. IMPORTANT: Always use exactly 5 seconds, no more and no less."
                    )

            # Return current task status and result if available
            return [
                types.TextContent(type="text", text=json.dumps(task_data, indent=2))
            ]

        else:
            raise ValueError(f"Unknown tool: {name}")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="browser_use",
                description="Performs a browser action and returns a task ID for async execution",
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
            ),
            types.Tool(
                name="browser_get_result",
                description="Gets the result of an asynchronous browser task",
                inputSchema={
                    "type": "object",
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "ID of the task to get results for",
                        }
                    },
                },
            ),
        ]

    @app.list_resources()
    async def list_resources() -> list[types.Resource]:
        # List all completed tasks as resources
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
    async def read_resource(uri: str) -> list[types.ResourceContents]:
        # Extract task ID from URI
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

        # Return task data
        return [
            types.ResourceContents(
                type="text", text=json.dumps(task_store[task_id], indent=2)
            )
        ]

    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            try:
                async with sse.connect_sse(
                    request.scope, request.receive, request._send
                ) as streams:
                    await app.run(
                        streams[0], streams[1], app.create_initialization_options()
                    )
            except Exception as e:
                logger.error(f"Error in handle_sse: {str(e)}")
                # Ensure browser context is reset if there's an error
                asyncio.create_task(reset_browser_context())
                raise

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        import uvicorn

        # Add a startup event to initialize the browser
        @starlette_app.on_event("startup")
        async def startup_event():
            logger.info("Starting browser context...")
            await reset_browser_context()
            logger.info("Browser context started")

            # Start background task cleanup
            asyncio.create_task(cleanup_old_tasks())

        @starlette_app.on_event("shutdown")
        async def shutdown_event():
            logger.info("Shutting down browser context...")
            await browser.close()
            logger.info("Browser context closed")

        async def cleanup_old_tasks():
            """Periodically clean up old completed tasks to prevent memory leaks."""
            while True:
                try:
                    # Sleep first to avoid cleaning up tasks too early
                    await asyncio.sleep(3600)  # Run cleanup every hour

                    current_time = datetime.now()
                    tasks_to_remove = []

                    # Find completed tasks older than 1 hour
                    for task_id, task_data in task_store.items():
                        if (
                            task_data["status"] in ["completed", "failed"]
                            and "end_time" in task_data
                        ):
                            end_time = datetime.fromisoformat(task_data["end_time"])
                            hours_elapsed = (
                                current_time - end_time
                            ).total_seconds() / 3600

                            if hours_elapsed > 1:  # Remove tasks older than 1 hour
                                tasks_to_remove.append(task_id)

                    # Remove old tasks
                    for task_id in tasks_to_remove:
                        del task_store[task_id]

                    if tasks_to_remove:
                        logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")

                except Exception as e:
                    logger.error(f"Error in task cleanup: {str(e)}")

        uvicorn.run(starlette_app, host="0.0.0.0", port=port)
    else:
        from mcp.server.stdio import stdio_server

        async def arun():
            try:
                # Ensure browser context is healthy before starting
                await check_browser_health()

                async with stdio_server() as streams:
                    await app.run(
                        streams[0], streams[1], app.create_initialization_options()
                    )
            except Exception as e:
                logger.error(f"Error in arun: {str(e)}")
                # Ensure browser context is reset if there's an error
                await reset_browser_context()
            finally:
                # Clean up resources
                try:
                    await context.close()
                    await browser.close()
                except Exception as e:
                    logger.error(f"Error cleaning up resources: {str(e)}")

        anyio.run(arun)

    return 0
