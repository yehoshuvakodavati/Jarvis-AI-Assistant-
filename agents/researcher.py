"""
Researcher Agent for Jarvis Multi-Agent AI Operating System.

Gathers information from the web through search and content extraction.
Can return structured search cards or synthesized summaries.

Uses tools:
- web_search: Find relevant web pages
- web_fetch: Extract content from pages
- web_search_cards: Rich search results for UI
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import MODEL_RESEARCHER, TEMP_CONVERSATIONAL
from core.models import AgentResponse, AgentTask, ExecutionTrace
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """
    Researches topics on the web and synthesizes findings.

    Capabilities:
    - Web search
    - Content extraction and summarization
    - Multi-source synthesis
    - Fact-checking against sources
    """

    name = "researcher"
    description = "Researches topics on the web, extracts content, and synthesizes findings"
    capabilities = ["research", "search", "summarize", "information_gathering"]
    default_model = MODEL_RESEARCHER

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """
        Execute research tasks.
        """
        user_input = task.context.get("user_input", task.description)
        memory_context = task.context.get("memory_context", "")

        if trace:
            trace.add_event("decision", "ResearcherAgent beginning research")

        # Determine research strategy
        use_cards = self._should_use_cards(user_input)

        if use_cards:
            return self._handle_card_search(task, user_input, trace)
        else:
            return self._handle_deep_research(task, user_input, memory_context, trace)

    def _should_use_cards(self, user_input: str) -> bool:
        """Determine if the request is best served with search cards."""
        card_keywords = [
            "latest", "news", "today", "score", "match", "ipl",
            "tutorials", "interview questions", "roadmap", "courses",
            "current", "recent", "update", "live", "headlines",
        ]
        lower = user_input.lower()
        return any(kw in lower for kw in card_keywords)

    def _handle_card_search(
        self, task: AgentTask, user_input: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Return search results as structured cards."""
        if trace:
            trace.add_event("tool_call", "Executing web_search_cards")

        result = self.call_tool("web_search_cards", query=user_input, max_results=6)

        if not result.success:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=False,
                response=f"Search failed: {result.error_message}",
            )

        cards = result.result or []
        if not cards:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="I couldn't find any relevant results for that query.",
            )

        # Format intro text
        intro = f"Here are the top results for \"{user_input}\":"

        if trace:
            trace.add_event("tool_result", f"Found {len(cards)} search results")

        # Store search as memory
        self.memory.store_memory(
            content=f"Searched for: {user_input}. Found {len(cards)} results.",
            memory_type="action",
            category="research",
            importance=0.5,
        )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=intro,
            data={"cards": cards, "query": user_input},
        )

    def _handle_deep_research(
        self, task: AgentTask, user_input: str, memory_context: str, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Perform deep research: search, fetch, and summarize."""
        if trace:
            trace.add_event("decision", "Performing deep research with fetch+summarize")

        # Step 1: Search
        if trace:
            trace.add_event("tool_call", f"Searching for: {user_input}")

        search_result = self.call_tool("web_search", query=user_input, max_results=3)

        if not search_result.success or not search_result.result:
            # Fallback: try to answer from knowledge
            answer = self._answer_from_knowledge(user_input, memory_context)
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=answer,
            )

        search_results = search_result.result
        if trace:
            trace.add_event("tool_result", f"Found {len(search_results)} results")

        # Step 2: Fetch top result
        best_result = search_results[0]
        url = best_result.get("url", "")

        if trace:
            trace.add_event("tool_call", f"Fetching content from: {url}")

        fetch_result = self.call_tool("web_fetch", url=url)

        if not fetch_result.success or not fetch_result.result:
            # Use search snippet as fallback
            summary = self._summarize_snippets(user_input, search_results)
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=summary,
                data={"sources": [r["url"] for r in search_results]},
            )

        content_data = fetch_result.result
        content = content_data.get("content", "")
        title = content_data.get("title", "")

        if trace:
            trace.add_event("tool_result", f"Fetched {len(content)} chars from {url}")

        # Step 3: Summarize with LLM
        summary = self._summarize_content(user_input, content, title, url)

        # Step 4: Save as note
        try:
            self.call_tool("note_create", title=user_input, content=summary, tags="research,auto")
        except Exception as e:
            logger.warning(f"Auto-note save failed: {e}")

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response=summary,
            data={
                "sources": [r["url"] for r in search_results],
                "primary_source": url,
                "word_count": content_data.get("word_count", 0),
            },
        )

    def _summarize_content(self, query: str, content: str, title: str, source: str) -> str:
        """Use LLM to summarize web content."""
        # Truncate content to fit in prompt
        max_content = 4000
        truncated = content[:max_content] if len(content) > max_content else content

        prompt = f"""You are a research assistant. Summarize the following web content for the user's query.

User Query: {query}
Article Title: {title}
Source: {source}

Content:
{truncated}

Instructions:
- Extract only the most relevant and important points
- Use bullet points ("- ")
- Keep each point concise
- Aim for 5-7 bullet points
- Include the source URL at the end
- Respond in plain text, no markdown headers

Summary:"""

        try:
            summary = self.call_llm(prompt, temperature=0.4)
            return f"**Research Summary**\n\n{summary}\n\n*Source: {source}*"
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return f"I found information on this topic but couldn't generate a summary. Source: {source}"

    def _summarize_snippets(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Summarize search result snippets when full content fetch fails."""
        lines = [f"**Quick Findings for: {query}**", ""]
        for r in results[:3]:
            lines.append(f"- **{r.get('title', 'Untitled')}**: {r.get('summary', 'No summary')[:150]}...")
            lines.append(f"  Source: {r.get('url', '')}")
            lines.append("")
        return "\n".join(lines)

    def _answer_from_knowledge(self, query: str, memory_context: str) -> str:
        """Attempt to answer from LLM knowledge when web search fails."""
        prompt = f"""Answer the following question from your knowledge:

{memory_context}

Question: {query}

Provide a clear, accurate answer. If you're uncertain, say so."""

        try:
            return self.call_llm(prompt, temperature=TEMP_CONVERSATIONAL)
        except Exception as e:
            return f"I couldn't search the web or find this in my knowledge. Error: {e}"
