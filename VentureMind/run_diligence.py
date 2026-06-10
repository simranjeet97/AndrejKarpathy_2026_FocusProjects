import asyncio
import logging
import os
import sys
import time
from src.api.dependencies import get_orchestrator, get_renderer, get_report_database
from src.report.renderer import ReportRenderer

# Set up logging to output info directly to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("run_diligence")

async def run_pipeline(startup_name: str):
    logger.info("=" * 60)
    logger.info(f"STARTING VENTUREMIND DUE DILIGENCE RUN FOR: {startup_name}")
    logger.info("=" * 60)

    # Initialize components
    orchestrator = get_orchestrator()
    renderer = get_renderer()
    db = get_report_database()

    # Connect to the SQLite audit and persistence database
    logger.info("Connecting to the database...")
    await db.connect()

    try:
        # Run 1: Cold start (fetches and LLM extraction)
        logger.info("\n--- Run 1: Cold Start (fetching web data & querying Ollama) ---")
        t0 = time.monotonic()
        report = await orchestrator.run(startup_name)
        elapsed_cold = time.monotonic() - t0
        logger.info(f"Run 1 completed in {elapsed_cold:.2f} seconds.")

        # Save to database
        logger.info("Persisting report to database...")
        report_id = await db.save_report(report)
        logger.info(f"Saved report ID: {report_id}")

        # Save agent results to audit log
        for result in report.agent_results:
            logger.info(f"Saving audit logs for agent: {result.agent_name}")
            await db.save_agent_result(startup_name, result)

        # Generate markdown and save to disk
        markdown_content = renderer.render_markdown(report)
        md_filename = os.path.join(renderer.output_dir, f"{startup_name.lower().replace(' ', '_')}_report.md")
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"Saved Markdown report to: {md_filename}")

        # Try rendering DOCX
        try:
            docx_filename = renderer.render_docx(report)
            logger.info(f"Saved Word/DOCX report to: {docx_filename}")
        except Exception as docx_err:
            logger.warning(f"Failed to generate Word/DOCX report: {docx_err}")

        # Run 2: Hot start (testing shared memory cache)
        logger.info("\n--- Run 2: Hot Start (testing Dragonfly/SQLite shared memory cache) ---")
        t1 = time.monotonic()
        cached_report = await orchestrator.run(startup_name)
        elapsed_cached = time.monotonic() - t1
        logger.info(f"Run 2 completed in {elapsed_cached:.4f} seconds.")
        logger.info(f"Cache speedup: {elapsed_cold / elapsed_cached:.1f}x faster!")

        # Print a short preview of the generated report
        logger.info("\n" + "=" * 60)
        logger.info("REPORT PREVIEW (FIRST 800 CHARACTERS)")
        logger.info("=" * 60)
        logger.info(markdown_content[:800] + "\n...")

    finally:
        logger.info("Disconnecting from the database...")
        await db.disconnect()

if __name__ == "__main__":
    startup = sys.argv[1] if len(sys.argv) > 1 else "Linear"
    asyncio.run(run_pipeline(startup))
