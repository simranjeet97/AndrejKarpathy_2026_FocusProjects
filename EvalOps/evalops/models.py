from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid

@dataclass
class EvalTask:
    """
    Represents a Golden Dataset task.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = field(default="")
    input_prompt: str = field(default="")
    expected_output: str = field(default="")
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert EvalTask instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalTask":
        """Create an EvalTask instance from a dictionary."""
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            name=data.get("name", ""),
            input_prompt=data.get("input_prompt", ""),
            expected_output=data.get("expected_output", ""),
            tags=data.get("tags") or [],
            created_at=data.get("created_at") or datetime.utcnow().isoformat()
        )


@dataclass
class EvalRun:
    """
    Represents the output and performance metrics of a single task evaluated on a model.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = field(default="")
    model: str = field(default="")
    output: str = field(default="")
    score: float = field(default=0.0)
    latency_ms: float = field(default=0.0)
    tokens_used: int = field(default=0)
    run_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # batch UUID

    def to_dict(self) -> Dict[str, Any]:
        """Convert EvalRun instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalRun":
        """Create an EvalRun instance from a dictionary."""
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            task_id=data.get("task_id", ""),
            model=data.get("model", ""),
            output=data.get("output", ""),
            score=float(data.get("score", 0.0)),
            latency_ms=float(data.get("latency_ms", 0.0)),
            tokens_used=int(data.get("tokens_used", 0)),
            run_at=data.get("run_at") or datetime.utcnow().isoformat(),
            run_id=data.get("run_id") or str(uuid.uuid4())
        )


@dataclass
class Regression:
    """
    Tracks performance regression between a baseline evaluation and a candidate run.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = field(default="")
    task_id: str = field(default="")
    baseline_score: float = field(default=0.0)
    current_score: float = field(default=0.0)
    delta: float = field(default=0.0)
    is_regression: bool = field(default=False)
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert Regression instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Regression":
        """Create a Regression instance from a dictionary."""
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            run_id=data.get("run_id", ""),
            task_id=data.get("task_id", ""),
            baseline_score=float(data.get("baseline_score", 0.0)),
            current_score=float(data.get("current_score", 0.0)),
            delta=float(data.get("delta", 0.0)),
            is_regression=bool(data.get("is_regression", False)),
            detected_at=data.get("detected_at") or datetime.utcnow().isoformat()
        )


@dataclass
class HumanFeedback:
    """
    Captures human feedback rating and notes for audit/manual review.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = field(default="")
    task_id: str = field(default="")
    rating: int = field(default=5)  # Rating between 1 and 5
    notes: str = field(default="")
    submitted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert HumanFeedback instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanFeedback":
        """Create a HumanFeedback instance from a dictionary."""
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            run_id=data.get("run_id", ""),
            task_id=data.get("task_id", ""),
            rating=int(data.get("rating", 5)),
            notes=data.get("notes", ""),
            submitted_at=data.get("submitted_at") or datetime.utcnow().isoformat()
        )
