import os
import sys
import time
import argparse
import urllib.request
import urllib.error
import json
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class DebouncedTrigger:
    """
    Debounces event triggers to prevent double firing on save.
    """
    def __init__(self, callback, delay: float = 2.0):
        self.callback = callback
        self.delay = delay
        self.timer = None
        self.lock = threading.Lock()

    def trigger(self, filepath: str):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.delay, self.callback, args=[filepath])
            self.timer.start()

class EvalFileHandler(FileSystemEventHandler):
    """
    Handles file system events for dataset and prompt modification.
    """
    def __init__(self, trigger_func):
        self.trigger_func = trigger_func
        self.allowed_extensions = {".json", ".txt", ".py"}

    def on_modified(self, event):
        if event.is_directory:
            return
        self._check_and_trigger(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        self._check_and_trigger(event.src_path)

    def _check_and_trigger(self, src_path: str):
        _, ext = os.path.splitext(src_path)
        if ext in self.allowed_extensions:
            self.trigger_func(src_path)


class EvalWatcher:
    """
    Monitors folders (golden_datasets/, prompts/) and triggers eval runs on change.
    """

    def __init__(self, watch_dir: str = ".", api_url: str = "http://localhost:8000"):
        self.watch_dir = os.path.abspath(watch_dir)
        self.api_url = api_url.rstrip('/')
        self.debouncer = DebouncedTrigger(self.trigger_eval_run, delay=2.0)

    def trigger_eval_run(self, changed_file: str):
        """
        Send a POST request to trigger the evaluation run on the backend.
        """
        print(f"[EvalOps Watcher] Change detected: {changed_file} → triggering eval run")
        url = f"{self.api_url}/run"
        # Determine dataset path (default to example if the modified file isn't one)
        dataset_path = "golden_datasets/example_dataset.json"
        if "golden_datasets" in changed_file and changed_file.endswith(".json"):
            # Use relative path for simplicity
            dataset_path = os.path.relpath(changed_file, self.watch_dir)

        payload = {
            "dataset_path": dataset_path,
            "model": "llama3"
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                print(f"[EvalOps Watcher] Triggered successfully. Run ID: {data.get('run_id')}")
        except urllib.error.URLError as e:
            print(f"[EvalOps Watcher] Failed to trigger run: {e}", file=sys.stderr)

    def start(self):
        """
        Start monitoring target directories using watchdog.
        """
        observer = Observer()
        handler = EvalFileHandler(self.debouncer.trigger)

        # Check paths to monitor
        monitored_paths = []
        
        datasets_path = os.path.join(self.watch_dir, "golden_datasets")
        if os.path.exists(datasets_path):
            monitored_paths.append(datasets_path)
            
        prompts_path = os.path.join(self.watch_dir, "prompts")
        if os.path.exists(prompts_path):
            monitored_paths.append(prompts_path)

        if not monitored_paths:
            print(f"[EvalOps Watcher] Warning: No target folders found (golden_datasets/ or prompts/) under {self.watch_dir}. Monitoring root instead.")
            observer.schedule(handler, path=self.watch_dir, recursive=True)
        else:
            for path in monitored_paths:
                print(f"[EvalOps Watcher] Monitoring path: {path}")
                observer.schedule(handler, path=path, recursive=True)

        observer.start()
        print("[EvalOps Watcher] File watcher started. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EvalOps File Watcher Daemon")
    parser.add_argument("--watch-dir", type=str, default=".", help="Directory root to monitor")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000", help="EvalOps API base URL")
    
    args = parser.parse_args()
    watcher = EvalWatcher(watch_dir=args.watch_dir, api_url=args.api_url)
    watcher.start()
