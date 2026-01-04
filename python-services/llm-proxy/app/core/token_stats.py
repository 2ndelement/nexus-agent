"""
app/core/token_stats.py — Token 统计存储

实现：
- 内存存储（进程内，重启清零）
- 线程安全（asyncio.Lock）
- 提供按 model 聚合的统计数据
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelCounter:
    """单个 model 的计数器。"""
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenStats:
    """
    Token 统计存储（内存实现）。

    线程安全：所有写操作通过 asyncio.Lock 保护。
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._counters: dict[str, ModelCounter] = {}
        self._total_requests: int = 0
        self._total_tokens: int = 0

    async def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """记录一次调用的 token 用量。"""
        total = prompt_tokens + completion_tokens

        async with self._lock:
            if model not in self._counters:
                self._counters[model] = ModelCounter()

            counter = self._counters[model]
            counter.requests += 1
            counter.prompt_tokens += prompt_tokens
            counter.completion_tokens += completion_tokens
            counter.total_tokens += total

            self._total_requests += 1
            self._total_tokens += total

        logger.debug(
            "token_stats.record: model=%s prompt=%d completion=%d total=%d",
            model, prompt_tokens, completion_tokens, total,
        )

    def snapshot(self) -> dict:
        """
        返回当前统计快照（同步，仅读，无需锁）。

        返回格式与 StatsResponse schema 对齐：
        {
          "total_requests": int,
          "total_tokens": int,
          "by_model": {
            "<model>": {
              "requests": int,
              "prompt_tokens": int,
              "completion_tokens": int,
              "total_tokens": int,
            }
          }
        }
        """
        by_model = {
            model: {
                "requests": c.requests,
                "prompt_tokens": c.prompt_tokens,
                "completion_tokens": c.completion_tokens,
                "total_tokens": c.total_tokens,
            }
            for model, c in self._counters.items()
        }
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "by_model": by_model,
        }

    def reset(self) -> None:
        """重置所有统计（用于测试）。"""
        self._counters.clear()
        self._total_requests = 0
        self._total_tokens = 0


# 单例
token_stats = TokenStats()
