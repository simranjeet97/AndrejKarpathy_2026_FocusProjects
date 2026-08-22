"""Memory agent condition — persists external structured memories across tasks."""

from __future__ import annotations

import json
import time

from agent_learning.agent.base import AgentBase, AgentResult
from agent_learning.environment.runner import CodeExtractor
from agent_learning.environment.task import Task
from agent_learning.memory.retrieval import MemoryRetriever
from agent_learning.memory.store import MemoryEntry, MemoryStore
from agent_learning.models.interface import Message, ModelInterface, TokenBudget


class MemoryAgent(AgentBase):
    """Memory agent condition.

    Retrieves external memories before solving tasks, and writes new
    structured memories after receiving feedback. Memory state persists.
    """

    def __init__(
        self,
        model: ModelInterface,
        memory_store: MemoryStore | None = None,
    ) -> None:
        super().__init__(model=model, condition_name="memory")
        self.memory_store = memory_store or MemoryStore()
        self.retriever = MemoryRetriever(self.memory_store)

    def solve(self, task: Task, budget: TokenBudget | None = None) -> AgentResult:
        budget = budget or TokenBudget()
        start_time = time.monotonic()
        attempts = 0
        final_code = task.starter_code
        success = False
        memories_written: list[str] = []
        memories_retrieved: list[str] = []

        # Step 1: Retrieve memories
        retrieved_entries = self.retriever.retrieve(
            query=task.specification, task_family=task.family.value, k=3
        )
        memories_retrieved = [e.id for e in retrieved_entries]

        memory_context = ""
        if retrieved_entries:
            formatted = "\n\n".join(e.to_prompt_str() for e in retrieved_entries)
            memory_context = f"\n\nRelevant Past Memories/Heuristics:\n{formatted}\n"

        messages = [
            Message(
                role="system",
                content="You are a coding assistant with external memory. Use relevant past memories to avoid repeating mistakes.",
            ),
            Message(
                role="user",
                content=f"Task ID: {task.id}\nTask Specification:\n{task.specification}{memory_context}\n\nStarter Code:\n{task.starter_code}\n\nVisible Tests:\n{task.visible_tests}",
            ),
        ]

        feedback_summary = ""

        while budget.can_call_model and budget.can_run_tests:
            attempts += 1
            response = self.model.complete(messages)
            budget.record_model_call(response)

            code = CodeExtractor.extract(response.content)
            if code:
                final_code = code

            messages.append(Message(role="assistant", content=response.content))

            budget.record_test_run()
            feedback = self.test_executor.run_visible_tests(task, final_code)
            feedback_summary = feedback.to_prompt_str()

            if feedback.success:
                success = True
                break

            messages.append(
                Message(
                    role="user",
                    content=f"Solution failed tests:\n{feedback_summary}\nPlease fix your code.",
                )
            )

        # Step 2: Write memory after feedback (if attempted/failed or solved)
        if budget.can_call_model:
            mem_prompt = [
                Message(
                    role="system",
                    content="Create a structured memory JSON with fields: 'failure_pattern', 'diagnosis', 'strategy', 'constraint'.",
                ),
                Message(
                    role="user",
                    content=f"Task: {task.specification}\nLast Test Feedback: {feedback_summary}\nSummarize key debugging heuristics learned into JSON.",
                ),
            ]
            mem_resp = self.model.complete(mem_prompt)
            budget.record_model_call(mem_resp)

            # Try parsing memory JSON
            try:
                start_idx = mem_resp.content.find("{")
                end_idx = mem_resp.content.rfind("}") + 1
                if start_idx != -1 and end_idx > start_idx:
                    data = json.loads(mem_resp.content[start_idx:end_idx])
                    entry = MemoryEntry(
                        task_id=task.id,
                        task_family=task.family.value,
                        failure_pattern=str(data.get("failure_pattern", "")),
                        diagnosis=str(data.get("diagnosis", "")),
                        strategy=str(data.get("strategy", "")),
                        constraint=str(data.get("constraint", "")),
                    )
                    self.memory_store.add(entry)
                    memories_written.append(entry.id)
            except Exception:
                pass

        elapsed = time.monotonic() - start_time
        return AgentResult(
            task_id=task.id,
            condition=self.condition_name,
            success=success,
            final_code=final_code,
            attempts=attempts,
            model_calls=budget.model_calls,
            input_tokens=budget.input_tokens,
            output_tokens=budget.output_tokens,
            total_tokens=budget.total_tokens,
            test_executions=budget.test_runs,
            elapsed_seconds=elapsed,
            memories_written=memories_written,
            memories_retrieved=memories_retrieved,
        )
