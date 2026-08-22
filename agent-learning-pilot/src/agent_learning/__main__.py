"""CLI entry point for the agent-learning experiment."""

import argparse
import sys
from pathlib import Path

from agent_learning.experiment.config import ExperimentConfig
from agent_learning.experiment.runner import ExperimentRunner


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="agent-learning",
        description="Can a Coding Agent Learn From Feedback? — Experiment Runner",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/pilot.yaml"),
        help="Path to experiment configuration YAML (default: configs/pilot.yaml)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock model instead of a real LLM (for testing/CI)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Run a single task by ID instead of the full experiment",
    )
    parser.add_argument(
        "--condition",
        type=str,
        choices=["baseline", "reflection", "memory", "workflow"],
        default=None,
        help="Run only one condition (default: all configured conditions)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override the random seed from config",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="Override the number of runs from config",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Override the results directory from config",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load configuration
    config = ExperimentConfig.from_yaml(args.config)

    # Apply CLI overrides
    if args.mock:
        config.model.provider = "mock"
    if args.seed is not None:
        config.experiment.seed = args.seed
    if args.runs is not None:
        config.experiment.runs = args.runs
    if args.results_dir is not None:
        config.output.results_dir = str(args.results_dir)
        config.output.raw_dir = str(args.results_dir / "raw")
        config.output.aggregated_dir = str(args.results_dir / "aggregated")
        config.output.figures_dir = str(args.results_dir / "figures")
        config.output.logs_dir = str(args.results_dir / "logs")
    if args.condition is not None:
        config.experiment.conditions = [args.condition]

    # Run experiment
    runner = ExperimentRunner(config)

    if args.task:
        runner.run_single_task(args.task)
    else:
        runner.run()

    print("\nExperiment complete. Results saved to:", config.output.results_dir)


if __name__ == "__main__":
    main()
