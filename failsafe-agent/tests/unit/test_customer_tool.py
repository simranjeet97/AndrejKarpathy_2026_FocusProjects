import pytest
from unittest.mock import AsyncMock, MagicMock

from src.tools.customer_tool import CustomerRepository, WriteCommandException


def test_query_guard_blocks_modifications() -> None:
    repo = CustomerRepository(dsn="postgresql://mock")
    
    # Check that forbidden keywords raise exceptions
    with pytest.raises(WriteCommandException):
        repo._guard_query("INSERT INTO customers (id) VALUES ('123')")
        
    with pytest.raises(WriteCommandException):
        repo._guard_query("UPDATE customers SET tier = 'vip'")
        
    with pytest.raises(WriteCommandException):
        repo._guard_query("DELETE FROM orders WHERE id = '1'")
        
    with pytest.raises(WriteCommandException):
        repo._guard_query("DROP TABLE customers")


def test_query_guard_allows_safe_queries() -> None:
    repo = CustomerRepository(dsn="postgresql://mock")
    
    # Safe SELECT queries should execute without issues
    # Ensure substring matches on words like "created_at" are NOT falsely flagged as "CREATE"
    repo._guard_query("SELECT id, created_at FROM customers WHERE id = $1")
    repo._guard_query("SELECT * FROM orders ORDER BY id DESC")


@pytest.mark.asyncio
async def test_get_customer() -> None:
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    
    # Configure mock connection to return a mock row
    mock_row = {"id": "cust_01", "email": "alice@example.com", "tier": "vip"}
    mock_conn.fetchrow.return_value = mock_row
    
    # Setup context manager mock for pool.acquire
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    repo = CustomerRepository(dsn="postgresql://mock", pool=mock_pool)
    customer = await repo.get_customer("cust_01")
    
    assert customer == mock_row
    mock_conn.fetchrow.assert_called_once_with(
        "SELECT id, email, tier, created_at FROM customers WHERE id = $1",
        "cust_01"
    )


@pytest.mark.asyncio
async def test_get_order_history() -> None:
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    
    mock_rows = [
        {"id": "ord_101", "amount_cents": 5000},
        {"id": "ord_102", "amount_cents": 12000}
    ]
    mock_conn.fetch.return_value = mock_rows
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    repo = CustomerRepository(dsn="postgresql://mock", pool=mock_pool)
    orders = await repo.get_order_history("cust_01", limit=5)
    
    assert orders == mock_rows
    mock_conn.fetch.assert_called_once()
    query = mock_conn.fetch.call_args[0][0]
    assert "LIMIT $2" in query
