import io
import tarfile
import asyncio
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
        # Connect to Docker daemon using DOCKER_HOST from settings/env if available
        # docker.from_env() automatically picks up DOCKER_HOST env var
        self.client = docker.from_env()

    def create_sandbox(self, task_id: str) -> str:
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
        loop = asyncio.get_running_loop()
        container = self.client.containers.get(container_id)

        def _exec():
            # exec_run executes command and returns (exit_code, output_bytes)
            # Demux is set to True to split stdout and stderr
            return container.exec_run(cmd=command, demux=True, workdir=cwd)

        try:
            # Wrap the blocking Docker SDK call in a thread executor with a timeout
            exit_code, output = await asyncio.wait_for(
                loop.run_in_executor(None, _exec),
                timeout=float(timeout_seconds)
            )
            
            stdout_bytes, stderr_bytes = output
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            
            logger.info(
                "sandbox_exec",
                container_id=container_id,
                command=command,
                exit_code=exit_code,
                cwd=cwd,
                timed_out=False
            )
            return ExecResult(exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=False)
        except asyncio.TimeoutError:
            logger.warning(
                "sandbox_exec_timeout",
                container_id=container_id,
                command=command,
                cwd=cwd,
                timed_out=True
            )
            return ExecResult(exit_code=-1, stdout="", stderr="Execution timed out", timed_out=True)
        except Exception as e:
            logger.error(
                "sandbox_exec_failed",
                container_id=container_id,
                command=command,
                cwd=cwd,
                error=str(e)
            )
            raise e


    def write_file(self, container_id: str, path: str, content: str) -> None:
        container = self.client.containers.get(container_id)
        
        # Create an in-memory tar archive containing the file
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            content_bytes = content.encode("utf-8")
            tarinfo = tarfile.TarInfo(name=path)
            tarinfo.size = len(content_bytes)
            tar.addfile(tarinfo, io.BytesIO(content_bytes))
            
        tar_stream.seek(0)
        
        # Put the archive into the container's root directory
        container.put_archive("/", tar_stream.read())
        logger.info("sandbox_write_file", container_id=container_id, path=path)

    def read_file(self, container_id: str, path: str) -> str:
        container = self.client.containers.get(container_id)
        try:
            # get_archive returns a tuple of (stream, stat)
            stream, stat = container.get_archive(path)
            tar_stream = io.BytesIO()
            for chunk in stream:
                tar_stream.write(chunk)
            tar_stream.seek(0)
            
            with tarfile.open(fileobj=tar_stream, mode="r") as tar:
                # Extract the first member (which is the file itself)
                member = tar.next()
                if member:
                    file_content = tar.extractfile(member)
                    if file_content:
                        content = file_content.read().decode("utf-8", errors="replace")
                        logger.info("sandbox_read_file", container_id=container_id, path=path)
                        return content
            raise FileNotFoundError(f"File not found in archive: {path}")
        except Exception as e:
            logger.error("sandbox_read_file_failed", container_id=container_id, path=path, error=str(e))
            raise e

    def list_files(self, container_id: str, directory: str = "/workspace") -> List[str]:
        container = self.client.containers.get(container_id)
        # Use find to locate all files recursively under the directory
        exit_code, output = container.exec_run(cmd=["find", directory, "-type", "f"])
        if exit_code != 0:
            logger.warning("sandbox_list_files_warning", container_id=container_id, exit_code=exit_code)
            return []
        
        stdout = output.decode("utf-8", errors="replace")
        files = [line.strip() for line in stdout.splitlines() if line.strip()]
        logger.info("sandbox_list_files", container_id=container_id, directory=directory, file_count=len(files))
        return files

    def destroy_sandbox(self, container_id: str, capture_logs: bool = True) -> str:
        container = self.client.containers.get(container_id)
        logs = ""
        try:
            if capture_logs:
                logs = container.logs().decode("utf-8", errors="replace")
            
            # Stop the container
            container.stop(timeout=2)
            # Remove the container
            container.remove(v=True, force=True)
            logger.info("sandbox_destroyed", container_id=container_id)
            return logs
        except Exception as e:
            logger.error("sandbox_destroy_failed", container_id=container_id, error=str(e))
            raise e
