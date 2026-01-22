"""
app/core/token_stats.py — Token 统计存储

实现：
- Redis 持久化存储（重启不丢失）
- 降级模式：Redis 不可用时回退到内存存储
- 线程安全（asyncio.Lock）
- 提供按 model 聚合的统计数据
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Redis 客户端（延迟初始化）
_redis_client = None
_redis_available: bool = False
_redis_attempted: bool = False

REDIS_PREFIX = "nexus:llm_proxy:token_stats"


async def _get_redis():
    """延迟初始化 Redis 连接。"""
    global _redis_client, _redis_available, _redis_attempted
    if _redis_attempted:
        return _redis_client if _redis_available else None
    _redis_attempted = True

    try:
        import redis.asyncio as aioredis
        from app.config import settings

        _redis_client = aioredis.Redis(
            host=getattr(settings, "redis_host", "127.0.0.1"),
            port=getattr(settings, "redis_port", 6379),
            decode_responses=True,
        )
        # 测试连接
        await _redis_client.ping()
        _redis_available = True
        logger.info("TokenStats: Redis 连接成功，使用持久化模式")
        return _redis_client
    except Exception as exc:
        logger.warning("TokenStats: Redis 连接失败，降级为内存模式: %s", exc)
        _redis_available = False
        return None


@dataclass
class ModelCounter:
    """单个 model 的计数器。"""
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenStats:
    """
    Token 统计存储（Redis 持久化 + 内存降级）。

    Redis 存储结构：
    - Hash: nexus:llm_proxy:token_stats:{model}
      - requests: int
      - prompt_tokens: int
      - completion_tokens: int
      - total_tokens: int
    - String: nexus:llm_proxy:token_stats:__total_requests
    - String: nexus:llm_proxy:token_stats:__total_tokens
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # 内存降级用
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

        redis = await _get_redis()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                model_key = f"{REDIS_PREFIX}:{model}"
                pipe.hincrby(model_key, "requests", 1)
                pipe.hincrby(model_key, "prompt_tokens", prompt_tokens)
                pipe.hincrby(model_key, "completion_tokens", completion_tokens)
                pipe.hincrby(model_key, "total_tokens", total)
                pipe.incr(f"{REDIS_PREFIX}:__total_requests")
                pipe.incrby(f"{REDIS_PREFIX}:__total_tokens", total)
                await pipe.execute()

                logger.debug(
                    "token_stats.record (Redis): model=%s prompt=%d completion=%d total=%d",
                    model, prompt_tokens, completion_tokens, total,
                )
                return
            except Exception as exc:
                logger.warning("TokenStats Redis 写入失败，降级内存: %s", exc)

        # 内存降级
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
            "token_stats.record (memory): model=%s prompt=%d completion=%d total=%d",
            model, prompt_tokens, completion_tokens, total,
        )

    async def snapshot(self) -> dict:
        """
        返回当前统计快照。

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
          },
          "storage": "redis" | "memory"
        }
        """
        redis = await _get_redis()
        if redis is not None:
            try:
                # 扫描所有 model keys
                by_model = {}
                async for key in redis.scan_iter(f"{REDIS_PREFIX}:*"):
                    key_str = key if isinstance(key, str) else key.decode()
                    if key_str.startswith(f"{REDIS_PREFIX}:__"):
                        continue
                    model_name = key_str.replace(f"{REDIS_PREFIX}:", "")
                    data = await redis.hgetall(key_str)
                    by_model[model_name] = {
                        "requests": int(data.get("requests", 0)),
                        "prompt_tokens": int(data.get("prompt_tokens", 0)),
                        "completion_tokens": int(data.get("completion_tokens", 0)),
                        "total_tokens": int(data.get("total_tokens", 0)),
                    }

                total_req = await redis.get(f"{REDIS_PREFIX}:__total_requests")
                total_tok = await redis.get(f"{REDIS_PREFIX}:__total_tokens")

                return {
                    "total_requests": int(total_req or 0),
                    "total_tokens": int(total_tok or 0),
                    "by_model": by_model,
                    "storage": "redis",
                }
            except Exception as exc:
                logger.warning("TokenStats Redis 读取失败: %s", exc)

        # 内存降级
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
            "storage": "memory",
        }

    def reset(self) -> None:
        """重置所有统计（用于测试）。"""
        self._counters.clear()
        self._total_requests = 0
        self._total_tokens = 0


# 单例
token_stats = TokenStats()
