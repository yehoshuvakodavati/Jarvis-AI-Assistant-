"""
Custom exception hierarchy for the Jarvis Multi-Agent AI Operating System.

Provides granular error classification for robust error handling,
retry policies, and observability.
"""


class JarvisError(Exception):
    """Base exception for all Jarvis system errors."""

    def __init__(self, message: str, *, details: dict | None = None, recoverable: bool = False):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.recoverable = recoverable

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# =============================================================================
# LLM ERRORS
# =============================================================================

class LLMError(JarvisError):
    """Errors originating from the LLM subsystem."""
    pass


class LLMConnectionError(LLMError):
    """Cannot connect to the LLM service."""

    def __init__(self, message: str = "Cannot connect to LLM service", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class LLMTimeoutError(LLMError):
    """LLM request exceeded timeout."""

    def __init__(self, message: str = "LLM request timed out", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""

    def __init__(self, message: str = "LLM rate limit exceeded", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class LLMResponseError(LLMError):
    """LLM returned invalid or unexpected response."""

    def __init__(self, message: str = "Invalid LLM response", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class LLMModelNotFoundError(LLMError):
    """Requested model is not available."""

    def __init__(self, model_name: str, **kwargs):
        super().__init__(f"Model '{model_name}' not found or not pulled", recoverable=False, **kwargs)


# =============================================================================
# TOOL ERRORS
# =============================================================================

class ToolError(JarvisError):
    """Errors during tool execution."""
    pass


class ToolNotFoundError(ToolError):
    """Requested tool does not exist in registry."""

    def __init__(self, tool_name: str, **kwargs):
        super().__init__(f"Tool '{tool_name}' not found in registry", recoverable=False, **kwargs)


class ToolExecutionError(ToolError):
    """Tool execution failed."""

    def __init__(self, tool_name: str, message: str, **kwargs):
        super().__init__(f"Tool '{tool_name}' execution failed: {message}", recoverable=True, **kwargs)


class ToolValidationError(ToolError):
    """Tool parameters failed validation."""

    def __init__(self, tool_name: str, message: str, **kwargs):
        super().__init__(f"Tool '{tool_name}' validation failed: {message}", recoverable=True, **kwargs)


class ToolTimeoutError(ToolError):
    """Tool execution exceeded timeout."""

    def __init__(self, tool_name: str, timeout: int, **kwargs):
        super().__init__(f"Tool '{tool_name}' timed out after {timeout}s", recoverable=True, **kwargs)


# =============================================================================
# AGENT ERRORS
# =============================================================================

class AgentError(JarvisError):
    """Errors originating from an agent."""
    pass


class AgentNotFoundError(AgentError):
    """Requested agent does not exist in registry."""

    def __init__(self, agent_name: str, **kwargs):
        super().__init__(f"Agent '{agent_name}' not found in registry", recoverable=False, **kwargs)


class AgentExecutionError(AgentError):
    """Agent failed to complete its task."""

    def __init__(self, agent_name: str, message: str, **kwargs):
        super().__init__(f"Agent '{agent_name}' failed: {message}", recoverable=True, **kwargs)


class AgentRoutingError(AgentError):
    """Commander failed to route a task appropriately."""

    def __init__(self, message: str = "Failed to route task", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


# =============================================================================
# MEMORY ERRORS
# =============================================================================

class MemoryError(JarvisError):
    """Errors in the memory subsystem."""
    pass


class MemoryStoreError(MemoryError):
    """Failed to store memory."""
    pass


class MemoryRetrievalError(MemoryError):
    """Failed to retrieve memory."""
    pass


class VectorStoreError(MemoryError):
    """Vector store operation failed."""
    pass


# =============================================================================
# SAFETY ERRORS
# =============================================================================

class SafetyError(JarvisError):
    """Operation blocked by safety checks."""

    def __init__(self, message: str, *, blocked_command: str | None = None, **kwargs):
        super().__init__(message, recoverable=False, **kwargs)
        self.blocked_command = blocked_command


class ConfirmationRequiredError(SafetyError):
    """Operation requires user confirmation."""

    def __init__(self, message: str, *, action_description: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.action_description = action_description


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================

class ConfigurationError(JarvisError):
    """System configuration is invalid or incomplete."""
    pass
