import calendar
from datetime import date
from typing import Optional, Union
from src.models import ChurnSegment
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

async def get_monthly_churn_by_segment(month: Optional[Union[str, int]] = None, year: Optional[int] = None) -> list[ChurnSegment]:
    """Returns churn rate broken down by customer segment for a given month.
    
    Args:
        month: Month name/number or 'current'/'last'. Defaults to current month.
        year: Year as integer. Defaults to current year.
    """
    m_num, r_year = _resolve_date_params(month, year)
    start_date = date(r_year, m_num, 1)
    last_day = calendar.monthrange(r_year, m_num)[1]
    end_date = date(r_year, m_num, last_day)

    query = """
        WITH segments AS (
            SELECT DISTINCT segment FROM customers
            UNION
            SELECT DISTINCT segment FROM churn_events
        ),
        start_active AS (
            SELECT segment, COUNT(*) as active_count
            FROM customers
            WHERE date(created_at) < $1 AND (cancelled_at IS NULL OR date(cancelled_at) >= $1)
            GROUP BY segment
        ),
        churned AS (
            SELECT segment, COUNT(*) as churned_count
            FROM churn_events
            WHERE date(churned_at) >= $1 AND date(churned_at) <= $2
            GROUP BY segment
        )
        SELECT 
            seg.segment,
            COALESCE(s.active_count, 0) as active_count,
            COALESCE(c.churned_count, 0) as churned_count
        FROM segments seg
        LEFT JOIN start_active s ON seg.segment = s.segment
        LEFT JOIN churned c ON seg.segment = c.segment
    """
    
    pool = get_pool()
    result = await pool.execute_query(query, (start_date, end_date))
    
    churn_segments = []
    period_str = f"{year}-{m_num:02d}"
    
    for row in result.rows:
        segment_name = row[0]
        active_count = int(row[1])
        churned_count = int(row[2])
        
        churn_rate = churned_count / active_count if active_count > 0 else 0.0
        
        churn_segments.append(
            ChurnSegment(
                segment_name=segment_name,
                churn_rate=churn_rate,
                customer_count=active_count,
                period=period_str
            )
        )
        
    return churn_segments

async def get_top_churned_segments(n: int = 5, period_months: int = 3) -> list[ChurnSegment]:
    """Returns the N segments with highest churn over the last period_months."""
    today = date.today()
    year = today.year
    month = today.month - period_months
    while month <= 0:
        month += 12
        year -= 1
        
    start_of_period = date(year, month, 1)
    end_of_period = today

    query = """
        WITH segments AS (
            SELECT DISTINCT segment FROM customers
            UNION
            SELECT DISTINCT segment FROM churn_events
        ),
        start_active AS (
            SELECT segment, COUNT(*) as active_count
            FROM customers
            WHERE date(created_at) < $1 AND (cancelled_at IS NULL OR date(cancelled_at) >= $1)
            GROUP BY segment
        ),
        churned AS (
            SELECT segment, COUNT(*) as churned_count
            FROM churn_events
            WHERE date(churned_at) >= $1 AND date(churned_at) <= $2
            GROUP BY segment
        )
        SELECT 
            seg.segment,
            COALESCE(s.active_count, 0) as active_count,
            COALESCE(c.churned_count, 0) as churned_count,
            CASE 
                WHEN COALESCE(s.active_count, 0) > 0 THEN CAST(COALESCE(c.churned_count, 0) AS REAL) / s.active_count
                ELSE 0.0
            END as churn_rate
        FROM segments seg
        LEFT JOIN start_active s ON seg.segment = s.segment
        LEFT JOIN churned c ON seg.segment = c.segment
        ORDER BY churn_rate DESC
        LIMIT $3
    """

    pool = get_pool()
    result = await pool.execute_query(query, (start_of_period, end_of_period, n))
    
    churn_segments = []
    period_str = f"Last {period_months} Months"
    
    for row in result.rows:
        segment_name = row[0]
        active_count = int(row[1])
        churn_rate = float(row[3])
        
        churn_segments.append(
            ChurnSegment(
                segment_name=segment_name,
                churn_rate=churn_rate,
                customer_count=active_count,
                period=period_str
            )
        )
        
    return churn_segments

async def get_churn_trend(segment_name: str, months_back: int = 12) -> list[dict]:
    """Returns monthly churn rate trend for a specific segment."""
    query = """
        WITH RECURSIVE months(month_date) AS (
            SELECT date('now', 'start of month', '-' || ($2 - 1) || ' month')
            UNION ALL
            SELECT date(month_date, '+1 month')
            FROM months
            WHERE month_date < date('now', 'start of month')
        ),
        monthly_metrics AS (
            SELECT 
                m.month_date,
                (
                    SELECT COUNT(*) 
                    FROM customers c
                    WHERE c.segment = $1 
                      AND date(c.created_at) < m.month_date 
                      AND (c.cancelled_at IS NULL OR date(c.cancelled_at) >= m.month_date)
                ) as active_count,
                (
                    SELECT COUNT(*) 
                    FROM churn_events ce
                    WHERE ce.segment = $1 
                      AND date(ce.churned_at) >= m.month_date 
                      AND date(ce.churned_at) < date(m.month_date, '+1 month')
                ) as churned_count
            FROM months m
        )
        SELECT 
            strftime('%Y-%m', month_date) as month,
            active_count,
            churned_count,
            CASE 
                WHEN active_count > 0 THEN CAST(churned_count AS REAL) / active_count
                ELSE 0.0
            END as churn_rate
        FROM monthly_metrics
        ORDER BY month_date ASC
    """

    pool = get_pool()
    result = await pool.execute_query(query, (segment_name, months_back))
    
    trend = []
    for row in result.rows:
        trend.append({
            "month": row[0],
            "active_count": int(row[1]),
            "churned_count": int(row[2]),
            "churn_rate": float(row[3])
        })
        
    return trend

async def get_customer_count_by_segment() -> dict[str, int]:
    """Returns current active customer count per segment."""
    pool = get_pool()
    query = """
        SELECT segment, COUNT(*) as count 
        FROM customers 
        WHERE cancelled_at IS NULL OR date(cancelled_at) > date('now')
        GROUP BY segment
    """
    result = await pool.execute_query(query)
    return {row[0]: int(row[1]) for row in result.rows}

async def get_revenue_at_risk(segment_name: str) -> dict:
    """Returns MRR at risk based on current churn rate for a segment."""
    # Retrieve the last completed month's churn rate to use as current rate
    today = date.today()
    year = today.year
    month = today.month - 1
    if month == 0:
        month = 12
        year -= 1

    churn_segments = await get_monthly_churn_by_segment(str(month), year)
    
    churn_rate = 0.0
    for s in churn_segments:
        if s.segment_name.lower() == segment_name.lower():
            churn_rate = s.churn_rate
            break

    # Get current active MRR for the segment
    pool = get_pool()
    query = """
        SELECT COALESCE(SUM(mrr_cents), 0) 
        FROM customers 
        WHERE segment = $1 AND (cancelled_at IS NULL OR date(cancelled_at) > date('now'))
    """
    result = await pool.execute_query(query, (segment_name,))
    active_mrr_cents = int(result.rows[0][0]) if result.rows else 0
    
    mrr_at_risk_cents = int(active_mrr_cents * churn_rate)

    return {
        "segment": segment_name,
        "mrr_at_risk_cents": mrr_at_risk_cents,
        "currency": "usd"
    }
