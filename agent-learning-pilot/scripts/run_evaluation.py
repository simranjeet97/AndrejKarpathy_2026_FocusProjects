"""Script for evaluating raw experiment output."""

from pathlib import Path
import argparse
from agent_learning.evaluation.evaluator import Evaluator
from agent_learning.reporting.tables import export_summary_csv, export_metrics_json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    
    raw_dir = args.results_dir / "raw"
    evaluator = Evaluator(raw_dir=raw_dir)
    agg = evaluator.evaluate()
    
    agg_dir = args.results_dir / "aggregated"
    export_summary_csv(agg, agg_dir / "results.csv")
    export_metrics_json(agg, agg_dir / "metrics.json")
    print(f"Evaluation metrics exported to {agg_dir}")

if __name__ == "__main__":
    main()
