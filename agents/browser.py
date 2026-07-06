"""
Browser Agent for Jarvis Multi-Agent AI Operating System.

Handles web browsing operations:
- Navigate to websites
- Extract specific content
- Browse multiple pages
- Formulate browsing strategies

Uses tools:
- web_fetch: Extract content from URLs
- web_search: Find relevant pages
- system_open_url: Open in default browser
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import MODEL_CONVERSATIONAL
from core.models import AgentResponse, AgentTask, ExecutionTrace
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class BrowserAgent(BaseAgent):
    """
    Navigates websites and extracts specific content.

    Capabilities:
    - Browse specific websites
    - Extract content from pages
    - Multi-page browsing strategies
    - Content comparison across sources
    """

    name = "browser"
    description = "Navigates websites and extracts content for research"
    capabilities = ["browsing", "web_navigation", "content_extraction"]
    default_model = MODEL_CONVERSATIONAL

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """Execute browsing tasks."""
        user_input = task.context.get("user_input", task.description)
        lower = user_input.lower()

        if trace:
            trace.add_event("decision", "BrowserAgent analyzing browsing request")

        # Extract URL if present
        import re
        url_match = re.search(r'(https?://[^\s]+)', user_input)
        url = url_match.group(1) if url_match else None

        if not url:
            # Try to find a domain
            domain_match = re.search(r'(?:go to |visit |open )([\w\-]+\.(?:com|org|net|io|dev|co))', lower)
            if domain_match:
                url = "https://" + domain_match.group(1)

        if url:
            if trace:
                trace.add_event("tool_call", f"Fetching content from: {url}")

            result = self.call_tool("web_fetch", url=url)

            if result.success and result.result:
                data = result.result
                content = data.get("content", "")
                title = data.get("title", url)

                # Summarize if content is large
                if len(content) > 1000:
                    summary = self._summarize_browse_result(title, content, url)
                    response_text = f"**{title}**\n\n{summary}\n\n*Full content: {len(content)} characters*"
                else:
                    response_text = f"**{title}**\n\n{content[:800]}...\n\n*Source: {url}*"

                return AgentResponse(
                    agent_name=self.name,
                    task_id=task.task_id,
                    success=True,
                    response=response_text,
                    data={"url": url, "title": title, "word_count": data.get("word_count", 0)},
                )
            else:
                # Fallback: open in browser
                self.call_tool("system_open_url", url=url)
                return AgentResponse(
                    agent_name=self.name,
                    task_id=task.task_id,
                    success=True,
                    response=f"I couldn't extract the content directly, so I opened {url} in your browser instead.",
                )

        # No URL found - search and browse
        if any(kw in lower for kw in ("search", "find", "look for")):
            # Extract search query
            query = user_input
            for prefix in ("search for", "find", "look for", "browse for"):
                if prefix in lower:
                    query = lower.split(prefix, 1)[-1].strip()
                    break

            search_result = self.call_tool("web_search", query=query, max_results=3)
            if search_result.success and search_result.result:
                results = search_result.result
                lines = [f"**Search results for '{query}':**", ""]
                for r in results:
                    lines.append(f"- **{r.get('title', 'Untitled')}** - {r.get('source', '')}")
                    lines.append(f"  {r.get('summary', '')[:120]}...")
                    lines.append(f"  {r.get('url', '')}")
                    lines.append("")

                return AgentResponse(
                    agent_name=self.name,
                    task_id=task.task_id,
                    success=True,
                    response="\n".join(lines),
                    data={"results": results},
                )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="I can browse websites for you. Please provide a URL or tell me what to search for.",
        )

    def _summarize_browse_result(self, title: str, content: str, url: str) -> str:
        """Summarize browsed content."""
        truncated = content[:3000]
        prompt = f"""Summarize the key information from this web page:

Title: {title}
URL: {url}

Content:
{truncated}

Provide a concise summary of the main points in bullet format."""

        try:
            return self.call_llm(prompt, temperature=0.4)
        except Exception:
            return content[:500] + "..."
