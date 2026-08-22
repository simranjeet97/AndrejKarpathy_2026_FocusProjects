"""Experiment configuration loader and models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ExperimentConfigModel:
    name: str = "controlled_pilot"
    description: str = ""
    seed: int = 42
    runs: int = 3
    conditions: list[str] = field(
        default_factory=lambda: ["baseline", "reflection", "memory", "workflow"]
    )


@dataclass
class ModelConfig:
    provider: str = "local"
    endpoint: str = "http://localhost:11434/v1"
    model: str = "codellama:7b"
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass
class BudgetConfig:
    max_model_calls: int = 20
    max_tokens: int = 120000
    max_test_runs: int = 30
    task_timeout: int = 120


@dataclass
class DatasetConfig:
    tasks_dir: str = "data/tasks"
    splits_dir: str = "configs/splits"
    feedback_split: str = "configs/splits/feedback.json"
    validation_split: str = "configs/splits/validation.json"
    test_split: str = "configs/splits/test.json"
    cross_family_split: str = "configs/splits/cross_family.json"
    regression_split: str = "configs/splits/regression.json"


@dataclass
class RetentionConfig:
    intervening_tasks: int = 5


@dataclass
class OutputConfig:
    results_dir: str = "results"
    raw_dir: str = "results/raw"
    aggregated_dir: str = "results/aggregated"
    figures_dir: str = "results/figures"
    logs_dir: str = "results/logs"


@dataclass
class LoggingConfigModel:
    level: str = "INFO"
    format: str = "json"
    log_prompts: bool = False


@dataclass
class ExperimentConfig:
    """Master configuration class."""

    experiment: ExperimentConfigModel = field(default_factory=ExperimentConfigModel)
    model: ModelConfig = field(default_factory=ModelConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    retention_test: RetentionConfig = field(default_factory=RetentionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfigModel = field(default_factory=LoggingConfigModel)

    @classmethod
    def from_yaml(cls, path: Path | str) -> ExperimentConfig:
        """Load experiment configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        exp = ExperimentConfigModel(**data.get("experiment", {}))
        mdl = ModelConfig(**data.get("model", {}))
        bgt = BudgetConfig(**data.get("budget", {}))
        dts = DatasetConfig(**data.get("dataset", {}))
        rtn = RetentionConfig(**data.get("retention_test", {}))
        out = OutputConfig(**data.get("output", {}))
        log = LoggingConfigModel(**data.get("logging", {}))

        return cls(
            experiment=exp,
            model=mdl,
            budget=bgt,
            dataset=dts,
            retention_test=rtn,
            output=out,
            logging=log,
        )
