"""
app/agent/graph.py — LangGraph 图定义

图结构：
  START → call_llm → [条件路由] → tool_call → call_llm → ... → END
  
  当 LLM 返回 tool_calls 时循环执行工具，否则结束。
  最大工具调用轮次由 settings.max_tool_iterations 控制。

设计原则：
- 禁止全局共享 compiled Graph 实例
- 每次 invoke/stream 使用独立的 config（含 thread_id）
- thread_id 格式严格为 f"{tenant_id}:{conversation_id}"
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import call_llm_node, tool_call_node, should_continue
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# ─────────────────────────── 图构建 ───────────────────────────


def build_graph(checkpointer=None) -> Any:
    """
    构建并编译 LangGraph 图。

    图结构:
        START → call_llm → [should_continue] 
                                ├── "tool_call" → tool_call_node → call_llm (循环)
                                └── "end" → END

    Args:
        checkpointer: 可选的 checkpointer 实例（AIOMySQLSaver 或测试 Mock）。
                      None 时图无状态持久化（测试场景）。

    Returns:
        编译后的 CompiledGraph。
    """
    builder = StateGraph(AgentState)

    # 节点
    builder.add_node("call_llm", call_llm_node)
    builder.add_node("tool_call", tool_call_node)

    # 边
    builder.add_edge(START, "call_llm")
    
    # 条件路由：LLM 输出后判断是否有 tool_calls
    builder.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "tool_call": "tool_call",   # 有工具调用 → 执行工具
            "end": END,                  # 无工具调用 → 结束
        },
    )
    
    # 工具执行后回到 LLM（形成循环）
    builder.add_edge("tool_call", "call_llm")

    return builder.compile(checkpointer=checkpointer)


def make_config(tenant_id: str, conversation_id: str) -> dict:
    """
    生成符合多租户隔离要求的 LangGraph config。

    多租户隔离核心：thread_id = f"{tenant_id}:{conversation_id}"
    租户 A 和租户 B 即使使用相同 conversation_id，其 thread_id 也不同，
    checkpoint 完全隔离。
    """
    thread_id = f"{tenant_id}:{conversation_id}"
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }


async def astream_agent(
    graph: Any,
    tenant_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
) -> AsyncIterator[str]:
    """
    以流式方式运行 Agent，逐 token yield AI 回复内容。

    支持 Tool Calling 循环：
    - LLM 返回 tool_calls → 执行工具 → 结果回传 LLM → 继续生成
    - 只 yield 最终回复的 content token

    Args:
        graph: 已编译的 LangGraph CompiledGraph。
        tenant_id: 租户 ID（来自 Header，非用户自填）。
        user_id: 用户 ID。
        conversation_id: 会话 ID。
        message: 用户输入消息。

    Yields:
        str: 每个 AI 回复 token（内容片段）。
    """
    config = make_config(tenant_id, conversation_id)

    input_state: dict = {
        "messages": [HumanMessage(content=message)],
        "tenant_id": tenant_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }

    logger.info(
        "astream_agent start: thread_id=%s:%s, user=%s",
        tenant_id,
        conversation_id,
        user_id,
    )

    # 使用 astream_events 捕获流式 token
    async for event in graph.astream_events(input_state, config, version="v2"):
        kind = event.get("event")
        # on_chat_model_stream: LLM 流式输出 token
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                yield chunk.content
