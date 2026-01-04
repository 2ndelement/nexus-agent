"""
app/api/v1/stats.py — Token 统计查询接口

GET /v1/stats       返回全局 Token 统计
DELETE /v1/stats    重置统计（仅测试/开发环境使用）
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.core.token_stats import token_stats
from app.schemas import ModelStats, StatsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Token 统计查询",
)
async def get_stats() -> StatsResponse:
    """返回按 model 聚合的 Token 用量统计。"""
    snap = token_stats.snapshot()
    by_model = {
        model: ModelStats(**data)
        for model, data in snap["by_model"].items()
    }
    return StatsResponse(
        total_requests=snap["total_requests"],
        total_tokens=snap["total_tokens"],
        by_model=by_model,
    )


@router.delete(
    "/stats",
    summary="重置统计（仅开发/测试）",
)
async def reset_stats() -> dict:
    """重置全局 Token 统计计数器。"""
    token_stats.reset()
    logger.warning("Token 统计已被手动重置")
    return {"message": "stats reset"}
