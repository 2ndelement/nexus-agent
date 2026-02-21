"""
middleware.py — 限流中间件

基于令牌桶算法的租户级限流
"""
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.rate_limiter import get_rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    租户级限流中间件
    
    读取 X-Tenant-Id 头进行限流
    """

    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-Id", "anonymous")
        
        # 检查限流
        limiter = get_rate_limiter()
        if not limiter.check(tenant_id):
            return JSONResponse(
                status_code=429,
                content={"error": "Too Many Requests"}
            )
        
        response = await call_next(request)
        return response


# 限流装饰器
def rate_limit(qps: int = 50):
    """限流装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 从 kwargs 或 request 获取租户ID
            tenant_id = kwargs.get("tenant_id", "anonymous")
            limiter = get_rate_limiter()
            
            if not limiter.check(tenant_id):
                return {"error": "Rate limit exceeded"}
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
