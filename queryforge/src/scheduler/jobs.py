import os
import time
import json
import logging
from datetime import date, datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.tools.database.churn_tools import get_top_churned_segments
from src.tools.web.search_tool import search_industry_benchmarks

logger = logging.getLogger(__name__)

async def refresh_churn_cache(memory) -> None:
    """Refresh the top churned segments cache in DragonflyDB/Redis."""
    try:
        logger.info("Starting refresh_churn_cache background job...")
        start_time = time.time()
        segments = await get_top_churned_segments(n=5, period_months=3)
        
        # Serialize list of ChurnSegment models to JSON
        data = json.dumps([s.model_dump() for s in segments])
        await memory.client.setex("cache:top_churned_segments", 15 * 60, data)
        
        elapsed = time.time() - start_time
        logger.info(f"Successfully refreshed churn cache in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"Failed to refresh churn cache: {e}")

async def fetch_industry_benchmarks(memory) -> None:
    """Fetch daily SaaS industry benchmarks and cache them for 24 hours."""
    try:
        logger.info("Starting fetch_industry_benchmarks background job...")
        metrics = ["churn", "LTV", "CAC"]
        for metric in metrics:
            benchmarks = await search_industry_benchmarks(metric, industry="saas")
            
            # Serialize benchmarks to JSON
            data = json.dumps([b.model_dump(mode='json') for b in benchmarks])
            await memory.client.setex(f"cache:benchmark:{metric}", 86400, data)
            logger.info(f"Updated industry benchmarks cache for metric: {metric}")
    except Exception as e:
        logger.error(f"Failed to fetch industry benchmarks: {e}")

async def cleanup_old_charts(charts_output_dir: str) -> None:
    """Delete chart PNG files older than 7 days from CHARTS_OUTPUT_DIR."""
    try:
        logger.info("Starting cleanup_old_charts background job...")
        if not os.path.exists(charts_output_dir):
            logger.warning(f"Charts output directory does not exist: {charts_output_dir}")
            return

        now = time.time()
        cutoff = now - (7 * 86400)  # 7 days in seconds
        deleted_count = 0

        for filename in os.listdir(charts_output_dir):
            if filename.endswith(".png"):
                filepath = os.path.join(charts_output_dir, filename)
                stat = os.stat(filepath)
                if stat.st_mtime < cutoff:
                    os.remove(filepath)
                    deleted_count += 1

        logger.info(f"Completed chart cleanup. Deleted {deleted_count} files.")
    except Exception as e:
        logger.error(f"Error cleaning up old charts: {e}")

async def log_daily_metrics(memory) -> None:
    """Pull daily tool usage stats and write summary to daily log file."""
    try:
        logger.info("Starting log_daily_metrics background job...")
        stats = await memory.get_tool_usage_stats(days=1)
        today_str = date.today().isoformat()

        # Resolve logs directory path
        log_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../data/cache")
        )
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_path = os.path.join(log_dir, "daily_metrics.log")

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] Date: {today_str}\n")
            f.write("Tool usage statistics (Last 1 day):\n")
            if stats:
                for tool, count in stats.items():
                    f.write(f"  - {tool}: {count} calls\n")
            else:
                f.write("  - No tools executed\n")
            f.write("-" * 40 + "\n")

        logger.info(f"Daily metrics logged to {log_path}")
    except Exception as e:
        logger.error(f"Failed to log daily metrics: {e}")

def setup_scheduler(memory, settings) -> AsyncIOScheduler:
    """Create and configure the AsyncIOScheduler background job scheduler."""
    scheduler = AsyncIOScheduler()

    # 1. Churn cache refresh: runs every 15 minutes
    scheduler.add_job(
        refresh_churn_cache,
        trigger="interval",
        minutes=15,
        args=[memory],
        name="refresh_churn_cache"
    )

    # 2. Benchmarks fetch: daily at 2:00 AM
    scheduler.add_job(
        fetch_industry_benchmarks,
        trigger="cron",
        hour=2,
        minute=0,
        args=[memory],
        name="fetch_industry_benchmarks"
    )

    # 3. Cleanup old charts: daily at 3:00 AM
    scheduler.add_job(
        cleanup_old_charts,
        trigger="cron",
        hour=3,
        minute=0,
        args=[settings.CHARTS_OUTPUT_DIR],
        name="cleanup_old_charts"
    )

    # 4. Daily metrics log: daily at midnight (0:00 AM)
    scheduler.add_job(
        log_daily_metrics,
        trigger="cron",
        hour=0,
        minute=0,
        args=[memory],
        name="log_daily_metrics"
    )

    return scheduler
