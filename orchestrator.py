"""
System Orchestrator for Jarvis Multi-Agent AI Operating System.

Handles initialization, agent registration, and provides the
central entry point (CommanderAgent) for the entire system.

Usage:
    from orchestrator import get_commander
    commander = get_commander()
    response = commander.process_user_input("Your query here")
"""

from __future__ import annotations

import logging
from typing import Optional

from core.registry import AgentRegistry
from core.state import SystemState

logger = logging.getLogger(__name__)

_initialized: bool = False
_commander: Optional["CommanderAgent"] = None  # type: ignore


def initialize_system() -> "CommanderAgent":
    """
    Initialize the entire Jarvis system.

    This function:
    1. Initializes the SQLite database
    2. Imports tools (triggers @tool decorator registration)
    3. Instantiates and registers all agents
    4. Returns the CommanderAgent ready to receive requests

    Safe to call multiple times - subsequent calls are no-ops.
    """
    global _initialized, _commander

    if _initialized:
        logger.debug("System already initialized")
        return _commander  # type: ignore

    logger.info("🚀 Initializing Jarvis AI Operating System...")

    # 1. Initialize database (creates tables if needed)
    try:
        from memory.database import init_database
        init_database()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning(f"Database init issue (may already exist): {e}")

    # 2. Import tools to trigger @tool decorator registration
    try:
        import framework.tools
        logger.info(f"✅ Tools registered: {len(__import__('core.registry').ToolRegistry().list_tools())}")
    except Exception as e:
        logger.warning(f"Tool registration issue: {e}")

    # 3. Instantiate and register all agents
    try:
        from agents import (
            CommanderAgent,
            PlannerAgent,
            ResearcherAgent,
            MemoryAgent,
            CoderAgent,
            ExecutorAgent,
            BrowserAgent,
            FileAgent,
            LearnerAgent,
        )

        registry = AgentRegistry()
        agents = [
            CommanderAgent(),
            PlannerAgent(),
            ResearcherAgent(),
            MemoryAgent(),
            CoderAgent(),
            ExecutorAgent(),
            BrowserAgent(),
            FileAgent(),
            LearnerAgent(),
        ]

        for agent in agents:
            registry.register(
                name=agent.name,
                agent_instance=agent,
                description=agent.description,
                capabilities=agent.capabilities,
            )
            logger.info(f"  ✅ Registered: {agent.name}")

        _commander = agents[0]  # CommanderAgent is first
        logger.info("✅ All agents registered")

    except Exception as e:
        logger.error(f"Agent registration failed: {e}")
        raise

    _initialized = True
    logger.info("🤖 Jarvis AI Operating System is ONLINE")
    return _commander


def get_commander() -> "CommanderAgent":
    """Get the initialized CommanderAgent. Initializes system if needed."""
    if _commander is None:
        return initialize_system()
    return _commander


def shutdown_system() -> None:
    """Gracefully shut down all agents."""
    global _initialized, _commander
    try:
        from core.registry import AgentRegistry
        registry = AgentRegistry()
        for name in registry.list_agents():
            agent = registry.get_safe(name)
            if agent and hasattr(agent, "shutdown"):
                agent.shutdown()
        logger.info("System shut down gracefully")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")
    finally:
        _initialized = False
        _commander = None
