import calendar
from datetime import date
from typing import Optional, Union
from src.tools.database.connection import get_pool

def _resolve_date_params(month: Optional[Union[str, int]], year: Optional[int]) -> tuple[int, int]:
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        return today.month, year
    
    month_str = str(month).strip().lower()
    if month_str == "current":
        return today.month, year
    elif month_str in ("last", "previous"):
        m = today.month - 1
        y = year
        if m == 0:
            m = 12
            y -= 1
        return m, y
        
    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
        "nov": 11, "november": 11, "dec": 12, "december": 12
    }
    
    if month_str.isdigit():
        return int(month_str), year
    return month_map.get(month_str, today.month), year

async def get_mrr_by_segment(month: Optional[Union[str, int]] = None, year: Optional[int] = None) -> dict[str, float]:
    """Monthly recurring revenue in USD by segment.
    
    Args:
        month: Month name/number or 'current'/'last'. Defaults to current month.
        year: Year as integer. Defaults to current year.
    """
    m_num, r_year = _resolve_date_params(month, year)
    start_date = date(r_year, m_num, 1)
    last_day = calendar.monthrange(r_year, m_num)[1]
    end_date = date(r_year, m_num, last_day)

    query = """
        SELECT segment, COALESCE(SUM(mrr_cents), 0) / 100.0 as mrr_usd
        FROM customers
        WHERE date(created_at) <= $2 AND (cancelled_at IS NULL OR date(cancelled_at) >= $1)
        GROUP BY segment
    """
    
    pool = get_pool()
    result = await pool.execute_query(query, (start_date, end_date))
    return {row[0]: float(row[1]) for row in result.rows}

async def get_ltv_by_segment() -> dict[str, float]:
    """Average customer lifetime value per segment."""
    query = """
        SELECT c.segment, 
               CASE 
                   WHEN COUNT(DISTINCT c.id) > 0 THEN COALESCE(SUM(p.amount_cents), 0) / (COUNT(DISTINCT c.id) * 100.0)
                   ELSE 0.0
               END as avg_ltv
        FROM customers c
        LEFT JOIN payments p ON c.id = p.customer_id AND p.status IN ('succeeded', 'paid', 'successful')
        GROUP BY c.segment
    """
    
    pool = get_pool()
    result = await pool.execute_query(query)
    return {row[0]: float(row[1]) for row in result.rows}

async def get_new_vs_churned_customers(month: Optional[Union[str, int]] = None, year: Optional[int] = None) -> dict:
    """Returns {"new": int, "churned": int, "net": int} for a given month.
    
    Args:
        month: Month name/number or 'current'/'last'. Defaults to current month.
        year: Year as integer. Defaults to current year.
    """
    m_num, r_year = _resolve_date_params(month, year)
    start_date = date(r_year, m_num, 1)
    last_day = calendar.monthrange(r_year, m_num)[1]
    end_date = date(r_year, m_num, last_day)

    query = """
        SELECT 
            (SELECT COUNT(*) FROM customers WHERE date(created_at) >= $1 AND date(created_at) <= $2) as new_count,
            (SELECT COUNT(*) FROM churn_events WHERE date(churned_at) >= $1 AND date(churned_at) <= $2) as churned_count
    """
    
    pool = get_pool()
    result = await pool.execute_query(query, (start_date, end_date))
    
    if result.rows:
        new_count = int(result.rows[0][0])
        churned_count = int(result.rows[0][1])
    else:
        new_count = 0
        churned_count = 0

    return {
        "new": new_count,
        "churned": churned_count,
        "net": new_count - churned_count
    }
