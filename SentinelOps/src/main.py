import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import structlog

from src.config import settings
from src.database import get_db_pool, close_db_pool
from src.agents.orchestrator import process_incident
from src.tools.runbook_tool import load_all_runbooks

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB pool & schema
    pool = await get_db_pool()
    logger.info("SentinelOps database connection initialized")
    yield
    await close_db_pool()
    logger.info("SentinelOps database connection closed")


app = FastAPI(title="SentinelOps API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncidentCreateRequest(BaseModel):
    service: str
    title: str
    description: Optional[str] = ""
    severity: Optional[str] = "P1"


@app.get("/health")
async def health():
    pool = await get_db_pool()
    db_ok = False
    incident_count = 0
    try:
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            db_ok = val == 1
            incident_count = await conn.fetchval("SELECT count(*) FROM incidents") or 0
    except Exception:
        db_ok = False

    ollama_ok = False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_base_url}/", timeout=2.0)
            ollama_ok = resp.status_code == 200
    except Exception:
        ollama_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": db_ok,
        "ollama": ollama_ok,
        "model": settings.ollama_model,
        "total_incidents": incident_count,
        "runbooks_loaded": len(load_all_runbooks()),
    }


@app.get("/api/incidents")
async def list_incidents():
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, incident_number, service, severity, title, description,
                       status, root_cause, remediation_patch, confidence_score,
                       risk_level, eval_passed, audit_hash, created_at, updated_at
                FROM incidents
                ORDER BY created_at DESC
                LIMIT 50
                """
            )
            return {"incidents": rows}
    except Exception as e:
        logger.error("Failed to list incidents", error=str(e))
        return {"incidents": []}


@app.post("/api/incidents")
async def create_incident(req: IncidentCreateRequest):
    if not req.service or not req.title:
        raise HTTPException(status_code=400, detail="Service and title are required")

    result = await process_incident(
        service=req.service,
        title=req.title,
        description=req.description or "",
        severity=req.severity or "P1",
    )
    return result


@app.get("/api/runbooks")
async def get_runbooks():
    return {"runbooks": load_all_runbooks()}


@app.get("/api/audit-trail")
async def get_audit_trail():
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, incident_id, event_type, payload, previous_hash, hash, created_at
                FROM audit_ledger
                ORDER BY created_at DESC
                LIMIT 50
                """
            )
            return {"audit_events": rows}
    except Exception as e:
        logger.error("Failed to query audit ledger", error=str(e))
        return {"audit_events": []}


# Mount Static UI Dashboard
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
