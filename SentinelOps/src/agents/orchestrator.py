import time
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
import structlog

from src.config import settings
from src.database import get_db_pool, append_audit_entry
from src.tools.metrics_tool import query_service_metrics
from src.tools.logs_tool import fetch_service_logs
from src.tools.runbook_tool import search_runbook

logger = structlog.get_logger()


async def process_incident(
    service: str,
    title: str,
    description: str,
    severity: str = "P1",
) -> Dict[str, Any]:
    incident_id = f"inc_{uuid.uuid4().hex[:8]}"
    now_str = datetime.now(timezone.utc).isoformat()
    pool = await get_db_pool()

    # Step 1: Telemetry & Log Investigation
    metrics = query_service_metrics(service, f"{title} {description}")
    logs = fetch_service_logs(service, f"{title} {description}")

    # Step 2: Runbook Lookup
    runbook = search_runbook(service, f"{title} {description}")
    runbook_id = runbook["id"] if runbook else "RB-GENERIC"
    remediation_template = runbook["remediation"] if runbook else f"# Restart service {service}\nkubectl rollout restart deployment {service} -n production"
    risk_level = runbook["risk_level"] if runbook else "LOW"
    confidence_score = runbook["confidence_baseline"] if runbook else 0.92

    # Step 3: Local Ollama Reasoning
    root_cause_explanation = (
        f"Incident on {service}: {title}. Metrics confirm critical threshold breach ({metrics.get('status')}). "
        f"Correlated stack traces indicate {runbook.get('title', 'service instability') if runbook else 'service instability'}."
    )

    try:
        async with httpx.AsyncClient() as client:
            prompt = (
                f"You are SentinelOps Autonomous DevOps Incident Response Agent.\n"
                f"Service: {service}\n"
                f"Alert Severity: {severity}\n"
                f"Issue Title: {title}\n"
                f"Description: {description}\n"
                f"Telemetry Metrics: {json.dumps(metrics)}\n"
                f"Recent Logs:\n" + "\n".join(logs[:3]) + "\n"
                f"Matching Runbook: {runbook.get('title') if runbook else 'None'}\n\n"
                f"Provide a 2-sentence precise root cause analysis and state the primary remediation action."
            )
            resp = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json={
                    "model": settings.ollama_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 250,
                },
                timeout=settings.timeout_seconds,
            )
            if resp.status_code == 200:
                data = resp.json()
                llm_text = data["choices"][0]["message"]["content"].strip()
                if len(llm_text) > 20:
                    root_cause_explanation = llm_text
    except Exception as e:
        logger.warn("Ollama call failed or offline, using rule-based diagnostic engine", error=str(e))

    # Step 4: Safety Eval Gate
    eval_passed = confidence_score >= 0.85 and risk_level != "CRITICAL_BLOCKED"

    # Step 5: Cryptographic Audit Trail
    audit_payload = {
        "service": service,
        "severity": severity,
        "title": title,
        "runbook_id": runbook_id,
        "risk_level": risk_level,
        "confidence_score": confidence_score,
        "eval_passed": eval_passed,
    }
    audit_hash = await append_audit_entry(incident_id, "INCIDENT_RESOLVED", audit_payload)

    # Step 6: Persist in Database
    async with pool.acquire() as conn:
        # Get next incident number
        count = await conn.fetchval("SELECT count(*) FROM incidents")
        inc_num = (count or 0) + 101

        await conn.execute(
            """
            INSERT INTO incidents (
                id, incident_number, service, severity, title, description, status,
                root_cause, remediation_patch, confidence_score, risk_level, eval_passed,
                audit_hash, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            """,
            incident_id,
            inc_num,
            service,
            severity,
            title,
            description,
            "RESOLVED" if eval_passed else "ESCALATED",
            root_cause_explanation,
            remediation_template,
            confidence_score,
            risk_level,
            eval_passed,
            audit_hash,
            now_str,
            now_str,
        )

        # Log sub-agent actions
        await conn.execute(
            """
            INSERT INTO agent_actions (id, incident_id, agent_role, action_type, summary, payload, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            f"act_{uuid.uuid4().hex[:8]}",
            incident_id,
            "TriageAgent",
            "ALERT_INGESTED",
            f"Triaged {severity} incident on {service}",
            json.dumps({"service": service, "severity": severity}),
            now_str,
        )

        await conn.execute(
            """
            INSERT INTO agent_actions (id, incident_id, agent_role, action_type, summary, payload, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            f"act_{uuid.uuid4().hex[:8]}",
            incident_id,
            "DiagnosticsAgent",
            "METRICS_CORRELATED",
            f"Correlated time-series telemetry and {len(logs)} log events",
            json.dumps(metrics),
            now_str,
        )

        await conn.execute(
            """
            INSERT INTO agent_actions (id, incident_id, agent_role, action_type, summary, payload, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            f"act_{uuid.uuid4().hex[:8]}",
            incident_id,
            "RemediationAgent",
            "PATCH_SYNTHESIZED",
            f"Synthesized remediation patch via runbook {runbook_id}",
            json.dumps({"patch": remediation_template}),
            now_str,
        )

    return {
        "incident_id": incident_id,
        "incident_number": inc_num,
        "service": service,
        "severity": severity,
        "title": title,
        "status": "RESOLVED" if eval_passed else "ESCALATED",
        "root_cause": root_cause_explanation,
        "remediation_patch": remediation_template,
        "confidence_score": confidence_score,
        "risk_level": risk_level,
        "eval_passed": eval_passed,
        "audit_hash": audit_hash,
        "metrics": metrics,
        "logs": logs,
        "runbook": runbook,
    }
