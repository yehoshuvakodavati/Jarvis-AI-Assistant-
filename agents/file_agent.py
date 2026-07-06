"""
File Agent for Jarvis Multi-Agent AI Operating System.

Handles file system operations:
- Search for files
- List directories
- Read file contents
- Find documents and PDFs
- Project search

Uses tools:
- file_search: Search by pattern
- file_read: Read file contents
- file_list: List directory contents
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import MODEL_CONVERSATIONAL
from core.models import AgentResponse, AgentTask, ExecutionTrace
from agents.base import BaseAgent
from framework.routing import parse_intent_via_llm

logger = logging.getLogger(__name__)


class FileAgent(BaseAgent):
    """
    Manages file system operations and searches.

    Capabilities:
    - File search by pattern
    - Directory listing
    - File content reading
    - Document discovery
    - Project structure analysis
    """

    name = "file_agent"
    description = "Searches files, lists directories, reads documents, and analyzes project structures"
    capabilities = ["files", "file_search", "document_discovery", "project_analysis"]
    default_model = MODEL_CONVERSATIONAL

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """Execute file system tasks via LLM-based intent parsing."""
        user_input = task.context.get("user_input", task.description)

        if trace:
            trace.add_event("decision", "FileAgent parsing intent via LLM")

        # Reasoning-based operation selection (replaces keyword if/elif).
        # The LLM picks one of these operations; handlers below extract params.
        valid_ops = ["search", "list", "read", "find_pdf", "project", "general"]
        prompt = (
            "You are the File Agent of Jarvis. Classify the user's file request into one operation.\n\n"
            "Operations:\n"
            '- "search"     : find files by name/pattern/extension\n'
            '- "list"       : list contents of a directory\n'
            '- "read"       : read a file\'s contents\n'
            '- "find_pdf"   : find PDF documents\n'
            '- "project"    : analyze a project/codebase structure\n'
            '- "general"    : none of the above (fallback)\n\n'
            f'User request: "{user_input}"\n\n'
            'Respond ONLY with JSON: {"intent": "<operation>", "parameters": {}}'
        )
        op, _params = parse_intent_via_llm(
            self.llm, prompt, valid_ops, model=self.default_model
        )

        if trace:
            trace.add_event("decision", f"LLM selected operation: {op}")

        # Delegate to the existing handler for that operation. The handlers
        # retain their parameter-extraction logic (regex for dir/pattern).
        handler_map = {
            "search": self._handle_file_search,
            "list": self._handle_directory_list,
            "read": self._handle_file_read,
            "find_pdf": self._handle_pdf_search,
            "project": self._handle_project_search,
        }
        handler = handler_map.get(op, self._handle_general_file)
        return handler(task, user_input, trace)

    def _handle_file_search(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Search for files matching a pattern."""
        # Extract search parameters
        directory = "."
        pattern = "*"

        # Try to extract from message
        import re

        # Pattern extraction
        for phrase in ("find file", "search file", "find", "search"):
            if phrase in user_input.lower():
                remainder = user_input.lower().split(phrase, 1)[-1].strip()
                # Check for wildcard patterns
                if "*" in remainder:
                    pattern = remainder.split()[-1] if " " in remainder else remainder
                    break
                # Common file types
                for ext in (".py", ".js", ".java", ".txt", ".md", ".json", ".csv", ".pdf", ".docx"):
                    if ext in user_input.lower():
                        pattern = f"*{ext}"
                        break

        # Directory extraction
        dir_match = re.search(r'in\s+([\w\-/\\.]+)', user_input.lower())
        if dir_match:
            directory = dir_match.group(1)

        if trace:
            trace.add_event("tool_call", f"Searching for {pattern} in {directory}")

        result = self.call_tool("file_search", directory=directory, pattern=pattern)

        if result.success and result.result:
            files = result.result[:20]  # Limit results
            lines = [f"**Found {len(files)} file(s) matching '{pattern}':**", ""]
            for f in files:
                lines.append(f"- {f}")
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="\n".join(lines),
                data={"files": files, "pattern": pattern},
            )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=f"No files found matching '{pattern}' in {directory}.",
        )

    def _handle_directory_list(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """List directory contents."""
        directory = "."

        import re
        dir_match = re.search(r'(?:in|of)\s+([\w\-/\\.~]+)', user_input.lower())
        if dir_match:
            directory = dir_match.group(1)
        elif "desktop" in user_input.lower():
            directory = str(Path.home() / "Desktop")
        elif "documents" in user_input.lower():
            directory = str(Path.home() / "Documents")
        elif "downloads" in user_input.lower():
            directory = str(Path.home() / "Downloads")

        if trace:
            trace.add_event("tool_call", f"Listing directory: {directory}")

        result = self.call_tool("file_list", directory=directory)

        if result.success and result.result:
            entries = result.result[:50]
            lines = [f"**Contents of {directory}:**", ""]
            for entry in entries:
                lines.append(f"- {entry}")
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="\n".join(lines),
                data={"entries": entries, "directory": directory},
            )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=f"Could not list contents of {directory}.",
        )

    def _handle_file_read(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Read a file's contents."""
        # Extract file path
        import re
        path_match = re.search(r'(?:read|show|open)\s+(?:file\s+)?[`\"\']?([\w\-./\\~]+)[`\"\']?', user_input.lower())
        path = path_match.group(1) if path_match else None

        if not path:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="Please specify which file you'd like me to read.",
            )

        if trace:
            trace.add_event("tool_call", f"Reading file: {path}")

        result = self.call_tool("file_read", path=path)

        if result.success:
            content = result.result
            if content and not content.startswith("Error"):
                # Truncate very large files
                if len(content) > 3000:
                    preview = content[:3000]
                    response = f"**{path}** (showing first 3000 chars)\n\n```\n{preview}\n```\n\n*... ({len(content)} total characters)*"
                else:
                    response = f"**{path}**\n\n```\n{content}\n```"

                return AgentResponse(
                    agent_name=self.name,
                    task_id=task.task_id,
                    success=True,
                    response=response,
                    data={"path": path, "length": len(content)},
                )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=False,
            response=f"Could not read file: {path}. {result.result if result.result else ''}",
        )

    def _handle_pdf_search(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Search for PDF documents."""
        directory = str(Path.home())

        import re
        dir_match = re.search(r'in\s+([\w\-/\\.~]+)', user_input.lower())
        if dir_match:
            directory = dir_match.group(1)

        if trace:
            trace.add_event("tool_call", f"Searching for PDFs in {directory}")

        result = self.call_tool("file_search", directory=directory, pattern="*.pdf")

        if result.success and result.result:
            pdfs = result.result[:20]
            lines = [f"**Found {len(pdfs)} PDF document(s):**", ""]
            for pdf in pdfs:
                lines.append(f"- {pdf}")
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="\n".join(lines),
                data={"pdfs": pdfs},
            )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=f"No PDFs found in {directory}.",
        )

    def _handle_project_search(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Analyze a project directory structure."""
        directory = "."

        import re
        dir_match = re.search(r'(?:project|repo)\s+(?:in\s+)?[`\"\']?([\w\-/\\.~]+)[`\"\']?', user_input.lower())
        if dir_match:
            directory = dir_match.group(1)

        if trace:
            trace.add_event("tool_call", f"Analyzing project in: {directory}")

        # List directory
        list_result = self.call_tool("file_list", directory=directory)
        if not list_result.success:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=f"Could not analyze project in {directory}.",
            )

        # Count code files
        code_result = self.call_tool("file_search", directory=directory, pattern="*.py")
        py_files = code_result.result if code_result.success else []

        js_result = self.call_tool("file_search", directory=directory, pattern="*.js")
        js_files = js_result.result if js_result.success else []

        md_result = self.call_tool("file_search", directory=directory, pattern="*.md")
        md_files = md_result.result if md_result.success else []

        entries = list_result.result or []
        lines = [f"**Project Analysis: {directory}**", ""]
        lines.append(f"Total entries: {len(entries)}")
        lines.append(f"Python files: {len(py_files)}")
        lines.append(f"JavaScript files: {len(js_files)}")
        lines.append(f"Markdown docs: {len(md_files)}")
        lines.append("")
        lines.append("**Top-level structure:**")
        for entry in entries[:20]:
            lines.append(f"- {entry}")

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
            data={
                "directory": directory,
                "entries": len(entries),
                "py_files": len(py_files),
                "js_files": len(js_files),
            },
        )

    def _handle_general_file(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Handle general file-related queries."""
        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=(
                "I can help you with files:\n"
                "- Find files: 'Find all PDFs in Documents'\n"
                "- List directories: 'Show me Desktop contents'\n"
                "- Read files: 'Read file README.md'\n"
                "- Project analysis: 'Analyze project in ./src'\n"
                "\nWhat would you like to do?"
            ),
        )
