"""
app/api/v1/models.py — 模型列表 API

使用静态模型列表，后续可扩展为数据库管理
"""
from __future__ import annotations

import logging
from typing import Dict, List

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════════
# 静态模型列表（管理员可编辑，后续可迁移到数据库）
# ═══════════════════════════════════════════════════════════════════════════════════

# 模型配置 - 确保 id 与 Copilot Hub 的 model id 完全一致
AVAILABLE_MODELS: List[Dict] = [
    # 轻量快速
    {
        "id": "gpt-5-mini",
        "name": "GPT-5 mini",
        "vendor": "OpenAI",
        "category": "lightweight",
        "description": "快速响应，性价比高",
        "supportsVision": True,
        "supportsTools": True,
    },
    {
        "id": "MiniMax-M2.7-highspeed",
        "name": "MiniMax M2.7",
        "vendor": "MiniMax",
        "category": "lightweight",
        "description": "极速响应",
        "supportsVision": False,
        "supportsTools": False,
    },
    # 国产模型
    {
        "id": "qwen3.5-plus",
        "name": "通义千问 3.5 Plus",
        "vendor": "阿里云",
        "category": "chinese",
        "description": "1M 上下文，深度思考",
        "supportsVision": False,
        "supportsTools": True,
        "supportsThinking": True,
    },
    {
        "id": "kimi-k2.5",
        "name": "Kimi K2.5",
        "vendor": "月之暗面",
        "category": "chinese",
        "description": "262K 上下文",
        "supportsVision": False,
        "supportsTools": True,
    },
    {
        "id": "glm-5",
        "name": "GLM-5",
        "vendor": "智谱AI",
        "category": "chinese",
        "description": "深度思考模型",
        "supportsVision": False,
        "supportsTools": True,
        "supportsThinking": True,
    },
]

# 分类元数据
CATEGORY_META = {
    "lightweight": {"name": "轻量快速", "description": "低延迟场景", "order": 1},
    "chinese": {"name": "国产模型", "description": "中文优化", "order": 2},
}


# ═══════════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════════

def _group_by_category(models: List[Dict]) -> List[Dict]:
    """按分类分组"""
    groups: Dict[str, List[Dict]] = {}

    for model in models:
        cat = model.get("category", "other")
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(model)

    # 按 order 排序
    result = []
    for cat_id in sorted(groups.keys(), key=lambda c: CATEGORY_META.get(c, {}).get("order", 99)):
        meta = CATEGORY_META.get(cat_id, {"name": cat_id, "description": ""})
        result.append({
            "id": cat_id,
            "name": meta["name"],
            "description": meta["description"],
            "models": groups[cat_id],
        })

    return result


# ═══════════════════════════════════════════════════════════════════════════════════
# API 路由
# ═══════════════════════════════════════════════════════════════════════════════════

@router.get("/models")
async def list_models(grouped: bool = True):
    """
    获取可用模型列表

    Args:
        grouped: 是否按分类分组，默认 True

    Returns:
        - grouped=True: { categories: [...] }
        - grouped=False: { models: [...] }
    """
    models = AVAILABLE_MODELS.copy()

    if grouped:
        return {
            "code": 200,
            "msg": "success",
            "data": {
                "categories": _group_by_category(models),
                "total": len(models),
            },
        }
    else:
        return {
            "code": 200,
            "msg": "success",
            "data": {
                "models": models,
                "total": len(models),
            },
        }


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """获取单个模型信息"""
    for m in AVAILABLE_MODELS:
        if m["id"] == model_id:
            return {"code": 200, "msg": "success", "data": m}

    return {"code": 404, "msg": f"模型 {model_id} 不存在", "data": None}
