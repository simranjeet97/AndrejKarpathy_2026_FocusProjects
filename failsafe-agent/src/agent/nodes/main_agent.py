import time
from typing import Any, Dict, List, Optional
import structlog

from src.agent.state import AgentState
from src.config import settings
from src.resilience.fallback_llm import call_with_fallback, SafeResponse
from src.resilience.timeout import with_timeout, TimeoutBudget
from src.tools.registry import registry
from src.observability.tracing import tool_call_span

logger = structlog.get_logger()


async def run_agent(state: AgentState, redis_client: Optional[Any] = None) -> AgentState:
    """
    Main agent execution node. Runs a reasoning loop with the LLM, 
    executing tools and logging decisions until the turn is complete.
    """
    start_time = time.time()
    
    # 1. System Prompt definition
    system_prompt = (
        "You are a customer support agent for Failsafe Inc. You are precise, empathetic, and always follow policies. "
        "Before issuing any refund: (1) check eligibility, (2) look up the relevant policy, (3) confirm the amount. "
        "If you are uncertain at any step, escalate to a human rather than guessing. "
        "Your confidence score should reflect your certainty about the correct action."
    )

    # 2. Reasoning and Tool execution loop
    max_tool_calls = 6
    tool_calls_count = 0
    
    while tool_calls_count < max_tool_calls:
        # Check remaining budget
        budget = TimeoutBudget(total_seconds=state["timeout_budget_remaining"])
        remaining_seconds = budget.remaining()
        
        if remaining_seconds <= 2.0:
            logger.warn("Time budget exhausted, forcing escalation")
            state["escalated"] = True
            state["resolved"] = False
            break

        # Setup messages and tools for current turn
        try:
            # Execute LLM call with fallback (handles primary and secondary model transitions)
            llm_response = await with_timeout(
                call_with_fallback(
                    messages=state["messages"],
                    tools=registry.get_schemas(),
                    system_prompt=system_prompt,
                    redis_client=redis_client,
                ),
                timeout_seconds=remaining_seconds,
                operation_name="main_agent_call",
            )
        except Exception as e:
            logger.error("Main agent LLM call failed", error=str(e))
            state["error_count"] += 1
            break

        # Handle Canned/SafeResponse
        if isinstance(llm_response, SafeResponse):
            state["messages"].append({
                "role": "assistant",
                "content": llm_response.message,
            })
            state["escalated"] = llm_response.escalate
            state["resolved"] = not llm_response.escalate
            break

        # Extract LLM response content
        content_blocks = llm_response.get("content", [])
        assistant_message = {
            "role": "assistant",
            "content": content_blocks,
        }
        state["messages"].append(assistant_message)

        # Detect tool uses in response
        tool_uses = [block for block in content_blocks if block.get("type") == "tool_use"]
        
        if not tool_uses:
            # No tools called, agent finished its reasoning/response
            state["resolved"] = True
            break

        # Process each tool call
        tool_results_content = []
        for tool_use in tool_uses:
            tool_name = tool_use["name"]
            tool_input = tool_use["input"]
            tool_use_id = tool_use["id"]
            
            tool_call_start = time.time()
            logger.info("Executing tool from main agent loop", tool=tool_name, input=tool_input)
            
            # Inject context parameters if required by the tool signature
            injected_kwargs = tool_input.copy()
            
            # Resolve db_pool and redis_client references if required
            # (Escalation tool expects db_pool and redis_client)
            # The calling harness or caller's dependencies can be passed here:
            inspect_args = inspect_tool_params(tool_name)
            if "db_pool" in inspect_args:
                # Pass back context references if present
                injected_kwargs["db_pool"] = getattr(state, "db_pool", None)
            if "redis_client" in inspect_args:
                injected_kwargs["redis_client"] = redis_client

            try:
                # Call tool via registry, wrapped in an OTel child span
                async with tool_call_span(tool_name=tool_name, input_keys=list(injected_kwargs.keys())):
                    tool_output = await registry.call(tool_name, **injected_kwargs)
                
                # Check if this was a human escalation tool call
                if tool_name == "escalate_to_human":
                    state["escalated"] = True
                    state["resolved"] = False
                    
                tool_status = "success"
            except Exception as tool_error:
                tool_status = "failure"
                tool_output = f"Error executing tool: {str(tool_error)}"
                
                # Increment error_count on any tool failure
                state["error_count"] += 1
                logger.warn("Tool execution failed", tool=tool_name, error=str(tool_error))
            
            # Record log
            state["tool_call_log"].append({
                "tool": tool_name,
                "input": tool_input,
                "output": tool_output,
                "status": tool_status,
                "timestamp": time.time(),
            })

            # Append to tool result contents
            tool_results_content.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(tool_output),
            })
            
            tool_calls_count += 1

        # Feed tool results back to conversation history
        state["messages"].append({
            "role": "user",
            "content": tool_results_content,
        })

    # Update remaining budget
    elapsed = time.time() - start_time
    state["timeout_budget_remaining"] = max(0.0, state["timeout_budget_remaining"] - elapsed)
    
    return state


def inspect_tool_params(tool_name: str) -> List[str]:
    """Helper to retrieve list of arguments expected by the registered tool function."""
    if tool_name not in registry.tools:
        return []
    import inspect
    sig = inspect.signature(registry.tools[tool_name])
    return list(sig.parameters.keys())
