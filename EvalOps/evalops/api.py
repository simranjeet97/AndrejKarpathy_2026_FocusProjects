from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any, Optional

app = FastAPI(
    title="EvalOps API",
    description="LLM Regression Testing Platform API Backend",
    version="0.1.0"
)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    """
    Serve the Jinja2 rendered HTML dashboard interface.

    Returns:
        HTMLResponse: Rendered web page.
    """
    pass

@app.get("/tasks")
async def list_tasks() -> List[Dict[str, Any]]:
    """
    Retrieve all tasks in the golden dataset.

    Returns:
        List[Dict[str, Any]]: List of task dict representations.
    """
    pass

@app.post("/tasks")
async def create_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a new task into the golden dataset database.

    Args:
        task_data (Dict[str, Any]): Task definition with input and expected keys.

    Returns:
        Dict[str, Any]: Saved task confirmation.
    """
    pass

@app.post("/runs")
async def trigger_evaluation_run(
    dataset_path: str, model_name: Optional[str] = None, background_tasks: BackgroundTasks = None
) -> Dict[str, Any]:
    """
    Trigger a new evaluation run over a specified golden dataset.

    Args:
        dataset_path (str): Relative or absolute path to dataset.
        model_name (str, optional): Target model name.
        background_tasks (BackgroundTasks): FastAPI async executor runner.

    Returns:
        Dict[str, Any]: Enqueued status and run ID.
    """
    pass

@app.get("/runs/{run_id}")
async def get_run_details(run_id: str) -> Dict[str, Any]:
    """
    Fetch comprehensive details, statistics, and results for a specific run.

    Args:
        run_id (str): Run UUID.

    Returns:
        Dict[str, Any]: Run metrics and list of results.
    """
    pass

@app.post("/compare")
async def compare_runs(run_a_id: str, run_b_id: str) -> Dict[str, Any]:
    """
    Initiate pairwise LLM-as-a-judge comparison between run A (baseline) and run B (candidate).

    Args:
        run_a_id (str): Baseline run.
        run_b_id (str): Candidate run.

    Returns:
        Dict[str, Any]: Pairwise comparison win rates and record details.
    """
    pass
