import uuid
from evalops.models import EvalTask, EvalRun, Regression, HumanFeedback

def test_eval_task_serialization():
    # Test defaults
    task = EvalTask()
    assert isinstance(task.id, str)
    assert task.name == ""
    assert task.input_prompt == ""
    assert task.expected_output == ""
    assert task.tags == []
    assert isinstance(task.created_at, str)

    # Test serialization roundtrip
    original = EvalTask(
        id="test-id-123",
        name="Test Task",
        input_prompt="Translate: tree",
        expected_output="arbol",
        tags=["nature", "spanish"]
    )
    serialized = original.to_dict()
    deserialized = EvalTask.from_dict(serialized)
    
    assert original.id == deserialized.id
    assert original.name == deserialized.name
    assert original.input_prompt == deserialized.input_prompt
    assert original.expected_output == deserialized.expected_output
    assert original.tags == deserialized.tags
    assert original.created_at == deserialized.created_at


def test_eval_run_serialization():
    # Test defaults
    run = EvalRun()
    assert isinstance(run.id, str)
    assert run.task_id == ""
    assert run.model == ""
    assert run.output == ""
    assert run.score == 0.0
    assert run.latency_ms == 0.0
    assert run.tokens_used == 0
    assert isinstance(run.run_at, str)
    assert isinstance(run.run_id, str)

    # Test serialization roundtrip
    original = EvalRun(
        id="run-id-123",
        task_id="task-1",
        model="gpt-4",
        output="arbol",
        score=0.95,
        latency_ms=120.5,
        tokens_used=45,
        run_id="batch-55"
    )
    serialized = original.to_dict()
    deserialized = EvalRun.from_dict(serialized)

    assert original.id == deserialized.id
    assert original.task_id == deserialized.task_id
    assert original.model == deserialized.model
    assert original.output == deserialized.output
    assert original.score == deserialized.score
    assert original.latency_ms == deserialized.latency_ms
    assert original.tokens_used == deserialized.tokens_used
    assert original.run_at == deserialized.run_at
    assert original.run_id == deserialized.run_id


def test_regression_serialization():
    # Test defaults
    reg = Regression()
    assert isinstance(reg.id, str)
    assert reg.run_id == ""
    assert reg.task_id == ""
    assert reg.baseline_score == 0.0
    assert reg.current_score == 0.0
    assert reg.delta == 0.0
    assert reg.is_regression is False
    assert isinstance(reg.detected_at, str)

    # Test serialization roundtrip
    original = Regression(
        id="reg-id-123",
        run_id="batch-55",
        task_id="task-1",
        baseline_score=0.9,
        current_score=0.6,
        delta=-0.3,
        is_regression=True
    )
    serialized = original.to_dict()
    deserialized = Regression.from_dict(serialized)

    assert original.id == deserialized.id
    assert original.run_id == deserialized.run_id
    assert original.task_id == deserialized.task_id
    assert original.baseline_score == deserialized.baseline_score
    assert original.current_score == deserialized.current_score
    assert original.delta == deserialized.delta
    assert original.is_regression == deserialized.is_regression
    assert original.detected_at == deserialized.detected_at


def test_human_feedback_serialization():
    # Test defaults
    feedback = HumanFeedback()
    assert isinstance(feedback.id, str)
    assert feedback.run_id == ""
    assert feedback.task_id == ""
    assert feedback.rating == 5
    assert feedback.notes == ""
    assert isinstance(feedback.submitted_at, str)

    # Test serialization roundtrip
    original = HumanFeedback(
        id="feedback-id-123",
        run_id="batch-55",
        task_id="task-1",
        rating=4,
        notes="Minor typos but correct overall"
    )
    serialized = original.to_dict()
    deserialized = HumanFeedback.from_dict(serialized)

    assert original.id == deserialized.id
    assert original.run_id == deserialized.run_id
    assert original.task_id == deserialized.task_id
    assert original.rating == deserialized.rating
    assert original.notes == deserialized.notes
    assert original.submitted_at == deserialized.submitted_at
