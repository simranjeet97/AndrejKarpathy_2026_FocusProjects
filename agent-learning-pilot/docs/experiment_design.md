# Experiment Design

## 1. Central Research Question
> **When a coding agent improves after receiving feedback, does that improvement persist and transfer after the original feedback is removed?**

## 2. Experimental Conditions & Architecture
1. **Baseline**: Standard coding agent receiving tasks with no cross-task state.
2. **Reflection**: Explicit intra-task reflection step on failure. Retains no memory across tasks.
3. **Memory**: External persistent memory store saving failure patterns, diagnoses, strategies, and constraints.
4. **Workflow Modification**: Proposes constrained structural modifications to its problem-solving pipeline sequence (e.g. `inspect_tests -> plan -> code -> test`). Workflow persists across tasks.

## 3. Anti-Confounding Controls & Compute Matching
* **Compute Matching**: All conditions strictly enforce per-task maximum LLM call limits, token limits, and test execution budgets.
* **Context Isolation**: After training/feedback phase, original conversation history is completely purged. Only external state (memory store or workflow schema) persists.
* **Deterministic Environment**: Subprocess test execution in isolated temporary directories with strict timeouts.
