"""
app/executor/session_manager.py — 会话容器管理器

V5 新架构：
- 会话绑定容器：同一会话复用同一容器
- 工作区隔离：不同用户/组织的文件系统完全隔离
- 智能回收：空闲会话自动回收容器
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import aiodocker

from app.config import settings

logger = logging.getLogger(__name__)


# 工作区根目录
WORKSPACE_ROOT = os.getenv("SANDBOX_WORKSPACE_ROOT", "/data/sandbox")


@dataclass
class SessionInfo:
    """会话信息"""
    session_key: str          # owner_type:owner_id:conversation_id
    container: Any            # Docker container object
    workspace_path: str       # 宿主机工作区路径
    created_at: float         # 创建时间
    last_access: float        # 最后访问时间
    execution_count: int = 0  # 执行次数


class SessionContainerManager:
    """
    会话容器管理器。

    特点：
    - 会话绑定：同一 conversation_id 复用同一容器
    - 工作区隔离：每个会话有独立的工作区目录
    - 预热池：新会话从预热池获取容器，减少冷启动
    - 自动回收：空闲会话自动回收，释放资源
    """

    def __init__(
        self,
        pool_size: int = 4,
        idle_timeout: int = 1800,  # 30 分钟
        max_sessions: int = 50,    # 最大活跃会话数
    ):
        self.pool_size = pool_size
        self.idle_timeout = idle_timeout
        self.max_sessions = max_sessions

        self._docker: Optional[aiodocker.Docker] = None
        self._warm_pool: asyncio.Queue[Any] = asyncio.Queue(maxsize=pool_size * 2)
        self._active_sessions: Dict[str, SessionInfo] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._closed = False

    async def _get_docker(self) -> aiodocker.Docker:
        """获取 Docker 客户端"""
        if self._docker is None:
            self._docker = aiodocker.Docker()
        return self._docker

    def _build_session_key(self, owner_type: str, owner_id: str, conversation_id: str) -> str:
        """构建会话键"""
        return f"{owner_type}:{owner_id}:{conversation_id}"

    def _build_workspace_path(self, owner_type: str, owner_id: str, conversation_id: str) -> str:
        """
        构建工作区路径。

        格式：/data/sandbox/{owner_type}/{owner_id}/{conversation_id}/
        示例：/data/sandbox/PERSONAL/17/conv_abc123/

        注意：不使用冒号分隔，因为 Docker Binds 格式使用冒号 (source:target:mode)
        """
        return os.path.join(WORKSPACE_ROOT, owner_type, owner_id, conversation_id)

    async def warmup(self) -> int:
        """预热容器池"""
        logger.info(f"[SessionManager] 开始预热，目标数量: {self.pool_size}")
        created = 0

        try:
            docker = await self._get_docker()

            # 确保镜像存在
            try:
                await docker.images.inspect(settings.docker_image)
            except aiodocker.exceptions.DockerError:
                logger.warning(f"镜像不存在: {settings.docker_image}，尝试拉取")
                await docker.images.pull(settings.docker_image)

            # 创建预热容器
            tasks = [self._create_warm_container() for _ in range(self.pool_size)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"创建预热容器失败: {result}")
                elif result is not None:
                    await self._warm_pool.put(result)
                    created += 1

            logger.info(f"[SessionManager] 预热完成，创建了 {created} 个容器")

            # 启动清理任务
            self._start_cleanup_task()

        except Exception as e:
            logger.exception(f"预热异常: {e}")

        return created

    async def _create_warm_container(self) -> Any:
        """创建预热容器（无挂载卷，待分配）"""
        import subprocess
        container_name = f"sandbox-warm-{uuid.uuid4().hex[:8]}"

        # 使用 docker 命令创建并启动容器
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--network", "none",
            "--cgroupns", "host",
            settings.docker_image,
            "sleep", "infinity"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to create container: {stderr.decode()}")

        # 获取容器 ID
        container_id = stdout.decode().strip()[:12]

        # 返回一个简单的包装对象
        class ContainerWrapper:
            def __init__(self, id, name):
                self.id = id
                self.name = name
            def __str__(self):
                return self.name

        return ContainerWrapper(container_id, container_name)

    async def get_or_create_session(
        self,
        owner_type: str,
        owner_id: str,
        conversation_id: str,
    ) -> SessionInfo:
        """
        获取或创建会话容器。

        如果会话已存在，返回现有容器；
        否则从预热池获取容器并绑定到会话。
        """
        session_key = self._build_session_key(owner_type, owner_id, conversation_id)

        async with self._lock:
            # 1. 检查是否已有活跃会话
            if session_key in self._active_sessions:
                session = self._active_sessions[session_key]
                session.last_access = time.time()
                logger.debug(f"复用现有会话: {session_key}")
                return session

            # 2. 检查会话数量限制
            if len(self._active_sessions) >= self.max_sessions:
                # 清理最旧的会话
                await self._evict_oldest_session()

            # 3. 创建工作区目录
            workspace_path = self._build_workspace_path(owner_type, owner_id, conversation_id)
            os.makedirs(workspace_path, exist_ok=True)
            logger.info(f"创建工作区: {workspace_path}")

            # 4. 获取或创建容器
            container = await self._acquire_container(workspace_path)

            # 5. 注册会话
            session = SessionInfo(
                session_key=session_key,
                container=container,
                workspace_path=workspace_path,
                created_at=time.time(),
                last_access=time.time(),
            )
            self._active_sessions[session_key] = session

            logger.info(f"创建新会话: {session_key}, 容器: {container.id[:12]}")
            return session

    async def _acquire_container(self, workspace_path: str) -> Any:
        """
        获取容器并挂载工作区。

        由于 Docker 不支持动态挂载卷，我们需要创建新容器。
        使用 subprocess + docker CLI 避免 aiodocker 的 cgroupv2 兼容性问题。
        """
        container_name = f"sandbox-session-{uuid.uuid4().hex[:8]}"

        # 构建 docker run 命令
        # 注意：此环境 cgroupfs driver 与 cgroupv2 kernel 不兼容，
        # 使用 --cgroupns host 时不能带内存/CPU 限制，否则会失败
        docker_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--network", "none",
            "--cgroupns", "host",
            "-v", f"{workspace_path}:{settings.work_dir}",
            "-w", settings.work_dir,
            settings.docker_image,
            "sleep", "infinity",
        ]

        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to create container: {stderr.decode()}")

        container_id = stdout.decode().strip()[:12]

        # 返回一个简单的包装对象
        class ContainerWrapper:
            def __init__(self, id, name):
                self.id = id
                self.name = name
            def __str__(self):
                return self.name
            async def show(self):
                """获取容器状态"""
                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", "--format", "{{.State.Running}}", self.name,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                running = stdout.decode().strip() == "true"
                return {"State": {"Running": running}}
            async def exec(self, cmd, stdout=False, stderr=False, workdir=None):
                """在容器中执行命令"""
                docker_exec_cmd = ["docker", "exec"]
                if workdir:
                    docker_exec_cmd.extend(["-w", workdir])
                docker_exec_cmd.append(self.name)
                docker_exec_cmd.extend(cmd)
                return await asyncio.create_subprocess_exec(
                    *docker_exec_cmd,
                    stdout=asyncio.subprocess.PIPE if stdout else asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE if stderr else asyncio.subprocess.DEVNULL
                )
            async def kill(self):
                proc = await asyncio.create_subprocess_exec(
                    "docker", "kill", self.name,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
            async def delete(self, force=False):
                proc = await asyncio.create_subprocess_exec(
                    "docker", "rm", "-f" if force else "rm", self.name,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

        logger.debug(f"创建会话容器: {container_name}, 工作区: {workspace_path}")
        return ContainerWrapper(container_id, container_name)

    async def execute_in_session(
        self,
        session: SessionInfo,
        code: str,
        language: str,
        timeout: int,
    ) -> Dict[str, Any]:
        """
        在会话容器中执行代码。
        """
        start = time.time()
        session.execution_count += 1
        session.last_access = time.time()

        container = session.container

        # 执行前检查容器状态
        try:
            info = await container.show()
            if info.get("State", {}).get("Running") != True:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Container not running: {info.get('State', {})}",
                    "exit_code": -1,
                    "duration_ms": int((time.time() - start) * 1000),
                    "error": "Container state error",
                }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to check container status: {e}",
                "exit_code": -1,
                "duration_ms": int((time.time() - start) * 1000),
                "error": str(e),
            }

        # 生成临时文件名
        import uuid as uuid_lib
        code_filename = f"code_{uuid_lib.uuid4().hex[:8]}.py"
        code_path = os.path.join(session.workspace_path, code_filename)

        # 记录执行前的文件列表（用于对比找出新生成的文件）
        files_before = set(os.listdir(session.workspace_path)) if os.path.exists(session.workspace_path) else set()

        # 写入代码文件到工作区（解决 python -c 引号转义问题）
        try:
            with open(code_path, "w") as f:
                f.write(code)
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to write code file: {e}",
                "exit_code": 1,
                "duration_ms": int((time.time() - start) * 1000),
                "error": str(e),
            }

        # 构建执行命令
        if language == "python":
            exec_cmd = ["python3", f"/workspace/{code_filename}"]
        else:
            exec_cmd = ["bash", f"/workspace/{code_filename}"]

        try:
            # 使用 docker exec 在容器中执行
            docker_exec_cmd = [
                "docker", "exec",
                "-w", settings.work_dir,
                container.name,
            ] + exec_cmd

            proc = await asyncio.create_subprocess_exec(
                *docker_exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # 超时，kill 进程
                try:
                    kill_proc = await asyncio.create_subprocess_exec(
                        "docker", "kill", container.name,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await asyncio.wait_for(kill_proc.communicate(), timeout=5)
                except Exception:
                    pass
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Execution timeout after {timeout}s",
                    "exit_code": 124,
                    "duration_ms": int((time.time() - start) * 1000),
                    "error": "Timeout",
                }

            output = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = proc.returncode

            # 获取工作区文件列表，对比执行前后找出新生成的文件
            files_after = set(os.listdir(session.workspace_path)) if os.path.exists(session.workspace_path) else set()
            new_files = files_after - files_before
            all_files = self._list_workspace_files(session.workspace_path)
            workspace_files = [f for f in all_files if f["name"] in new_files]

            return {
                "success": exit_code == 0,
                "stdout": output,
                "stderr": stderr,
                "exit_code": exit_code,
                "duration_ms": int((time.time() - start) * 1000),
                "workspace_files": workspace_files,
                "session_id": session.session_key,
            }

        except Exception as e:
            logger.exception(f"执行异常: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
                "duration_ms": int((time.time() - start) * 1000),
                "error": str(e),
            }

    def _list_workspace_files(self, workspace_path: str, max_files: int = 100) -> list:
        """列出工作区文件，返回文件信息列表"""
        files = []
        try:
            path = Path(workspace_path)
            if path.exists():
                for item in list(path.iterdir())[:max_files]:
                    if item.is_file():
                        files.append({
                            "name": item.name,
                            "size": item.stat().st_size,
                            "mime_type": self._guess_mime_type(item.name),
                        })
        except Exception as e:
            logger.warning(f"列出工作区文件失败: {e}")
        return files

    def _guess_mime_type(self, filename: str) -> str:
        """根据扩展名猜测 MIME 类型"""
        import mimetypes
        mime, _ = mimetypes.guess_type(filename)
        return mime or "application/octet-stream"

    async def _evict_oldest_session(self):
        """驱逐最旧的会话"""
        if not self._active_sessions:
            return

        # 找到最旧的会话
        oldest_key = min(
            self._active_sessions.keys(),
            key=lambda k: self._active_sessions[k].last_access
        )

        session = self._active_sessions.pop(oldest_key)
        await self._cleanup_session(session)
        logger.info(f"驱逐最旧会话: {oldest_key}")

    async def _cleanup_session(self, session: SessionInfo):
        """清理会话容器"""
        try:
            container = session.container
            try:
                await container.kill()
            except Exception:
                pass
            await container.delete(force=True)
            logger.debug(f"清理会话容器: {session.session_key}")
        except Exception as e:
            logger.warning(f"清理会话失败: {e}")

    def _start_cleanup_task(self):
        """启动定期清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """定期清理空闲会话"""
        while not self._closed:
            await asyncio.sleep(60)  # 每分钟检查一次

            now = time.time()
            expired_keys = []

            for key, session in self._active_sessions.items():
                if now - session.last_access > self.idle_timeout:
                    expired_keys.append(key)

            for key in expired_keys:
                session = self._active_sessions.pop(key, None)
                if session:
                    await self._cleanup_session(session)
                    logger.info(f"回收空闲会话: {key}")

    async def close(self):
        """关闭管理器"""
        self._closed = True

        if self._cleanup_task:
            self._cleanup_task.cancel()

        # 清理所有活跃会话
        for session in list(self._active_sessions.values()):
            await self._cleanup_session(session)
        self._active_sessions.clear()

        # 清理预热池
        while not self._warm_pool.empty():
            try:
                container = self._warm_pool.get_nowait()
                try:
                    await container.kill()
                except Exception:
                    pass
                await container.delete(force=True)
            except Exception:
                pass

        if self._docker:
            await self._docker.close()

        logger.info("[SessionManager] 已关闭")

    def _parse_memory(self, mem_str: str) -> int:
        """解析内存字符串"""
        mem_str = mem_str.lower().strip()
        if mem_str.endswith("g"):
            return int(float(mem_str[:-1]) * 1024 * 1024 * 1024)
        elif mem_str.endswith("m"):
            return int(float(mem_str[:-1]) * 1024 * 1024)
        elif mem_str.endswith("k"):
            return int(float(mem_str[:-1]) * 1024)
        return int(mem_str)

    @property
    def active_session_count(self) -> int:
        """活跃会话数量"""
        return len(self._active_sessions)

    @property
    def warm_pool_size(self) -> int:
        """预热池大小"""
        return self._warm_pool.qsize()

    def get_session_info(self, owner_type: str, owner_id: str, conversation_id: str) -> Optional[SessionInfo]:
        """获取会话信息"""
        key = self._build_session_key(owner_type, owner_id, conversation_id)
        return self._active_sessions.get(key)


# 全局单例
_session_manager: Optional[SessionContainerManager] = None


def get_session_manager() -> SessionContainerManager:
    """获取会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionContainerManager(
            pool_size=settings.container_pool_size,
        )
    return _session_manager


async def init_session_manager() -> int:
    """初始化会话管理器"""
    manager = get_session_manager()
    return await manager.warmup()


async def close_session_manager():
    """关闭会话管理器"""
    global _session_manager
    if _session_manager:
        await _session_manager.close()
        _session_manager = None
