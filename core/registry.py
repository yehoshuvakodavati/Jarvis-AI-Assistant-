"""
Agent and Tool Registries for Jarvis Multi-Agent AI Operating System.

Provides centralized registration, discovery, and lookup for all agents
and tools in the system. Supports dynamic registration and introspection.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Type

from core.exceptions import AgentNotFoundError, ToolNotFoundError
from core.models import ToolSchema

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for all agent classes/instances.

    Agents register themselves on instantiation or can be pre-registered.
    The Commander queries this registry to discover available agents.
    """

    _instance: Optional[AgentRegistry] = None
    _initialized: bool = False

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if AgentRegistry._initialized:
            return
        self._agents: Dict[str, Any] = {}
        self._agent_metadata: Dict[str, Dict[str, Any]] = {}
        AgentRegistry._initialized = True

    def register(self, name: str, agent_instance: Any, *, description: str = "", capabilities: List[str] | None = None) -> None:
        """
        Register an agent instance.

        Args:
            name: Unique agent identifier.
            agent_instance: The agent object.
            description: Human-readable description.
            capabilities: List of capability strings.
        """
        self._agents[name] = agent_instance
        self._agent_metadata[name] = {
            "description": description or getattr(agent_instance, "description", "No description"),
            "capabilities": capabilities or getattr(agent_instance, "capabilities", []),
            "class": type(agent_instance).__name__,
        }
        logger.info(f"Registered agent: {name}")

    def get(self, name: str) -> Any:
        """Retrieve an agent by name."""
        if name not in self._agents:
            raise AgentNotFoundError(name)
        return self._agents[name]

    def get_safe(self, name: str) -> Any | None:
        """Retrieve an agent by name, returning None if not found."""
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def get_metadata(self, name: str) -> Dict[str, Any]:
        """Get metadata for an agent."""
        return self._agent_metadata.get(name, {})

    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all agents."""
        return dict(self._agent_metadata)

    def describe_for_llm(self) -> str:
        """
        Generate a compact description of all agents for LLM context.

        Returns a string suitable for inclusion in a prompt.
        """
        lines = ["Available Agents:"]
        for name, meta in self._agent_metadata.items():
            caps = ", ".join(meta.get("capabilities", [])) or "general"
            lines.append(f"  - {name}: {meta['description']} [Capabilities: {caps}]")
        return "\n".join(lines)

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(name, None)
        self._agent_metadata.pop(name, None)
        logger.info(f"Unregistered agent: {name}")


class ToolRegistry:
    """
    Registry for all tools/functions available to agents.

    Tools are registered with a schema describing their interface.
    Agents can discover and invoke tools dynamically.
    """

    _instance: Optional[ToolRegistry] = None
    _initialized: bool = False

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if ToolRegistry._initialized:
            return
        self._tools: Dict[str, Callable[..., Any]] = {}
        self._schemas: Dict[str, ToolSchema] = {}
        ToolRegistry._initialized = True

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        schema: ToolSchema | None = None,
        description: str = "",
        dangerous: bool = False,
        requires_confirmation: bool = False,
    ) -> None:
        """
        Register a tool function.

        Args:
            name: Unique tool identifier.
            func: Callable implementing the tool.
            schema: Optional ToolSchema. Auto-generated from signature if absent.
            description: Human-readable description.
            dangerous: Whether this tool can cause harm.
            requires_confirmation: Whether user confirmation is required.
        """
        self._tools[name] = func

        if schema is None:
            schema = self._infer_schema(func, description, dangerous, requires_confirmation)
        self._schemas[name] = schema
        logger.info(f"Registered tool: {name} (dangerous={dangerous}, confirm={requires_confirmation})")

    def get(self, name: str) -> Callable[..., Any]:
        """Retrieve a tool function by name."""
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def get_safe(self, name: str) -> Callable[..., Any] | None:
        """Retrieve a tool by name, returning None if not found."""
        return self._tools.get(name)

    def get_schema(self, name: str) -> ToolSchema:
        """Retrieve the schema for a tool."""
        if name not in self._schemas:
            raise ToolNotFoundError(name)
        return self._schemas[name]

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def list_schemas(self) -> List[ToolSchema]:
        """List all tool schemas."""
        return list(self._schemas.values())

    def get_all_schemas(self) -> Dict[str, ToolSchema]:
        """Get all tool schemas keyed by name."""
        return dict(self._schemas)

    def is_dangerous(self, name: str) -> bool:
        """Check if a tool is marked as dangerous."""
        schema = self._schemas.get(name)
        return schema.dangerous if schema else False

    def requires_confirmation(self, name: str) -> bool:
        """Check if a tool requires user confirmation."""
        schema = self._schemas.get(name)
        return schema.requires_confirmation if schema else False

    def describe_for_llm(self) -> str:
        """
        Generate a compact description of all tools for LLM context.

        Returns a string suitable for inclusion in a prompt.
        """
        lines = ["Available Tools:"]
        for name, schema in self._schemas.items():
            params = ", ".join(
                f"{p.name}: {p.type}" + (" (required)" if p.required else "")
                for p in schema.parameters
            )
            lines.append(f"  - {name}({params}): {schema.description}")
        return "\n".join(lines)

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)
        self._schemas.pop(name, None)
        logger.info(f"Unregistered tool: {name}")

    @staticmethod
    def _infer_schema(
        func: Callable[..., Any],
        description: str,
        dangerous: bool,
        requires_confirmation: bool,
    ) -> ToolSchema:
        """Infer a ToolSchema from a function's signature."""
        sig = inspect.signature(func)
        from core.models import ToolParameter

        params: List[ToolParameter] = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            ptype = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation in (int,):
                    ptype = "integer"
                elif param.annotation in (float,):
                    ptype = "number"
                elif param.annotation in (bool,):
                    ptype = "boolean"
                elif param.annotation in (list, List):
                    ptype = "array"
                elif param.annotation in (dict, Dict):
                    ptype = "object"
            params.append(ToolParameter(
                name=param_name,
                type=ptype,
                description=f"Parameter '{param_name}'",
                required=param.default == inspect.Parameter.empty,
                default=param.default if param.default != inspect.Parameter.empty else None,
            ))

        return ToolSchema(
            name=func.__name__,
            description=description or (func.__doc__ or "No description").strip().split("\n")[0],
            parameters=params,
            dangerous=dangerous,
            requires_confirmation=requires_confirmation,
        )
