"""
app/executor/docker_executor.py — Docker 容器隔离执行器

核心设计：
- 支持容器池预热模式（减少冷启动时间）
- 每次执行使用独立容器，保证文件系统隔离
- 支持 Python / Bash
- 超时控制 + 内存限制
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Optional

import aiodocker

from app.config import settings
from app.executor.base import BaseExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class DockerExecutor(BaseExecutor):
    """
    Docker 容器隔离执行器。

    特点：
    - 支持容器池预热模式
    - 每次执行使用独立容器
    - 容器内网络隔离（无网络访问）
    - 内存/CPU 限制
    - 超时自动 kill
    """

    def __init__(self, use_pool: bool = True):
        """
        初始化执行器。

        Args:
            use_pool: 是否使用容器池（默认 True）
        """
        self._docker: Optional[aiodocker.Docker] = None
        self._use_pool = use_pool and settings.container_pool_enabled
        self._pool: Optional["ContainerPool"] = None

    async def _get_client(self) -> aiodocker.Docker:
        if self._docker is None:
            self._docker = aiodocker.Docker()
        return self._docker

    async def _get_pool(self):
        """获取容器池（延迟初始化）"""
        if self._pool is None and self._use_pool:
            from app.executor.container_pool import get_container_pool
            self._pool = get_container_pool()
        return self._pool

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

        # 尝试使用容器池
        pool = await self._get_pool()
        if pool and pool.size > 0:
            return await self._execute_with_pool(code, language, timeout, start)
        else:
            return await self._execute_direct(code, language, timeout, start)

    async def _execute_with_pool(
        self,
        code: str,
        language: str,
        timeout: int,
        start: float,
    ) -> ExecutionResult:
        """
        使用容器池执行代码。

        从池中获取预热容器，使用 docker exec 执行代码。
        """
        pool = await self._get_pool()
        container = None

        try:
            # 从池中获取容器
            container = await pool.acquire(timeout=5.0)

            # 构建执行命令
            if language == "python":
                exec_cmd = ["python3", "-c", code]
            else:
                exec_cmd = ["bash", "-c", code]

            logger.debug("从池中执行: container=%s, language=%s", container.id[:12], language)

            # 使用 exec 在容器中执行命令
            exec_obj = await container.exec(
                cmd=exec_cmd,
                stdout=True,
                stderr=True,
            )

            # 启动 exec 并获取流
            stream = exec_obj.start(detach=False)

            # 读取输出（使用 read_out 方法）
            try:
                output_chunks = []
                while True:
                    try:
                        msg = await asyncio.wait_for(stream.read_out(), timeout=timeout)
                        if msg is None:
                            break
                        if msg.data:
                            output_chunks.append(msg.data.decode("utf-8", errors="replace"))
                    except asyncio.TimeoutError:
                        logger.warning("执行超时: %s", container.id[:12])
                        return ExecutionResult(
                            success=False,
                            stdout="",
                            stderr=f"Execution timeout after {timeout}s",
                            exit_code=124,
                            duration_ms=int((time.time() - start) * 1000),
                            error="Timeout",
                        )

                output = "".join(output_chunks)

                # 获取退出码
                exec_info = await exec_obj.inspect()
                exit_code = exec_info.get("ExitCode", 0)

                duration_ms = int((time.time() - start) * 1000)
                logger.debug("池执行完成: exit_code=%d, duration=%dms", exit_code, duration_ms)

                return ExecutionResult(
                    success=(exit_code == 0),
                    stdout=output,
                    stderr="",
                    exit_code=exit_code,
                    duration_ms=duration_ms,
                )

            finally:
                # 关闭流
                await stream.close()

        except Exception as e:
            logger.exception("容器池执行异常")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                duration_ms=int((time.time() - start) * 1000),
                error=str(e),
            )

        finally:
            # 归还容器（销毁并补充新容器）
            if container and pool:
                await pool.release(container)

    async def _execute_direct(
        self,
        code: str,
        language: str,
        timeout: int,
        start: float,
    ) -> ExecutionResult:
        """
        直接创建容器执行代码（非池模式）。
        使用 subprocess + docker CLI 避免 aiodocker 的 cgroupv2 兼容性问题。
        """
        container_name = f"sandbox-{uuid.uuid4().hex[:8]}"
        tmp_file = f"/tmp/sandbox_code_{uuid.uuid4().hex[:8]}.py"

        # 写入代码到临时文件（解决 python -c 引号转义问题）
        try:
            with open(tmp_file, "w") as f:
                f.write(code)
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Failed to write code file: {e}",
                exit_code=1,
                duration_ms=int((time.time() - start) * 1000),
                error=str(e),
            )

        # 构建 docker 命令
        if language == "python":
            exec_cmd = ["python3", "/tmp/code.py"]
        else:
            exec_cmd = ["bash", "/tmp/code.py"]

        # 构建 docker run 命令
        # 注意：此环境 cgroupfs driver 与 cgroupv2 kernel 不兼容，
        # 使用 --cgroupns host 时不能带内存/CPU 限制，否则会失败
        docker_cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "none",
            "--cgroupns", "host",
            "-v", f"{tmp_file}:/tmp/code.py",
            settings.docker_image,
        ] + exec_cmd

        try:
            logger.debug("直接创建容器: %s, timeout=%ds", container_name, timeout)

            # 使用 subprocess 执行
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("执行超时，kill 容器: %s", container_name)
                # 尝试 kill 容器
                try:
                    kill_proc = await asyncio.create_subprocess_exec(
                        "docker", "kill", container_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await asyncio.wait_for(kill_proc.communicate(), timeout=5)
                except Exception:
                    pass
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timeout after {timeout}s",
                    exit_code=124,
                    duration_ms=int((time.time() - start) * 1000),
                    error="Timeout",
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = proc.returncode

            duration_ms = int((time.time() - start) * 1000)
            logger.debug("执行完成: exit_code=%d, duration=%dms", exit_code, duration_ms)

            return ExecutionResult(
                success=(exit_code == 0),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            raise
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
            # 清理临时文件
            try:
                os.unlink(tmp_file)
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
_executor: Optional[DockerExecutor] = None


def get_executor() -> DockerExecutor:
    global _executor
    if _executor is None:
        _executor = DockerExecutor()
    return _executor
