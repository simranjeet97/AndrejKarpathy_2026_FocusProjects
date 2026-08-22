"""Result evaluation aggregator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_learning.evaluation import metrics, statistics


class Evaluator:
    """Evaluates raw experiment JSON results into aggregated metrics."""

    def __init__(self, raw_dir: Path | str) -> None:
        self.raw_dir = Path(raw_dir)

    def evaluate(self) -> dict[str, Any]:
        """Aggregate results across runs and conditions."""
        if not self.raw_dir.exists():
            return {}

        results: dict[str, Any] = {}
        for run_dir in sorted(self.raw_dir.glob("run_*")):
            for cond_dir in sorted(run_dir.iterdir()):
                if not cond_dir.is_dir():
                    continue
                cond = cond_dir.name
                if cond not in results:
                    results[cond] = {}

                for res_file in cond_dir.glob("*_results.json"):
                    phase = res_file.name.replace("_results.json", "")
                    with open(res_file, "r") as f:
                        data = json.load(f)

                    if phase not in results[cond]:
                        results[cond][phase] = []
                    results[cond][phase].append(data)

        # Aggregate metrics
        aggregated: dict[str, Any] = {}
        for cond, phases in results.items():
            aggregated[cond] = {}
            for phase, runs_data in phases.items():
                pass_rates = [metrics.success_rate(run) for run in runs_data]
                avg_rate = statistics.mean(pass_rates)
                sd_rate = statistics.std_dev(pass_rates)
                aggregated[cond][phase] = {
                    "mean_success_rate": avg_rate,
                    "std_dev": sd_rate,
                    "runs_count": len(runs_data),
                }

        return aggregated
