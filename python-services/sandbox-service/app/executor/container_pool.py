"""
app/executor/container_pool.py — 容器池管理器

设计思路：
- 预热：启动时创建 pool_size 个待命容器
- 获取：从池中取出一个容器执行任务
- 归还：执行完毕后销毁容器，异步补充新容器
- 隔离：每个容器独立，不复用，保证文件系统隔离
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

import aiodocker

logger = logging.getLogger(__name__)


class ContainerPool:
    """
    Docker 容器池管理器。

    特点：
    - 预热：启动时创建 N 个待命容器（已拉取镜像，减少冷启动时间）
    - 获取：从池中获取容器，如果池空则创建新容器
    - 归还：容器使用后销毁，异步补充新容器到池中
    - 隔离：每个执行使用独立容器，不复用容器内状态
    """

    def __init__(
        self,
        pool_size: int = 4,
        image: str = "nexus-sandbox:full",
        network_mode: str = "none",
        working_dir: str = "/workspace",
    ):
        """
        初始化容器池。

        Args:
            pool_size: 池大小（预热容器数量）
            image: Docker 镜像名称
            network_mode: 网络模式（默认 none 隔离网络）
            working_dir: 容器工作目录
        """
        self.pool_size = pool_size
        self.image = image
        self.network_mode = network_mode
        self.working_dir = working_dir

        self._pool: asyncio.Queue[Any] = asyncio.Queue(maxsize=pool_size * 2)
        self._docker: Optional[aiodocker.Docker] = None
        self._warming = False
        self._closed = False
        self._replenish_task: Optional[asyncio.Task] = None

    async def _get_docker(self) -> aiodocker.Docker:
        """获取 Docker 客户端"""
        if self._docker is None:
            self._docker = aiodocker.Docker()
        return self._docker

    async def warmup(self) -> int:
        """
        预热容器池：创建 pool_size 个待命容器。

        Returns:
            成功创建的容器数量
        """
        if self._warming:
            logger.warning("容器池正在预热中，跳过重复调用")
            return 0

        self._warming = True
        created = 0

        logger.info(f"[ContainerPool] 开始预热，目标数量: {self.pool_size}")

        try:
            docker = await self._get_docker()

            # 确保镜像存在
            try:
                await docker.images.inspect(self.image)
                logger.info(f"[ContainerPool] 镜像已存在: {self.image}")
            except aiodocker.exceptions.DockerError:
                logger.warning(f"[ContainerPool] 镜像不存在: {self.image}，尝试拉取")
                try:
                    await docker.images.pull(self.image)
                    logger.info(f"[ContainerPool] 镜像拉取成功: {self.image}")
                except Exception as e:
                    logger.error(f"[ContainerPool] 镜像拉取失败: {e}")
                    return 0

            # 创建容器
            tasks = [self._create_container() for _ in range(self.pool_size)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"[ContainerPool] 创建容器失败: {result}")
                elif result is not None:
                    await self._pool.put(result)
                    created += 1

            logger.info(f"[ContainerPool] 预热完成，创建了 {created} 个容器")

        except Exception as e:
            logger.exception(f"[ContainerPool] 预热异常: {e}")
        finally:
            self._warming = False

        return created

    async def _create_container(self) -> Any:
        """
        创建一个待命容器。

        容器创建后处于停止状态，等待被获取后启动执行。
        """
        docker = await self._get_docker()
        container_name = f"sandbox-pool-{uuid.uuid4().hex[:8]}"

        config = {
            "Image": self.image,
            # 创建时不执行任何命令，等待获取后注入
            "Cmd": ["sleep", "infinity"],
            "HostConfig": {
                "NetworkMode": self.network_mode,
            },
            "WorkingDir": self.working_dir,
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "OpenStdin": False,
        }

        try:
            container = await docker.containers.create(config, name=container_name)
            # 启动容器（进入 sleep infinity 状态）
            await container.start()
            logger.debug(f"[ContainerPool] 创建容器: {container_name}")
            return container
        except Exception as e:
            logger.warning(f"[ContainerPool] 创建容器失败: {e}")
            raise

    async def acquire(self, timeout: float = 30.0) -> Any:
        """
        从池中获取一个容器。

        如果池为空，等待直到有可用容器或创建新容器。

        Args:
            timeout: 等待超时秒数

        Returns:
            Container 对象

        Raises:
            asyncio.TimeoutError: 超时
        """
        if self._closed:
            raise RuntimeError("容器池已关闭")

        try:
            # 尝试从池中获取
            container = await asyncio.wait_for(
                self._pool.get(),
                timeout=min(timeout, 5.0)  # 最多等待 5 秒
            )
            logger.debug(f"[ContainerPool] 从池中获取容器: {container.id[:12]}")

            # 触发异步补充
            self._schedule_replenish()

            return container

        except asyncio.TimeoutError:
            # 池为空，直接创建新容器
            logger.info("[ContainerPool] 池为空，创建新容器")
            return await self._create_container()

    async def release(self, container: Any, force_delete: bool = True):
        """
        归还容器（实际是销毁，保证隔离性）。

        Args:
            container: 要归还的容器
            force_delete: 是否强制删除（默认 True）
        """
        if container is None:
            return

        try:
            # 停止并删除容器
            try:
                await container.kill()
            except Exception:
                pass  # 容器可能已停止

            await container.delete(force=True)
            logger.debug(f"[ContainerPool] 销毁容器: {container.id[:12]}")

        except Exception as e:
            logger.warning(f"[ContainerPool] 销毁容器失败: {e}")

    def _schedule_replenish(self):
        """调度异步补充任务"""
        if self._replenish_task is None or self._replenish_task.done():
            self._replenish_task = asyncio.create_task(self._replenish())

    async def _replenish(self):
        """补充容器到池中"""
        if self._closed:
            return

        current_size = self._pool.qsize()
        need = self.pool_size - current_size

        if need <= 0:
            return

        logger.debug(f"[ContainerPool] 补充容器: 当前 {current_size}, 需要 {need}")

        for _ in range(need):
            try:
                container = await self._create_container()
                if container and not self._pool.full():
                    await self._pool.put(container)
            except Exception as e:
                logger.warning(f"[ContainerPool] 补充容器失败: {e}")

    async def close(self):
        """关闭容器池，清理所有容器"""
        self._closed = True

        # 取消补充任务
        if self._replenish_task and not self._replenish_task.done():
            self._replenish_task.cancel()

        # 清理池中所有容器
        cleaned = 0
        while not self._pool.empty():
            try:
                container = self._pool.get_nowait()
                await self.release(container)
                cleaned += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.warning(f"[ContainerPool] 清理容器失败: {e}")

        # 关闭 Docker 客户端
        if self._docker:
            await self._docker.close()
            self._docker = None

        logger.info(f"[ContainerPool] 已关闭，清理了 {cleaned} 个容器")

    @property
    def size(self) -> int:
        """当前池中可用容器数量"""
        return self._pool.qsize()

    @property
    def is_warming(self) -> bool:
        """是否正在预热"""
        return self._warming


# 全局单例
_container_pool: Optional[ContainerPool] = None


def get_container_pool() -> ContainerPool:
    """获取容器池单例"""
    global _container_pool
    if _container_pool is None:
        from app.config import settings
        _container_pool = ContainerPool(
            pool_size=settings.container_pool_size,
            image=settings.docker_image,
        )
    return _container_pool


async def init_container_pool() -> int:
    """初始化并预热容器池"""
    pool = get_container_pool()
    return await pool.warmup()


async def close_container_pool():
    """关闭容器池"""
    global _container_pool
    if _container_pool:
        await _container_pool.close()
        _container_pool = None
