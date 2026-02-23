"""
app/agent/graph.py — LangGraph 图定义

图结构：
  START → call_llm → [条件路由] → tool_call → call_llm → ... → END

  当 LLM 返回 tool_calls 时循环执行工具，否则结束。
  最大工具调用轮次由 settings.max_tool_iterations 控制。

设计原则：
- 禁止全局共享 compiled Graph 实例
- 每次 invoke/stream 使用独立的 config（包含 thread_id）
- V5: thread_id 格式为 f"{owner_type}:{owner_id}:{conversation_id}"
- 兼容旧版: 如果只提供 tenant_id，使用 f"{tenant_id}:{conversation_id}"
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    call_llm_node,
    tool_call_node,
    should_continue,
)
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════ 工具结果判断 ═══════════════════════════════════════════════════════════════════


def _is_tool_error(result_str: str, tool_name: str) -> bool:
    """
    判断工具执行是否失败。

    Args:
        result_str: 工具执行结果字符串
        tool_name: 工具名称

    Returns:
        True 表示失败，False 表示成功
    """
    if not result_str:
        return False

    # sandbox_execute 工具返回 JSON，解析 success 字段
    # 注意：result_str 可能被截断，但 JSON 开头仍可识别
    if tool_name == "sandbox_execute":
        # 先尝试完整解析
        try:
            result = json.loads(result_str)
            if "success" in result:
                return result.get("success") is False
        except (json.JSONDecodeError, TypeError):
            pass

        # JSON 可能被截断，尝试从开头提取 success 字段
        # 匹配 {"success":true 或 {"success": true 或 {"success":false
        success_match = re.search(r'^\s*\{\s*"success"\s*:\s*(true|false)', result_str, re.IGNORECASE)
        if success_match:
            return success_match.group(1).lower() == 'false'

        # 如果是截断的 JSON（以 { 开头），不使用正则匹配
        # 因为 stdout 内容可能包含 "Error" 等词（如 Python 之禅 "Errors should never pass silently"）
        if result_str.strip().startswith('{'):
            # JSON 格式但无法解析，假定成功（保守策略）
            return False

    # 其他工具使用改进的关键词匹配
    # 使用正则表达式匹配独立的错误词，避免匹配 JSON 字段名如 "error":null
    error_patterns = [
        r'(?<!["\'])\b错误\b',           # 中文"错误"，不在引号内
        r'(?<!["\'])\b失败\b',           # 中文"失败"，不在引号内
        r'^Error:',                       # 行首 Error:（明确的错误输出）
        r'(?<!["\'])Exception\b',        # Exception
        r'^Failed:',                      # 行首 Failed:
        r'Traceback \(most recent call last\)',  # Python 异常栈
        r'"success"\s*:\s*false',        # JSON 中的 success: false
    ]

    for pattern in error_patterns:
        if re.search(pattern, result_str, re.IGNORECASE | re.MULTILINE):
            return True

    return False

# ═══════════════════════════════════════════════════════════════════ 图构建设 ═══════════════════════════════════════════════════════════════════


def build_graph(checkpointer=None) -> Any:
    """
    编译并翻译 LangGraph 图。

    图结构:
        START → call_llm → [should_continue] 
                                ├─ "tool_call" → tool_call_node → call_llm (循环)
                                └─ "end" → END

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


def make_config(owner_type: str, owner_id: str, conversation_id: str, platform: str = None, bot_id: str = None) -> dict:
    """
    生成符合多租户隔离要求的 LangGraph config。

    V5 多租户/多空间隔离：
    - 个人空间: thread_id = "PERSONAL:{user_id}:{conversation_id}"
    - 组织空间: thread_id = "ORGANIZATION:{org_code}:{conversation_id}"
    - 平台隔离: thread_id = "PERSONAL:{user_id}:{platform}:{bot_id}:{conversation_id}"

    这样不同空间即使使用相同 conversation_id，其 thread_id 也不同，
    checkpoint 完全隔离。
    """
    if platform and bot_id:
        thread_id = f"{owner_type}:{owner_id}:{platform}:{bot_id}:{conversation_id}"
    else:
        thread_id = f"{owner_type}:{owner_id}:{conversation_id}"
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }


