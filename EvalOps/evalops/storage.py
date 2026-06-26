import json
import sqlite3
from typing import List, Optional
from evalops.config import get_settings
from evalops.models import EvalTask, EvalRun, Regression, HumanFeedback

class SQLiteStorage:
    """
    Handles SQLite CRUD operations for evaluation tasks, runs, regressions,
    and feedback using raw sqlite3 queries.
    """

    def __init__(self):
        self.settings = get_settings()
        self.db_path = self.settings.db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Helper to get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create database tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    input_prompt TEXT NOT NULL,
                    expected_output TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            # 2. eval_runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS eval_runs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    output TEXT NOT NULL,
                    score REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    tokens_used INTEGER NOT NULL,
                    run_at TEXT NOT NULL,
                    run_id TEXT NOT NULL
                )
            """)
            # 3. regressions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS regressions (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    baseline_score REAL NOT NULL,
                    current_score REAL NOT NULL,
                    delta REAL NOT NULL,
                    is_regression INTEGER NOT NULL,
                    detected_at TEXT NOT NULL
                )
            """)
            # 4. human_feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS human_feedback (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    notes TEXT NOT NULL,
                    submitted_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_task(self, task: EvalTask) -> str:
        """
        Create or update a Golden Dataset task.
        """
        tags_json = json.dumps(task.tags)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (id, name, input_prompt, expected_output, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    input_prompt=excluded.input_prompt,
                    expected_output=excluded.expected_output,
                    tags=excluded.tags
            """, (task.id, task.name, task.input_prompt, task.expected_output, tags_json, task.created_at))
            conn.commit()
        return task.id

    def get_tasks(self, tags: Optional[List[str]] = None) -> List[EvalTask]:
        """
        Retrieve tasks, optionally filtered by tags.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if tags:
                cursor.execute("SELECT * FROM tasks")
                rows = cursor.fetchall()
                tasks = []
                for row in rows:
                    row_tags = json.loads(row["tags"])
                    # Check if any tag matches
                    if any(t in row_tags for t in tags):
                        tasks.append(EvalTask(
                            id=row["id"],
                            name=row["name"],
                            input_prompt=row["input_prompt"],
                            expected_output=row["expected_output"],
                            tags=row_tags,
                            created_at=row["created_at"]
                        ))
                return tasks
            else:
                cursor.execute("SELECT * FROM tasks")
                rows = cursor.fetchall()
                return [
                    EvalTask(
                        id=row["id"],
                        name=row["name"],
                        input_prompt=row["input_prompt"],
                        expected_output=row["expected_output"],
                        tags=json.loads(row["tags"]),
                        created_at=row["created_at"]
                    ) for row in rows
                ]

    def save_run(self, run: EvalRun) -> str:
        """
        Save or update an evaluation run (upsert).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO eval_runs (id, task_id, model, output, score, latency_ms, tokens_used, run_at, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    output=excluded.output,
                    score=excluded.score,
                    latency_ms=excluded.latency_ms,
                    tokens_used=excluded.tokens_used,
                    run_id=excluded.run_id
            """, (run.id, run.task_id, run.model, run.output, run.score, run.latency_ms, run.tokens_used, run.run_at, run.run_id))
            conn.commit()
        return run.id

    def get_runs(self, run_id: Optional[str] = None, task_id: Optional[str] = None) -> List[EvalRun]:
        """
        Retrieve evaluation runs, optionally filtered by run_id or task_id.
        """
        query = "SELECT * FROM eval_runs WHERE 1=1"
        params = []
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                EvalRun(
                    id=row["id"],
                    task_id=row["task_id"],
                    model=row["model"],
                    output=row["output"],
                    score=row["score"],
                    latency_ms=row["latency_ms"],
                    tokens_used=row["tokens_used"],
                    run_at=row["run_at"],
                    run_id=row["run_id"]
                ) for row in rows
            ]

    def save_regression(self, r: Regression) -> str:
        """
        Save a regression entry.
        """
        is_regression_int = 1 if r.is_regression else 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO regressions (id, run_id, task_id, baseline_score, current_score, delta, is_regression, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (r.id, r.run_id, r.task_id, r.baseline_score, r.current_score, r.delta, is_regression_int, r.detected_at))
            conn.commit()
        return r.id

    def get_regressions(self, run_id: Optional[str] = None) -> List[Regression]:
        """
        Retrieve regressions, optionally filtered by run_id.
        """
        query = "SELECT * FROM regressions WHERE 1=1"
        params = []
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                Regression(
                    id=row["id"],
                    run_id=row["run_id"],
                    task_id=row["task_id"],
                    baseline_score=row["baseline_score"],
                    current_score=row["current_score"],
                    delta=row["delta"],
                    is_regression=(row["is_regression"] == 1),
                    detected_at=row["detected_at"]
                ) for row in rows
            ]

    def save_feedback(self, f: HumanFeedback) -> str:
        """
        Save human feedback.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO human_feedback (id, run_id, task_id, rating, notes, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (f.id, f.run_id, f.task_id, f.rating, f.notes, f.submitted_at))
            conn.commit()
        return f.id

    def get_baseline(self, task_id: str) -> Optional[EvalRun]:
        """
        Retrieve the most recent passing run for a given task.
        A run is considered passing if its score is >= judge_threshold.
        """
        threshold = self.settings.judge_threshold
        query = """
            SELECT * FROM eval_runs
            WHERE task_id = ? AND score >= ?
            ORDER BY run_at DESC LIMIT 1
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (task_id, threshold))
            row = cursor.fetchone()
            if row:
                return EvalRun(
                    id=row["id"],
                    task_id=row["task_id"],
                    model=row["model"],
                    output=row["output"],
                    score=row["score"],
                    latency_ms=row["latency_ms"],
                    tokens_used=row["tokens_used"],
                    run_at=row["run_at"],
                    run_id=row["run_id"]
                )
            return None
