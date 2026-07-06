"""
In-memory Message Bus for inter-agent communication.

Implements a lightweight publish/subscribe pattern suitable for a
single-process multi-agent system. Agents subscribe to topics and
receive callbacks when messages are published.

Thread-safe using locks. Designed for synchronous operation within
Streamlit's execution model.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from core.models import Message

logger = logging.getLogger(__name__)

SubscriptionCallback = Callable[[str, Any], None]


class MessageBus:
    """
    Central message bus for agent coordination.

    Topics:
        - "user_input": Raw user messages
        - "agent_request": Task dispatch requests
        - "agent_response": Completed agent responses
        - "tool_call": Tool execution requests
        - "tool_result": Tool execution results
        - "memory_update": Memory store events
        - "system_event": Internal system events
    """

    _instance: Optional[MessageBus] = None
    _initialized: bool = False

    def __new__(cls) -> MessageBus:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if MessageBus._initialized:
            return
        self._subscriptions: Dict[str, List[SubscriptionCallback]] = defaultdict(list)
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_history = 1000
        MessageBus._initialized = True

    # -------------------------------------------------------------------------
    # SUBSCRIPTION API
    # -------------------------------------------------------------------------

    def subscribe(self, topic: str, callback: SubscriptionCallback) -> None:
        """
        Subscribe a callback to a topic.

        Args:
            topic: Topic name (e.g., "agent_response").
            callback: Function(topic, data) to call on publish.
        """
        with self._lock:
            if callback not in self._subscriptions[topic]:
                self._subscriptions[topic].append(callback)
                qn = getattr(callback, "__qualname__", repr(callback))
                logger.debug(f"Subscribed to '{topic}': {qn}")

    def unsubscribe(self, topic: str, callback: SubscriptionCallback) -> None:
        """Remove a callback subscription from a topic."""
        with self._lock:
            subs = self._subscriptions.get(topic, [])
            if callback in subs:
                subs.remove(callback)
                logger.debug(f"Unsubscribed from '{topic}': {getattr(callback, '__qualname__', repr(callback))}")

    # -------------------------------------------------------------------------
    # PUBLISH API
    # -------------------------------------------------------------------------

    def publish(self, topic: str, data: Any, *, source: str | None = None) -> int:
        """
        Publish data to a topic, notifying all subscribers.

        Args:
            topic: Topic to publish to.
            data: Payload (any serializable type).
            source: Optional source identifier.

        Returns:
            Number of subscribers notified.
        """
        event = {
            "topic": topic,
            "data": data,
            "source": source,
        }

        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            callbacks = list(self._subscriptions.get(topic, []))

        notified = 0
        for cb in callbacks:
            try:
                cb(topic, data)
                notified += 1
            except Exception as e:
                logger.error(f"MessageBus callback error on '{topic}': {e}")

        logger.debug(f"Published to '{topic}': {notified} subscriber(s) notified")
        return notified

    def publish_user_message(self, content: str, **metadata: Any) -> int:
        """Convenience: publish a user Message to 'user_input'."""
        msg = Message(role="user", content=content, metadata=metadata)
        return self.publish("user_input", msg, source="user")

    def publish_agent_response(self, agent_name: str, response: Any, **metadata: Any) -> int:
        """Convenience: publish an agent response to 'agent_response'."""
        return self.publish("agent_response", {
            "agent_name": agent_name,
            "response": response,
            "metadata": metadata,
        }, source=agent_name)

    # -------------------------------------------------------------------------
    # QUERY API
    # -------------------------------------------------------------------------

    def get_history(self, topic: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent message history, optionally filtered by topic."""
        with self._lock:
            events = list(self._history)
        if topic:
            events = [e for e in events if e.get("topic") == topic]
        return events[-limit:]

    def get_last_message(self, topic: str) -> Dict[str, Any] | None:
        """Get the most recent message for a topic."""
        history = self.get_history(topic=topic, limit=1)
        return history[0] if history else None

    def clear_history(self) -> None:
        """Clear message history."""
        with self._lock:
            self._history.clear()

    def subscriber_count(self, topic: str) -> int:
        """Count subscribers for a topic."""
        with self._lock:
            return len(self._subscriptions.get(topic, []))

    def topic_list(self) -> List[str]:
        """List all topics with subscribers."""
        with self._lock:
            return list(self._subscriptions.keys())
