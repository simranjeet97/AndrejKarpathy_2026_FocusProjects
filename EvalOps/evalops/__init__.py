"""
EvalOps — CI/CD for your prompts and AI agents.
An LLM regression testing platform for local-first evaluation.
"""

__version__ = "0.1.0"

from evalops.runner import EvalRunner
from evalops.judge import LLMJudge
from evalops.regression_engine import RegressionEngine
from evalops.metrics import MetricsCollector
from evalops.storage import SQLiteStorage
from evalops.scorer import EvalScorer
from evalops.comparator import PairwiseComparator
from evalops.ollama_client import OllamaClient
from evalops.models import EvalTask, EvalRun, Regression, HumanFeedback

__all__ = [
    "EvalRunner",
    "LLMJudge",
    "RegressionEngine",
    "MetricsCollector",
    "SQLiteStorage",
    "EvalScorer",
    "PairwiseComparator",
    "OllamaClient",
    "EvalTask",
    "EvalRun",
    "Regression",
    "HumanFeedback",
    "print_last_report",
]


def print_last_report() -> None:
    """
    Convenience function to print the most recent evaluation run report.
    Queries the database for all runs, finds the latest batch run_id,
    and prints a formatted summary.
    """
    storage = SQLiteStorage()
    storage.init_db()

    all_runs = storage.get_runs()
    if not all_runs:
        print("No evaluation runs found in the database.")
        print("Run 'make eval' to execute your first evaluation.")
        return

    # Find the most recent run_id (by latest run_at timestamp)
    sorted_runs = sorted(all_runs, key=lambda r: r.run_at, reverse=True)
    latest_run_id = sorted_runs[0].run_id

    # Get all runs for this batch
    batch_runs = [r for r in all_runs if r.run_id == latest_run_id]

    # Generate regression report
    engine = RegressionEngine(storage=storage)
    report = engine.generate_report(latest_run_id)

    # Generate metrics report
    metrics = MetricsCollector(storage=storage)
    metrics_report = metrics.full_report(latest_run_id, batch_runs)

    # Get regressions
    regressions = storage.get_regressions(run_id=latest_run_id)

    # Print formatted report
    print("═" * 60)
    print("  EvalOps — Evaluation Report")
    print("═" * 60)
    print(f"  Run ID:         {latest_run_id}")
    print(f"  Total Tasks:    {report['total_tasks']}")
    print(f"  Passed:         {report['passed']}")
    print(f"  Failed:         {report['failed']}")
    print(f"  Regressions:    {report['regressions']}")
    print(f"  Avg Score:      {report['avg_score']:.3f}")
    print(f"  Avg Latency:    {report['avg_latency_ms']:.1f} ms")
    print(f"  Total Tokens:   {report['total_tokens']}")
    print(f"  Pass Rate:      {metrics_report.get('pass_rate', 0):.1%}")
    print(f"  P95 Latency:    {metrics_report.get('p95_latency_ms', 0):.1f} ms")
    print("─" * 60)

    # Per-task breakdown
    print("\n  Task Results:")
    print(f"  {'Task':<25} {'Model':<12} {'Score':>7} {'Latency':>10} {'Tokens':>7}")
    print("  " + "─" * 63)
    for run in batch_runs:
        status = "✓ PASS" if run.score >= 0.7 else "✗ FAIL"
        print(f"  {run.task_id:<25} {run.model:<12} {run.score:>7.3f} {run.latency_ms:>8.1f}ms {run.tokens_used:>7}")

    # Regressions
    if regressions:
        print("\n  ⚠ Regressions Detected:")
        print("  " + "─" * 63)
        for r in regressions:
            print(f"  Task: {r.task_id}  |  Baseline: {r.baseline_score:.3f} → Current: {r.current_score:.3f}  |  Δ {r.delta:+.3f}")
    else:
        print("\n  ✓ No regressions detected.")

    print("\n" + "═" * 60)
