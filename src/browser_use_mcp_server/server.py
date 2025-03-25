"""
Server module that re-exports the main server module.

This provides a clean import path for the CLI and other code.
"""

import os
import sys
from server.server import (
    Server,
    main,
    create_browser_context_for_task,
    run_browser_task_async,
    cleanup_old_tasks,
    create_mcp_server,
    init_configuration,
    CONFIG,
    task_store,
)

# Add the root directory to the Python path to find server module
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, root_dir)

# Re-export everything we imported
__all__ = [
    "Server",
    "main",
    "create_browser_context_for_task",
    "run_browser_task_async",
    "cleanup_old_tasks",
    "create_mcp_server",
    "init_configuration",
    "CONFIG",
    "task_store",
]
