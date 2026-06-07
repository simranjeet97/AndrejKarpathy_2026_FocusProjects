import time
import json
import re
import asyncio
import inspect
import hashlib
import logging
from datetime import datetime
from src.models import AgentResponse, ToolOutput, ToolCall, ToolInput, PermissionLevel
from src.llm.adk_bridge import OllamaADKModel

logger = logging.getLogger(__name__)

class AgentPermissionError(Exception):
    """Exception raised when a tool execution permission check fails."""
    pass

class QueryForgeAgent:
    """The main agent class orchestrating tool execution and LLM response generation."""

    def __init__(self, tool_registry, ollama_bridge, memory, settings):
        """Initialize QueryForgeAgent with registry, ollama bridge, memory, and settings."""
        self.tool_registry = tool_registry
        self.ollama_bridge = ollama_bridge
        self.memory = memory
        self.settings = settings

    async def run(self, user_query: str) -> AgentResponse:
        """Main entry point. Takes a natural language query, returns full response with tool calls."""
        start_agent_time = time.time()
        query_hash = hashlib.sha256(user_query.encode()).hexdigest()

        # Check memory cache
        if self.memory:
            try:
                if hasattr(self.memory, "get_cached_response"):
                    cached_resp = await self.memory.get_cached_response(user_query)
                else:
                    cached_resp = await self.memory.get(query_hash)
                if cached_resp:
                    if isinstance(cached_resp, dict):
                        return AgentResponse.model_validate(cached_resp)
                    elif isinstance(cached_resp, AgentResponse):
                        return cached_resp
            except Exception:
                pass

        available_tools = self.tool_registry.list_tool_names()
        steps = await self._plan_tool_sequence(user_query, available_tools)
        
        # Check and log warning for excessive tool use
        if len(steps) > 3:
            logger.warning(f"Excessive tool use planned: {len(steps)} steps. Recommended limit is 3.")


        executed_outputs = {}  # step_index -> ToolOutput
        tool_outputs = []
        tool_calls = []

        # Execute steps respecting depends_on indices (topological order)
        pending_steps = list(enumerate(steps))
        
        while pending_steps:
            progress = False
            for idx, step in list(pending_steps):
                depends_on = step.get("depends_on", [])
                
                # Check if all dependencies have been executed
                if all(dep in executed_outputs for dep in depends_on):
                    tool_name = step.get("tool")
                    reason = step.get("reason", f"Execution of step {idx}")

                    # Generate arguments given context and prior outputs
                    prior_outputs = list(executed_outputs.values())
                    args = await self._generate_tool_arguments(tool_name, user_query, prior_outputs)

                    tool_input = ToolInput(
                        tool_name=tool_name,
                        arguments=args,
                        caller_context=reason
                    )

                    try:
                        exec_args = {**args, "caller_context": f"{user_query} | {reason}"}
                        output = await self._execute_tool(tool_name, exec_args)
                    except AgentPermissionError as pe:
                        output = ToolOutput(
                            tool_name=tool_name,
                            success=False,
                            result=None,
                            error=str(pe),
                            latency_ms=0
                        )

                    tool_call = ToolCall(
                        input=tool_input,
                        output=output,
                        timestamp=datetime.utcnow()
                    )

                    tool_calls.append(tool_call)
                    tool_outputs.append(output)
                    executed_outputs[idx] = output
                    
                    pending_steps.remove((idx, step))
                    progress = True
                    break

            if not progress:
                # Fallback: resolve remaining steps in original order if a dependency is missing/cyclic
                for idx, step in pending_steps:
                    tool_name = step.get("tool")
                    reason = step.get("reason", f"Fallback execution of step {idx}")
                    prior_outputs = list(executed_outputs.values())
                    args = await self._generate_tool_arguments(tool_name, user_query, prior_outputs)

                    tool_input = ToolInput(
                        tool_name=tool_name,
                        arguments=args,
                        caller_context=reason
                    )

                    try:
                        exec_args = {**args, "caller_context": f"{user_query} | {reason}"}
                        output = await self._execute_tool(tool_name, exec_args)
                    except AgentPermissionError as pe:
                        output = ToolOutput(
                            tool_name=tool_name,
                            success=False,
                            result=None,
                            error=str(pe),
                            latency_ms=0
                        )

                    tool_call = ToolCall(
                        input=tool_input,
                        output=output,
                        timestamp=datetime.utcnow()
                    )
                    tool_calls.append(tool_call)
                    tool_outputs.append(output)
                    executed_outputs[idx] = output
                break

        # Extract chart paths
        chart_paths = []
        for out in tool_outputs:
            if out.success and out.result:
                if hasattr(out.result, "filepath"):
                    chart_paths.append(str(out.result.filepath))
                elif isinstance(out.result, dict) and "filepath" in out.result:
                    chart_paths.append(str(out.result["filepath"]))

        # Synthesize final response
        synthesis = await self._synthesize_response(user_query, tool_outputs)
        
        total_latency_ms = int((time.time() - start_agent_time) * 1000)

        agent_response = AgentResponse(
            query=user_query,
            answer=synthesis.get("answer", "Failed to generate synthesis response."),
            tool_calls=tool_calls,
            sources=synthesis.get("sources", []),
            chart_paths=chart_paths,
            total_latency_ms=total_latency_ms
        )

        # Store in cache
        if self.memory:
            try:
                if hasattr(self.memory, "cache_response"):
                    await self.memory.cache_response(user_query, agent_response, ttl=3600)
                else:
                    await self.memory.set(query_hash, agent_response.model_dump(), expire=3600)
            except Exception:
                pass

        return agent_response

    async def _plan_tool_sequence(self, query: str, available_tools: list[str]) -> list[dict]:
        """Ask Ollama to plan which tools to call and in what order."""
        prompt = self._build_planning_prompt(query, available_tools)
        try:
            if isinstance(self.ollama_bridge, OllamaADKModel):
                res = await self.ollama_bridge.client.generate(prompt, expect_json=True)
            else:
                res = await self.ollama_bridge.generate(prompt, expect_json=True)

            if isinstance(res, dict) and "steps" in res:
                return res["steps"]
        except Exception:
            pass

        # Fallback sequence creation if parsing fails
        query_lower = query.lower()
        matched_tools = []
        for tool_name in available_tools:
            tool_words = tool_name.replace("_", " ").lower().split()
            if any(word in query_lower for word in tool_words if len(word) > 3):
                matched_tools.append({
                    "tool": tool_name,
                    "reason": "Fallback keyword match",
                    "depends_on": []
                })

        if not matched_tools and available_tools:
            matched_tools.append({
                "tool": available_tools[0],
                "reason": "Fallback default tool",
                "depends_on": []
            })
            
        return matched_tools

    async def _generate_tool_arguments(self, tool_name: str, query: str, previous_outputs: list[ToolOutput]) -> dict:
        """Ask Ollama to generate arguments for a tool call given the query and prior outputs."""
        tool = self.tool_registry.get_tool_by_name(tool_name)
        if not tool:
            return {}

        sig = inspect.signature(tool.func)
        params_info = []
        for name, param in sig.parameters.items():
            if name in ["tool_context", "input_stream"]:
                continue
            ann = param.annotation.__name__ if hasattr(param.annotation, "__name__") else str(param.annotation)
            params_info.append(f"- {name}: type {ann}")

        params_str = "\n".join(params_info)

        outputs_summary = []
        for out in previous_outputs:
            if out.success:
                outputs_summary.append(f"Tool {out.tool_name} returned: {str(out.result)[:500]}")

        outputs_str = "\n".join(outputs_summary)

        prompt = (
            f"You are QueryForge argument generator. Your task is to generate arguments for the tool '{tool_name}'.\n\n"
            f"User Query:\n\"{query}\"\n\n"
            f"Prior Tool Executions:\n{outputs_str}\n\n"
            f"Expected Parameters for '{tool_name}':\n{params_str}\n\n"
            "Rules:\n"
            "1. Output ONLY a valid JSON dictionary where the keys are parameter names and values are the generated argument values.\n"
            "2. Do not output conversational text.\n"
            "3. If a parameter cannot be determined, default to a sensible type or None.\n"
        )

        try:
            if isinstance(self.ollama_bridge, OllamaADKModel):
                res = await self.ollama_bridge.client.generate(prompt, expect_json=True)
            else:
                res = await self.ollama_bridge.generate(prompt, expect_json=True)

            if isinstance(res, dict):
                return res
        except Exception:
            pass
        return {}

    async def _execute_tool(self, tool_name: str, arguments: dict) -> ToolOutput:
        """Execute a single tool call with retry logic and permission check."""
        context = arguments.get("caller_context", "General Query execution")
        if not self._check_permission(tool_name, context):
            raise AgentPermissionError(
                f"Permission denied: cannot execute tool '{tool_name}' in this context."
            )

        tool = self.tool_registry.get_tool_by_name(tool_name)
        if not tool:
            return ToolOutput(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f"Tool '{tool_name}' not found in registry.",
                latency_ms=0
            )

        max_retries = self.settings.MAX_TOOL_RETRIES
        retries = 0
        error_msg = None
        start_time = time.time()

        while retries <= max_retries:
            try:
                is_async = asyncio.iscoroutinefunction(tool.func) or (
                    hasattr(tool.func, "__call__") and asyncio.iscoroutinefunction(tool.func.__call__)
                )

                sig = inspect.signature(tool.func)
                filtered_args = {k: v for k, v in arguments.items() if k in sig.parameters}

                if is_async:
                    res = await tool.func(**filtered_args)
                else:
                    res = tool.func(**filtered_args)

                latency_ms = int((time.time() - start_time) * 1000)
                return ToolOutput(
                    tool_name=tool_name,
                    success=True,
                    result=res,
                    error=None,
                    latency_ms=latency_ms
                )
            except Exception as e:
                import pydantic
                non_retryable_errors = (
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    FileNotFoundError,
                    PermissionError,
                    pydantic.ValidationError,
                )
                if isinstance(e, non_retryable_errors):
                    retries = max_retries + 1
                    error_msg = str(e)
                    break

                retries += 1
                error_msg = str(e)
                if retries <= max_retries:
                    await asyncio.sleep(0.5 * retries)

        latency_ms = int((time.time() - start_time) * 1000)
        return ToolOutput(
            tool_name=tool_name,
            success=False,
            result=None,
            error=f"Execution failed after {max_retries} retries. Error: {error_msg}",
            latency_ms=latency_ms
        )

    async def _synthesize_response(self, query: str, tool_outputs: list[ToolOutput]) -> dict:
        """Ask Ollama to synthesize all tool outputs into a final answer."""
        prompt = self._build_synthesis_prompt(query, tool_outputs)
        try:
            if isinstance(self.ollama_bridge, OllamaADKModel):
                res = await self.ollama_bridge.client.generate(prompt, expect_json=True)
            else:
                res = await self.ollama_bridge.generate(prompt, expect_json=True)

            if isinstance(res, dict):
                return {
                    "answer": res.get("answer", "No synthesis answer generated."),
                    "key_findings": res.get("key_findings", []),
                    "sources": res.get("sources", [])
                }
        except Exception:
            pass

        # Fallback synthesis if JSON parsing fails
        summary_lines = []
        sources = []
        for out in tool_outputs:
            sources.append(out.tool_name)
            if out.success:
                summary_lines.append(f"- Tool {out.tool_name} completed with result: {out.result}")
            else:
                summary_lines.append(f"- Tool {out.tool_name} failed: {out.error}")

        return {
            "answer": "Failed to generate structured synthesis. Execution log:\n" + "\n".join(summary_lines),
            "key_findings": ["Execution completed with fallbacks."],
            "sources": list(set(sources))
        }

    def _check_permission(self, tool_name: str, context: str) -> bool:
        """Validate tool use is appropriate for the query context."""
        tool_perm = self.tool_registry.permissions.get(tool_name)
        if not tool_perm:
            level = PermissionLevel.RESTRICTED
        else:
            level = tool_perm.permission_level

        context_lower = context.lower()

        if level == PermissionLevel.READ_ONLY:
            return True

        if level == PermissionLevel.RESTRICTED:
            business_keywords = [
                "churn", "mrr", "revenue", "customer", "segment", "ltv", "billing",
                "metrics", "subscription", "payments", "active", "trend", "risk"
            ]
            return any(kw in context_lower for kw in business_keywords)

        if level == PermissionLevel.INTERNAL:
            internal_keywords = ["internal data", "internal report", "confidential", "proprietary", "workspace"]
            return any(kw in context_lower for kw in internal_keywords)

        return False

    def _build_planning_prompt(self, query: str, tools: list[str]) -> str:
        """Construct prompt for the LLM to plan tool usage."""
        tool_descriptions = []
        for tool_name in tools:
            tool = self.tool_registry.get_tool_by_name(tool_name)
            desc = tool.description if (tool and tool.description) else "No description available."
            tool_descriptions.append(f"- Name: {tool_name}\n  Description: {desc}")

        tools_str = "\n".join(tool_descriptions)

        prompt = (
            "You are QueryForge planning agent. Your task is to analyze the user's query and decide "
            "which tools to execute and in what order to solve the query.\n\n"
            f"User Query:\n\"{query}\"\n\n"
            "Available Tools:\n"
            f"{tools_str}\n\n"
            "Rules:\n"
            "1. Use the minimum number of tools necessary.\n"
            "2. Prefer specific-purpose tools over generic ones.\n"
            "3. Output ONLY a valid JSON object matching the schema below. No conversational text.\n\n"
            "Schema:\n"
            "{\n"
            "  \"steps\": [\n"
            "    {\n"
            "      \"tool\": \"tool_name\",\n"
            "      \"reason\": \"explanation of why this tool is chosen\",\n"
            "      \"depends_on\": [index of step this depends on, or empty list]\n"
            "    }\n"
            "  ]\n"
            "}\n"
        )
        return prompt

    def _build_synthesis_prompt(self, query: str, outputs: list[ToolOutput]) -> str:
        """Construct prompt for the LLM to synthesize tool outputs into an answer."""
        def to_serializable(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "dict"):
                return obj.dict()
            if isinstance(obj, list):
                return [to_serializable(x) for x in obj]
            if isinstance(obj, dict):
                return {k: to_serializable(v) for k, v in obj.items()}
            return obj

        outputs_str = []
        for out in outputs:
            status = "Success" if out.success else "Failed"
            val = out.result if out.success else out.error
            try:
                serializable_val = to_serializable(val)
                if isinstance(serializable_val, (dict, list)):
                    val_str = json.dumps(serializable_val, indent=2)
                else:
                    val_str = str(serializable_val)
            except Exception:
                val_str = str(val)

            outputs_str.append(
                f"Tool: {out.tool_name}\n"
                f"Status: {status}\n"
                f"Result:\n{val_str}"
            )

        all_outputs = "\n\n---\n\n".join(outputs_str)

        prompt = (
            "You are the QueryForge synthesis agent. Your task is to compile all tool execution results "
            "and generate a coherent final answer for the user query.\n\n"
            f"Original User Query:\n\"{query}\"\n\n"
            "Tool Execution Outputs:\n"
            f"{all_outputs}\n\n"
            "Requirements:\n"
            "1. Provide a comprehensive summary answering the query.\n"
            "2. List key findings.\n"
            "3. Cite data sources (e.g. database table names, source URLs, etc.).\n"
            "4. If any tool output represents a generated chart file (containing filepath and title), "
            "reference the chart file and its path in your answer.\n"
            "5. Output ONLY a valid JSON object matching the schema below. No conversational text outside JSON.\n\n"
            "Schema:\n"
            "{\n"
            "  \"answer\": \"Detailed markdown summary explaining the answer and referencing any generated charts.\",\n"
            "  \"key_findings\": [\n"
            "    \"Key finding 1\",\n"
            "    \"Key finding 2\"\n"
            "  ],\n"
            "  \"sources\": [\n"
            "    \"Source 1 (e.g. table name or URL)\"\n"
            "  ]\n"
            "}\n"
        )
        return prompt
