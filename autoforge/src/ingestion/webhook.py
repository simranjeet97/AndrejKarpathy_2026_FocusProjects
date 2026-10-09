import hmac
import hashlib
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
import asyncpg
import structlog

from src.config import settings
from src.database import get_db_conn
from src.celery_app import celery_app

logger = structlog.get_logger()
router = APIRouter()


class IssueEvent(BaseModel):
    repo_full_name: str
    issue_number: int
    title: str
    body: Optional[str] = ""
    labels: List[str]
    author: str


def verify_signature(body: bytes, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    
    received_sig = signature_header.split("sha256=")[-1]
    secret = settings.github_webhook_secret.get_secret_value().encode("utf-8")
    
    expected_sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, received_sig)


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    response: Response,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: asyncpg.Connection = Depends(get_db_conn),
):
    # 1. Read raw body bytes
    body_bytes = await request.body()

    # 2. Verify X-Hub-Signature-256 header
    if not x_hub_signature_256 or not verify_signature(body_bytes, x_hub_signature_256):
        logger.warning("webhook_signature_verification_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    # 3. Parse X-GitHub-Event header
    if x_github_event != "issues":
        logger.info("webhook_event_skipped", event=x_github_event)
        return {"skipped": True}

    # 4. Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    action = payload.get("action")
    issue = payload.get("issue", {})
    labels = [label.get("name", "") for label in issue.get("labels", [])]

    # Only process opened issues, or issues labeled "autoforge"
    is_opened = action == "opened"
    is_labeled_autoforge = action == "labeled" and any(l == "autoforge" for l in labels)

    if not (is_opened or is_labeled_autoforge):
        logger.info("webhook_issue_action_skipped", action=action, labels=labels)
        return {"skipped": True}

    # Parse payload into IssueEvent
    repo_info = payload.get("repository", {})
    repo_full_name = repo_info.get("full_name", "")
    issue_number = issue.get("number")
    title = issue.get("title", "")
    body = issue.get("body", "")
    author = issue.get("user", {}).get("login", "")

    if not repo_full_name or issue_number is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing repository or issue number in payload"
        )

    event_data = IssueEvent(
        repo_full_name=repo_full_name,
        issue_number=issue_number,
        title=title,
        body=body,
        labels=labels,
        author=author
    )

    # 5. Create a task row in Postgres with status="pending"
    task_id = uuid.uuid4()
    query = """
        INSERT INTO tasks (id, issue_number, repo_full_name, title, body, status, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
    """
    await db.execute(
        query,
        task_id,
        event_data.issue_number,
        event_data.repo_full_name,
        event_data.title,
        event_data.body,
        "pending"
    )

    # 6. Enqueue process_issue.delay(task_id) to Celery
    # We use signature / send_task to invoke process_issue without static circular import issues
    celery_app.send_task("src.agent.tasks.process_issue", args=[str(task_id)])

    # 7. Log event
    logger.info(
        "webhook_issue_enqueued",
        event=x_github_event,
        repo=event_data.repo_full_name,
        issue_number=event_data.issue_number,
        task_id=str(task_id),
    )

    response.status_code = status.HTTP_202_ACCEPTED
    return {"task_id": str(task_id), "queued": True}
