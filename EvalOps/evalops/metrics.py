from datetime import datetime
from typing import List, Dict, Any, Optional
import math

from evalops.models import EvalRun
from evalops.storage import SQLiteStorage

class MetricsCollector:
    """
    Collects, aggregates, and reports metrics such as latency, token usage,
    estimated costs, score history, and overall pass rate.
    """

    COST_PER_1K_TOKENS = 0.0015  # Structured default rate (e.g., $0.0015 / 1K tokens)

    def __init__(self, storage: Optional[SQLiteStorage] = None):
        self.storage = storage or SQLiteStorage()
        # In-memory dictionary for active/live latency tracking
        self.latencies: Dict[str, List[float]] = {}

    def record_latency(self, run: EvalRun) -> None:
        """
        Record generation latency for a task in-memory.
        """
        if run.task_id not in self.latencies:
            self.latencies[run.task_id] = []
        self.latencies[run.task_id].append(run.latency_ms)

    def avg_latency(self, task_id: Optional[str] = None) -> float:
        """
        Compute average latency across all tasks or for a specific task.
        """
        if task_id:
            task_lats = self.latencies.get(task_id, [])
            if not task_lats:
                return 0.0
            return sum(task_lats) / len(task_lats)
        else:
            all_lats = []
            for lats in self.latencies.values():
                all_lats.extend(lats)
            if not all_lats:
                return 0.0
            return sum(all_lats) / len(all_lats)

    def p95_latency(self, task_id: Optional[str] = None) -> float:
        """
        Compute 95th percentile latency across all tasks or for a specific task.
        """
        if task_id:
            task_lats = self.latencies.get(task_id, [])
            if not task_lats:
                return 0.0
            sorted_l = sorted(task_lats)
        else:
            all_lats = []
            for lats in self.latencies.values():
                all_lats.extend(lats)
            if not all_lats:
                return 0.0
            sorted_l = sorted(all_lats)

        idx = min(len(sorted_l) - 1, int(len(sorted_l) * 0.95))
        return sorted_l[idx]

    def latency_trend(self, task_id: str, last_n: int = 10) -> List[float]:
        """
        Retrieve latency values for the last N runs of a specific task.
        """
        task_lats = self.latencies.get(task_id, [])
        return task_lats[-last_n:]

    def total_tokens(self, run_id: str) -> int:
        """
        Sum all tokens used across tasks within a specific batch run.
        """
        runs = self.storage.get_runs(run_id=run_id)
        return sum(run.tokens_used for run in runs)

    def avg_tokens(self, task_id: Optional[str] = None) -> float:
        """
        Compute average tokens consumed for a task or across all runs.
        """
        if task_id:
            runs = self.storage.get_runs(task_id=task_id)
        else:
            runs = self.storage.get_runs()
        
        if not runs:
            return 0.0
        return sum(run.tokens_used for run in runs) / len(runs)

    def estimate_cost(self, tokens: int) -> float:
        """
        Estimate API/inference cost for the specified token count.
        """
        return (tokens / 1000.0) * self.COST_PER_1K_TOKENS

    def run_cost_report(self, run_id: str) -> Dict[str, Any]:
        """
        Generate token usage and cost analysis for a run.
        """
        runs = self.storage.get_runs(run_id=run_id)
        tokens = sum(run.tokens_used for run in runs)
        cost = self.estimate_cost(tokens)
        model = runs[0].model if runs else "unknown"
        return {
            "total_tokens": tokens,
            "estimated_cost": cost,
            "model": model
        }

    def score_history(self, task_id: str, last_n: int = 20) -> List[float]:
        """
        Retrieve evaluation scores from database for the last N runs of a specific task.
        """
        runs = self.storage.get_runs(task_id=task_id)
        # Sort runs by execution time descending
        sorted_runs = sorted(runs, key=lambda r: r.run_at, reverse=True)
        # Take last N (most recent), but output chronologically
        recent_runs = sorted_runs[:last_n]
        recent_runs.reverse()
        return [run.score for run in recent_runs]

    def overall_pass_rate(self, run_id: str, threshold: float = 0.7) -> float:
        """
        Compute percentage of tasks in a run that met or exceeded score threshold.
        """
        runs = self.storage.get_runs(run_id=run_id)
        if not runs:
            return 0.0
        passing = sum(1 for run in runs if run.score >= threshold)
        return passing / len(runs)

    def full_report(self, run_id: str, runs: List[EvalRun]) -> Dict[str, Any]:
        """
        Compile full evaluation metrics report.
        """
        total_runs = len(runs)
        if total_runs == 0:
            return {
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat(),
                "total_runs": 0,
                "avg_score": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "total_tokens": 0,
                "pass_rate": 0.0,
                "regressions_count": 0
            }

        avg_score = sum(r.score for r in runs) / total_runs
        avg_latency = sum(r.latency_ms for r in runs) / total_runs
        
        sorted_l = sorted([r.latency_ms for r in runs])
        idx = min(len(sorted_l) - 1, int(len(sorted_l) * 0.95))
        p95_latency = sorted_l[idx]

        total_tokens = sum(r.tokens_used for r in runs)
        
        # Pull regressions from database
        regs = self.storage.get_regressions(run_id=run_id)
        regressions_count = len(regs)

        # Get settings for default pass rate threshold
        settings = self.storage.settings
        pass_rate = sum(1 for r in runs if r.score >= settings.judge_threshold) / total_runs

        return {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_runs": total_runs,
            "avg_score": avg_score,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "total_tokens": total_tokens,
            "pass_rate": pass_rate,
            "regressions_count": regressions_count
        }
