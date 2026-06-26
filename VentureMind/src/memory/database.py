import os
import json
import uuid
import logging
from datetime import datetime, timezone
import aiosqlite
from ..models.domain import DiligenceReport, AgentResult

logger = logging.getLogger("VentureMind.ReportDatabase")

class ReportDatabase:
    """SQLite database provider using aiosqlite for persisting finalized diligence reports and auditing specialist agent results."""

    def __init__(self, database_url: str):
        """Initialize database provider with connection path configurations."""
        self.database_url = database_url
        self.db_path = database_url
        self.conn = None

    async def connect(self) -> None:
        """Open the sqlite connection and initialize database tables."""
        db_path = self.db_path
        if db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        
        try:
            self.conn = await aiosqlite.connect(db_path)
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            await self.conn.execute("PRAGMA busy_timeout = 5000;")
            await self._init_tables()
        except Exception as e:
            logger.error(f"Failed to connect or initialize the report database: {e}", exc_info=True)
            raise

    async def disconnect(self) -> None:
        """Close the SQLite database connection gracefully."""
        if self.conn:
            await self.conn.close()

    async def save_report(self, report: DiligenceReport) -> str:
        """Insert a finalized DiligenceReport into the database and return its string UUID."""
        if not self.conn:
            await self.connect()
        report_id = str(uuid.uuid4())
        report_dict = report.model_dump() if hasattr(report, "model_dump") else report.dict()
        report_json = json.dumps(report_dict, default=str)
        
        # Handle datetime formats
        generated_at_str = report.generated_at.isoformat() if hasattr(report.generated_at, "isoformat") else str(report.generated_at)

        try:
            await self.conn.execute(
                """
                INSERT INTO diligence_reports (id, startup_name, generated_at, investment_score, report_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_id, report.startup_name, generated_at_str, report.investment_score, report_json)
            )
            await self.conn.commit()
            return report_id
        except Exception as e:
            logger.error(f"Failed to save diligence report for {report.startup_name}: {e}", exc_info=True)
            raise

    async def get_report(self, startup_name: str) -> DiligenceReport | None:
        """Query the database for the most recent diligence report generated for a startup."""
        if not self.conn:
            await self.connect()
        try:
            async with self.conn.execute(
                """
                SELECT report_json FROM diligence_reports
                WHERE startup_name = ?
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                (startup_name,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    report_data = json.loads(row["report_json"])
                    return DiligenceReport.model_validate(report_data) if hasattr(DiligenceReport, "model_validate") else DiligenceReport.parse_obj(report_data)
        except Exception as e:
            logger.error(f"Failed to retrieve report for {startup_name}: {e}", exc_info=True)
        return None

    async def list_reports(self, limit: int = 20) -> list[dict]:
        """List recently generated reports limited to the specified count."""
        if not self.conn:
            await self.connect()
        try:
            async with self.conn.execute(
                """
                SELECT id, startup_name, generated_at, investment_score
                FROM diligence_reports
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "id": r["id"],
                        "startup_name": r["startup_name"],
                        "generated_at": r["generated_at"],
                        "investment_score": r["investment_score"]
                    })
                return results
        except Exception as e:
            logger.error(f"Failed to list reports: {e}", exc_info=True)
            return []

    async def save_agent_result(self, startup_name: str, result: AgentResult) -> None:
        """Save a single agent result to the audit log tables."""
        if not self.conn:
            await self.connect()
        result_id = str(uuid.uuid4())
        result_dict = result.model_dump() if hasattr(result, "model_dump") else result.dict()
        data_json = json.dumps(result_dict, default=str)
        status_str = result.status.value if hasattr(result.status, "value") else str(result.status)

        try:
            await self.conn.execute(
                """
                INSERT INTO agent_results (id, startup_name, agent_name, status, duration_ms, created_at, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (result_id, startup_name, result.agent_name, status_str, result.duration_ms, datetime.now(timezone.utc).isoformat(), data_json)
            )
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to save agent result for {startup_name} ({result.agent_name}): {e}", exc_info=True)
            raise

    async def _init_tables(self) -> None:
        """Create essential tables and indexes if they do not already exist in the local SQLite database."""
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS diligence_reports (
                id TEXT PRIMARY KEY,
                startup_name TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                investment_score REAL NOT NULL,
                report_json TEXT NOT NULL
            )
            """
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_results (
                id TEXT PRIMARY KEY,
                startup_name TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                data_json TEXT
            )
            """
        )
        # Create performance indexes
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_startup ON diligence_reports (startup_name);")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_generated ON diligence_reports (generated_at DESC);")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_results_startup ON agent_results (startup_name);")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_results_created ON agent_results (created_at DESC);")
        await self.conn.commit()
