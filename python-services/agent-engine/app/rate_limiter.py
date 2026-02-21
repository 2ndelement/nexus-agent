"""
rate_limiter.py — 租户级QPS限流器

基于令牌桶算法，每个租户独立的限流器
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TenantRateLimiter:
    """租户限流器配置"""
    tenant_id: str
    qps: int  # 每秒请求数
    burst: int  # 突发容量
    tokens: float
    last_update: float
    
    def __init__(self, tenant_id: str, qps: int = 50, burst: int = 100):
        self.tenant_id = tenant_id
        self.qps = qps
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.time()


class TenantRateLimiterManager:
    """
    租户级限流管理器
    
    令牌桶算法：
    - 每个租户独立限流
    - 动态调整QPS
    - 限流时返回429
    """
    
    # 默认QPS（可配置）
    DEFAULT_QPS = 50
    DEFAULT_BURST = 100
    
    def __init__(self):
        self._limiters: dict[str, TenantRateLimiter] = {}
        self._lock = Lock()
    
    def get_limiter(self, tenant_id: str, qps: int = None) -> TenantRateLimiter:
        """获取租户限流器，不存在则创建"""
        with self._lock:
            if tenant_id not in self._limiters:
                self._limiters[tenant_id] = TenantRateLimiter(
                    tenant_id=tenant_id,
                    qps=qps or self.DEFAULT_QPS,
                    burst=qps or self.DEFAULT_BURST,
                )
            return self._limitors[tenant_id]
    
    def check(self, tenant_id: str) -> bool:
        """
        检查是否允许请求
        
        Returns:
            True 允许，False 限流
        """
        limiter = self.get_limiter(tenant_id)
        
        now = time.time()
        elapsed = now - limiter.last_update
        
        # 补充令牌
        limiter.tokens = min(
            limiter.burst,
            limiter.tokens + elapsed * limiter.qps
        )
        limiter.last_update = now
        
        if limiter.tokens >= 1:
            limiter.tokens -= 1
            return True
        return False
    
    def set_qps(self, tenant_id: str, qps: int):
        """动态调整租户QPS"""
        limiter = self.get_limiter(tenant_id)
        limiter.qps = qps
    
    def get_remaining(self, tenant_id: str) -> float:
        """获取剩余令牌数"""
        limiter = self._limiters.get(tenant_id)
        if not limiter:
            return self.DEFAULT_QPS
        return limiter.tokens
    
    def reset(self, tenant_id: str):
        """重置租户限流器"""
        with self._lock:
            self._limiters.pop(tenant_id, None)


# 全局单例
_rate_limiter: Optional[TenantRateLimiterManager] = None


def get_rate_limiter() -> TenantRateLimiterManager:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = TenantRateLimiterManager()
    return _rate_limiter
