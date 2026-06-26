#!/usr/bin/env python3
"""VentureMind — System Health Check Script.

Validates that all external dependencies (Ollama, models, databases)
are accessible and correctly configured before running the pipeline.

Usage:
    python scripts/health_check.py
"""

import asyncio
import os
import sys

# Ensure project root is on the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


async def check_ollama(settings) -> bool:
    """Verify Ollama server is reachable and required models are pulled."""
    from src.llm.ollama_client import OllamaClient

    client = OllamaClient(
        base_url=str(settings.OLLAMA_BASE_URL),
        orchestrator_model=settings.OLLAMA_ORCHESTRATOR_MODEL,
        analyst_model=settings.OLLAMA_ANALYST_MODEL,
        summary_model=settings.OLLAMA_SUMMARY_MODEL,
        embed_model=settings.OLLAMA_EMBED_MODEL,
        timeout=15.0,
    )

    try:
        is_healthy = await client.health_check()
        if not is_healthy:
            fail(f"Ollama server is not responding at {settings.OLLAMA_BASE_URL}")
            return False
        ok(f"Ollama server is online at {settings.OLLAMA_BASE_URL}")

        # Check models
        models = await client.list_models()
        required_models = list(set([
            settings.OLLAMA_ORCHESTRATOR_MODEL,
            settings.OLLAMA_ANALYST_MODEL,
            settings.OLLAMA_SUMMARY_MODEL,
            settings.OLLAMA_EMBED_MODEL,
        ]))

        all_present = True
        for model in required_models:
            norm_model = model if ":" in model else f"{model}:latest"
            norm_available = [m if ":" in m else f"{m}:latest" for m in models]
            if norm_model in norm_available or model in models:
                ok(f"Model available: {model}")
            else:
                fail(f"Model MISSING: {model} — run: ollama pull {model}")
                all_present = False

        return all_present

    except Exception as e:
        fail(f"Ollama connectivity check failed: {e}")
        return False
    finally:
        await client.close()


async def check_shared_memory(settings) -> bool:
    """Verify that the SharedMemory SQLite database is writable."""
    from src.memory.shared_memory import SharedMemory

    memory = SharedMemory(db_path=str(settings.DRAGONFLY_URL))
    try:
        healthy = await memory.health_check()
        if healthy:
            ok(f"Shared memory database is accessible: {settings.DRAGONFLY_URL}")
            return True
        else:
            fail(f"Shared memory database health check failed: {settings.DRAGONFLY_URL}")
            return False
    except Exception as e:
        fail(f"Shared memory database error: {e}")
        return False


async def check_report_database(settings) -> bool:
    """Verify that the Report SQLite database is writable."""
    from src.memory.database import ReportDatabase

    db = ReportDatabase(database_url=str(settings.DATABASE_URL))
    try:
        await db.connect()
        ok(f"Report database is accessible: {settings.DATABASE_URL}")
        await db.disconnect()
        return True
    except Exception as e:
        fail(f"Report database connection failed: {e}")
        return False


def check_data_directories(settings) -> bool:
    """Verify data output directories exist and are writable."""
    output_dir = settings.REPORTS_OUTPUT_DIR
    if os.path.isdir(output_dir):
        ok(f"Reports output directory exists: {output_dir}")
        # Check writability
        test_file = os.path.join(output_dir, ".health_check_test")
        try:
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            ok(f"Reports output directory is writable")
            return True
        except OSError as e:
            fail(f"Reports output directory is NOT writable: {e}")
            return False
    else:
        warn(f"Reports output directory does not exist: {output_dir} (will be created on first run)")
        return True


def check_env_file() -> bool:
    """Verify a .env file exists."""
    if os.path.isfile(".env"):
        ok(".env configuration file found")
        return True
    elif os.path.isfile(".env.example"):
        warn(".env file not found. Copy from .env.example: cp .env.example .env")
        return False
    else:
        fail("Neither .env nor .env.example found. Configuration is missing.")
        return False


def check_prompt_templates() -> bool:
    """Verify prompt template files exist."""
    prompts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
    if not os.path.isdir(prompts_dir):
        warn(f"Prompts directory not found: {prompts_dir}")
        return False

    expected = [
        "market_analysis.txt",
        "financial_analysis.txt",
        "competitor_positioning.txt",
        "profile_extraction.txt",
        "legal_classification.txt",
        "synthesis.txt",
        "scoring.txt"
    ]
    all_found = True
    for template in expected:
        path = os.path.join(prompts_dir, template)
        if os.path.isfile(path):
            ok(f"Prompt template found: {template}")
        else:
            warn(f"Prompt template missing: {template}")
            all_found = False
    return all_found


async def main():
    print(f"\n{BOLD}═══════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}  VentureMind System Health Check{RESET}")
    print(f"{BOLD}═══════════════════════════════════════════════════════{RESET}\n")

    results: dict[str, bool] = {}

    # 1. Environment file
    print(f"{BOLD}[1/6] Configuration{RESET}")
    results["env_file"] = check_env_file()

    # 2. Load settings
    print(f"\n{BOLD}[2/6] Settings Validation{RESET}")
    try:
        from src.config.settings import get_settings
        settings = get_settings()
        ok(f"Settings loaded successfully")
        ok(f"  Ollama URL:          {settings.OLLAMA_BASE_URL}")
        ok(f"  Orchestrator Model:  {settings.OLLAMA_ORCHESTRATOR_MODEL}")
        ok(f"  Analyst Model:       {settings.OLLAMA_ANALYST_MODEL}")
        ok(f"  Summary Model:       {settings.OLLAMA_SUMMARY_MODEL}")
        ok(f"  Embed Model:         {settings.OLLAMA_EMBED_MODEL}")
        results["settings"] = True
    except Exception as e:
        fail(f"Failed to load settings: {e}")
        print(f"\n{RED}Cannot continue health check without valid settings.{RESET}")
        sys.exit(1)

    # 3. Ollama
    print(f"\n{BOLD}[3/6] Ollama LLM Server{RESET}")
    results["ollama"] = await check_ollama(settings)

    # 4. Databases
    print(f"\n{BOLD}[4/6] Databases{RESET}")
    results["shared_memory"] = await check_shared_memory(settings)
    results["report_db"] = await check_report_database(settings)

    # 5. Data directories
    print(f"\n{BOLD}[5/6] Data Directories{RESET}")
    results["data_dirs"] = check_data_directories(settings)

    # 6. Prompt templates
    print(f"\n{BOLD}[6/6] Prompt Templates{RESET}")
    results["prompts"] = check_prompt_templates()

    # ── Summary ─────────────────────────────────────────────
    print(f"\n{BOLD}═══════════════════════════════════════════════════════{RESET}")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    all_ok = all(results.values())

    if all_ok:
        print(f"  {GREEN}{BOLD}ALL CHECKS PASSED ({passed}/{total}){RESET}")
        print(f"  System is ready to run the diligence pipeline.")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  {YELLOW}{BOLD}CHECKS: {passed}/{total} passed{RESET}")
        print(f"  {RED}Failed: {', '.join(failed)}{RESET}")
        print(f"  Please resolve the issues above before running the pipeline.")

    print(f"{BOLD}═══════════════════════════════════════════════════════{RESET}\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
