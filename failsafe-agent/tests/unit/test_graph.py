import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent.graph import run_conversation
from src.agent.state import Intent


@pytest.mark.asyncio
@patch("src.agent.graph.classify_intent")
@patch("src.agent.graph.raw_run_agent")
@patch("src.agent.graph.raw_should_escalate")
async def test_run_conversation_happy_path(
    mock_should_escalate: AsyncMock,
    mock_run_agent: AsyncMock,
    mock_classify: AsyncMock,
) -> None:
    # 1. Mock Node return states
    async def side_effect_classify(state):
        state["intent"] = Intent.GENERAL_INQUIRY.value
        return state
    mock_classify.side_effect = side_effect_classify

    async def side_effect_agent(state, *args, **kwargs):
        state["messages"].append({
            "role": "assistant",
            "content": [{"type": "text", "text": "I can help with that."}]
        })
        return state
    mock_run_agent.side_effect = side_effect_agent

    mock_should_escalate.return_value = "continue"

    # 2. Run harness
    final_state = await run_conversation(
        customer_id="cust_1",
        message="Hello",
        db_pool=AsyncMock(),
        redis_client=AsyncMock()
    )

    # 3. Assertions
    assert final_state["intent"] == Intent.GENERAL_INQUIRY.value
    assert final_state["resolved"] is True
    assert final_state["escalated"] is False
    assert len(final_state["messages"]) == 2
    assert final_state["messages"][1]["content"][0]["text"] == "I can help with that."


@pytest.mark.asyncio
@patch("src.agent.graph.classify_intent")
@patch("src.agent.graph.raw_run_agent")
@patch("src.agent.graph.raw_should_escalate")
async def test_run_conversation_escalation_path(
    mock_should_escalate: MagicMock,
    mock_run_agent: AsyncMock,
    mock_classify: AsyncMock,
) -> None:
    async def side_effect_classify(state):
        state["intent"] = Intent.UNCLEAR.value
        state["confidence_score"] = 0.3
        return state
    mock_classify.side_effect = side_effect_classify

    async def side_effect_agent(state, *args, **kwargs):
        return state
    mock_run_agent.side_effect = side_effect_agent

    async def side_effect_escalate(state, *args, **kwargs):
        state["escalated"] = True
        return "escalate"
    mock_should_escalate.side_effect = side_effect_escalate

    final_state = await run_conversation(
        customer_id="cust_1",
        message="Confused question",
        db_pool=AsyncMock(),
        redis_client=AsyncMock()
    )

    assert final_state["resolved"] is False
    assert final_state["escalated"] is True
