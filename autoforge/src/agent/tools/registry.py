"""
ToolRegistry — central registry for AutoForge agent tools.

Usage
-----
Register a tool:

    registry = ToolRegistry()

    @registry.register(
        name="my_tool",
        description="Does something useful.",
        input_schema={...},
    )
    async def my_tool(container_id: str, task_id: str, **kwargs) -> str:
        ...

Query:

    schemas   = registry.schemas()          # List[dict] for Anthropic API
    result    = await registry.dispatch(    # call by name
        tool_name, tool_input, container_id, task_id
    )

All handler functions must be **async** and accept `container_id` and
`task_id` as the first two keyword arguments, plus whatever is declared in
the tool's input_schema.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

import structlog

logger = structlog.get_logger()


class ToolRegistry:
    """Singleton-style registry that accumulates tool handlers and schemas."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[..., Any]] = {}
        self._schemas: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator that registers an async handler function."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            if name in self._handlers:
                raise ValueError(f"Tool '{name}' is already registered.")
            self._handlers[name] = fn
            self._schemas.append(
                {
                    "name": name,
                    "description": description,
                    "input_schema": input_schema,
                }
            )
            return fn

        return decorator

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def schemas(self) -> List[Dict[str, Any]]:
        """Return the list of tool schemas for the Anthropic API."""
        return list(self._schemas)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        container_id: str,
        task_id: str,
    ) -> str:
        """
        Route a Claude tool-use request to the registered handler.

        Returns a JSON-serialisable string (tool_result content).
        Exceptions are caught and returned as {"error": "..."} so the agent
        can decide how to proceed rather than crashing.
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            logger.warning("tool_not_found", tool=tool_name, task_id=task_id)
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = await handler(
                container_id=container_id,
                task_id=task_id,
                **tool_input,
            )
            return result
        except Exception as exc:
            logger.error(
                "tool_dispatch_error",
                tool=tool_name,
                task_id=task_id,
                error=str(exc),
            )
            return json.dumps({"error": str(exc)})


# Module-level singleton — import this everywhere
registry = ToolRegistry()
