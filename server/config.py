import os
from typing import Any, Dict


def parse_bool_env(env_var: str, default: bool = False) -> bool:
    """
    Parse a boolean environment variable.

    Args:
        env_var: The environment variable name
        default: Default value if not set

    Returns:
        Boolean value of the environment variable
    """
    value = os.environ.get(env_var)
    if value is None:
        return default

    return value.lower() in ("true", "yes", "1", "y", "on")


def init_configuration() -> Dict[str, Any]:
    """
    Initialize configuration from environment variables with defaults.

    Returns:
        Dictionary containing all configuration parameters
    """
    config = {
        # Browser window settings
        "DEFAULT_WINDOW_WIDTH": int(os.environ.get("BROWSER_WINDOW_WIDTH", 1280)),
        "DEFAULT_WINDOW_HEIGHT": int(os.environ.get("BROWSER_WINDOW_HEIGHT", 1100)),
        # Browser config settings
        "DEFAULT_LOCALE": os.environ.get("BROWSER_LOCALE", "en-US"),
        "DEFAULT_USER_AGENT": os.environ.get(
            "BROWSER_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
        ),
        # Task settings
        "DEFAULT_TASK_EXPIRY_MINUTES": int(os.environ.get("TASK_EXPIRY_MINUTES", 60)),
        "DEFAULT_ESTIMATED_TASK_SECONDS": int(
            os.environ.get("ESTIMATED_TASK_SECONDS", 60)
        ),
        "CLEANUP_INTERVAL_SECONDS": int(
            os.environ.get("CLEANUP_INTERVAL_SECONDS", 3600)
        ),  # 1 hour
        "MAX_AGENT_STEPS": int(os.environ.get("MAX_AGENT_STEPS", 10)),
        # Browser arguments
        "BROWSER_ARGS": [
            "--no-sandbox",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--remote-debugging-port=0",  # Use random port to avoid conflicts
        ],
        # Patient mode - if true, functions wait for task completion before returning
        "PATIENT_MODE": parse_bool_env("PATIENT", True),
        # Streamable HTTP Server Settings (NEW)
        "STREAMABLE_HTTP_PORT": int(os.environ.get("STREAMABLE_HTTP_PORT", 3000)),
        "JSON_RESPONSE": parse_bool_env("JSON_RESPONSE", False),
        "EVENT_STORE_MAX_EVENTS_PER_STREAM": int(
            os.environ.get("EVENT_STORE_MAX_EVENTS_PER_STREAM", 1000)
        ),
    }

    return config

CONFIG = init_configuration()
