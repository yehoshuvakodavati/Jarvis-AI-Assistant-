"""
Tool decorators for Jarvis Multi-Agent AI Operating System.

Provides the @tool decorator for easy function registration as agent-usable tools.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from core.models import ToolSchema, ToolParameter
from core.registry import ToolRegistry


def tool(
    name: str | None = None,
    description: str | None = None,
    dangerous: bool = False,
    requires_confirmation: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to register a function as an agent-usable tool.

    Args:
        name: Tool name (defaults to function name).
        description: Tool description (defaults to docstring first line).
        dangerous: Whether this tool can cause harm.
        requires_confirmation: Whether user confirmation is required.

    Example:
        @tool(description="Search the web")
        def web_search(query: str, max_results: int = 5) -> list:
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "No description").strip().split("\n")[0]

        # Build schema from signature
        sig = inspect.signature(func)
        params: list[ToolParameter] = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            ptype = "string"
            if param.annotation != inspect.Parameter.empty:
                ann = param.annotation
                # Handle typing generics
                origin = getattr(ann, "__origin__", None)
                if origin is list or ann is list:
                    ptype = "array"
                elif origin is dict or ann is dict:
                    ptype = "object"
                elif ann is int:
                    ptype = "integer"
                elif ann is float:
                    ptype = "number"
                elif ann is bool:
                    ptype = "boolean"
                elif ann is str:
                    ptype = "string"

            params.append(ToolParameter(
                name=param_name,
                type=ptype,
                description=f"Parameter '{param_name}'",
                required=param.default == inspect.Parameter.empty,
                default=param.default if param.default != inspect.Parameter.empty else None,
            ))

        schema = ToolSchema(
            name=tool_name,
            description=tool_desc,
            parameters=params,
            dangerous=dangerous,
            requires_confirmation=requires_confirmation,
        )

        # Register with the global registry
        registry = ToolRegistry()
        registry.register(tool_name, func, schema=schema)

        # Mark the function
        func._jarvis_tool = True  # type: ignore
        func._jarvis_tool_name = tool_name  # type: ignore
        func._jarvis_tool_schema = schema  # type: ignore

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper
    return decorator
