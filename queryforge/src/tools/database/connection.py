import aiosqlite
from typing import Optional
import re
from src.models import QueryResult

class AsyncDBPool:
    """Infrastructure-only asynchronous database connection wrapper using aiosqlite."""

    def __init__(self, database_url: str):
        # Clean url prefix to extract the SQLite database path
        db_path = database_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        self.database_url = database_url
        self.db_path = db_path
        self._conn = None
        self.memory = None

    async def connect(self) -> None:
        """Initialize the aiosqlite connection."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row

    async def disconnect(self) -> None:
        """Close the aiosqlite connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def execute_query(self, query: str, params: tuple = ()) -> QueryResult:
        """INTERNAL ONLY. Execute a query and return a structured QueryResult model."""
        if not self._conn:
            raise RuntimeError("Database is not connected. Call connect() first.")

        # Cache only SELECT and WITH queries
        is_select = query.strip().lower().startswith("select") or query.strip().lower().startswith("with")
        memory = self.memory
        query_key = f"db_query:{query}:{params}"
        
        if is_select and memory:
            try:
                cached = await memory.get_cached_query(query_key)
                if cached:
                    return cached
            except Exception:
                pass

        # Convert Postgres-style $1, $2, ... placeholders to SQLite ?
        # Reconstruct params to match the order and replication of placeholders in SQLite
        placeholders = re.findall(r'\$(\d+)', query)
        if placeholders:
            new_params = []
            for p in placeholders:
                idx = int(p) - 1
                if idx < len(params):
                    new_params.append(params[idx])
                else:
                    raise IndexError(f"Query placeholder ${p} is out of bounds for params (len={len(params)})")
            params = tuple(new_params)
            sqlite_query = re.sub(r'\$\d+', '?', query)
        else:
            sqlite_query = query

        async with self._conn.execute(sqlite_query, params) as cursor:
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            
            # Convert Row objects to list of values
            processed_rows = [list(row) for row in rows]

            result = QueryResult(
                columns=columns,
                rows=processed_rows,
                row_count=len(processed_rows),
                query_name=query[:50].strip()
            )

            if is_select and memory:
                try:
                    await memory.cache_query_result(query_key, result)
                except Exception:
                    pass

            return result

    async def health_check(self) -> bool:
        """Check if the database is reachable."""
        if not self._conn:
            return False
        try:
            async with self._conn.execute("SELECT 1") as cursor:
                await cursor.fetchone()
            return True
        except Exception:
            return False


_pool_instance: Optional[AsyncDBPool] = None

def get_pool(database_url: str = None) -> AsyncDBPool:
    """Get the active database pool singleton instance, creating it if needed."""
    global _pool_instance
    from src.config.settings import get_settings
    target_url = database_url if database_url is not None else str(get_settings().DATABASE_URL)

    if _pool_instance is None or _pool_instance.database_url != target_url:
        _pool_instance = AsyncDBPool(target_url)
    return _pool_instance
