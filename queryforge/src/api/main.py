import os
import time
import shutil
import logging
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.models import AgentResponse, PDFSummary
from src.api.dependencies import (
    get_agent,
    get_memory,
    get_db_pool,
    get_ollama_client,
    get_pdf_tool,
    get_tool_registry,
    get_settings,
)
from src.scheduler.jobs import setup_scheduler

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    """Request model for agent queries."""
    query: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("Lifespan Startup: Initializing database connection pool...")
    db_pool = get_db_pool()
    await db_pool.connect()

    logger.info("Lifespan Startup: Connecting and checking memory layer health...")
    memory = get_memory()
    memory_ok = await memory.health_check()
    logger.info(f"Memory layer health: {memory_ok}")

    logger.info("Lifespan Startup: Starting background task scheduler...")
    settings = get_settings()
    scheduler = setup_scheduler(memory, settings)
    scheduler.start()
    app.state.scheduler = scheduler

    logger.info("Lifespan Startup: Eagerly registering tool registry...")
    registry = get_tool_registry()
    logger.info(f"Registered tools successfully: {registry.list_tool_names()}")

    yield

    # Shutdown sequence
    logger.info("Lifespan Shutdown: Stopping background task scheduler...")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown()

    logger.info("Lifespan Shutdown: Closing database connection pool...")
    await db_pool.disconnect()

    logger.info("Lifespan Shutdown: Closing Ollama client session...")
    ollama = get_ollama_client()
    await ollama.close()

    logger.info("Lifespan Shutdown: Closing memory layer client...")
    await memory.close()

# Initialize FastAPI App
app = FastAPI(
    title="QueryForge API",
    description="FastAPI endpoint interface for the QueryForge Multi-Tool Research Agent",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/query", response_model=AgentResponse)
async def run_query(request: QueryRequest, agent = Depends(get_agent), memory = Depends(get_memory)):
    """Primary QueryForge endpoint: Executes planning, execution, and synthesis of research query."""
    try:
        response = await agent.run(request.query)
        # Log tool calls to statistics list in Redis
        for call in response.tool_calls:
            await memory.log_tool_call(call)
        return response
    except Exception as e:
        logger.error(f"Error running query: {e}")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {e}")

@app.get("/health")
async def health(
    db_pool = Depends(get_db_pool),
    ollama = Depends(get_ollama_client),
    memory = Depends(get_memory)
):
    """Retrieve system component health statuses."""
    db_ok = await db_pool.health_check()
    ollama_ok = await ollama.health_check()
    dragonfly_ok = await memory.health_check()

    status = "ok" if (db_ok and ollama_ok and dragonfly_ok) else "degraded"
    return {
        "status": status,
        "db": db_ok,
        "ollama": ollama_ok,
        "dragonfly": dragonfly_ok
    }

@app.get("/tools")
async def list_tools(registry = Depends(get_tool_registry)):
    """List all currently registered tools and their functional descriptions."""
    tool_list = []
    for name in registry.list_tool_names():
        tool = registry.get_tool_by_name(name)
        tool_list.append({
            "name": name,
            "description": tool.description or "No description available."
        })
    return tool_list

@app.get("/tool-stats")
async def tool_stats(memory = Depends(get_memory)):
    """Get usage count statistics for tools over the past 7 days."""
    stats = await memory.get_tool_usage_stats(days=7)
    return stats

@app.get("/charts/{filename}")
async def serve_chart(filename: str, settings = Depends(get_settings)):
    """Serve a generated cohort or MRR chart file safely."""
    # Prevent path traversal vulnerabilities
    filepath = os.path.realpath(os.path.join(settings.CHARTS_OUTPUT_DIR, filename))
    real_dir = os.path.realpath(settings.CHARTS_OUTPUT_DIR)
    if os.path.commonpath([real_dir, filepath]) != real_dir:
        raise HTTPException(status_code=403, detail="Forbidden: path traversal detected.")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Chart file not found.")

    return FileResponse(filepath, media_type="image/png")

@app.post("/ingest-pdf", response_model=PDFSummary)
async def ingest_pdf(
    file: UploadFile = File(...),
    pdf_tool = Depends(get_pdf_tool),
    settings = Depends(get_settings)
):
    """Ingest, read, chunk, and summarize an uploaded PDF document."""
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDFs are allowed.")

    # Save to a temporary filepath in the pdfs folder
    pdf_dir = os.path.abspath(os.path.join(settings.CHARTS_OUTPUT_DIR, "../pdfs"))
    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)

    temp_filename = f"{int(time.time())}_{file.filename}"
    filepath = os.path.join(pdf_dir, temp_filename)

    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        summary = await pdf_tool.summarize_pdf(filepath)
        return summary
    except Exception as e:
        logger.error(f"Error during PDF ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"PDF ingestion failure: {e}")
    finally:
        # Cleanup file after processing
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

@app.get("/cache/clear")
async def clear_cache(memory = Depends(get_memory)):
    """Clear all cached agent responses from memory (Admin endpoint)."""
    try:
        keys = await memory.client.keys("response:*")
        if keys:
            await memory.client.delete(*keys)
        return {"status": "success", "cleared_count": len(keys)}
    except Exception as e:
        logger.error(f"Failed to clear Redis response cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")

# Mount static files to serve the HTML/CSS/JS frontend UI at root
app.mount("/", StaticFiles(directory="src/api/static", html=True), name="static")

