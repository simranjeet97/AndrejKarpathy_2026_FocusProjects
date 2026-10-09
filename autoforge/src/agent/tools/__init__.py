"""
src/agent/tools package.

Importing this package populates the module-level `registry` singleton by
side-effect (each submodule calls @registry.register on import).

Usage in loop.py:
    from src.agent.tools import registry
    schemas = registry.schemas()
    result  = await registry.dispatch(name, input, container_id, task_id)
"""
from src.agent.tools.registry import registry  # noqa: F401 – re-export

# Import tool modules so their @registry.register decorators run
import src.agent.tools.file_tools       # noqa: F401
import src.agent.tools.test_runner_tool  # noqa: F401
import src.agent.tools.shell_tool        # noqa: F401
import src.agent.tools.issue_tool        # noqa: F401
import src.agent.tools.meta_tools        # noqa: F401
