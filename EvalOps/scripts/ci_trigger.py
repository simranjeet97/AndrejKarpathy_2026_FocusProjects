#!/usr/bin/env python3
import os
import sys
import time
import argparse
import json
import urllib.request
import urllib.error

def get_env_or_default(key: str, default: str) -> str:
    return os.environ.get(key, default)

def main():
    parser = argparse.ArgumentParser(description="EvalOps CI Trigger Tool")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit with code 1 if regressions are detected")
    args = parser.parse_args()

    # Read configuration from environment or defaults
    api_url = get_env_or_default("EVALOPS_API_URL", "http://localhost:8000").rstrip('/')
    model = get_env_or_default("EVALOPS_MODEL", "llama3")
    dataset_path = get_env_or_default("EVALOPS_DATASET", "golden_datasets/example_dataset.json")

    # Load dataset to determine total expected tasks
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset not found at {dataset_path}", file=sys.stderr)
        sys.exit(1)

    with open(dataset_path, "r") as f:
        dataset = json.load(f)
    expected_tasks_count = len(dataset)

    print(f"Triggering evaluation run on {api_url}...")
    print(f"Model: {model}")
    print(f"Dataset: {dataset_path} ({expected_tasks_count} tasks expected)")

    # 1. Trigger the run
    trigger_url = f"{api_url}/run"
    payload = {
        "dataset_path": dataset_path,
        "model": model
    }
    
    req = urllib.request.Request(
        trigger_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            trigger_data = json.loads(resp.read().decode())
            run_id = trigger_data.get("run_id")
            print(f"Triggered evaluation run. Run ID: {run_id}")
    except urllib.error.URLError as e:
        print(f"Failed to trigger evaluation run: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Poll the status
    print("Polling evaluation results...")
    timeout = 300
    interval = 5
    elapsed = 0
    report = None

    while elapsed < timeout:
        report_url = f"{api_url}/runs/{run_id}"
        req_report = urllib.request.Request(report_url, method="GET")
        
        try:
            with urllib.request.urlopen(req_report) as resp:
                report = json.loads(resp.read().decode())
                current_tasks = report.get("total_tasks", 0)
                # Check if all runs are complete and written
                if current_tasks >= expected_tasks_count:
                    print(f"Evaluation complete! ({current_tasks}/{expected_tasks_count} tasks processed)")
                    break
                else:
                    print(f"Processing: {current_tasks}/{expected_tasks_count} tasks completed...")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Background tasks hasn't written any runs yet
                print("In progress: waiting for initial runs...")
            else:
                print(f"HTTP Error polling results: {e}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"Connection error polling results: {e}", file=sys.stderr)

        time.sleep(interval)
        elapsed += interval

    if not report or report.get("total_tasks", 0) < expected_tasks_count:
        print("Timeout reached or evaluation failed to complete all tasks.", file=sys.stderr)
        sys.exit(1)

    # 3. Print report to stdout
    print("\n" + "="*50)
    print("               EVALOPS EVALUATION REPORT")
    print("="*50)
    print(f"Run ID:        {report.get('run_id')}")
    print(f"Total Tasks:   {report.get('total_tasks')}")
    print(f"Passed:        {report.get('passed')}")
    print(f"Failed:        {report.get('failed')}")
    print(f"Regressions:   {report.get('regressions')}")
    print(f"Avg Score:     {report.get('avg_score'):.2f}")
    print(f"Avg Latency:   {report.get('avg_latency_ms'):.0f} ms")
    print(f"Total Tokens:  {report.get('total_tokens')}")
    print("="*50)

    # 4. Check for regressions
    regressions_count = report.get("regressions", 0)
    if regressions_count > 0:
        print(f"⚠️ Warning: {regressions_count} regression(s) detected!", file=sys.stderr)
        
        # Fetch detailed regressions
        try:
            reg_url = f"{api_url}/runs/{run_id}/regressions"
            with urllib.request.urlopen(urllib.request.Request(reg_url)) as resp:
                regs = json.loads(resp.read().decode())
                print("\nRegression Details:")
                for r in regs:
                    print(f" - {r.get('task_name')}: Baseline {r.get('baseline_score')}, Current {r.get('current_score')} (Delta: {r.get('delta'):.2f})")
        except Exception as e:
            print(f"Failed to fetch regression details: {e}")

        if args.fail_on_regression or os.environ.get("FAIL_ON_REGRESSION", "false").lower() == "true":
            print("\nCI Status: FAILED (regressions detected)")
            sys.exit(1)

    print("\nCI Status: SUCCESS")
    sys.exit(0)

if __name__ == "__main__":
    main()
