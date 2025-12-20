"""
web_search 内置工具：通过 DuckDuckGo Instant Answer API 执行搜索。

在测试环境或 DuckDuckGo 不可用时，返回模拟结果。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx


DUCKDUCKGO_API = "https://api.duckduckgo.com/"
TIMEOUT_SECONDS = 8.0


async def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    使用 DuckDuckGo Instant Answer API 执行 web 搜索。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数，默认 5

    Returns:
        {
            "query": 搜索词,
            "results": [{"title": ..., "url": ..., "snippet": ...}, ...],
            "answer": 即时答案（可能为空）
        }
    """
    if not query or not query.strip():
        raise ValueError("搜索关键词不能为空")

    query = query.strip()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(
                DUCKDUCKGO_API,
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError):
        # 网络不可用时返回模拟结果
        return _mock_results(query, max_results)

    results: List[Dict[str, str]] = []

    # 优先提取 AbstractText（摘要）
    if data.get("AbstractText"):
        results.append({
            "title": data.get("Heading", query),
            "url": data.get("AbstractURL", ""),
            "snippet": data["AbstractText"][:500],
        })

    # 提取 RelatedTopics
    for topic in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        if isinstance(topic, dict) and topic.get("Text"):
            results.append({
                "title": topic.get("Text", "")[:100],
                "url": topic.get("FirstURL", ""),
                "snippet": topic.get("Text", "")[:300],
            })

    # 如果结果为空，返回模拟结果
    if not results:
        return _mock_results(query, max_results)

    return {
        "query": query,
        "results": results[:max_results],
        "answer": data.get("Answer", ""),
    }


def _mock_results(query: str, max_results: int) -> Dict[str, Any]:
    """
    当真实搜索不可用时，返回模拟搜索结果。
    用于测试环境和离线场景。
    """
    mock_results = [
        {
            "title": f"搜索结果 {i+1}：{query}",
            "url": f"https://example.com/result-{i+1}?q={query.replace(' ', '+')}",
            "snippet": (
                f"这是关于 '{query}' 的模拟搜索结果 {i+1}。"
                f"在实际部署中，此处将返回真实的 DuckDuckGo 搜索结果。"
            ),
        }
        for i in range(min(max_results, 3))
    ]
    return {
        "query": query,
        "results": mock_results,
        "answer": "",
        "note": "mock_results",  # 标识这是模拟结果
    }


# ── 工具元数据（OpenAI function calling schema）──────────────────────────────

TOOL_DEFINITION = {
    "name": "web_search",
    "description": (
        "使用 DuckDuckGo 搜索引擎查询网络信息，返回相关网页标题、URL 和摘要。"
        "适用于获取最新信息、查询事实、研究某个话题。"
        "例如：查询'Python 最新版本'、搜索'Spring Boot 教程'。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，例如 'Python 3.13 新特性' 或 'Spring Boot 3 教程'",
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数，默认 5，最大 10",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}
