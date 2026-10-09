import time
import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import httpx
import jwt
import structlog
from github import Github
from github.Repository import Repository
import redis.asyncio as aioredis

from src.config import settings

logger = structlog.get_logger()


class GitHubAppClient:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.app_id = settings.github_app_id
        self.private_key_path = settings.github_app_private_key_path
        self.redis = redis_client
        self.private_key = self._load_private_key()

    def _load_private_key(self) -> str:
        with open(self.private_key_path, "r") as f:
            return f.read()

    def _generate_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60 seconds leeway in the past
            "exp": now + 540,  # 9 minutes in the future (within 10 min max)
            "iss": self.app_id,
        }
        return jwt.encode(self.private_key, payload, algorithm="RS256")

    async def _async_retry(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        attempts = 3
        delay = 1.0
        for attempt in range(1, attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "github_api_call_failed",
                    attempt=attempt,
                    error=str(e),
                    next_retry_in=delay if attempt < attempts else 0,
                )
                if attempt == attempts:
                    raise e
                await asyncio.sleep(delay)
                delay *= 2.0

    async def _make_api_call(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]] = None,
        repo: Optional[str] = None,
    ) -> httpx.Response:
        async def _call():
            async with httpx.AsyncClient() as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=json_data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                logger.info(
                    "github_api_call",
                    action=f"{method} {url}",
                    repo=repo,
                    status_code=response.status_code,
                )
                response.raise_for_status()
                return response

        return await self._async_retry(_call)

    async def get_installation_token(self, repo_full_name: str) -> str:
        owner = repo_full_name.split("/")[0]

        # 1. Fetch installations using App JWT
        app_jwt = self._generate_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        }
        
        installations_url = "https://api.github.com/app/installations"
        response = await self._make_api_call(
            "GET", installations_url, headers=headers, repo=repo_full_name
        )
        installations = response.json()

        installation_id = None
        for inst in installations:
            if inst.get("account", {}).get("login", "").lower() == owner.lower():
                installation_id = inst.get("id")
                break

        if not installation_id:
            raise ValueError(f"No installation found for owner: {owner}")

        # 2. Check cache (Redis) for token
        cache_key = f"gh_token:{installation_id}"
        cached_token = await self.redis.get(cache_key)
        if cached_token:
            return cached_token.decode("utf-8")

        # 3. Request a new installation access token
        token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        token_response = await self._make_api_call(
            "POST", token_url, headers=headers, repo=repo_full_name
        )
        token_data = token_response.json()
        token = token_data["token"]

        # Cache the token in Redis with a TTL of 3500 seconds
        await self.redis.setex(cache_key, 3500, token)

        return token

    async def get_installation_client(self, repo_full_name: str) -> Github:
        token = await self.get_installation_token(repo_full_name)
        return Github(token)

    async def get_repo(self, repo_full_name: str) -> Repository:
        # Wrap the repository retrieval in our async retry mechanism
        async def _retrieve_repo():
            client = await self.get_installation_client(repo_full_name)
            # PyGithub is synchronous, so we run the blocking get_repo in a thread executor
            loop = asyncio.get_running_loop()
            repo_obj = await loop.run_in_executor(None, client.get_repo, repo_full_name)
            logger.info(
                "github_api_call",
                action="get_repo",
                repo=repo_full_name,
                status_code=200,
            )
            return repo_obj

        return await self._async_retry(_retrieve_repo)
