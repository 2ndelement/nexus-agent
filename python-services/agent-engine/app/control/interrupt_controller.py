"""
app/control/interrupt_controller.py — Agent 中断控制器

功能：
- 管理 Agent 执行中断
- 支持停止、暂停、恢复
- 消息注入

原理：
- 使用 asyncio.Event 作为信号量
- Agent 节点执行时检查中断标志
- 抛出 NodeInterrupt 异常暂停执行
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class InterruptSignal:
    """中断信号"""
    conversation_id: str
    action: str  # "stop" | "pause" | "inject"
    data: Optional[dict] = None  # 注入消息等数据


class InterruptController:
    """
    Agent 中断控制器
    
    使用内存 + Redis 存储中断信号
    """

    def __init__(self):
        self._pending_signals: dict[str, asyncio.Event] = {}
        self._signal_data: dict[str, InterruptSignal] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock = Lock()
        self._redis_client = None

    async def initialize(self):
        """初始化 Redis"""
        try:
            import redis.asyncio as redis
            self._redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True,
            )
            logger.info("[InterruptController] Redis 连接成功")
        except Exception as e:
            logger.warning(f"[InterruptController] Redis 连接失败: {e}")

    def _get_lock(self, conversation_id: str) -> asyncio.Lock:
        """获取对话锁"""
        with self._lock:
            if conversation_id not in self._locks:
                self._locks[conversation_id] = asyncio.Lock()
            return self._locks[conversation_id]

    def _get_event(self, conversation_id: str) -> asyncio.Event:
        """获取或创建中断事件"""
        with self._lock:
            if conversation_id not in self._pending_signals:
                self._pending_signals[conversation_id] = asyncio.Event()
            return self._pending_signals[conversation_id]

    async def send_signal(self, signal: InterruptSignal):
        """
        发送中断信号
        
        Args:
            signal: 中断信号
        """
        lock = self._get_lock(signal.conversation_id)
        async with lock:
            # 存储信号数据
            self._signal_data[signal.conversation_id] = signal
            
            # 设置事件
            event = self._get_event(signal.conversation_id)
            event.set()
            
            # 持久化到 Redis
            if self._redis_client:
                try:
                    key = f"interrupt:{signal.conversation_id}"
                    import json
                    await self._redis_client.set(
                        key,
                        json.dumps({
                            "action": signal.action,
                            "data": signal.data,
                        }),
                        ex=3600  # 1小时过期
                    )
                except Exception as e:
                    logger.error(f"[InterruptController] Redis 写入失败: {e}")
            
            logger.info(
                f"[InterruptController] 发送信号: conv={signal.conversation_id}, "
                f"action={signal.action}"
            )

    async def wait_for_signal(
        self,
        conversation_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[InterruptSignal]:
        """
        等待中断信号
        
        Args:
            conversation_id: 对话ID
            timeout: 超时时间（秒）
        
        Returns:
            中断信号或 None（超时）
        """
        event = self._get_event(conversation_id)
        
        try:
            # 等待信号
            triggered = event.wait(timeout=timeout)
            
            if not triggered:
                return None
            
            # 获取信号并清除
            async with self._get_lock(conversation_id):
                signal = self._signal_data.pop(conversation_id, None)
                event.clear()
                
                # 从 Redis 删除
                if self._redis_client:
                    try:
                        await self._redis_client.delete(f"interrupt:{conversation_id}")
                    except Exception:
                        pass
                
                return signal
                
        except asyncio.TimeoutError:
            return None

    async def check_interrupted(self, conversation_id: str) -> bool:
        """
        检查是否被中断（非阻塞）
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            是否被中断
        """
        if self._redis_client:
            try:
                key = f"interrupt:{conversation_id}"
                exists = await self._redis_client.exists(key)
                return bool(exists)
            except Exception:
                pass
        
        return conversation_id in self._signal_data

    def clear_signal(self, conversation_id: str):
        """清除信号"""
        with self._lock:
            if conversation_id in self._pending_signals:
                self._pending_signals[conversation_id].clear()
            self._signal_data.pop(conversation_id, None)


class AgentRunner:
    """
    Agent 运行器 - 封装带中断支持的 Agent 执行
    
    用法：
    ```python
    runner = AgentRunner(agent_controller)
    
    # 启动 Agent
    task = asyncio.create_task(runner.run_stream(...))
    
    # 停止
    await runner.stop(conversation_id)
    
    # 注入消息
    await runner.inject_message(conversation_id, "新的消息")
    
    # 恢复
    await runner.resume(conversation_id)
    ```
    """

    def __init__(self, interrupt_controller: InterruptController):
        self._interrupt_controller = interrupt_controller
        self._running_tasks: dict[str, asyncio.Task] = {}

    async def run_stream(
        self,
        conversation_id: str,
        graph: Any,
        tenant_id: str,
        user_id: str,
        message: str,
        callback: Callable[[str], Awaitable[None]],
    ):
        """
        运行 Agent（流式）
        
        Args:
            conversation_id: 对话ID
            graph: LangGraph
            tenant_id: 租户ID
            user_id: 用户ID
            message: 消息
            callback: Token 回调
        """
        from app.agent.graph import astream_agent
        
        self._running_tasks[conversation_id] = asyncio.current_task()
        
        try:
            async for token in astream_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
            ):
                # 检查中断
                if await self._interrupt_controller.check_interrupted(conversation_id):
                    signal = await self._interrupt_controller.wait_for_signal(conversation_id, timeout=0.1)
                    if signal:
                        if signal.action == "stop":
                            logger.info(f"[AgentRunner] 收到停止信号: {conversation_id}")
                            break
                        elif signal.action == "inject":
                            # 注入消息 - 需要特殊处理
                            logger.info(f"[AgentRunner] 收到注入信号: {conversation_id}")
                            break
                
                # 发送 token
                await callback(token)
            
            # 清理任务
            self._running_tasks.pop(conversation_id, None)
            
        except Exception as e:
            logger.error(f"[AgentRunner] Agent 执行异常: {e}")
            self._running_tasks.pop(conversation_id, None)
            raise

    async def stop(self, conversation_id: str):
        """停止 Agent"""
        signal = InterruptSignal(
            conversation_id=conversation_id,
            action="stop",
        )
        await self._interrupt_controller.send_signal(signal)

    async def inject_message(self, conversation_id: str, message: str):
        """注入消息"""
        signal = InterruptSignal(
            conversation_id=conversation_id,
            action="inject",
            data={"message": message},
        )
        await self._interrupt_controller.send_signal(signal)

    async def pause(self, conversation_id: str):
        """暂停 Agent"""
        signal = InterruptSignal(
            conversation_id=conversation_id,
            action="pause",
        )
        await self._interrupt_controller.send_signal(signal)

    async def resume(self, conversation_id: str):
        """恢复 Agent"""
        self._interrupt_controller.clear_signal(conversation_id)


# 全局单例
_interrupt_controller: Optional[InterruptController] = None


async def get_interrupt_controller() -> InterruptController:
    """获取中断控制器单例"""
    global _interrupt_controller
    if _interrupt_controller is None:
        _interrupt_controller = InterruptController()
        await _interrupt_controller.initialize()
    return _interrupt_controller
