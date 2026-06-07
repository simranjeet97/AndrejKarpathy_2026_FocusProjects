import asyncio
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Header
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

async def run_agent_review_task(repo_full_name: str, pr_number: int) -> None:
    """
    Background task to invoke the review agent.
    """
    try:
        from .dependencies import get_agent, get_github_client

        github_client = get_github_client()
        pr_event = await asyncio.to_thread(github_client.get_pr, repo_full_name, pr_number)

        agent = get_agent()
        await agent.run(pr_event)
    except Exception as e:
        logger.error(f"Error running agent review for {repo_full_name} PR #{pr_number}: {e}", exc_info=True)

@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None)
) -> dict:
    """
    GitHub Webhook receiver endpoint.
    Validates payload signature and triggers review agent as background task.
    """
    body = await request.body()
    
    settings = get_settings()
    secret = settings.GITHUB_WEBHOOK_SECRET
    
    # Signature Verification
    if secret:
        if not x_hub_signature_256:
            raise HTTPException(status_code=403, detail="X-Hub-Signature-256 header missing")
            
        hash_type, signature = x_hub_signature_256.split("=", 1) if "=" in x_hub_signature_256 else (None, None)
        if hash_type != "sha256" or not signature:
            raise HTTPException(status_code=403, detail="Invalid signature format")
            
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(status_code=403, detail="Signature verification failed")

    # Parse Payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from e
        
    action = payload.get("action")
    # Only trigger reviews for opened, synchronize, or reopened pull requests
    if action not in ["opened", "synchronize", "reopened"]:
        return {"status": "ignored", "reason": f"Action '{action}' is not a PR review trigger"}
        
    pull_request = payload.get("pull_request")
    repository = payload.get("repository")
    
    if not pull_request or not repository:
        raise HTTPException(status_code=400, detail="Missing pull_request or repository in payload")
        
    pr_number = pull_request.get("number")
    repo_full_name = repository.get("full_name")
    
    if not pr_number or not repo_full_name:
        raise HTTPException(status_code=400, detail="Missing PR number or repository full name")
        
    # Enqueue review agent run as a background task
    background_tasks.add_task(run_agent_review_task, repo_full_name, pr_number)
    
    return {"status": "enqueued", "repo": repo_full_name, "pr": pr_number}
