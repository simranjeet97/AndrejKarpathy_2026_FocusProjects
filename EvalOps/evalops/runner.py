import asyncio
import json
import time
import uuid
import os
import logging
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from google.adk import Agent
from google.adk.tools import FunctionTool

from evalops.config import get_settings
from evalops.models import EvalTask, EvalRun
from evalops.storage import SQLiteStorage
from evalops.ollama_client import OllamaClient, OllamaError

logger = logging.getLogger(__name__)

# Define Tool wrapper functions for Agent SDK integration
async def run_eval_task(task_json: str) -> str:
    """
    Runs a single evaluation task.
    
    Args:
        task_json (str): JSON string representation of the EvalTask.
        
    Returns:
        str: JSON string of the completed EvalRun.
    """
    try:
        task_dict = json.loads(task_json)
        task = EvalTask.from_dict(task_dict)
        settings = get_settings()
        runner = EvalRunner()
        # Initialize DB in case it isn't
        runner.storage.init_db()
        run_result = await runner.run_task(task, settings.default_model)
        return json.dumps(run_result.to_dict())
    except Exception as e:
        return json.dumps({"error": str(e)})

async def list_available_models() -> str:
    """
    Lists all locally available Ollama models.
    
    Returns:
        str: JSON list of model names.
    """
    try:
        client = OllamaClient()
        models = await client.list_models()
        return json.dumps(models)
    except Exception as e:
        return json.dumps({"error": str(e)})

# Instantiating the Google Agent SDK Agent
eval_agent = Agent(
    name="eval_runner",
    description="Runs LLM eval tasks",
    tools=[
        FunctionTool(run_eval_task),
        FunctionTool(list_available_models)
    ]
)

class EvalRunner:
    """
    Orchestrates the evaluation runs. Loads golden datasets, executes LLM calls,
    records results, and tracks latencies.
    """

    def __init__(self):
        self.settings = get_settings()
        self.storage = SQLiteStorage()
        self.ollama = OllamaClient()

    async def run_task(self, task: EvalTask, model: str, run_id: Optional[str] = None) -> EvalRun:
        """
        Execute a single evaluation task using local inference.

        Args:
            task (EvalTask): Task details.
            model (str): The name of the model to call.
            run_id (str, optional): The associated batch run ID.

        Returns:
            EvalRun: Evaluation result containing generated response and metrics.
        """
        start_time = time.monotonic()
        try:
            resp = await self.ollama.generate(model=model, prompt=task.input_prompt)
            output = resp["text"]
            tokens_used = resp["tokens_used"]
            # Record latency using time.monotonic (in ms)
            latency_ms = (time.monotonic() - start_time) * 1000.0
        except OllamaError as e:
            output = f"Ollama generation failed: {e}"
            tokens_used = 0
            latency_ms = (time.monotonic() - start_time) * 1000.0

        run = EvalRun(
            task_id=task.id,
            model=model,
            output=output,
            score=0.0,  # Score will be populated later by scorer/judge
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            run_id=run_id or str(uuid.uuid4())
        )
        self.storage.save_run(run)
        return run

    async def run_batch(
        self, tasks: List[EvalTask], model: str, run_id: Optional[str] = None
    ) -> List[EvalRun]:
        """
        Runs tasks concurrently with asyncio.gather (max 3 concurrent) and tracks progress with tqdm.

        Args:
            tasks (List[EvalTask]): List of tasks to evaluate.
            model (str): Model name.
            run_id (str, optional): Batch ID. Defaults to auto-generated UUID.

        Returns:
            List[EvalRun]: List of populated EvalRun results.
        """
        if not run_id:
            run_id = str(uuid.uuid4())

        sem = asyncio.Semaphore(3)
        pbar = tqdm(total=len(tasks), desc=f"Evaluating {model}")

        async def worker(task: EvalTask) -> EvalRun:
            async with sem:
                run = await self.run_task(task, model, run_id=run_id)
                pbar.update(1)
                return run

        results = await asyncio.gather(*(worker(task) for task in tasks))
        pbar.close()
        return list(results)

    async def run_from_dataset(self, dataset_path: str, model: str) -> List[EvalRun]:
        """
        Load tasks from JSON dataset file, parse them, and run batch evaluation.

        Args:
            dataset_path (str): Relative or absolute path to the golden dataset file.
            model (str): Model name.

        Returns:
            List[EvalRun]: List of evaluation runs.
        """
        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"Dataset path {dataset_path} does not exist")

        with open(dataset_path, "r") as f:
            data = json.load(f)

        tasks = [EvalTask.from_dict(t) for t in data]
        # Save tasks to database as well
        for task in tasks:
            self.storage.save_task(task)

        return await self.run_batch(tasks, model)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="EvalOps Runner CLI")
    parser.add_argument("--dataset", type=str, default="golden_datasets/example_dataset.json", help="Path to golden dataset json")
    parser.add_argument("--model", type=str, default=None, help="Inference model to evaluate")
    parser.add_argument("--output", type=str, default=None, help="Output JSON filepath for results")

    args = parser.parse_args()
    
    settings = get_settings()
    target_model = args.model or settings.default_model

    async def main():
        runner = EvalRunner()
        runner.storage.init_db()
        print(f"Starting evaluation batch using model: {target_model}")
        try:
            runs = await runner.run_from_dataset(args.dataset, target_model)
            print(f"Batch completed successfully. Evaluated {len(runs)} tasks.")
            if args.output:
                with open(args.output, "w") as f:
                    json.dump([r.to_dict() for r in runs], f, indent=2)
                print(f"Saved evaluation results to {args.output}")
        except Exception as e:
            print(f"Error during evaluation: {e}")

    asyncio.run(main())
