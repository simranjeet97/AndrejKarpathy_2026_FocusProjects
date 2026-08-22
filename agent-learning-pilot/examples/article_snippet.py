"""20-40 line Medium article code snippet demonstrating the conceptual loop."""

from agent_learning.models.mock import MockModel
from agent_learning.agent.memory import MemoryAgent
from agent_learning.environment.task import Task, TaskFamily, TaskDifficulty
from agent_learning.environment.tests import TestExecutor

# 1. Initialize local or mock model and agent with external memory
model = MockModel()
agent = MemoryAgent(model=model)

# 2. Define feedback task
task = Task(
    id="dm_01",
    family=TaskFamily.DATA_MANIPULATION,
    difficulty=TaskDifficulty.EASY,
    title="Filter Predicate",
    specification="Filter items matching predicate",
    starter_code="def solve(items, p): pass",
    visible_tests="def test_basic(): assert solve([1,2,3], lambda x: x>1) == [2,3]",
    hidden_tests="def test_hidden(): assert solve([], lambda x: True) == []",
)

# 3. Training/Feedback Phase: agent receives test feedback & updates external memory
result = agent.solve(task)

# 4. Critical Step: Stop providing feedback & strip original task context!
# The memory agent retains ONLY external state (memory_store), no conversation history.
held_out_task = Task(
    id="dm_02",
    family=TaskFamily.DATA_MANIPULATION,
    difficulty=TaskDifficulty.EASY,
    title="Group By Key",
    specification="Group items by key function",
    starter_code="def solve(items, k): pass",
    visible_tests="def test_basic(): assert solve(['a'], len) == {1: ['a']}",
    hidden_tests="def test_hidden(): assert solve([], len) == {}",
)

# 5. Held-out Evaluation: Measure if improvement persists & transfers to unseen tasks
eval_result = agent.solve(held_out_task)
print(f"Transfer Test Result: {'SUCCESS' if eval_result.success else 'FAIL'}")
