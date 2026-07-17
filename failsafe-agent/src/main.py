import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

import asyncpg
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.resilience.circuit_breaker import router as cb_router
from src.policy.rate_limiter import RateLimitMiddleware
from prometheus_client import make_asgi_app as make_metrics_app
from src.api.conversations import router as conv_router
from src.api.webhooks import router as webhook_router

# Configure structured logging via structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Database & Cache URLs from Environment (with defaults)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: Initialize connections
    app.state.start_time = time.time()
    
    logger.info("Starting up application and initializing connections")
    
    # Initialize Redis Client
    try:
        app.state.redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await app.state.redis_client.ping()
        logger.info("Successfully connected to Redis")
    except Exception as e:
        logger.error("Failed to connect to Redis on startup", error=str(e))
        app.state.redis_client = None

    # Initialize Postgres Connection Pool
    try:
        app.state.db_pool = await asyncpg.create_pool(dsn=DATABASE_URL)
        logger.info("Successfully connected to Postgres pool")
    except Exception as e:
        logger.error("Failed to connect to Postgres pool on startup", error=str(e))
        app.state.db_pool = None

    yield

    # Shutdown: Close connections
    logger.info("Shutting down application and closing connections")
    if getattr(app.state, "redis_client", None):
        await app.state.redis_client.close()
        logger.info("Closed Redis connection")
    if getattr(app.state, "db_pool", None):
        await app.state.db_pool.close()
        logger.info("Closed Postgres pool")


app = FastAPI(title="Failsafe Agent API", lifespan=lifespan)

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(cb_router)
app.include_router(conv_router)
app.include_router(webhook_router)

# Mount Prometheus /metrics endpoint
metrics_app = make_metrics_app()
app.mount("/metrics", metrics_app)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    logger.error(
        "Unhandled exception occurred",
        trace_id=trace_id,
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "trace_id": trace_id,
        },
    )


@app.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    redis_client = getattr(request.app.state, "redis_client", None)
    db_pool = getattr(request.app.state, "db_pool", None)
    
    redis_ok = False
    db_ok = False
    
    # Check Redis
    if redis_client:
        try:
            redis_ok = await redis_client.ping()
        except Exception as e:
            logger.warn("Redis ping failed during health check", error=str(e))
            
    # Check Postgres
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                val = await conn.fetchval("SELECT 1")
                db_ok = val == 1
        except Exception as e:
            logger.warn("Postgres query failed during health check", error=str(e))

    uptime_seconds = int(time.time() - request.app.state.start_time)
    
    overall_status = "healthy" if (redis_ok and db_ok) else "unhealthy"
    
    return {
        "status": overall_status,
        "db_ok": db_ok,
        "redis_ok": redis_ok,
        "uptime_seconds": uptime_seconds,
    }
