"""
Memory Agent for Jarvis Multi-Agent AI Operating System.

Manages all memory operations:
- Storing and retrieving memories
- Managing user preferences
- Creating and searching notes
- Answering questions about stored information
- Providing context for other agents
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from config import MODEL_CONVERSATIONAL
from core.models import (
    AgentResponse,
    AgentTask,
    ExecutionTrace,
    MemoryEntry,
    MemoryType,
)
from agents.base import BaseAgent
from framework.routing import parse_intent_via_llm

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """
    Manages the system's memory, preferences, notes, and goals.

    Capabilities:
    - Store/recall memories
    - Manage user preferences
    - Create/search notes
    - Answer questions about stored data
    - Provide context to other agents
    """

    name = "memory_agent"
    description = "Manages memories, preferences, notes, and provides context retrieval"
    capabilities = ["memory", "preferences", "notes", "context", "recall"]
    default_model = MODEL_CONVERSATIONAL

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """Execute memory-related tasks via LLM-based intent parsing."""
        user_input = task.context.get("user_input", task.description)

        if trace:
            trace.add_event("decision", "MemoryAgent parsing intent via LLM")

        valid_ops = ["note_create", "note_search", "preference", "recall", "goal", "general"]
        prompt = (
            "You are the Memory Agent of Jarvis. Classify the user's memory request into one operation.\n\n"
            "Operations:\n"
            '- "note_create" : save/create/write a note\n'
            '- "note_search" : search/find/list notes\n'
            '- "preference"  : get/set user preferences or settings\n'
            '- "recall"      : remember/recall past info ("what did i", "tell me about my")\n'
            '- "goal"        : query goals/objectives/tasks\n'
            '- "general"     : none of the above (fallback)\n\n'
            f'User request: "{user_input}"\n\n'
            'Respond ONLY with JSON: {"intent": "<operation>", "parameters": {}}'
        )
        op, _params = parse_intent_via_llm(
            self.llm, prompt, valid_ops, model=self.default_model
        )

        if trace:
            trace.add_event("decision", f"LLM selected operation: {op}")

        handler_map = {
            "note_create": self._handle_note_creation,
            "note_search": self._handle_note_search,
            "preference": self._handle_preference,
            "recall": self._handle_memory_query,
            "goal": self._handle_goal_query,
        }
        handler = handler_map.get(op, self._handle_general_memory)
        return handler(task, user_input, trace)

    # -------------------------------------------------------------------------
    # NOTE OPERATIONS
    # -------------------------------------------------------------------------

    def _handle_note_creation(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Extract note content from request and save it."""
        if trace:
            trace.add_event("tool_call", "Creating note from user request")

        # Try to extract title and content using LLM
        prompt = f"""Extract a note title and content from this request:
"{user_input}"

Respond in JSON:
{{
  "title": "short title",
  "content": "full note content",
  "tags": "tag1, tag2"
}}

If the user just says "save a note" or similar without content, create a generic placeholder."""

        try:
            parsed = self.call_llm_structured(prompt, temperature=0.3)
            title = parsed.get("title", "Untitled Note")
            content = parsed.get("content", user_input)
            tags = parsed.get("tags", "")

            note_id = self.memory.save_note(title=title, content=content, tags=tags)

            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=f"Note '{title}' saved successfully (ID: {note_id}).",
                data={"note_id": note_id, "title": title},
            )
        except Exception as e:
            logger.error(f"Note creation failed: {e}")
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=f"Failed to save note: {e}",
            )

    def _handle_note_search(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Search for notes."""
        if trace:
            trace.add_event("tool_call", "Searching notes")

        # Extract search query
        query = user_input
        for prefix in ("search notes for", "search notes", "find notes", "my notes about"):
            if prefix in user_input.lower():
                query = user_input.lower().split(prefix, 1)[-1].strip()
                break

        notes = self.memory.get_notes(search=query, limit=10)

        if not notes:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=f"No notes found matching '{query}'.",
            )

        lines = [f"**Notes matching '{query}':**", ""]
        for note in notes:
            lines.append(f"- **{note.get('title', 'Untitled')}** ({note.get('updated_at', 'unknown date')})")
            content_preview = note.get('content', '')[:100].replace('\n', ' ')
            lines.append(f"  {content_preview}...")
            lines.append("")

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
            data={"notes": notes, "query": query},
        )

    # -------------------------------------------------------------------------
    # PREFERENCE OPERATIONS
    # -------------------------------------------------------------------------

    def _handle_preference(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Handle preference get/set requests."""
        lower = user_input.lower()

        # Check for "set preference X to Y" pattern
        if any(kw in lower for kw in ("set", "change", "update", "make")):
            # Try to parse using LLM
            prompt = f"""Parse this preference command:
"{user_input}"

Extract the preference key and value. Respond in JSON:
{{"key": "preference_name", "value": "preference_value", "action": "set"}}

If it's asking to GET a preference, use {{"action": "get", "key": "preference_name"}}."""

            try:
                parsed = self.call_llm_structured(prompt, temperature=0.3)
                action = parsed.get("action", "get")
                key = parsed.get("key", "")
                value = parsed.get("value")

                if action == "set" and key and value is not None:
                    self.memory.set_preference(key, value)
                    return AgentResponse(
                        agent_name=self.name,
                        task_id=task.task_id,
                        success=True,
                        response=f"Preference '{key}' set to '{value}'.",
                    )
                elif action == "get" and key:
                    val = self.memory.get_preference(key, "(not set)")
                    return AgentResponse(
                        agent_name=self.name,
                        task_id=task.task_id,
                        success=True,
                        response=f"{key}: {val}",
                    )
            except Exception as e:
                logger.error(f"Preference parsing failed: {e}")

        # Default: list all preferences
        prefs = self.memory.get_all_preferences()
        if not prefs:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="No preferences set yet.",
            )

        lines = ["**Current Preferences:**", ""]
        for k, v in prefs.items():
            lines.append(f"- {k}: {v}")
        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
            data={"preferences": prefs},
        )

    # -------------------------------------------------------------------------
    # MEMORY QUERY
    # -------------------------------------------------------------------------

    def _handle_memory_query(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Answer questions based on stored memories."""
        if trace:
            trace.add_event("decision", "Querying memories for answer")

        # Search memories
        results = self.memory.search(user_input, top_k=8)

        if not results:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="I don't have any memories related to that. Would you like me to research it?",
            )

        # Build context from retrieved memories
        context_parts = []
        for mr in results:
            m = mr.memory
            context_parts.append(f"[{m.memory_type.value}] {m.content[:200]}")

        context = "\n".join(context_parts)

        # Use LLM to synthesize answer
        prompt = f"""Based on the following memories, answer the user's question:

Memories:
{context}

User Question: {user_input}

Provide a natural, helpful answer using the memories. If the memories don't fully answer the question, say so and offer to research further."""

        try:
            answer = self.call_llm(prompt, temperature=0.5)
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=answer,
                data={"memories_used": len(results)},
            )
        except Exception as e:
            # Fallback: just list relevant memories
            lines = ["I found these relevant memories:", ""]
            for mr in results[:5]:
                lines.append(f"- {mr.memory.content[:150]}...")
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="\n".join(lines),
            )

    # -------------------------------------------------------------------------
    # GOAL QUERY
    # -------------------------------------------------------------------------

    def _handle_goal_query(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Handle queries about goals and tasks."""
        goals = self.memory.get_active_goals()

        if not goals:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="You don't have any active goals at the moment. Would you like to set one?",
            )

        lines = ["**Your Active Goals:**", ""]
        for g in goals:
            progress = g.get("progress", 0) * 100
            due = g.get("due_date", "no deadline")
            lines.append(f"- **{g.get('title', 'Untitled')}** ({progress:.0f}% complete, due: {due})")
            lines.append(f"  {g.get('description', '')[:100]}")
            lines.append("")

        # Also get pending tasks
        tasks = self.memory.get_pending_tasks()
        if tasks:
            lines.append("**Pending Tasks:**")
            for t in tasks[:5]:
                lines.append(f"- {t.get('title', 'Task')} [Assigned to: {t.get('assigned_agent', 'unassigned')}]")

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
            data={"goals": goals, "pending_tasks": tasks},
        )

    # -------------------------------------------------------------------------
    # GENERAL MEMORY
    # -------------------------------------------------------------------------

    def _handle_general_memory(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Store the input as a general memory and acknowledge."""
        self.memory.store_memory(
            content=user_input,
            memory_type=MemoryType.CONVERSATION,
            importance=0.5,
            source="memory_agent",
        )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="I've noted that. I'll remember it for future reference.",
        )
