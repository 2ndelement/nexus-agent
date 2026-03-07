"""
builtin_tools/knowledge_search.py — 知识库检索工具

允许 Agent 查询绑定的知识库获取相关信息
"""
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# RAG Service URL
RAG_SERVICE_URL = "http://127.0.0.1:8003"


async def knowledge_search(
    query: str,
    knowledge_base_id: str,
    tenant_id: str,
    top_k: int = 5,
) -> dict:
    """
    从知识库中检索相关信息

    Args:
        query: 检索查询文本
        knowledge_base_id: 知识库ID
        tenant_id: 租户ID
        top_k: 返回结果数量

    Returns:
        检索结果列表
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RAG_SERVICE_URL}/api/v1/knowledge/retrieve",
                headers={
                    "Content-Type": "application/json",
                    "X-Tenant-Id": tenant_id,
                },
                json={
                    "query": query,
                    "knowledge_base_id": knowledge_base_id,
                    "top_k": top_k,
                },
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                # 格式化输出
                if not results:
                    return {
                        "success": True,
                        "message": "未找到相关信息",
                        "results": [],
                    }

                formatted_results = []
                for r in results:
                    formatted_results.append({
                        "content": r.get("content", ""),
                        "score": r.get("score", 0),
                        "doc_id": r.get("doc_id", ""),
                        "metadata": r.get("metadata", {}),
                    })

                return {
                    "success": True,
                    "message": f"找到 {len(results)} 条相关信息",
                    "results": formatted_results,
                }
            else:
                return {
                    "success": False,
                    "message": f"检索失败: HTTP {response.status_code}",
                    "results": [],
                }

    except Exception as e:
        logger.error(f"Knowledge search error: {e}")
        return {
            "success": False,
            "message": f"检索异常: {str(e)}",
            "results": [],
        }


# 工具定义 (供 tool-registry 注册使用)
TOOL_DEFINITION = {
    "name": "knowledge_search",
    "description": "从知识库中检索相关信息。当用户询问需要查阅知识库的问题时使用此工具。",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索查询文本，描述要搜索的内容",
            },
            "knowledge_base_id": {
                "type": "string",
                "description": "知识库ID，从 Agent 配置中获取",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认5条",
                "default": 5,
            },
        },
        "required": ["query", "knowledge_base_id"],
    },
    "scope": "BUILTIN",
    "category": "knowledge",
}


def get_tool_definition():
    """返回工具定义"""
    return TOOL_DEFINITION


async def execute(
    query: str,
    knowledge_base_id: str,
    tenant_id: str = "default",
    top_k: int = 5,
    **kwargs
) -> dict:
    """工具执行入口"""
    return await knowledge_search(
        query=query,
        knowledge_base_id=knowledge_base_id,
        tenant_id=tenant_id,
        top_k=top_k,
    )
