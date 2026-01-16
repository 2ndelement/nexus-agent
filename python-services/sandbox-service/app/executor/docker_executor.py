"""
app/executor/docker_executor.py — Docker 容器隔离执行器

核心设计：
- 每次执行创建临时容器，运行完即销毁
- 支持 Python / Bash
- 超时控制 + 内存限制
- 容器池复用（减少创建开销）
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Any

import aiodocker

from app.config import settings
from app.executor.base import BaseExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class DockerExecutor(BaseExecutor):
    """
    Docker 容器隔离执行器。
    
    特点：
    - 每次执行创建临时容器
    - 容器内网络隔离（无网络访问）
    - 内存/CPU 限制
    - 超时自动 kill
    """
    
    def __init__(self):
        self._docker: aiodocker.Docker | None = None

    async def _get_client(self) -> aiodocker.Docker:
        if self._docker is None:
            self._docker = aiodocker.Docker()
        return self._docker

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
    ) -> ExecutionResult:
        """
        在 Docker 容器中执行代码。
        
        Args:
            code: 代码内容
            language: python | bash
            timeout: 超时秒数
            
        Returns:
            ExecutionResult
        """
        start = time.time()
        
        # 参数校验
        timeout = min(timeout, settings.max_timeout)
        if language not in ("python", "bash", "sh"):
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=1,
                duration_ms=int((time.time() - start) * 1000),
                error=f"Language {language} not supported",
            )

        docker = await self._get_client()
        
        # 构建命令
        if language == "python":
            # 写入文件再执行，避免 stdin 交互问题
            cmd = f"python3 -c '''{code.replace(\"'''\", \"'\\\"'\\\"\")}'''"
        else:
            cmd = f"bash -c '{code.replace(\"'\", \"'\\\\''\")}'"

        # 容器配置
        container_config = {
            "Image": settings.docker_image,
            "Cmd": ["sh", "-c", cmd],
            "HostConfig": {
                "Memory": self._parse_memory(settings.container_max_memory),
                "CpuPeriod": 100000,
                "CpuQuota": int(100000 * settings.container_cpu_limit),
                "NetworkMode": "none",  # 网络隔离
            },
            "WorkingDir": settings.work_dir,
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "OpenStdin": False,
        }

        try:
            # 创建并启动容器
            container = await docker.containers.create_or_replace(
                name=f"sandbox-{asyncio.get_event_loop().time()}",
                config=container_config,
            )
            
            logger.debug("容器启动: %s, timeout=%ds", container.id[:12], timeout)
            
            # 等待执行完成或超时
            try:
                await container.start()
                await asyncio.wait_for(
                    container.wait(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # 超时 kill 容器
                logger.warning("执行超时，kill 容器: %s", container.id[:12])
                await container.kill()
                await container.wait()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timeout after {timeout}s",
                    exit_code=124,
                    duration_ms=int((time.time() - start) * 1000),
                    error="Timeout",
                )

            # 获取输出
            logs = await container.logs(stdout=True, stderr=True)
            output = logs.decode("utf-8", errors="replace")
            
            # 分离 stdout/stderr（简单按行分割，末尾是 exit code）
            lines = output.split("\n")
            # Docker logs 可能混合输出，简化处理
            stdout = output
            stderr = ""

            # 获取退出码
            info = await container.inspect()
            exit_code = info["State"]["ExitCode"]

            duration_ms = int((time.time() - start) * 1000)
            
            logger.debug("执行完成: exit_code=%d, duration=%dms", exit_code, duration_ms)
            
            return ExecutionResult(
                success=(exit_code == 0),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.exception("容器执行异常")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                duration_ms=int((time.time() - start) * 1000),
                error=str(e),
            )
        
        finally:
            # 清理容器
            try:
                if container:
                    await container.delete(force=True)
            except Exception:
                pass

    async def health_check(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            docker = await self._get_client()
            await docker.ping()
            return True
        except Exception as e:
            logger.warning("Docker health check failed: %s", e)
            return False

    def _parse_memory(self, mem_str: str) -> int:
        """解析内存字符串，如 '256m' → 268435456"""
        mem_str = mem_str.lower().strip()
        if mem_str.endswith("g"):
            return int(float(mem_str[:-1]) * 1024 * 1024 * 1024)
        elif mem_str.endswith("m"):
            return int(float(mem_str[:-1]) * 1024 * 1024)
        elif mem_str.endswith("k"):
            return int(float(mem_str[:-1]) * 1024)
        else:
            return int(mem_str)


# 全局单例
_executor: DockerExecutor | None = None


def get_executor() -> DockerExecutor:
    global _executor
    if _executor is None:
        _executor = DockerExecutor()
    return _executor
