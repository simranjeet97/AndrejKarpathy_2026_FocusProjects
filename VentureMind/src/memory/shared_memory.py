import os
import json
from datetime import datetime, timedelta
import aiosqlite
from ..models.domain import AgentResult, StartupProfile, DiligenceReport, AgentStatus

class SharedMemory:
    """SQLite-based shared memory provider (using aiosqlite) to persist inter-agent state and workflow execution progress without requiring server dependencies."""

    def __init__(self, db_path: str):
        """Initialize the local SQLite key-value store database path."""
        if db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "")
        self.db_path = db_path
        self._initialized = False

    async def _ensure_db(self) -> None:
        """Ensure parent directories and table exist using aiosqlite asynchronously."""
        if self._initialized:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    expires_at TEXT
                )
            ''')
            await db.commit()
        self._initialized = True

    async def _cleanup_expired(self, db) -> None:
        """Helper to clear out expired entries from the KV database table."""
        await db.execute(
            "DELETE FROM kv_store WHERE expires_at IS NOT NULL AND expires_at < ?",
            (datetime.utcnow().isoformat(),)
        )

    async def _set(self, key: str, value: str, ttl_seconds: int = None) -> None:
        """Set a value in the key-value store with an optional TTL expiration in seconds."""
        expires_at = None
        if ttl_seconds:
            expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()
        try:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                await self._cleanup_expired(db)
                await db.execute(
                    "INSERT OR REPLACE INTO kv_store (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, value, expires_at)
                )
                await db.commit()
        except Exception:
            pass

    async def _get(self, key: str) -> str | None:
        """Retrieve a value by key, resolving expiration details."""
        try:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                await self._cleanup_expired(db)
                async with db.execute(
                    "SELECT value FROM kv_store WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                    (key, datetime.utcnow().isoformat())
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception:
            pass
        return None

    async def get(self, key: str) -> str | None:
        """Alias for _get to provide compatibility with generic KV interfaces."""
        return await self._get(key)

    async def set(self, key: str, value: str, ex: int = None) -> None:
        """Alias for _set to provide compatibility with generic KV interfaces supporting ex (TTL)."""
        await self._set(key, value, ttl_seconds=ex)


    async def store_agent_result(self, startup_name: str, agent_name: str, result: AgentResult) -> None:
        """Persist an agent's execution output for 24 hours."""
        key = f"result:{startup_name}:{agent_name}"
        data = result.model_dump_json() if hasattr(result, "model_dump_json") else result.json()
        await self._set(key, data, ttl_seconds=86400)

    async def get_agent_result(self, startup_name: str, agent_name: str) -> AgentResult | None:
        """Retrieve the persisted execution output of a specific agent."""
        key = f"result:{startup_name}:{agent_name}"
        data = await self._get(key)
        if data:
            try:
                return AgentResult.model_validate_json(data) if hasattr(AgentResult, "model_validate_json") else AgentResult.parse_raw(data)
            except Exception:
                pass
        return None

    async def store_startup_profile(self, startup_name: str, profile: StartupProfile) -> None:
        """Persist a parsed startup profile for 1 hour."""
        key = f"profile:{startup_name}"
        data = profile.model_dump_json() if hasattr(profile, "model_dump_json") else profile.json()
        await self._set(key, data, ttl_seconds=3600)

    async def get_startup_profile(self, startup_name: str) -> StartupProfile | None:
        """Retrieve the cached startup profile."""
        key = f"profile:{startup_name}"
        data = await self._get(key)
        if data:
            try:
                return StartupProfile.model_validate_json(data) if hasattr(StartupProfile, "model_validate_json") else StartupProfile.parse_raw(data)
            except Exception:
                pass
        return None

    async def store_report(self, startup_name: str, report: DiligenceReport) -> None:
        """Store the compiled final DiligenceReport for 24 hours."""
        key = f"report:{startup_name}"
        data = report.model_dump_json() if hasattr(report, "model_dump_json") else report.json()
        await self._set(key, data, ttl_seconds=86400)

    async def get_report(self, startup_name: str) -> DiligenceReport | None:
        """Retrieve the cached compiled due diligence report."""
        key = f"report:{startup_name}"
        data = await self._get(key)
        if data:
            try:
                return DiligenceReport.model_validate_json(data) if hasattr(DiligenceReport, "model_validate_json") else DiligenceReport.parse_raw(data)
            except Exception:
                pass
        return None

    async def mark_agent_running(self, startup_name: str, agent_name: str) -> None:
        """Mark an agent as currently active (auto-expires in 5 minutes)."""
        key = f"running:{startup_name}:{agent_name}"
        await self._set(key, "running", ttl_seconds=300)

    async def is_agent_running(self, startup_name: str, agent_name: str) -> bool:
        """Check if a specific agent is currently running."""
        key = f"running:{startup_name}:{agent_name}"
        val = await self._get(key)
        return val == "running"

    async def get_workflow_status(self, startup_name: str) -> dict[str, str]:
        """Aggregate workflow progress status for all specialist agents."""
        agents = ["market_research", "competitor", "financial", "legal", "summarization"]
        status_dict = {}
        for agent in agents:
            if await self.is_agent_running(startup_name, agent):
                status_dict[agent] = "running"
                continue
            result = await self.get_agent_result(startup_name, agent)
            if result:
                status_str = result.status.upper() if isinstance(result.status, str) else result.status.value.upper()
                if status_str == "SUCCESS":
                    status_dict[agent] = "completed"
                elif status_str in ("FAILED", "TIMEOUT"):
                    status_dict[agent] = "failed"
                else:
                    status_dict[agent] = "pending"
            else:
                status_dict[agent] = "pending"
        return status_dict

    async def health_check(self) -> bool:
        """Ping the shared memory backend to verify SQLite status."""
        try:
            await self._ensure_db()
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT 1") as cursor:
                    row = await cursor.fetchone()
                    return row is not None and row[0] == 1
        except Exception:
            return False
