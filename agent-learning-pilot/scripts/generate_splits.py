"""Script for generating task dataset splits."""

from pathlib import Path
import argparse
from agent_learning.environment.task import load_all_tasks
from agent_learning.experiment.splits import generate_splits

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", type=Path, default=Path("data/tasks"))
    parser.add_argument("--splits-dir", type=Path, default=Path("configs/splits"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    tasks = load_all_tasks(args.tasks_dir)
    splits = generate_splits(tasks, seed=args.seed)
    splits.save(args.splits_dir)
    print(f"Generated task splits saved to {args.splits_dir}")

if __name__ == "__main__":
    main()
