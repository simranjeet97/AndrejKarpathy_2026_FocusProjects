import os
import uuid
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from evalops.config import get_settings, Settings
from evalops.models import EvalTask, EvalRun, Regression, HumanFeedback
from evalops.storage import SQLiteStorage
from evalops.ollama_client import OllamaClient
from evalops.runner import EvalRunner
from evalops.judge import LLMJudge
from evalops.regression_engine import RegressionEngine
from evalops.comparator import PairwiseComparator
from evalops.metrics import MetricsCollector
from evalops.utils import timestamp_now

# Ensure templates and static directories exist to avoid mounting errors
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

# Write a minimal dashboard template if it doesn't exist so mounting doesn't throw errors
dashboard_html_path = "templates/dashboard.html"
if not os.path.exists(dashboard_html_path):
    with open(dashboard_html_path, "w") as f:
        f.write("<html><body><h1>EvalOps Dashboard Stub</h1></body></html>")

app = FastAPI(
    title="EvalOps API",
    description="FastAPI REST API for LLM Regression Testing",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# FastAPI Dependency Injection
def get_storage() -> SQLiteStorage:
    storage = SQLiteStorage()
    storage.init_db()
    return storage

def get_runner() -> EvalRunner:
    return EvalRunner()

def get_judge() -> LLMJudge:
    return LLMJudge()

def get_regression_engine(storage: SQLiteStorage = Depends(get_storage)) -> RegressionEngine:
    return RegressionEngine(storage=storage)

def get_comparator(judge: LLMJudge = Depends(get_judge)) -> PairwiseComparator:
    return PairwiseComparator(judge=judge)

def get_metrics(storage: SQLiteStorage = Depends(get_storage)) -> MetricsCollector:
    return MetricsCollector(storage=storage)

# Pydantic Schemas for Requests
class TaskCreate(BaseModel):
    name: str
    input_prompt: str
    expected_output: str
    tags: List[str] = Field(default_factory=list)

class RunTrigger(BaseModel):
    dataset_path: str
    model: str
    run_id: Optional[str] = None

class FeedbackCreate(BaseModel):
    run_id: str
    task_id: str
    rating: int = Field(..., ge=1, le=5)
    notes: str = ""

# Background evaluation task
async def run_evaluation_flow(
    dataset_path: str,
    model: str,
    run_id: str,
    storage: SQLiteStorage,
    runner: EvalRunner,
    judge: LLMJudge,
    engine: RegressionEngine
):
    try:
        # 1. Run inference for all dataset tasks
        runs = await runner.run_from_dataset(dataset_path, model)
        
        # 2. Update run IDs
        for run in runs:
            run.run_id = run_id

        # 3. Fetch tasks for referencing expected outputs
        tasks = storage.get_tasks()
        task_map = {t.id: t for t in tasks}

        # 4. Score completions using the LLM judge
        scored_runs = []
        for run in runs:
            task = task_map.get(run.task_id)
            if task:
                score_res = await judge.score(task, run)
                run.score = score_res["score"]
                # Save scored run
                storage.save_run(run)
            scored_runs.append(run)

        # 5. Perform regression check
        engine.detect_batch(scored_runs, list(task_map.values()))
    except Exception as e:
        print(f"Background evaluation error for run {run_id}: {e}")

# API Endpoints
@app.get("/health")
async def health(
    storage: SQLiteStorage = Depends(get_storage),
    judge: LLMJudge = Depends(get_judge)
) -> Dict[str, Any]:
    ollama_ok = await judge.client.health_check()
    db_ok = False
    try:
        storage.get_tasks()
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if (ollama_ok and db_ok) else "degraded",
        "ollama": ollama_ok,
        "db": db_ok
    }

@app.get("/tasks")
async def list_tasks(
    tags: Optional[str] = Query(None, description="Comma-separated list of tags to filter by"),
    storage: SQLiteStorage = Depends(get_storage)
) -> List[Dict[str, Any]]:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    tasks = storage.get_tasks(tags=tag_list)
    return [t.to_dict() for t in tasks]

@app.post("/tasks")
async def create_task(
    task: TaskCreate,
    storage: SQLiteStorage = Depends(get_storage)
) -> Dict[str, Any]:
    new_task = EvalTask(
        name=task.name,
        input_prompt=task.input_prompt,
        expected_output=task.expected_output,
        tags=task.tags
    )
    storage.save_task(new_task)
    return new_task.to_dict()

