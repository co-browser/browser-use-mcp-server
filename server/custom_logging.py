import asyncio
import json
import logging
import sys
from datetime import datetime

from pythonjsonlogger import jsonlogger

JSON_FORMATTER = jsonlogger.JsonFormatter(
    '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
)


def setup_root_logger():
    """Configures the root logger and uvicorn loggers with JSON formatting."""
    logger = logging.getLogger()
  
    already_added = any(
        isinstance(h, logging.StreamHandler) and h.formatter == JSON_FORMATTER
        for h in logger.handlers
    )

    if not already_added:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JSON_FORMATTER)
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)

   
    uvicorn_logger_names = ["uvicorn", "uvicorn.error", "uvicorn.access"]
    for name in uvicorn_logger_names:
        uvicorn_logger = logging.getLogger(name)
        if not any(
            isinstance(h, logging.StreamHandler) and h.formatter == JSON_FORMATTER
            for h in uvicorn_logger.handlers
        ):
            uvicorn_handler = logging.StreamHandler(sys.stderr)
            uvicorn_handler.setFormatter(JSON_FORMATTER)
            uvicorn_logger.addHandler(uvicorn_handler)
        uvicorn_logger.setLevel(logging.INFO)  
        uvicorn_logger.propagate = False  


class TaskLogListHandler(logging.Handler):
    def __init__(self, task_logs_list):
        super().__init__()
        self.task_logs_list = task_logs_list

    def emit(self, record):
        log_entry = {
            "level": record.levelname,
            "name": record.name,
            "message": self.format(record),
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
        }
        self.task_logs_list.append(log_entry)

setup_root_logger()
