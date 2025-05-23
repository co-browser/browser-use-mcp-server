import asyncio
import json
import logging
import os
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Literal
import sys

import mcp.types as types
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import (
    BrowserContext,
    BrowserContextConfig,
    BrowserContextState,
)
from browser_use.controller.service import Controller
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from .config import CONFIG
from .custom_logging import TaskLogListHandler

logger = logging.getLogger(__name__) 

task_store: Dict[str, Dict[str, Any]] = {}


class TextStreamPartParams(BaseModel):
    """Parameters for a text stream part notification."""

    type: Literal["text_stream_part"] = Field(default="text_stream_part", frozen=True)
    text: str


class TextStreamPartNotification(BaseModel):
    """Custom notification model for sending text stream parts."""

    method: Literal["text_stream_event"] = Field(
        default="text_stream_event", frozen=True
    )
    params: TextStreamPartParams


async def create_browser_context_for_task(
    chrome_path: Optional[str] = None,
    window_width: int = CONFIG["DEFAULT_WINDOW_WIDTH"],
    window_height: int = CONFIG["DEFAULT_WINDOW_HEIGHT"],
    locale: str = CONFIG["DEFAULT_LOCALE"],
    cdp_target_id: Optional[str] = None,
    cdp_url: Optional[str] = None,
    ctx: Optional[Any] = None,
    mcp_request_id: Optional[str] = None,
    event_loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Tuple[Browser, BrowserContext, Controller]:
    """
    Create a fresh browser and context for a task.
    """
    try:
        browser_config = BrowserConfig(
            extra_chromium_args=CONFIG["BROWSER_ARGS"],
        )
        if chrome_path:
            browser_config.chrome_instance_path = chrome_path
        if cdp_url:
            browser_config.cdp_url = cdp_url
            logger.info(f"Using CDP URL: {cdp_url}")

        browser = Browser(config=browser_config)
        context_config = BrowserContextConfig(
            wait_for_network_idle_page_load_time=0.6,
            maximum_wait_page_load_time=1.2,
            minimum_wait_page_load_time=0.2,
            browser_window_size={"width": window_width, "height": window_height},
            locale=locale,
            user_agent=CONFIG["DEFAULT_USER_AGENT"],
            highlight_elements=True,
            viewport_expansion=0,
        )
        state = None
        if cdp_target_id:
            state = BrowserContextState(target_id=cdp_target_id)
            logger.info(f"Using specific tab with target ID: {cdp_target_id}")

        controller = Controller(background_mode=True)
        logger.info("Using background mode to prevent focus stealing")

        context = BrowserContext(
            browser=browser,
            config=context_config,
            state=state,
            background_mode=True,
        )
        return browser, context, controller
    except Exception as e:
        logger.error(f"Error creating browser context: {str(e)}")
        raise


async def run_browser_task_async(
    task_id: str,
    url: str,
    action: str,
    llm: BaseLanguageModel,
    window_width: int = CONFIG["DEFAULT_WINDOW_WIDTH"],
    window_height: int = CONFIG["DEFAULT_WINDOW_HEIGHT"],
    locale: str = CONFIG["DEFAULT_LOCALE"],
    cdp_target_id: Optional[str] = None,
    cdp_url: Optional[str] = None,
    ctx: Optional[Any] = None,
    mcp_request_id: Optional[str] = None,
    event_loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    browser = None
    context = None
    controller = None
    task_logs = []
    list_handler = TaskLogListHandler(task_logs)
    browser_use_logger = logging.getLogger("browser_use")

    try:
        # Stream task start
        if ctx and hasattr(ctx, "send_notification"):
            start_message_text = f"🟢 Task {task_id} started"
            logger.info(f"Sending TASK START via notification: {start_message_text}")

            start_payload_json = json.dumps(
                {"type": "status", "task_id": task_id, "message": start_message_text}
            )

            text_part_params = TextStreamPartParams(text=start_payload_json)
            notification = TextStreamPartNotification(params=text_part_params)
            await ctx.send_notification(notification, related_request_id=mcp_request_id)
        else:
            logger.warning(
                "Session (ctx) or send_notification method not available for initial stream."
            )

        browser_use_logger.addHandler(list_handler)
        browser_use_logger.setLevel(logging.INFO)

        task_store[task_id]["status"] = "running"
        task_store[task_id]["start_time"] = datetime.now().isoformat()
        task_store[task_id]["logs"] = task_logs
        task_store[task_id]["progress"] = {
            "current_step": 0,
            "total_steps": 0,
            "steps": [],
        }

        async def step_callback(
            browser_state: Any, agent_output: Any, step_number: int
        ) -> None:
            task_store[task_id]["progress"]["current_step"] = step_number
            task_store[task_id]["progress"]["total_steps"] = max(
                task_store[task_id]["progress"]["total_steps"], step_number
            )
            step_info = {"step": step_number, "time": datetime.now().isoformat()}

            current_goal = None
            current_memory = None
            current_evaluation = None

            if agent_output and hasattr(agent_output, "current_state"):
                current_state = agent_output.current_state
                if hasattr(current_state, "next_goal"):
                    current_goal = current_state.next_goal
                    step_info["goal"] = current_goal
                if hasattr(current_state, "memory_summary"):
                    current_memory = current_state.memory_summary
                    step_info["memory"] = current_memory
                elif hasattr(current_state, "memory"):
                    current_memory = current_state.memory
                    step_info["memory"] = current_memory
                if hasattr(current_state, "last_step_evaluation"):
                    current_evaluation = current_state.last_step_evaluation
                    step_info["evaluation"] = current_evaluation
                elif hasattr(current_state, "evaluation"):
                    current_evaluation = current_state.evaluation
                    step_info["evaluation"] = current_evaluation

            task_store[task_id]["progress"]["steps"].append(step_info)
            logger.info(
                f"Task {task_id}: Step {step_number} completed - Goal: {current_goal}, Eval: {current_evaluation}, Mem: {current_memory}"
            )

            if ctx and hasattr(ctx, "send_notification"):
                progress_payload_dict = {
                    "type": "progress",
                    "task_id": task_id,
                    "goal": current_goal,
                    "memory": current_memory,
                    "evaluation": current_evaluation,
                    "time": datetime.now().isoformat(),
                }

                progress_payload_json = json.dumps(progress_payload_dict)
                logger.info(
                    f"BROWSER.PY: Sending PROGRESS STEP via notification: {progress_payload_json}"
                )

                text_part_params = TextStreamPartParams(text=progress_payload_json)
                notification = TextStreamPartNotification(params=text_part_params)
                await ctx.send_notification(
                    notification, related_request_id=mcp_request_id
                )
            else:
                logger.warning(
                    "BROWSER.PY: Session (ctx) or send_notification method not available for progress stream."
                )

        async def done_callback(history: Any) -> None:
            logger.info(f"Task {task_id}: Completed with {len(history.history)} steps")
            current_step = task_store[task_id]["progress"]["current_step"] + 1
            task_store[task_id]["progress"]["steps"].append(
                {
                    "step": current_step,
                    "time": datetime.now().isoformat(),
                    "status": "completed",
                }
            )
            if ctx and hasattr(ctx, "send_notification"):
                done_data = {
                    "type": "done",
                    "task_id": task_id,
                    "time": datetime.now().isoformat(),
                }

                done_json = json.dumps(done_data)
                logger.info(
                    f"BROWSER.PY: Sending TASK DONE via notification: {done_json}"
                )

                text_part_params = TextStreamPartParams(text=done_json)
                notification = TextStreamPartNotification(params=text_part_params)
                await ctx.send_notification(
                    notification, related_request_id=mcp_request_id
                )
            else:
                logger.warning(
                    "BROWSER.PY: Session (ctx) or send_notification method not available for done stream."
                )

        chrome_path = os.environ.get("CHROME_PATH")
        if cdp_target_id:
            logger.info(f"Using CDP target ID from params: {cdp_target_id}")
        if cdp_url:
            logger.info(f"Using CDP URL from params: {cdp_url}")

        browser, context, controller = await create_browser_context_for_task(
            chrome_path=chrome_path,
            window_width=window_width,
            window_height=window_height,
            locale=locale,
            cdp_target_id=cdp_target_id,
            cdp_url=cdp_url,
            ctx=ctx,
            mcp_request_id=mcp_request_id,
            event_loop=event_loop,
        )

        agent = Agent(
            task=f"First, navigate to {url}. Then, {action}",
            llm=llm,
            browser_context=context,
            controller=controller,
            background_mode=True,
            register_new_step_callback=step_callback,
            register_done_callback=done_callback,
        )

        agent_result = await agent.run(max_steps=CONFIG["MAX_AGENT_STEPS"])
        final_result = agent_result.final_result()

        if final_result and hasattr(final_result, "raise_for_status"):
            final_result.raise_for_status()
            result_text = str(final_result.text)
        else:
            result_text = (
                str(final_result) if final_result else "No final result available"
            )

        response_data = {
            "final_result": result_text,
            "success": agent_result.is_successful(),
            "has_errors": agent_result.has_errors(),
            "errors": [str(err) for err in agent_result.errors() if err],
            "urls_visited": [str(url) for url in agent_result.urls() if url],
            "actions_performed": agent_result.action_names(),
            "extracted_content": agent_result.extracted_content(),
            "steps_taken": agent_result.number_of_steps(),
        }

        task_store[task_id]["status"] = "completed"
        task_store[task_id]["end_time"] = datetime.now().isoformat()
        task_store[task_id]["result"] = response_data

        if ctx and hasattr(ctx, "send_notification"):
            result_data = {
                "type": "result",
                "task_id": task_id,
                "result": response_data,
                "time": datetime.now().isoformat(),
            }

            result_json = json.dumps(result_data)
            logger.info(
                f"BROWSER.PY: Sending TASK RESULT via notification: {result_json}"
            )

            text_part_params = TextStreamPartParams(text=result_json)
            notification = TextStreamPartNotification(params=text_part_params)
            await ctx.send_notification(notification, related_request_id=mcp_request_id)
        else:
            logger.warning(
                "BROWSER.PY: Session (ctx) or send_notification method not available for result stream."
            )

    except Exception as e:
        logger.error(f"Error in async browser task {task_id}: {str(e)}")
        tb = traceback.format_exc()
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["end_time"] = datetime.now().isoformat()
        task_store[task_id]["error"] = str(e)
        task_store[task_id]["traceback"] = tb

        if ctx and hasattr(ctx, "send_notification"):
            error_data = {
                "type": "error",
                "task_id": task_id,
                "error": str(e),
                "time": datetime.now().isoformat(),
            }

            error_json = json.dumps(error_data)
            logger.info(
                f"BROWSER.PY: Sending TASK ERROR via notification: {error_json}"
            )

            text_part_params = TextStreamPartParams(text=error_json)
            notification = TextStreamPartNotification(params=text_part_params)
            await ctx.send_notification(notification, related_request_id=mcp_request_id)
        else:
            logger.warning(
                "BROWSER.PY: Session (ctx) or send_notification method not available for error stream."
            )

    finally:
        try:
            if context:
                await context.close()
            if browser:
                await browser.close()
            logger.info(f"Browser resources for task {task_id} cleaned up")
        except Exception as e:
            logger.error(
                f"Error cleaning up browser resources for task {task_id}: {str(e)}"
            )
        finally:
            browser_use_logger.removeHandler(list_handler)


async def cleanup_old_tasks() -> None:
    """
    Periodically clean up old completed tasks to prevent memory leaks.
    """
    while True:
        try:
            await asyncio.sleep(CONFIG["CLEANUP_INTERVAL_SECONDS"])
            current_time = datetime.now()
            tasks_to_remove = []
            for task_id, task_data in list(
                task_store.items()
            ):  # Iterate over a copy for safe deletion
                if (
                    task_data["status"] in ["completed", "failed"]
                    and "end_time" in task_data
                ):
                    end_time = datetime.fromisoformat(task_data["end_time"])
                    hours_elapsed = (current_time - end_time).total_seconds() / 3600
                    if hours_elapsed > 1:
                        tasks_to_remove.append(task_id)
            for task_id in tasks_to_remove:
                del task_store[task_id]
            if tasks_to_remove:
                logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")
        except Exception as e:
            logger.error(f"Error in task cleanup: {str(e)}")
