"""
Coder Agent for Jarvis Multi-Agent AI Operating System.

Handles code-related tasks:
- Code generation
- Code review and analysis
- Debugging assistance
- Algorithm explanation
- File reading/writing for code

Uses tools:
- file_read: Read existing code
- file_write: Write generated code (marked dangerous)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import MODEL_CODER, TEMP_CODE
from core.models import AgentResponse, AgentTask, ExecutionTrace
from agents.base import BaseAgent
from framework.routing import parse_intent_via_llm

logger = logging.getLogger(__name__)


class CoderAgent(BaseAgent):
    """
    Handles code generation, review, debugging, and explanation.

    Capabilities:
    - Generate code from descriptions
    - Review and analyze existing code
    - Explain algorithms and concepts
    - Debug error messages
    - Read/write code files
    """

    name = "coder"
    description = "Generates, reviews, debugs, and explains code in various languages"
    capabilities = ["coding", "code_generation", "code_review", "debugging", "algorithm_explanation"]
    default_model = MODEL_CODER

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """Execute coding tasks via LLM-based intent parsing."""
        user_input = task.context.get("user_input", task.description)

        if trace:
            trace.add_event("decision", "CoderAgent parsing intent via LLM")

        valid_ops = ["review", "debug", "explain", "generate", "generate"]
        prompt = (
            "You are the Coder Agent of Jarvis. Classify the user's coding request into one operation.\n\n"
            "Operations:\n"
            '- "review"   : review/analyze code, find issues\n'
            '- "debug"    : debug an error/exception/traceback\n'
            '- "explain"  : explain how code or a concept works\n'
            '- "generate" : write/create/implement new code (fallback)\n\n'
            f'User request: "{user_input}"\n\n'
            'Respond ONLY with JSON: {"intent": "<operation>", "parameters": {}}'
        )
        op, _params = parse_intent_via_llm(
            self.llm, prompt, valid_ops, model=self.default_model
        )

        if trace:
            trace.add_event("decision", f"LLM selected operation: {op}")

        handler_map = {
            "review": self._handle_code_review,
            "debug": self._handle_debugging,
            "explain": self._handle_explanation,
            "generate": self._handle_code_generation,
        }
        handler = handler_map.get(op, self._handle_code_generation)
        return handler(task, user_input, trace)

    # -------------------------------------------------------------------------
    # CODE GENERATION
    # -------------------------------------------------------------------------

    def _handle_code_generation(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Generate code based on user description."""
        if trace:
            trace.add_event("decision", "Generating code")

        prompt = f"""You are an expert programmer. Write clean, well-documented code for the following request.

Request: {user_input}

Requirements:
- Write production-quality code
- Include comments explaining key logic
- Handle edge cases where appropriate
- Use best practices for the target language
- If the language isn't specified, use Python

Provide ONLY the code in a markdown code block, followed by a brief explanation."""

        try:
            code_response = self.call_llm(prompt, temperature=TEMP_CODE)

            # Store as memory
            self.memory.store_memory(
                content=f"Generated code for: {user_input[:100]}",
                memory_type="action",
                category="coding",
                importance=0.6,
            )

            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=code_response,
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=f"Failed to generate code: {e}",
            )

    # -------------------------------------------------------------------------
    # CODE REVIEW
    # -------------------------------------------------------------------------

    def _handle_code_review(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Review code provided by the user."""
        if trace:
            trace.add_event("decision", "Reviewing code")

        # Try to extract code from the message
        code = self._extract_code(user_input)

        if not code:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="I don't see any code to review. Please paste the code you'd like me to analyze.",
            )

        prompt = f"""Review the following code and provide constructive feedback:

```python
{code}
```

Analyze:
1. Correctness - Are there bugs or logical errors?
2. Style - Follows PEP 8 / language conventions?
3. Performance - Any inefficiencies?
4. Security - Any vulnerabilities?
5. Maintainability - Readable and well-structured?

Provide your review in a structured format with actionable suggestions."""

        try:
            review = self.call_llm(prompt, temperature=0.3)
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=review,
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=f"Review failed: {e}",
            )

    # -------------------------------------------------------------------------
    # DEBUGGING
    # -------------------------------------------------------------------------

    def _handle_debugging(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Help debug errors or issues."""
        if trace:
            trace.add_event("decision", "Debugging code/error")

        prompt = f"""Help debug the following issue:

{user_input}

Provide:
1. What likely caused the error
2. How to fix it
3. Best practices to prevent it in the future

Be specific and actionable."""

        try:
            debug_help = self.call_llm(prompt, temperature=0.3)
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=debug_help,
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=f"Debug analysis failed: {e}",
            )

    # -------------------------------------------------------------------------
    # EXPLANATION
    # -------------------------------------------------------------------------

    def _handle_explanation(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Explain code or concepts."""
        if trace:
            trace.add_event("decision", "Explaining code/concept")

        code = self._extract_code(user_input)

        if code:
            prompt = f"""Explain the following code in simple terms:

```python
{code}
```

Break down:
- What the code does overall
- How each section works
- Key functions and their purposes
- Any important patterns or techniques used

Make it understandable for someone learning to code."""
        else:
            prompt = f"""Explain the following programming concept:

{user_input}

Provide:
- A clear definition
- Why it's useful
- A simple example
- Common pitfalls or best practices

Make it beginner-friendly but technically accurate."""

        try:
            explanation = self.call_llm(prompt, temperature=0.4)
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=explanation,
            )
        except Exception as e:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=f"Explanation failed: {e}",
            )

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------

    def _extract_code(self, text: str) -> str | None:
        """Extract code from markdown code blocks or plain text."""
        import re

        # Try markdown code block
        code_block_match = re.search(r'```[\w]*\n(.*?)```', text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Try inline code blocks
        inline_match = re.search(r'`([^`]+)`', text)
        if inline_match and len(inline_match.group(1)) > 30:
            return inline_match.group(1)

        # Heuristic: if text looks like code (has indentation, def/class, etc.)
        lines = text.split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('def ', 'class ', 'import ', 'from ', '#', '//', 'function ', 'const ', 'let ', 'var ')):
                in_code = True
            if in_code:
                code_lines.append(line)
            if in_code and stripped == '' and len(code_lines) > 3:
                break

        if len(code_lines) >= 3:
            return '\n'.join(code_lines)

        return None
