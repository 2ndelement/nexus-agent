"""
RAG 知识库检索工具

从 rag-service 检索知识库内容，供 Agent 在对话中引用。
通过 Nacos 服务发现调用 rag-service。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from common.nacos import discover_service

logger = logging.getLogger(__name__)


async def knowledge_retrieve(
    tenant_id: str,
    knowledge_base_id: str,
    query: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    从知识库检索相关内容

    Args:
        tenant_id: 租户 ID
        knowledge_base_id: 知识库 ID
        query: 查询文本
        top_k: 返回结果数量

    Returns:
        {
            "success": True,
            "results": [
                {"content": "...", "score": 0.95, "source": "doc1.pdf"},
                ...
            ],
            "context": "格式化的上下文文本，可直接用于 LLM"
        }
    """
    # 通过 Nacos 发现 RAG 服务，降级使用配置的地址
    rag_url = discover_service("nexus-rag-service", fallback=settings.rag_service_url)
    if rag_url and rag_url.endswith(":8003"):
        fallback_url = settings.rag_service_url or "http://127.0.0.1:8013"
        logger.warning("RAG fallback 指向旧端口 8003，切换到配置地址: %s", fallback_url)
        rag_url = fallback_url
    if not rag_url:
        return {
            "success": False,
            "error": "RAG 服务不可用",
            "context": "知识库服务不可用",
        }

    url = f"{rag_url}/api/v1/knowledge/retrieve"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={
                    "X-Tenant-Id": tenant_id,
                    "Content-Type": "application/json",
                },
                json={
                    "knowledge_base_id": knowledge_base_id,
                    "query": query,
                    "top_k": top_k,
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])

                # 格式化为 LLM 可用的上下文
                if results:
                    context_parts = []
                    for i, r in enumerate(results):
                        source = r.get("source", f"文档{i+1}")
                        content = r.get("content", "")
                        score = r.get("score", 0)
                        context_parts.append(
                            f"[来源: {source}, 相关度: {score:.2f}]\n{content}"
                        )
                    context = "\n\n---\n\n".join(context_parts)
                else:
                    context = "未找到相关内容"

                return {
                    "success": True,
                    "results": results,
                    "context": context,
                }
            else:
                error_msg = f"检索失败: HTTP {resp.status_code}"
                logger.warning(f"RAG retrieve failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "context": "知识库检索失败",
                }

    except httpx.TimeoutException:
        logger.error("RAG retrieve timeout")
        return {
            "success": False,
            "error": "检索超时",
            "context": "知识库检索超时",
        }
    except Exception as e:
        logger.error(f"RAG retrieve error: {e}")
        return {
            "success": False,
            "error": str(e),
            "context": f"知识库检索错误: {e}",
        }


# 工具定义（用于 LLM function calling）
RAG_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "knowledge_retrieve",
        "description": "从知识库检索相关信息。当用户询问需要特定领域知识的问题时使用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询词，应该是用户问题的关键信息",
                },
                "knowledge_base_id": {
                    "type": "string",
                    "description": "知识库 ID。当前环境必须显式提供。",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                    "description": "返回结果数量",
                },
            },
            "required": ["query", "knowledge_base_id"],
        },
    },
}