# ═══════════════════════════════════════════════════════════════════ 流式执行 ═══════════════════════════════════════════════════════════════════

async def astream_agent(
    graph: Any,
    owner_type: str,
    owner_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
    agent_id: str = None,
    system_prompt: str = "",
    model: str = None,
    temperature: float = None,
    iteration_limit: int = 30,
    platform: str = None,
    bot_id: str = None,
    knowledge_base_ids: list[str] | None = None,
    max_context: int = 2000,
) -> AsyncIterator[dict]:
    """
    以流式方式运行 Agent，逐 token yield AI 回复内容和工具调用事件。

    支持 Tool Calling 循环：
    - LLM 返回 tool_calls → 执行工具 → 结果回传 LLM → 继续生成
    - yield 文本 token 和工具调用事件

    Args:
        graph: 已编译的 LangGraph CompiledGraph。
        owner_type: 所有者类型（PERSONAL 或 ORGANIZATION）。
        owner_id: 所有者 ID（user_id 或 org_code）。
        user_id: 用户 ID。
        conversation_id: 会话 ID。
        message: 用户输入消息。
        agent_id: Agent 配置 ID（可选）。
        system_prompt: 系统提示词（可选）。
        model: 模型 ID（可选，如 gpt-5-mini）。
        temperature: 温度参数（可选）。
        iteration_limit: 最大迭代次数。
        platform: 平台类型（可选，如 WEB, QQ, FEISHU）。
        bot_id: Bot ID（可选）。

    Yields:
        dict: 事件对象，可能是：
            - {"type": "chunk", "content": "..."}  文本片段
            - {"type": "tool_call", "tool_name": "...", "tool_args": {...}, "status": "start"|"complete", "result": "..."}
    """
    config = make_config(owner_type, owner_id, conversation_id, platform, bot_id)

    input_state: dict = {
        "messages": [HumanMessage(content=message)],
        "owner_type": owner_type,
        "owner_id": owner_id,
        "platform": platform,
        "bot_id": bot_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "system_prompt": system_prompt,
        "model": model,
        "temperature": temperature,
        "knowledge_base_ids": knowledge_base_ids or [],
        "max_context": max_context,
        "_iteration": 0,  # 初始化迭代计数器
    }

    logger.info(
        "astream_agent start: thread_id=%s:%s:%s:%s:%s, user=%s, agent_id=%s, model=%s, has_system_prompt=%s, iteration_limit=%d",
        owner_type,
        owner_id,
        platform or "",
        bot_id or "",
        conversation_id,
        user_id,
        agent_id,
        model,
        bool(system_prompt),
        iteration_limit,
    )

    # 记录正在执行的工具调用
    pending_tool_calls: dict[str, dict] = {}

    # 使用 astream_events 捕获流式 token
    async for event in graph.astream_events(input_state, config, version="v2"):
        kind = event.get("event")

        # 检查迭代次数
        if "_iteration" in event.get("data", {}).get("state", {}).get("channel_values", {}):
            iteration = event["data"]["state"]["channel_values"]["_iteration"]
            if iteration >= iteration_limit:
                logger.info("达到最大迭代次数 %d，强制结束", iteration_limit)
                break

        # on_chat_model_stream: LLM 流式输出 token
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")

            # 检查是否有 reasoning_content（MiniMax 等模型的思考过程）
            # MiniMax 在 additional_kwargs 中返回 reasoning_content
            if hasattr(chunk, 'additional_kwargs') and chunk.additional_kwargs:
                reasoning = chunk.additional_kwargs.get('reasoning_content')
                if reasoning:
                    # 发送 thinking 事件，不发送普通 chunk
                    logger.info(f"[Thinking] MiniMax reasoning content: {reasoning[:100]}...")
                    yield {"type": "thinking", "content": reasoning}
                    continue  # 跳过普通 content 处理

            if chunk and hasattr(chunk, "content") and chunk.content:
                yield {"type": "chunk", "content": chunk.content}

            # 检查是否有 tool_calls（流式中可能分批返回）
            # 注意：流式 tool_call_chunks 的参数可能不完整，暂时收集但不发送 start 事件
            if chunk and hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                for tc in chunk.tool_call_chunks:
                    # tool_call_chunks 可能只有部分字段
                    if tc.get("id") and tc.get("name"):
                        tool_id = tc["id"]
                        tool_name = tc["name"]
                        tool_args = tc.get("args", {})
                        if isinstance(tool_args, str):
                            try:
                                import json
                                tool_args = json.loads(tool_args) if tool_args else {}
                            except:
                                tool_args = {}
                        # 仅记录，不发送事件（等 on_chat_model_end 时参数完整后再发送）
                        if tool_id not in pending_tool_calls:
                            pending_tool_calls[tool_id] = {
                                "name": tool_name,
                                "args": tool_args,
                                "sent_start": False,
                            }
                        elif tool_args:
                            # 更新 args（流式中可能分批返回参数）
                            pending_tool_calls[tool_id]["args"].update(tool_args)

        # on_chat_model_end: LLM 输出完成，检查完整的 tool_calls
        elif kind == "on_chat_model_end":
            output = event.get("data", {}).get("output")
            if output and hasattr(output, "tool_calls") and output.tool_calls:
                for tc in output.tool_calls:
                    tool_id = tc.get("id", "")
                    tool_name = tc.get("name", "")
                    tool_args = tc.get("args", {})

                    # 检查是否已发送过 start 事件
                    existing = pending_tool_calls.get(tool_id, {})
                    if not existing.get("sent_start", False):
                        # 使用完整的参数
                        pending_tool_calls[tool_id] = {
                            "name": tool_name,
                            "args": tool_args,
                            "sent_start": True,
                        }
                        logger.info("工具调用: %s, args=%s", tool_name, tool_args)
                        yield {
                            "type": "tool_call",
                            "tool_call_id": tool_id,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "status": "start",
                        }

        # on_tool_end: 工具执行完成
        elif kind == "on_tool_end":
            tool_output = event.get("data", {}).get("output", "")
            tool_name = event.get("name", "unknown")
            # 截断结果避免过长
            result_str = str(tool_output)[:500] if tool_output else ""

            # 使用改进的错误判断逻辑
            is_error = _is_tool_error(result_str, tool_name)

            # 检查是否是 media_send 工具，返回了 media 类型结果
            if tool_name == "media_send" and not is_error:
                try:
                    # 尝试解析 JSON 结果
                    if result_str.startswith("{") or result_str.startswith("["):
                        result_data = json.loads(result_str)
                    else:
                        result_data = {"type": "media", "url": result_str, "media_type": "image"}

                    if result_data.get("type") == "media":
                        logger.info(f"[Media] 发送媒体事件: {result_data.get('media_type')}, url={result_data.get('url')[:50]}...")
                        yield {
                            "type": "media",
                            "media_type": result_data.get("media_type", "image"),
                            "url": result_data.get("url", ""),
                            "mime_type": result_data.get("mime_type", "image/png"),
                            "filename": result_data.get("filename"),
                        }
                        # 不再 continue，继续发送 tool_call complete 事件
                except json.JSONDecodeError:
                    pass  # 解析失败，继续发送普通 tool_call 事件

            logger.info("工具执行完成: %s, error=%s", tool_name, is_error)
            tool_call_id = next((tid for tid, info in pending_tool_calls.items() if info.get("name") == tool_name), None)
            yield {
                "type": "tool_call",
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_args": {},
                "status": "error" if is_error else "complete",
                "result": result_str if not is_error else None,
                "error": result_str if is_error else None,
            }

        # on_chain_end: 节点执行完成 - 用于检测 call_llm / tool_call 节点
        elif kind == "on_chain_end":
            node_name = event.get("name", "")
            output_data = event.get("data", {}).get("output", {})

            if node_name == "call_llm":
                context_stats = output_data.get("context_stats")
                if context_stats:
                    yield {
                        "type": "context_stats",
                        "token_count": context_stats.get("token_count", 0),
                        "max_context": context_stats.get("max_context", 0),
                        "compressed": context_stats.get("compressed", False),
                        "read_tokens": context_stats.get("read_tokens", 0),
                        "write_tokens": context_stats.get("write_tokens", 0),
                        "message_tokens": context_stats.get("message_tokens", 0),
                    }

            # 检查是否是 tool_call 节点完成
            if node_name == "tool_call":
                # 从 output 中获取 ToolMessage 列表
                tool_messages = output_data.get("messages", [])
                for msg in tool_messages:
                    if hasattr(msg, 'content') and hasattr(msg, 'tool_call_id'):
                        result_str = str(msg.content)[:500] if msg.content else ""

                        # 尝试从 pending_tool_calls 找到对应的工具名称
                        tool_call_id = msg.tool_call_id
                        tool_info = pending_tool_calls.get(tool_call_id, {})
                        tool_name = tool_info.get("name", "unknown")

                        # 使用改进的错误判断逻辑
                        is_error = _is_tool_error(result_str, tool_name)

                        # 检查是否是 media_send 工具，返回了 media 类型结果
                        if tool_name == "media_send" and not is_error:
                            try:
                                if result_str.startswith("{") or result_str.startswith("["):
                                    result_data = json.loads(result_str)
                                else:
                                    result_data = {"type": "media", "url": result_str, "media_type": "image"}

                                if result_data.get("type") == "media":
                                    logger.info(f"[Media] 发送媒体事件: {result_data.get('media_type')}, url={result_data.get('url')[:50]}...")
                                    yield {
                                        "type": "media",
                                        "media_type": result_data.get("media_type", "image"),
                                        "url": result_data.get("url", ""),
                                        "mime_type": result_data.get("mime_type", "image/png"),
                                        "filename": result_data.get("filename"),
                                    }
                                    # 不再 continue，继续发送 tool_call complete 事件
                            except json.JSONDecodeError:
                                pass  # 解析失败，继续发送普通 tool_call 事件

                        logger.info("节点工具执行完成: %s, result_len=%d, error=%s", tool_name, len(result_str), is_error)
                        yield {
                            "type": "tool_call",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "tool_args": {},
                            "status": "error" if is_error else "complete",
                            "result": result_str if not is_error else None,
                            "error": result_str if is_error else None,
                        }

                # V5: 检查是否有注入的 follow-up 消息（从 nodes.py 返回）
                injected_followups = output_data.get("followup_injected", [])
                if injected_followups:
                    logger.info("[Followup] 发送注入事件: %d 条消息", len(injected_followups))
                    for f in injected_followups:
                        yield {
                            "type": "followup_injected",
                            "followup_id": f["followup_id"],
                            "content": f["content"],
                            "injected_tool": f.get("injected_tool"),
                        }

                # V5: 检查是否有 pending follow-up 消息（用于前端实时显示）
                # 在 tool_call 节点完成后检查，以便在下一次 LLM 调用前注入
                try:
                    from app.control.followup_queue import get_followup_queue
                    followup_queue = await get_followup_queue()
                    pending_followups = await followup_queue.get_pending(conversation_id)
                    if pending_followups:
                        logger.info("[Followup] 检测到 %d 条 pending follow-up 消息", len(pending_followups))
                        for f in pending_followups:
                            yield {
                                "type": "followup_pending",
                                "followup_id": f.followup_id,
                                "content": f.content,
                            }
                except Exception as e:
                    logger.warning(f"[Followup] 检查 follow-up 队列失败: {e}")


