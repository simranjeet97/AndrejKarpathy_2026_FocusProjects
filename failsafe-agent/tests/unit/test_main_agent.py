import pytest
from unittest.mock import AsyncMock, patch

from src.agent.nodes.main_agent import run_agent
from src.agent.state import init_state


@pytest.mark.asyncio
@patch("src.agent.nodes.main_agent.call_with_fallback")
async def test_run_agent_simple_response(mock_call: AsyncMock) -> None:
    # Set up LLM mock to return simple assistant text
    mock_call.return_value = {
        "content": [{"type": "text", "text": "Hello, how can I help you today?"}],
        "stop_reason": "end_turn"
    }

    state = init_state(customer_id="cust_1", first_message="hi")
    updated_state = await run_agent(state)

    assert updated_state["resolved"] is True
    assert updated_state["escalated"] is False
    assert len(updated_state["messages"]) == 2  # user message + assistant message
    assert updated_state["messages"][1]["content"][0]["text"] == "Hello, how can I help you today?"


@pytest.mark.asyncio
@patch("src.agent.nodes.main_agent.call_with_fallback")
@patch("src.tools.registry.registry.call")
async def test_run_agent_with_tool_loop(mock_tool_call: AsyncMock, mock_call: AsyncMock) -> None:
    # First turn: call check_refund_eligibility
    # Second turn: provide text answer and end turn
    mock_call.side_effect = [
        {
            "content": [
                {"type": "text", "text": "Let me check eligibility"},
                {
                    "type": "tool_use",
                    "id": "tool_01",
                    "name": "check_refund_eligibility",
                    "input": {"charge_id": "ch_123"}
                }
            ],
            "stop_reason": "tool_use"
        },
        {
            "content": [{"type": "text", "text": "You are indeed eligible!"}],
            "stop_reason": "end_turn"
        }
    ]

    mock_tool_call.return_value = {"eligible": True, "amount_refundable": 1000}

    state = init_state(customer_id="cust_1", first_message="Refund check")
    updated_state = await run_agent(state)

    assert updated_state["resolved"] is True
    # 2 LLM turns + 1 tool result injected = 5 messages in conversation history:
    # 1. User: Refund check
    # 2. Assistant: text + tool_use block
    # 3. User: tool_result block
    # 4. Assistant: text answer
    assert len(updated_state["messages"]) == 4
    assert len(updated_state["tool_call_log"]) == 1
    assert updated_state["tool_call_log"][0]["tool"] == "check_refund_eligibility"
    assert updated_state["tool_call_log"][0]["status"] == "success"
