from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

from evalops.config import get_settings
from evalops.models import EvalTask, EvalRun, Regression
from evalops.storage import SQLiteStorage

@dataclass
class RegressionAlert:
    """
    User-facing alert metadata for a performance regression.
    """
    task_name: str
    baseline_score: float
    current_score: float
    delta: float
    model: str
    run_id: str

class RegressionEngine:
    """
    Engine to identify regressions between current evaluation runs and historical baseline runs.
    """

    REGRESSION_THRESHOLD = 0.1

    def __init__(self, storage: Optional[SQLiteStorage] = None):
        self.storage = storage or SQLiteStorage()
        self.settings = get_settings()

    def detect(self, task_id: str, current_run: EvalRun) -> Optional[Regression]:
        """
        Detects if the current run has regressed compared to the baseline run for the task.

        Args:
            task_id (str): Unique task identifier.
            current_run (EvalRun): Current execution details.

        Returns:
            Regression, optional: The regression record if detected, else None.
        """
        baseline = self.storage.get_baseline(task_id)
        if not baseline:
            # No baseline exists yet — current run is already persisted by the runner.
            # It will become the baseline once its score meets the threshold.
            return None

        delta = current_run.score - baseline.score
        if delta <= -self.REGRESSION_THRESHOLD:
            regression = Regression(
                run_id=current_run.run_id,
                task_id=task_id,
                baseline_score=baseline.score,
                current_score=current_run.score,
                delta=delta,
                is_regression=True
            )
            self.storage.save_regression(regression)
            return regression

        return None

    def detect_batch(self, runs: List[EvalRun], tasks: List[EvalTask]) -> List[Regression]:
        """
        Detect regressions across a batch of runs.

        Returns:
            List[Regression]: List of detected regressions.
        """
        regressions = []
        for run in runs:
            reg = self.detect(run.task_id, run)
            if reg:
                regressions.append(reg)
        return regressions

    def generate_report(self, run_id: str) -> Dict[str, Any]:
        """
        Query DB and construct a regression evaluation report summary for a batch run.
        """
        runs = self.storage.get_runs(run_id=run_id)
        regressions = self.storage.get_regressions(run_id=run_id)

        total_tasks = len(runs)
        if total_tasks == 0:
            return {
                "run_id": run_id,
                "total_tasks": 0,
                "passed": 0,
                "failed": 0,
                "regressions": 0,
                "avg_score": 0.0,
                "avg_latency_ms": 0.0,
                "total_tokens": 0
            }

        passed = 0
        failed = 0
        total_score = 0.0
        total_latency = 0.0
        total_tokens = 0

        threshold = self.settings.judge_threshold
        for run in runs:
            total_score += run.score
            total_latency += run.latency_ms
            total_tokens += run.tokens_used
            if run.score >= threshold:
                passed += 1
            else:
                failed += 1

        return {
            "run_id": run_id,
            "total_tasks": total_tasks,
            "passed": passed,
            "failed": failed,
            "regressions": len(regressions),
            "avg_score": total_score / total_tasks,
            "avg_latency_ms": total_latency / total_tasks,
            "total_tokens": total_tokens
        }

    def format_alerts(self, regressions: List[Regression], tasks: List[EvalTask]) -> List[RegressionAlert]:
        """
        Format regression records into easy-to-read RegressionAlert summaries.
        """
        task_map = {t.id: t for t in tasks}
        alerts = []
        for r in regressions:
            task = task_map.get(r.task_id)
            task_name = task.name if task else "Unknown Task"
            
            # Retrieve model name from run if possible
            model = "unknown"
            runs = self.storage.get_runs(run_id=r.run_id, task_id=r.task_id)
            if runs:
                model = runs[0].model

            alerts.append(RegressionAlert(
                task_name=task_name,
                baseline_score=r.baseline_score,
                current_score=r.current_score,
                delta=r.delta,
                model=model,
                run_id=r.run_id
            ))
        return alerts
