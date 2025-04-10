"""
Server module that re-exports the main server module.

This provides a clean import path for the CLI and other code.
"""

from server.server import (
    CONFIG,
    Server,
    cleanup_old_tasks,
    create_browser_context_for_task,
    create_mcp_server,
    init_configuration,
    main,
    run_browser_task_async,
    task_store,
)

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