async def invoke_agent(
    graph: Any,
    owner_type: str,
    owner_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
    agent_id: str = None,
    system_prompt: str = "",
    model: str = None,
    temperature: float = None,
    platform: str = None,
    bot_id: str = None,
    max_context: int = 2000,
) -> str:
    """
    以非流式方式运行 Agent，等待完整回复后返回。

    用于 QQ 机器人等不需要流式输出的场景。

    Args:
        graph: 已编译的 LangGraph CompiledGraph。
        owner_type: 所有者类型（PERSONAL 或 ORGANIZATION）。
        owner_id: 所有者 ID（user_id 或 org_code）。
        user_id: 用户 ID。
        conversation_id: 会话 ID。
        message: 用户输入消息。
        agent_id: Agent 配置 ID（可选）。
        system_prompt: 系统提示词（可选）。
        model: 模型 ID（可选，如 gpt-5-mini）。
        temperature: 温度参数（可选）。
        platform: 平台类型（可选，如 WEB, QQ, FEISHU）。
        bot_id: Bot ID（可选）。

    Returns:
        str: AI 完整回复内容。
    """
    config = make_config(owner_type, owner_id, conversation_id, platform, bot_id)

    input_state: dict = {
        "messages": [HumanMessage(content=message)],
        "owner_type": owner_type,
        "owner_id": owner_id,
        "platform": platform,
        "bot_id": bot_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "system_prompt": system_prompt,
        "model": model,
        "temperature": temperature,
        "max_context": max_context,
    }

    logger.info(
        "invoke_agent start: thread_id=%s:%s:%s:%s:%s, user=%s, agent_id=%s, has_system_prompt=%s",
        owner_type,
        owner_id,
        platform or "",
        bot_id or "",
        conversation_id,
        user_id,
        agent_id,
        bool(system_prompt),
    )

    # 使用 ainvoke 等待完整结果
    result = await graph.ainvoke(input_state, config)

    # 从结果中提取最终 AI 回复
    messages = result.get("messages", [])
    if messages:
        last_message = messages[-1]
        # 返回最终消息的 content
        return last_message.content if hasattr(last_message, "content") else str(last_message)

    return ""


