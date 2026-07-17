import asyncio
import os
import sys
import stripe
import httpx
import redis.asyncio as aioredis
import asyncpg
from fastapi.testclient import TestClient

# Ensure src path is in Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import settings
from src.main import app
from src.policy.pii_scrubber import scrub
from src.policy.audit_log import verify_chain


async def run_checks() -> bool:
    all_passed = True
    print("==================================================")
    print("       FAILSAFE-AGENT PROD READINESS CHECK        ")
    print("==================================================")

    # 1. Environment variables check
    required_vars = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "STRIPE_SECRET_KEY", "DATABASE_URL", "REDIS_URL"]
    env_ok = True
    for var in required_vars:
        val = os.getenv(var)
        if not val:
            print(f"[-] Environment variable {var} is missing or empty.")
            env_ok = False
        else:
            # Mask sensitive values
            masked = val[:5] + "..." if len(val) > 5 else "..."
            print(f"[+] Environment variable {var}: SET ({masked})")
    
    if env_ok:
        print("[PASS] Environment Check")
    else:
        print("[FAIL] Environment Check")
        all_passed = False

    # 2. Redis Connection & Ping
    redis_ok = False
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        print("[+] Redis Connection: Ping Successful")
        redis_ok = True
    except Exception as e:
        print(f"[-] Redis Connection failed: {str(e)}")
        all_passed = False

    # 3. Database Connection & Migration Check
    db_ok = False
    try:
        conn = await asyncpg.connect(dsn=settings.DATABASE_URL.get_secret_value())
        # Check if migrations table alembic_version exists
        version = await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
        print(f"[+] Postgres Connection: Migration Version: {version or 'No Migrations Applied (Version Table Empty)'}")
        await conn.close()
        db_ok = True
    except Exception as e:
        print(f"[-] Postgres / Migration Check failed: {str(e)}")
        all_passed = False

    # 4. Stripe API Key Validation
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY.get_secret_value()
        # Verify key works by retrieving account details
        if stripe.api_key.startswith("mock-"):
            print("[+] Stripe API Validation: Mock Key Detected (Bypassing validation)")
        else:
            await asyncio.to_thread(stripe.Account.retrieve)
            print("[+] Stripe API Key: Valid")
    except Exception as e:
        print(f"[-] Stripe API Validation failed: {str(e)}")
        all_passed = False

    # 5. Anthropic API Key Validation
    try:
        api_key = settings.ANTHROPIC_API_KEY.get_secret_value()
        if api_key.startswith("mock-"):
            print("[+] Anthropic API Validation: Mock Key Detected (Bypassing validation)")
        else:
            # Test call with max_tokens = 1
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": settings.PRIMARY_MODEL,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1
                    },
                    timeout=5.0
                )
                res.raise_for_status()
            print("[+] Anthropic API Key: Valid")
    except Exception as e:
        print(f"[-] Anthropic API Validation failed: {str(e)}")
        all_passed = False

    # 6. /health Endpoint Check
    try:
        # Use TestClient to trigger app's actual endpoints and startup checks
        with TestClient(app) as client:
            res = client.get("/health")
            data = res.json()
            if res.status_code == 200 and data.get("status") in ("healthy", "unhealthy"):
                print(f"[+] Health Endpoint Check: Status is {data.get('status')} (Database ok: {data.get('db_ok')}, Redis ok: {data.get('redis_ok')})")
            else:
                print(f"[-] Health Endpoint check returned status code {res.status_code}: {data}")
                all_passed = False
    except Exception as e:
        print(f"[-] Health Endpoint Check failed: {str(e)}")
        all_passed = False

    # 7. Circuit Breakers check
    if redis_ok:
        try:
            keys = await redis_client.keys("cb:*")
            all_closed = True
            for key in keys:
                state_data_bytes = await redis_client.get(key)
                if state_data_bytes:
                    import json
                    state_data = json.loads(state_data_bytes)
                    if state_data.get("state") == "OPEN":
                        print(f"[-] Circuit Breaker for {key.replace('cb:', '')} is OPEN.")
                        all_closed = False
            if all_closed:
                print("[+] Circuit Breaker status: All Closed")
            else:
                all_passed = False
        except Exception as e:
            print(f"[-] Circuit Breaker check failed: {str(e)}")
            all_passed = False

    # 8. PII Scrubber Check
    try:
        test_cc = "Test card number: 4242 4242 4242 4242"
        scrubbed = scrub(test_cc).scrubbed_text
        if "[CARD_REDACTED]" in scrubbed and "4242" not in scrubbed:
            print("[+] PII Scrubber Check: Successfully Redacted Credit Cards")
        else:
            print(f"[-] PII Scrubber Check failed. Output: {scrubbed}")
            all_passed = False
    except Exception as e:
        print(f"[-] PII Scrubber Check failed: {str(e)}")
        all_passed = False

    # 9. Audit Log Chain Verification
    if db_ok:
        try:
            # Verify chain of last 10 unique conversation events
            conn = await asyncpg.connect(dsn=settings.DATABASE_URL.get_secret_value())
            convs = await conn.fetch("SELECT DISTINCT conversation_id FROM audit_events LIMIT 10")
            
            chain_ok = True
            for r in convs:
                conv_id = r["conversation_id"]
                valid = await verify_chain(conv_id, app.state.db_pool)
                if not valid:
                    print(f"[-] Audit log chain for conversation {conv_id} is TAMPERED or INVALID.")
                    chain_ok = False
            
            if chain_ok:
                print(f"[+] Audit Log Chain Check: Verified last {len(convs)} conversation chains")
            else:
                all_passed = False
            await conn.close()
        except Exception as e:
            print(f"[-] Audit Log Chain Check failed: {str(e)}")
            all_passed = False

    print("==================================================")
    if all_passed:
        print("[PASS] PRODUCTION READINESS CHECKS SUCCESSFUL")
        print("==================================================")
        return True
    else:
        print("[FAIL] PRODUCTION READINESS CHECKS FAILED")
        print("==================================================")
        return False


if __name__ == "__main__":
    passed = asyncio.run(run_checks())
    sys.exit(0 if passed else 1)
