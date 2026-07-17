import re
from typing import Any, Dict, List, Optional
import asyncpg
import structlog

logger = structlog.get_logger()


class WriteCommandException(PermissionError):
    """Exception raised when a modification query is detected in a read-only repository."""
    pass


class CustomerRepository:
    """Read-only repository for querying customer profiles and order histories."""
    def __init__(self, dsn: str, pool: Optional[asyncpg.Pool] = None) -> None:
        self.dsn = dsn
        self.pool = pool

    async def initialize(self) -> None:
        """Initializes connection pool if not already provided."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self.dsn,
                min_size=2,
                max_size=10,
            )
            logger.info("Created Postgres pool for CustomerRepository", min_size=2, max_size=10)

    async def close(self) -> None:
        """Closes the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed Postgres pool for CustomerRepository")

    def _guard_query(self, query: str) -> None:
        """Guards against write operations using a case-insensitive regex check."""
        forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
        normalized = query.upper()
        
        for keyword in forbidden_keywords:
            # Match only full word boundaries to avoid false positives (e.g. 'created_at')
            if re.search(r'\b' + re.escape(keyword) + r'\b', normalized):
                raise WriteCommandException(
                    f"Security Exception: Write command '{keyword}' is prohibited in this read-only repository."
                )

    async def _fetch_row(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        self._guard_query(query)
        if not self.pool:
            raise RuntimeError("Repository is not initialized. Call initialize() first.")
            
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def _fetch_all(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        self._guard_query(query)
        if not self.pool:
            raise RuntimeError("Repository is not initialized. Call initialize() first.")
            
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves customer record by ID."""
        query = "SELECT id, email, tier, created_at FROM customers WHERE id = $1"
        return await self._fetch_row(query, customer_id)

    async def get_order_history(self, customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves ordered history list for a customer."""
        query = """
            SELECT id, customer_id, stripe_charge_id, status, amount_cents, created_at 
            FROM orders 
            WHERE customer_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
        """
        return await self._fetch_all(query, customer_id, limit)
