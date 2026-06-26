import pytest
from evalops.models import EvalTask, EvalRun
from evalops.judge import LLMJudge, HallucinationDetector
from evalops.config import get_settings

@pytest.mark.asyncio
async def test_llm_judge_score_mock_success():
    judge = LLMJudge()
    task = EvalTask(input_prompt="Count to 3", expected_output="1, 2, 3")
    run = EvalRun(output="1, 2, 3")

    # Call score (which in mock mode returns score 0.9, hallucination false)
    result = await judge.score(task, run)
    
    assert result["score"] == 0.9
    assert result["hallucination"] is False
    assert "correct" in result["reason"].lower()


@pytest.mark.asyncio
async def test_llm_judge_score_fallback_on_error(monkeypatch):
    judge = LLMJudge()
    task = EvalTask(input_prompt="Count to 3", expected_output="1, 2, 3")
    run = EvalRun(output="1, 2, 3")

    # Monkeypatch generate to raise an error
    async def mock_generate(*args, **kwargs):
        raise Exception("Mock Ollama Error")
    monkeypatch.setattr(judge.client, "generate", mock_generate)

    # Call score -> should fallback to composite score (1.0 for perfect match)
    result = await judge.score(task, run)
    
    assert result["score"] == 1.0
    assert "fallback" in result["reason"].lower()
    assert result["hallucination"] is False


def test_hallucination_detector_check():
    detector = HallucinationDetector()
    
    output = "Amelia Thorne invented the engine in 1985 in London"
    known_facts = [
        "Amelia Thorne is a fictional character",
        "No engine was invented"
    ]
    
    # Check returns fraction of words in output NOT in known facts
    score = detector.check(output, known_facts)
    # output tokens: amelia (fact), thorne (fact), invented (fact), the, engine (fact), in (fact), 1985, london
    # should be between 0 and 1
    assert 0.0 < score < 1.0

    # Perfect overlap
    assert detector.check("Amelia Thorne fictional", known_facts) == 0.0