async def invoke_agent_with_media(
    graph: Any,
    owner_type: str,
    owner_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
    agent_id: str = None,
    system_prompt: str = "",
    model: str = None,
    temperature: float = None,
    platform: str = None,
    bot_id: str = None,
    max_context: int = 2000,
) -> tuple[str, list[dict]]:
    """
    带媒体事件捕获的 Agent 调用。

    使用 astream_events 捕获所有事件，包括：
    - 文本响应（on_chat_model_stream）
    - 媒体事件（on_tool_end 中 media_send 工具的输出）

    用于平台机器人等需要同时返回文本和媒体的场景。

    Args:
        graph: 已编译的 LangGraph CompiledGraph。
        owner_type: 所有者类型（PERSONAL 或 ORGANIZATION）。
        owner_id: 所有者 ID（user_id 或 org_code）。
        user_id: 用户 ID。
        conversation_id: 会话 ID。
        message: 用户输入消息。
        agent_id: Agent 配置 ID（可选）。
        system_prompt: 系统提示词（可选）。
        model: 模型 ID（可选，如 gpt-5-mini）。
        temperature: 温度参数（可选）。
        platform: 平台类型（可选，如 WEB, QQ, FEISHU）。
        bot_id: Bot ID（可选）。

    Returns:
        tuple[str, list[dict]]: (文本响应, 媒体事件列表)
    """
    config = make_config(owner_type, owner_id, conversation_id, platform, bot_id)

    input_state: dict = {
        "messages": [HumanMessage(content=message)],
        "owner_type": owner_type,
        "owner_id": owner_id,
        "platform": platform,
        "bot_id": bot_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "system_prompt": system_prompt,
        "model": model,
        "temperature": temperature,
        "max_context": max_context,
    }

    logger.info(
        "invoke_agent_with_media start: thread_id=%s:%s:%s:%s:%s, user=%s, agent_id=%s",
        owner_type,
        owner_id,
        platform or "",
        bot_id or "",
        conversation_id,
        user_id,
        agent_id,
    )

    media_events = []
    full_response = ""

    async for event in graph.astream_events(input_state, config, version="v2"):
        kind = event.get("event")

        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                full_response += chunk.content

        elif kind == "on_tool_end":
            tool_name = event.get("name", "")
            tool_output = event.get("data", {}).get("output", "")

            if tool_name == "media_send" and not _is_tool_error(str(tool_output), tool_name):
                try:
                    result_str = str(tool_output)[:500] if tool_output else ""
                    if result_str.startswith("{") or result_str.startswith("["):
                        result_data = json.loads(result_str)
                    else:
                        result_data = {"type": "media", "url": result_str, "media_type": "image"}

                    if result_data.get("type") == "media":
                        logger.info(f"[Media] 捕获媒体事件: {result_data.get('media_type')}, url={result_data.get('url')[:50]}...")
                        media_events.append({
                            "type": "media",
                            "media_type": result_data.get("media_type", "image"),
                            "url": result_data.get("url", ""),
                            "mime_type": result_data.get("mime_type", "image/png"),
                            "filename": result_data.get("filename"),
                        })
                except json.JSONDecodeError:
                    pass

    return full_response, media_events
