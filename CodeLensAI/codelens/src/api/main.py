import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pandas as pd
import aiosqlite

from .webhook import router as webhook_router
from .dependencies import (
    get_settings,
    get_ollama_client,
    get_short_term_memory,
    get_excel_logger,
    get_long_term_memory,
    get_agent,
    get_github_client,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: log service URLs from settings
    settings = get_settings()
    logger.info("Starting up CodeLens AI FastAPI Application...")
    logger.info(f"Ollama Base URL: {settings.OLLAMA_BASE_URL}")
    logger.info(f"Chroma DB Path: {settings.CHROMA_PATH}")
    logger.info(f"SQLite Path: {settings.SQLITE_PATH}")
    logger.info(f"Dragonfly (Redis) URL: {settings.DRAGONFLY_URL}")
    logger.info(f"Excel Path: {settings.EXCEL_PATH}")
    yield
    # Shutdown: clean up connection pools
    logger.info("Shutting down CodeLens AI FastAPI Application...")
    try:
        short_term = get_short_term_memory()
        await short_term.close()
        logger.info("Redis/Dragonfly short-term memory connection closed.")
    except Exception as e:
        logger.error(f"Error closing short-term memory connection: {e}")


app = FastAPI(title="CodeLens AI", lifespan=lifespan)

# CORS Middleware (dev mode - allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include GitHub webhook router
app.include_router(webhook_router)

# Serve the dashboard UI
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the glassmorphism dashboard UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(content="<h1>CodeLens AI</h1><p>Dashboard not found.</p>", status_code=404)


class ManualReviewRequest(BaseModel):
    """Request body for triggering a manual PR review."""
    repo: str
    pr_number: int


@app.post("/review/manual")
async def trigger_manual_review(
    request: ManualReviewRequest,
    background_tasks: BackgroundTasks,
):
    """
    Manually trigger a code review for a specific PR.
    The review runs as a background task.
    """
    # Validate that GITHUB_TOKEN is configured
    settings = get_settings()
    if not settings.GITHUB_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="GITHUB_TOKEN is not configured. Please set it in your .env file."
        )

    repo_name = request.repo.strip()
    pr_num = request.pr_number

    # Support full GitHub URLs, e.g. https://github.com/owner/repo/pull/number
    if repo_name.startswith("http") or "github.com" in repo_name:
        import re
        match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", repo_name)
        if match:
            repo_name = f"{match.group(1)}/{match.group(2)}"
            pr_num = int(match.group(3))
        else:
            raise HTTPException(
                status_code=400,
                detail="Could not parse GitHub Pull Request URL. Ensure it follows format: https://github.com/owner/repo/pull/number"
            )

    # Validate repo format
    if "/" not in repo_name or len(repo_name.split("/")) != 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository format. Use 'owner/repo' format (e.g. 'simranjeet97/Awsome_AI_Agents') or a full Pull Request URL."
        )

    # Validate that the PR exists on GitHub before enqueuing
    try:
        github_client = get_github_client()
        await asyncio.to_thread(github_client.get_pr, repo_name, pr_num)
    except Exception as e:
        logger.error(f"Failed to fetch PR {pr_num} from {repo_name} for manual review: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"PR #{pr_num} not found or is inaccessible in repository '{repo_name}'. Error: {e}"
        )

    from .webhook import run_agent_review_task
    background_tasks.add_task(run_agent_review_task, repo_name, pr_num)
    return {"status": "enqueued", "repo": repo_name, "pr": pr_num}


@app.get("/health")
async def health(
    ollama_client=Depends(get_ollama_client),
    short_term=Depends(get_short_term_memory),
):
    """
    Check health status of external dependencies (Ollama and Dragonfly/Redis).
    """
    ollama_ok = await asyncio.to_thread(ollama_client.health_check)
    dragonfly_ok = await short_term.health_check()

    return {
        "status": "ok",
        "ollama": ollama_ok,
        "dragonfly": dragonfly_ok,
    }


@app.get("/config")
async def get_config(settings=Depends(get_settings)):
    """
    Retrieve current settings configuration for the UI (excluding secrets).
    """
    return {
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "ollama_model_code": settings.OLLAMA_MODEL_CODE,
        "ollama_model_reason": settings.OLLAMA_MODEL_REASON,
        "ollama_embed_model": settings.OLLAMA_EMBED_MODEL,
        "max_context_tokens": settings.MAX_CONTEXT_TOKENS,
        "sqlite_path": settings.SQLITE_PATH,
        "excel_path": settings.EXCEL_PATH,
        "dragonfly_url": settings.DRAGONFLY_URL,
        "github_token_configured": bool(settings.GITHUB_TOKEN),
    }


@app.get("/reviews")
async def get_reviews(excel_logger=Depends(get_excel_logger)):
    """
    Retrieve the 50 most recent reviews logged in the Excel workbook.
    """
    try:
        df = await asyncio.to_thread(excel_logger.get_history)
        if df.empty:
            return []

        # Convert NaN values to None to avoid JSON serialization issues
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

        # Convert any timestamp objects to ISO strings
        for record in records:
            for key, val in record.items():
                if hasattr(val, "isoformat"):
                    record[key] = val.isoformat()
                elif isinstance(val, (int, float)) and pd.isna(val):
                    record[key] = None

        # Return the 50 most recent records (reversed order, newest first)
        return list(reversed(records))[:50]
    except Exception as e:
        logger.error(f"Failed to retrieve reviews from Excel history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not read Excel review history.")


@app.get("/reviews/{pr_id}")
async def get_review(
    pr_id: int,
    short_term=Depends(get_short_term_memory),
    long_term=Depends(get_long_term_memory),
):
    """
    Retrieve a specific review by Pull Request ID from short-term cache or SQLite.
    """
    # 1. Check short-term cache
    try:
        cached_review = await short_term.get_review(str(pr_id))
        if cached_review:
            return cached_review
    except Exception as e:
        logger.warning(f"Failed to retrieve PR {pr_id} review from short-term cache: {e}")

    # 2. Check SQLite database
    try:
        async with aiosqlite.connect(long_term.sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT pr_id, repo, commit_sha, summary, approval, tokens_used, issues_json, suggestions_json, created_at
                FROM reviews
                WHERE pr_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (pr_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    data = dict(row)
                    import json
                    try:
                        data["issues"] = json.loads(data["issues_json"]) if data.get("issues_json") else []
                    except Exception:
                        data["issues"] = []
                    try:
                        data["suggestions"] = json.loads(data["suggestions_json"]) if data.get("suggestions_json") else []
                    except Exception:
                        data["suggestions"] = []
                    return data
    except Exception as e:
        logger.error(f"Database lookup failed for PR {pr_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database lookup error.")

    raise HTTPException(status_code=404, detail=f"Review for Pull Request {pr_id} not found.")