@app.post("/run")
async def trigger_run(
    payload: RunTrigger,
    background_tasks: BackgroundTasks,
    storage: SQLiteStorage = Depends(get_storage),
    runner: EvalRunner = Depends(get_runner),
    judge: LLMJudge = Depends(get_judge),
    engine: RegressionEngine = Depends(get_regression_engine)
) -> Dict[str, str]:
    run_id = payload.run_id or str(uuid.uuid4())
    
    background_tasks.add_task(
        run_evaluation_flow,
        payload.dataset_path,
        payload.model,
        run_id,
        storage,
        runner,
        judge,
        engine
    )
    return {"run_id": run_id, "status": "started"}

@app.get("/runs/{run_id}")
async def get_run_report(
    run_id: str,
    storage: SQLiteStorage = Depends(get_storage),
    engine: RegressionEngine = Depends(get_regression_engine),
    metrics: MetricsCollector = Depends(get_metrics)
) -> Dict[str, Any]:
    runs = storage.get_runs(run_id=run_id)
    if not runs:
        raise HTTPException(status_code=404, detail="Run not found")
        
    report = engine.generate_report(run_id)
    metrics_report = metrics.full_report(run_id, runs)
    return {**report, **metrics_report, "runs": [r.to_dict() for r in runs]}

@app.get("/runs/{run_id}/regressions")
async def get_run_regressions(
    run_id: str,
    storage: SQLiteStorage = Depends(get_storage),
    engine: RegressionEngine = Depends(get_regression_engine)
) -> List[Dict[str, Any]]:
    regressions = storage.get_regressions(run_id=run_id)
    tasks = storage.get_tasks()
    alerts = engine.format_alerts(regressions, tasks)
    return [
        {
            "task_name": a.task_name,
            "baseline_score": a.baseline_score,
            "current_score": a.current_score,
            "delta": a.delta,
            "model": a.model,
            "run_id": a.run_id
        }
        for a in alerts
    ]

@app.get("/runs/{run_id}/compare")
async def compare_runs(
    run_id: str,
    baseline_run_id: str = Query(..., description="Baseline run ID for pairwise comparison"),
    storage: SQLiteStorage = Depends(get_storage),
    comparator: PairwiseComparator = Depends(get_comparator)
) -> List[Dict[str, Any]]:
    candidate_runs = storage.get_runs(run_id=run_id)
    baseline_runs = storage.get_runs(run_id=baseline_run_id)

    if not candidate_runs or not baseline_runs:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    baseline_map = {r.task_id: r for r in baseline_runs}
    comparisons = []

    for rc in candidate_runs:
        rb = baseline_map.get(rc.task_id)
        if rb:
            comp = comparator.compare(rb, rc)
            comp["task_id"] = rc.task_id
            comparisons.append(comp)

    return comparisons

@app.post("/feedback")
async def submit_feedback(
    feedback: FeedbackCreate,
    storage: SQLiteStorage = Depends(get_storage)
) -> Dict[str, Any]:
    new_feedback = HumanFeedback(
        run_id=feedback.run_id,
        task_id=feedback.task_id,
        rating=feedback.rating,
        notes=feedback.notes
    )
    storage.save_feedback(new_feedback)
    return new_feedback.to_dict()

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(
    request: Request,
    storage: SQLiteStorage = Depends(get_storage)
) -> HTMLResponse:
    # Quick queries to render dashboard overview
    all_runs = storage.get_runs()
    # Unique runs list
    unique_run_ids = list(set(r.run_id for r in all_runs))
    
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"run_ids": unique_run_ids}
    )

@app.get("/runs")
async def list_unique_runs(storage: SQLiteStorage = Depends(get_storage)) -> List[str]:
    all_runs = storage.get_runs()
    return list(set(r.run_id for r in all_runs))

@app.get("/report/{run_id}")
async def download_report(
    run_id: str,
    storage: SQLiteStorage = Depends(get_storage),
    engine: RegressionEngine = Depends(get_regression_engine),
    metrics: MetricsCollector = Depends(get_metrics)
) -> JSONResponse:
    runs = storage.get_runs(run_id=run_id)
    if not runs:
        raise HTTPException(status_code=404, detail="Run not found")

    report = engine.generate_report(run_id)
    metrics_report = metrics.full_report(run_id, runs)
    
    headers = {"Content-Disposition": f"attachment; filename=report_{run_id}.json"}
    return JSONResponse(content={**report, **metrics_report}, headers=headers)
