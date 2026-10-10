import json
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Request

logger = structlog.get_logger()
router = APIRouter(prefix="/admin")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    """Exception raised when the circuit breaker is OPEN or HALF_OPEN and refusing calls."""
    pass


class CircuitBreaker:
    def __init__(
        self,
        redis_client: aioredis.Redis,
        service_name: str,
        failure_threshold: int = 5,
        failure_window: float = 60.0,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.redis = redis_client
        self.service_name = service_name
        self.redis_key = f"cb:{service_name}"
        self.failure_threshold = failure_threshold
        self.failure_window = failure_window
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

    async def _get_state_data(self) -> Dict[str, Any]:
        """Fetch the circuit breaker state data from Redis."""
        data = await self.redis.get(self.redis_key)
        if data:
            try:
                return json.loads(data)
            except Exception as e:
                logger.error("Failed to parse circuit breaker state data", error=str(e))
        
        # Default state data if not exists
        return {
            "state": CircuitState.CLOSED.value,
            "last_state_change": time.time(),
            "failures": [],
            "half_open_calls_active": 0,
        }

    async def _save_state_data(self, data: Dict[str, Any]) -> None:
        """Save the circuit breaker state data to Redis."""
        await self.redis.set(self.redis_key, json.dumps(data))
        from src.observability.metrics import set_circuit_breaker_state
        set_circuit_breaker_state(self.service_name, data["state"])

    async def get_state(self) -> str:
        """Expose current state, handling recovery transition if needed."""
        data = await self._get_state_data()
        now = time.time()
        
        if data["state"] == CircuitState.OPEN.value:
            if now - data["last_state_change"] > self.recovery_timeout:
                data["state"] = CircuitState.HALF_OPEN.value
                data["last_state_change"] = now
                data["half_open_calls_active"] = 0
                await self._save_state_data(data)
                logger.info("Circuit breaker transitioned to HALF_OPEN", service=self.service_name)
                return CircuitState.HALF_OPEN.value
                
        return data["state"]

    async def call(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """Execute the coroutine wrapped with circuit breaker logic."""
        state = await self.get_state()
        data = await self._get_state_data()
        now = time.time()
        
        if state == CircuitState.OPEN.value:
            coro.close()  # prevent ResourceWarning for unawaited coroutine
            raise CircuitOpenError(f"Circuit breaker for {self.service_name} is OPEN")
            
        if state == CircuitState.HALF_OPEN.value:
            if data.get("half_open_calls_active", 0) >= self.half_open_max_calls:
                coro.close()  # prevent ResourceWarning for unawaited coroutine
                raise CircuitOpenError(f"Circuit breaker for {self.service_name} is HALF_OPEN (max probe calls reached)")
            
            data["half_open_calls_active"] = data.get("half_open_calls_active", 0) + 1
            await self._save_state_data(data)

        try:
            result = await coro
            
            # On success, if we were HALF_OPEN, we close the circuit
            if state == CircuitState.HALF_OPEN.value:
                data = await self._get_state_data()
                data["state"] = CircuitState.CLOSED.value
                data["failures"] = []
                data["half_open_calls_active"] = 0
                data["last_state_change"] = time.time()
                await self._save_state_data(data)
                logger.info("Circuit breaker transitioned to CLOSED (probe success)", service=self.service_name)
                
            return result
            
        except Exception as e:
            # On failure, handle state updates
            data = await self._get_state_data()
            if state == CircuitState.HALF_OPEN.value:
                # Direct re-open
                data["state"] = CircuitState.OPEN.value
                data["last_state_change"] = time.time()
                data["half_open_calls_active"] = 0
                await self._save_state_data(data)
                logger.warn("Circuit breaker transitioned to OPEN (probe failure)", service=self.service_name, error=str(e))
            else:
                # CLOSED state: record failure
                failures: List[float] = data.get("failures", [])
                failures.append(time.time())
                # Filter failures outside the window
                failures = [f for f in failures if time.time() - f <= self.failure_window]
                data["failures"] = failures
                
                if len(failures) >= self.failure_threshold:
                    data["state"] = CircuitState.OPEN.value
                    data["last_state_change"] = time.time()
                    logger.error("Circuit breaker transitioned to OPEN (threshold exceeded)", service=self.service_name, failures_count=len(failures))
                    
                await self._save_state_data(data)
                
            raise e


@router.get("/circuit-breakers")
async def get_circuit_breakers(request: Request) -> Dict[str, Any]:
    """Retrieve state of all circuit breakers stored in Redis."""
    redis_client = getattr(request.app.state, "redis_client", None)
    if not redis_client:
        return {"error": "Redis client not initialized"}
        
    keys = await redis_client.keys("cb:*")
    breakers = {}
    for key in keys:
        name = key.replace("cb:", "")
        val = await redis_client.get(key)
        if val:
            try:
                breakers[name] = json.loads(val)
            except Exception:
                pass
            
    # Include default known services if not tripped yet
    for svc in ["stripe_refund", "llm:claude-sonnet-4-6", "llm:claude-haiku-4-5-20251001"]:
        if svc not in breakers:
            breakers[svc] = {"state": "CLOSED", "failures": [], "last_state_change": time.time()}

    return {"circuit_breakers": breakers}


@router.post("/circuit-breakers/{service_name}/trip")
async def trip_circuit_breaker(service_name: str, request: Request) -> Dict[str, Any]:
    """Trip a circuit breaker manually for fault-injection simulation."""
    redis_client = getattr(request.app.state, "redis_client", None)
    if not redis_client:
        return {"error": "Redis client not initialized"}
    cb = CircuitBreaker(redis_client, service_name)
    data = await cb._get_state_data()
    data["state"] = CircuitState.OPEN.value
    data["last_state_change"] = time.time()
    await cb._save_state_data(data)
    return {"status": "success", "service": service_name, "state": "OPEN"}


@router.post("/circuit-breakers/{service_name}/reset")
async def reset_circuit_breaker(service_name: str, request: Request) -> Dict[str, Any]:
    """Reset a circuit breaker back to CLOSED state."""
    redis_client = getattr(request.app.state, "redis_client", None)
    if not redis_client:
        return {"error": "Redis client not initialized"}
    cb = CircuitBreaker(redis_client, service_name)
    data = await cb._get_state_data()
    data["state"] = CircuitState.CLOSED.value
    data["failures"] = []
    data["last_state_change"] = time.time()
    await cb._save_state_data(data)
    return {"status": "success", "service": service_name, "state": "CLOSED"}


@router.get("/audit-events")
async def get_all_audit_events(request: Request) -> Dict[str, Any]:
    """Retrieve recent cryptographic audit log events."""
    db_pool = getattr(request.app.state, "db_pool", None)
    if not db_pool:
        return {"events": []}
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, conversation_id, event_type, actor, payload, hash, created_at FROM audit_events ORDER BY created_at DESC LIMIT 50"
        )
    events = []
    for r in rows:
        payload_data = r["payload"]
        if isinstance(payload_data, str):
            try:
                payload_dict = json.loads(payload_data)
            except Exception:
                payload_dict = {"raw": payload_data}
        else:
            payload_dict = payload_data
        created = r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"])
        events.append({
            "id": r["id"],
            "conversation_id": r["conversation_id"],
            "event_type": r["event_type"],
            "actor": r["actor"],
            "payload": payload_dict,
            "hash": r["hash"],
            "created_at": created,
        })
    return {"events": events}
