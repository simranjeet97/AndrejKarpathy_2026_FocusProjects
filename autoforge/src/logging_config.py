import logging
import os
import sys
import structlog

# Define context variables that are bound dynamically per request or task
# Users can use structlog.contextvars.bind_contextvars(task_id="...", trace_id="...", repo="...")
# to bind these variables. They will be auto-injected.

def configure_logging() -> None:
    # Read environment to determine log format
    env = os.getenv("ENV", "development").lower()
    is_production = env in ("production", "prod")

    # Shared processors for both structlog and standard logging
    shared_processors = [
        # Merge structlog.contextvars context variables (task_id, trace_id, repo, etc.)
        structlog.contextvars.merge_contextvars,
        # Add log level
        structlog.processors.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if is_production:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Colored Console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

    # Redirect standard logging to structlog if needed
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
