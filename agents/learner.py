"""
Learner Agent for Jarvis Multi-Agent AI Operating System.

Tracks outcomes, identifies patterns, and generates insights for improvement.

This is NOT fake learning. It implements a realistic learning architecture:
- Records every user request, action, result, and success/failure
- Analyzes patterns in outcomes over time
- Identifies common failure modes
- Suggests adjustments to routing and tool usage
- Stores insights as memories for future reference

The system gets smarter over time through accumulated experience.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from config import MODEL_CONVERSATIONAL, MIN_OUTCOMES_FOR_PATTERN, LEARNING_ENABLED
from core.models import (
    AgentResponse,
    AgentTask,
    ExecutionTrace,
    MemoryType,
    Outcome,
    PatternInsight,
)
from agents.base import BaseAgent
from framework.routing import parse_intent_via_llm

logger = logging.getLogger(__name__)


class LearnerAgent(BaseAgent):
    """
    Analyzes outcomes and discovers patterns for system improvement.

    Capabilities:
    - Outcome tracking and analysis
    - Pattern discovery in failures
    - Routing accuracy assessment
    - Tool effectiveness measurement
    - Insight generation and storage
    """

    name = "learner"
    description = "Tracks outcomes, analyzes patterns, and generates insights for continuous improvement"
    capabilities = ["learning", "analysis", "pattern_discovery", "improvement"]
    default_model = MODEL_CONVERSATIONAL

    def execute_task(self, task: AgentTask, trace: ExecutionTrace | None = None) -> AgentResponse:
        """
        Execute learning/analysis tasks.
        """
        if not LEARNING_ENABLED:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response="Learning system is currently disabled.",
            )

        user_input = task.context.get("user_input", task.description)

        if trace:
            trace.add_event("decision", "LearnerAgent parsing intent via LLM")

        valid_ops = ["stats", "insights", "accuracy", "summary"]
        prompt = (
            "You are the Learner Agent of Jarvis. Classify the user's learning query into one operation.\n\n"
            "Operations:\n"
            '- "stats"    : performance statistics, how am I doing\n'
            '- "insights" : patterns, what have you learned, analysis\n'
            '- "accuracy" : routing accuracy, decisions\n'
            '- "summary"  : general learning summary (fallback)\n\n'
            f'User request: "{user_input}"\n\n'
            'Respond ONLY with JSON: {"intent": "<operation>", "parameters": {}}'
        )
        op, _params = parse_intent_via_llm(
            self.llm, prompt, valid_ops, model=self.default_model
        )

        if trace:
            trace.add_event("decision", f"LLM selected operation: {op}")

        handler_map = {
            "stats": self._handle_performance_stats,
            "insights": self._handle_insight_generation,
            "accuracy": self._handle_routing_analysis,
        }
        handler = handler_map.get(op, self._handle_learning_summary)
        return handler(task, trace)

    # -------------------------------------------------------------------------
    # PERFORMANCE STATISTICS
    # -------------------------------------------------------------------------

    def _handle_performance_stats(
        self, task: AgentTask, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Generate performance statistics for all agents."""
        if trace:
            trace.add_event("decision", "Generating performance statistics")

        # Get stats from memory store
        from core.registry import AgentRegistry
        registry = AgentRegistry()
        all_agents = registry.list_agents()

        lines = ["**System Performance Statistics**", ""]
        total_requests = 0
        total_successes = 0

        for agent_name in all_agents:
            if agent_name == "learner":
                continue
            stats = self.memory.store.get_outcome_stats(agent_name)
            total_requests += stats["total"]
            total_successes += stats["successes"]

            if stats["total"] > 0:
                success_rate = (stats["successes"] / stats["total"]) * 100
                lines.append(
                    f"- **{agent_name}**: {stats['successes']}/{stats['total']} "
                    f"successful ({success_rate:.1f}%) "
                    f"| avg confidence: {stats['avg_confidence']:.2f}"
                )

        if total_requests > 0:
            overall_rate = (total_successes / total_requests) * 100
            lines.append("")
            lines.append(f"**Overall**: {total_successes}/{total_requests} successful ({overall_rate:.1f}%)")

        # Get memory stats
        mem_stats = self.memory.get_stats()
        lines.append("")
        lines.append("**Memory:**")
        lines.append(f"- Conversations: {mem_stats['conversations']}")
        lines.append(f"- Memories: {mem_stats['memories']}")
        lines.append(f"- Vectors: {mem_stats['vectors']}")

        # Get routing accuracy
        routing_acc = self.memory.store.get_routing_accuracy()
        lines.append("")
        lines.append(f"**Routing Accuracy**: {routing_acc:.1f}%")

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
            data={"total_requests": total_requests, "overall_success_rate": overall_rate if total_requests > 0 else 0},
        )

    # -------------------------------------------------------------------------
    # INSIGHT GENERATION
    # -------------------------------------------------------------------------

    def _handle_insight_generation(
        self, task: AgentTask, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Analyze outcomes and generate insights."""
        if trace:
            trace.add_event("decision", "Generating insights from outcome data")

        # Get recent outcomes
        outcomes = self.memory.store.get_outcomes(limit=200)

        if len(outcomes) < MIN_OUTCOMES_FOR_PATTERN:
            return AgentResponse(
                agent_name=self.name,
                task_id=task.task_id,
                success=True,
                response=f"Not enough data yet for meaningful insights. I have {len(outcomes)} outcomes recorded. Need at least {MIN_OUTCOMES_FOR_PATTERN}.",
            )

        # Analyze patterns
        insights = self._discover_patterns(outcomes)

        # Store insights as memories
        for insight in insights:
            self.memory.store_memory(
                content=f"Insight: {insight.pattern_description}. "
                        f"Success rate: {insight.success_rate*100:.1f}%. "
                        f"Suggestion: {insight.suggested_adjustment or 'None'}",
                memory_type=MemoryType.LEARNING,
                category="insight",
                importance=min(0.9, insight.confidence),
                source="learner_agent",
            )

        # Format response
        if insights:
            lines = ["**Discovered Insights:**", ""]
            for i, insight in enumerate(insights[:5], 1):
                lines.append(f"{i}. **{insight.pattern_description}**")
                lines.append(f"   - Occurrences: {insight.occurrence_count}")
                lines.append(f"   - Success rate: {insight.success_rate*100:.1f}%")
                if insight.suggested_adjustment:
                    lines.append(f"   - Suggestion: {insight.suggested_adjustment}")
                lines.append("")
        else:
            lines = ["I've analyzed the data but no strong patterns emerged yet.", "Keep using the system - insights improve with more data!"]

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
            data={"insights": [insight.model_dump() for insight in insights]},
        )

    def _discover_patterns(self, outcomes: List[Outcome]) -> List[PatternInsight]:
        """Discover patterns in outcome data."""
        insights: List[PatternInsight] = []

        # Pattern 1: Agent-specific failure rates
        agent_outcomes: Dict[str, List[bool]] = defaultdict(list)
        for o in outcomes:
            agent_outcomes[o.agent_name].append(o.success)

        for agent, results in agent_outcomes.items():
            if len(results) >= MIN_OUTCOMES_FOR_PATTERN:
                success_rate = sum(results) / len(results)
                if success_rate < 0.6:
                    insights.append(PatternInsight(
                        pattern_description=f"{agent} has a low success rate ({success_rate*100:.0f}%)",
                        occurrence_count=len(results),
                        success_rate=success_rate,
                        applicable_agents=[agent],
                        suggested_adjustment=f"Review {agent} error logs and consider parameter adjustments",
                        confidence=min(0.9, len(results) / 50),
                    ))

        # Pattern 2: Common failure combinations
        failure_combos: Counter = Counter()
        for o in outcomes:
            if not o.success:
                combo = f"{o.agent_name}:{o.action_taken}"
                failure_combos[combo] += 1

        for combo, count in failure_combos.most_common(3):
            if count >= 2:
                agent, action = combo.split(":", 1)
                insights.append(PatternInsight(
                    pattern_description=f"'{action}' frequently fails when handled by {agent}",
                    occurrence_count=count,
                    success_rate=0.0,
                    applicable_agents=[agent],
                    suggested_adjustment=f"Consider routing '{action}' to a different agent or adding validation",
                    confidence=min(0.8, count / 10),
                ))

        # Pattern 3: Time-based patterns (recent degradation)
        recent = [o for o in outcomes[-50:] if not o.success]
        older = [o for o in outcomes[:-50] if not o.success] if len(outcomes) > 50 else []
        # This analysis would be more sophisticated in production

        return insights

    # -------------------------------------------------------------------------
    # ROUTING ANALYSIS
    # -------------------------------------------------------------------------

    def _handle_routing_analysis(
        self, task: AgentTask, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Analyze routing decision accuracy."""
        if trace:
            trace.add_event("decision", "Analyzing routing accuracy")

        accuracy = self.memory.store.get_routing_accuracy()

        # Get per-agent accuracy
        from core.registry import AgentRegistry
        registry = AgentRegistry()
        lines = ["**Routing Decision Analysis**", ""]
        lines.append(f"Overall routing accuracy: {accuracy:.1f}%")
        lines.append("")

        for agent in registry.list_agents():
            agent_acc = self.memory.store.get_routing_accuracy(agent)
            lines.append(f"- {agent}: {agent_acc:.1f}%")

        lines.append("")
        lines.append("To improve accuracy, provide feedback when I route incorrectly (e.g., 'That should have gone to the researcher').")

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
        )

    # -------------------------------------------------------------------------
    # LEARNING SUMMARY
    # -------------------------------------------------------------------------

    def _handle_learning_summary(
        self, task: AgentTask, trace: ExecutionTrace | None = None
    ) -> AgentResponse:
        """Provide a summary of what the learning system has observed."""
        outcomes = self.memory.store.get_outcomes(limit=50)
        insights = self.memory.get_recent_memories(memory_type=MemoryType.LEARNING, limit=5)

        lines = ["**Learning System Summary**", ""]
        lines.append(f"Total outcomes recorded: {len(outcomes)}")
        lines.append(f"Insights discovered: {len(insights)}")
        lines.append("")

        if insights:
            lines.append("**Recent Insights:**")
            for i, mem in enumerate(insights[:3], 1):
                lines.append(f"{i}. {mem.content[:120]}...")

        lines.append("")
        lines.append(
            "I'm continuously learning from every interaction. "
            "I track which agents succeed, which fail, and why. "
            "Over time, this helps me make better routing decisions and suggest improvements."
        )

        return AgentResponse(
            agent_name=self.name,
            task_id=task.task_id,
            success=True,
            response="\n".join(lines),
        )
