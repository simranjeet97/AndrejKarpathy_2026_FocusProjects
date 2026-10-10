import io
import os
import shutil
import tarfile
import asyncio
import subprocess
from typing import List, Dict, Optional
from dataclasses import dataclass
import docker
import structlog

from src.config import settings

logger = structlog.get_logger()


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


class SandboxManager:
    def __init__(self) -> None:
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception:
            self.client = None
            logger.info("Docker daemon unavailable. Using local workspace sandbox runner.")

    def create_sandbox(self, task_id: str) -> str:
        if self.client is None:
            workspace_dir = os.path.abspath(f"data/workspaces/{task_id}")
            os.makedirs(f"{workspace_dir}/workspace/repo", exist_ok=True)
            logger.info("local_sandbox_created", task_id=task_id, path=workspace_dir)
            return workspace_dir

        try:
            container = self.client.containers.run(
                image=settings.sandbox_image,
                name=f"autoforge-{task_id}",
                network_mode="none",
                mem_limit=f"{settings.max_sandbox_memory_mb}m",
                nano_cpus=int(settings.max_sandbox_cpu * 1e9),
                read_only=False,
                auto_remove=False,
                working_dir="/workspace",
                labels={"autoforge.task_id": str(task_id)},
                detach=True,
                command="/bin/sh"
            )
            logger.info("sandbox_created", task_id=task_id, container_id=container.id)
            return container.id
        except Exception as e:
            logger.error("sandbox_creation_failed", task_id=task_id, error=str(e))
            raise e

    async def exec_in_sandbox(
        self, container_id: str, command: List[str], timeout_seconds: int = 30, cwd: Optional[str] = None
    ) -> ExecResult:
        if self.client is None:
            # Local workspace execution
            work_dir = container_id
            if cwd:
                if os.path.isabs(cwd):
                    # Map /workspace to container_id/workspace
                    rel = os.path.relpath(cwd, "/workspace") if cwd.startswith("/workspace") else cwd.lstrip("/")
                    work_dir = os.path.join(container_id, "workspace", rel) if cwd.startswith("/workspace") else os.path.join(container_id, rel)
                else:
                    work_dir = os.path.join(container_id, cwd)
            os.makedirs(work_dir, exist_ok=True)

            try:
                proc = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=work_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                try:
                    stdout_b, stderr_b = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=float(timeout_seconds)
                    )
                    stdout = stdout_b.decode("utf-8", errors="replace")
                    stderr = stderr_b.decode("utf-8", errors="replace")
                    exit_code = proc.returncode if proc.returncode is not None else 0
                    return ExecResult(exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=False)
                except asyncio.TimeoutError:
                    proc.kill()
                    return ExecResult(exit_code=-1, stdout="", stderr="Execution timed out", timed_out=True)
            except Exception as e:
                return ExecResult(exit_code=-1, stdout="", stderr=str(e), timed_out=False)

        loop = asyncio.get_running_loop()
        container = self.client.containers.get(container_id)

        def _exec():
            return container.exec_run(cmd=command, demux=True, workdir=cwd)

        try:
            exit_code, output = await asyncio.wait_for(
                loop.run_in_executor(None, _exec),
                timeout=float(timeout_seconds)
            )
            stdout_bytes, stderr_bytes = output
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            return ExecResult(exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=False)
        except asyncio.TimeoutError:
            return ExecResult(exit_code=-1, stdout="", stderr="Execution timed out", timed_out=True)
        except Exception as e:
            logger.error("sandbox_exec_failed", container_id=container_id, command=command, error=str(e))
            raise e

    def write_file(self, container_id: str, path: str, content: str) -> None:
        if self.client is None:
            rel = os.path.relpath(path, "/workspace") if path.startswith("/workspace") else path.lstrip("/")
            target = os.path.join(container_id, "workspace", rel) if path.startswith("/workspace") else os.path.join(container_id, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return

        container = self.client.containers.get(container_id)
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            content_bytes = content.encode("utf-8")
            tarinfo = tarfile.TarInfo(name=path)
            tarinfo.size = len(content_bytes)
            tar.addfile(tarinfo, io.BytesIO(content_bytes))
        tar_stream.seek(0)
        container.put_archive("/", tar_stream.read())

    def read_file(self, container_id: str, path: str) -> str:
        if self.client is None:
            rel = os.path.relpath(path, "/workspace") if path.startswith("/workspace") else path.lstrip("/")
            target = os.path.join(container_id, "workspace", rel) if path.startswith("/workspace") else os.path.join(container_id, rel)
            with open(target, "r", encoding="utf-8") as f:
                return f.read()

        container = self.client.containers.get(container_id)
        stream, stat = container.get_archive(path)
        tar_stream = io.BytesIO()
        for chunk in stream:
            tar_stream.write(chunk)
        tar_stream.seek(0)
        with tarfile.open(fileobj=tar_stream, mode="r") as tar:
            member = tar.next()
            if member:
                file_content = tar.extractfile(member)
                if file_content:
                    return file_content.read().decode("utf-8", errors="replace")
        raise FileNotFoundError(f"File not found in archive: {path}")

    def list_files(self, container_id: str, directory: str = "/workspace") -> List[str]:
        if self.client is None:
            rel = os.path.relpath(directory, "/workspace") if directory.startswith("/workspace") else directory.lstrip("/")
            target = os.path.join(container_id, "workspace", rel) if directory.startswith("/workspace") else os.path.join(container_id, rel)
            files = []
            if os.path.exists(target):
                for root, _, filenames in os.walk(target):
                    for fn in filenames:
                        files.append(os.path.join(root, fn))
            return files

        container = self.client.containers.get(container_id)
        exit_code, output = container.exec_run(cmd=["find", directory, "-type", "f"])
        if exit_code != 0:
            return []
        stdout = output.decode("utf-8", errors="replace")
        return [line.strip() for line in stdout.splitlines() if line.strip()]

    def destroy_sandbox(self, container_id: str, capture_logs: bool = True) -> str:
        if self.client is None:
            return "Local workspace sandbox destroyed."
        container = self.client.containers.get(container_id)
        logs = container.logs().decode("utf-8", errors="replace") if capture_logs else ""
        container.stop(timeout=2)
        container.remove(v=True, force=True)
        return logs
