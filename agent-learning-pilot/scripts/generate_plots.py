"""Script for generating Matplotlib plots for figures 1-4."""

from pathlib import Path
import argparse, json
from agent_learning.reporting.plots import generate_all_plots

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    
    metrics_json = args.results_dir / "aggregated" / "metrics.json"
    data = {}
    if metrics_json.exists():
        with open(metrics_json, "r") as f:
            data = json.load(f)
            
    fig_dir = args.results_dir / "figures"
    generate_all_plots(data, fig_dir)
    print(f"Figures successfully generated in {fig_dir}")

if __name__ == "__main__":
    main()
