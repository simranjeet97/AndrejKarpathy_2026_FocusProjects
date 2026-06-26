import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .dependencies import (
    get_orchestrator,
    get_report_database,
    get_renderer,
    get_ollama_client,
    get_shared_memory,
)
from ..models.domain import DiligenceReport

logger = logging.getLogger("VentureMind.API")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle during app startup and shutdown."""
    logger.info("Starting up FastAPI application...")
    db = get_report_database()
    try:
        await db.connect()
        logger.info("Successfully connected to report database.")
    except Exception as e:
        logger.error(f"Failed to connect to database during startup: {e}", exc_info=True)
    yield
    logger.info("Shutting down FastAPI application...")
    try:
        await db.disconnect()
        logger.info("Successfully disconnected from report database.")
    except Exception as e:
        logger.error(f"Failed to disconnect from database during shutdown: {e}", exc_info=True)

# Initialize FastAPI App with lifespans
app = FastAPI(
    title="VentureMind API",
    description="Production-grade API for VentureMind Multi-Agent Due Diligence system.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    startup_name: str

@app.post("/api/v1/analyze", response_model=DiligenceReport)
async def analyze_startup(
    payload: AnalyzeRequest,
    orchestrator = Depends(get_orchestrator),
    db = Depends(get_report_database),
    renderer = Depends(get_renderer),
):
    """Trigger a full multi-agent due diligence pipeline run for a startup.

    Fetches web signals, extracts details using Ollama specialized agents, compiles
    the final report, and saves it in the database and on disk.
    """
    logger.info(f"Received API request to analyze startup: {payload.startup_name}")
    try:
        report = await orchestrator.run(payload.startup_name)
        
        # Save report and specialist results to database
        logger.info("Persisting diligence report to database...")
        await db.save_report(report)
        for result in report.agent_results:
            await db.save_agent_result(payload.startup_name, result)
            
        # Render markdown, HTML, and DOCX reports on disk asynchronously (non-blocking)
        try:
            renderer.render_markdown(report)
            renderer.render_html(report)
            renderer.render_docx(report)
            logger.info("Reports rendered successfully on disk.")
        except Exception as render_err:
            logger.warning(f"Failed to render document outputs on disk: {render_err}")

        return report
    except RuntimeError as run_err:
        logger.error(f"Pre-flight health check failed: {run_err}")
        raise HTTPException(status_code=503, detail=str(run_err))
    except Exception as e:
        logger.error(f"Analysis pipeline execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Diligence analysis failed: {str(e)}")

@app.get("/api/v1/reports")
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_report_database),
):
    """Retrieve list of recently generated diligence reports."""
    try:
        reports = await db.list_reports(limit=limit)
        return {"reports": reports}
    except Exception as e:
        logger.error(f"Failed to list reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query reports list.")

@app.get("/api/v1/reports/{startup_name}", response_model=DiligenceReport)
async def get_report(
    startup_name: str,
    db = Depends(get_report_database),
):
    """Retrieve the most recent compiled diligence report for a specific startup name."""
    try:
        report = await db.get_report(startup_name)
        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Diligence report not found for startup '{startup_name}'."
            )
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve report for {startup_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query report database.")

@app.get("/api/v1/health")
async def health_status(
    ollama_client = Depends(get_ollama_client),
    db = Depends(get_report_database),
    memory = Depends(get_shared_memory),
):
    """System health check endpoint evaluating database, cache, and Ollama connections."""
    ollama_ok = await ollama_client.health_check()
    memory_ok = await memory.health_check()
    
    # Check Report database
    db_ok = False
    try:
        if not db.conn:
            await db.connect()
        async with db.conn.execute("SELECT 1") as cursor:
            row = await cursor.fetchone()
            db_ok = row is not None and row[0] == 1
    except Exception:
        pass

    all_ok = ollama_ok and memory_ok and db_ok
    return {
        "status": "healthy" if all_ok else "degraded",
        "components": {
            "ollama": "online" if ollama_ok else "offline",
            "database": "online" if db_ok else "offline",
            "shared_memory": "online" if memory_ok else "offline",
        }
    }
