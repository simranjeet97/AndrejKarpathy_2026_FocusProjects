from src.agent.state import init_state, Intent


def test_init_state() -> None:
    state = init_state(customer_id="cust_abc", first_message="Hello, I need help.")
    
    # Assert fields are initialized correctly
    assert state["customer_id"] == "cust_abc"
    assert len(state["messages"]) == 1
    assert state["messages"][0]["role"] == "user"
    assert state["messages"][0]["content"] == "Hello, I need help."
    
    assert state["conversation_id"].startswith("conv_")
    assert state["tool_call_log"] == []
    assert state["confidence_score"] == 1.0
    assert state["intent"] is None
    assert state["escalated"] is False
    assert state["resolved"] is False
    assert state["error_count"] == 0
    assert state["active_policies"] == []
    assert state["refund_data"] is None
    assert state["timeout_budget_remaining"] == 28.0


def test_intent_enum_values() -> None:
    assert Intent.REFUND_REQUEST.value == "REFUND_REQUEST"
    assert Intent.POLICY_LOOKUP.value == "POLICY_LOOKUP"
