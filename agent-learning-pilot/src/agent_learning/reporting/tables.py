"""CSV and JSON table generation for machine-readable evaluation output."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def export_summary_csv(aggregated_data: dict[str, Any], output_path: Path | str) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["condition", "phase", "mean_success_rate", "std_dev", "runs_count"])
        for cond, phases in aggregated_data.items():
            for phase, stats in phases.items():
                writer.writerow(
                    [
                        cond,
                        phase,
                        f"{stats.get('mean_success_rate', 0.0):.4f}",
                        f"{stats.get('std_dev', 0.0):.4f}",
                        stats.get("runs_count", 0),
                    ]
                )


def export_metrics_json(aggregated_data: dict[str, Any], output_path: Path | str) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(aggregated_data, f, indent=2)
