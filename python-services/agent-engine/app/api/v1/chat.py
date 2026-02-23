"""
app/api/v1/chat.py — SSE 流式对话接口

POST /api/v1/agent/chat/stream
POST /api/v1/agent/chat

V5 重构：使用 X-Context 替代 X-Tenant-Id
X-Context 格式：
  - "personal" - 个人空间
  - "org:<orgCode>" - 组织空间
"""
from __future__ import annotations

import logging
import time
from typing import AsyncIterator, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import astream_agent, build_graph, invoke_agent
from app.agent.title_generator import generate_title
from app.checkpointer import get_mysql_checkpointer
from app.client.agent_config_client import get_agent_config_client
from app.client.session_client import get_session_client
from app.control.interrupt_controller import get_interrupt_controller
from app.schemas import ChatRequest, ChatRequestNonStream, ChatResponse, SSEChunk, SSEContextStats, SSEDone, SSEError, SSEToolCall, SSEThinking, SSEMedia, SSEFollowupPending, SSEFollowupInjected

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse_data(obj) -> str:
    """将 Pydantic model 序列化为 SSE data 字符串。"""
    return obj.model_dump_json()


def _parse_context(
    x_context: str | None,
    x_user_id: str,
) -> tuple[Literal["PERSONAL", "ORGANIZATION"], str]:
    """
    解析 X-Context header，返回 (owner_type, owner_id)

    V5 重构：使用 X-Context 替代 X-Tenant-Id
    - "personal" -> ("PERSONAL", user_id)
    - "org:<orgCode>" -> ("ORGANIZATION", orgId)  # orgId 需要从数据库或缓存查询

    注意：目前暂时使用 user_id 作为 owner_id，后续需要根据 orgCode 查询 orgId
    """
    if x_context and x_context.startswith("org:"):
        # 组织空间：owner_id 暂时用 user_id（后续需要解析 orgCode 获取 orgId）
        # TODO: 需要通过 API 获取 orgId
        return ("ORGANIZATION", x_user_id)
    else:
        # 个人空间
        return ("PERSONAL", x_user_id)


async def _chat_event_generator(
    owner_type: Literal["PERSONAL", "ORGANIZATION"],
    owner_id: str,
    user_id: str,
    conversation_id: str,
    message: str,
    agent_id: str | None = None,
    max_context: int = 128000,
) -> AsyncIterator[dict]:
    """
    SSE 事件生成器。

    V5 重构：使用 owner_type 和 owner_id 替代 tenant_id
    """
    session_client = get_session_client()
    interrupt_ctrl = await get_interrupt_controller()
    agent_config_client = get_agent_config_client()

    # 1. 保存用户消息（使用 owner_type + owner_id）
    await session_client.add_message(
        conversation_id=conversation_id,
        owner_type=owner_type,
        owner_id=owner_id,
        user_id=user_id,
        role="user",
        content=message,
    )

    # 2. 读取 Agent 配置（用于模型、上下文、知识库白名单）
    agent_config = None
    if agent_id:
        agent_config = await agent_config_client.get_agent_config(int(agent_id), str(owner_id))
    if agent_config is None:
        agent_config = await agent_config_client.get_default_agent_config(str(owner_id))

    knowledge_base_ids = []
    raw_kb_ids = (agent_config or {}).get("knowledge_base_ids")
    if isinstance(raw_kb_ids, str) and raw_kb_ids.strip():
        try:
            import json
            parsed = json.loads(raw_kb_ids)
            if isinstance(parsed, list):
                knowledge_base_ids = [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass
    elif isinstance(raw_kb_ids, list):
        knowledge_base_ids = [str(x) for x in raw_kb_ids if str(x).strip()]

    # 3. 执行 Agent（astream_agent 内部构建状态）
    agent_stream = None
    try:
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)

            # 收集完整回复与可持久化运行轨迹
            full_response = ""
            tool_call_records: dict[str, dict] = {}
            tool_call_order: list[str] = []
            followup_records: dict[str, dict] = {}
            followup_order: list[str] = []
            attachments: list[dict] = []
            latest_context_stats: dict | None = None
            thinking_buffer = ""
            timeline: list[dict] = []

            agent_stream = astream_agent(
                graph=graph,
                owner_type=owner_type,
                owner_id=owner_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                agent_id=(agent_config or {}).get("id"),
                system_prompt=(agent_config or {}).get("system_prompt") or "",
                model=(agent_config or {}).get("model"),
                temperature=(agent_config or {}).get("temperature"),
                knowledge_base_ids=knowledge_base_ids,
                max_context=max_context,
            )

            async for token in agent_stream:
                # 检查是否被中断
                if interrupt_ctrl.is_stopped(conversation_id):
                    logger.info(f"[Chat] 对话被停止: {conversation_id}")
                    yield {"data": _sse_data(SSEError(message="User stopped"))}
                    interrupt_ctrl.clear(conversation_id)
                    return

                if isinstance(token, dict):
                    token_type = token.get("type")

                    if token_type == "context_stats":
                        token["timestamp"] = token.get("timestamp") or time.time()
                        latest_context_stats = {
                            "token_count": token.get("token_count", 0),
                            "max_context": token.get("max_context", 0),
                            "compressed": token.get("compressed", False),
                            "timestamp": token.get("timestamp"),
                            "read_tokens": token.get("read_tokens", 0),
                            "write_tokens": token.get("write_tokens", 0),
                            "message_tokens": token.get("message_tokens", 0),
                        }
                        yield {"data": _sse_data(SSEContextStats(**token))}
                        continue
                    if token_type == "tool_call":
                        tool_call_id = token.get("tool_call_id") or f"{token.get('tool_name', 'tool')}-{len(tool_call_order)}"
                        record = tool_call_records.get(tool_call_id)
                        if record is None:
                            record = {
                                "id": tool_call_id,
                                "name": token.get("tool_name", "unknown"),
                                "args": token.get("tool_args", {}) or {},
                                "status": "running",
                                "result": None,
                                "error": None,
                                "startTime": time.time(),
                            }
                            tool_call_records[tool_call_id] = record
                            tool_call_order.append(tool_call_id)
                            timeline.append({"type": "tool_call", "ref": tool_call_id})
                        if token.get("tool_args"):
                            record["args"] = token.get("tool_args", {}) or {}
                        status = token.get("status")
                        if status == "start":
                            record["status"] = "running"
                            record.setdefault("startTime", time.time())
                        elif status == "complete":
                            record["status"] = "success"
                            record["result"] = token.get("result")
                            record["endTime"] = time.time()
                        elif status == "error":
                            record["status"] = "error"
                            record["error"] = token.get("error")
                            record["endTime"] = time.time()
                        token["tool_call_id"] = tool_call_id
                        yield {"data": _sse_data(SSEToolCall(**token))}
                        continue
                    if token_type == "thinking":
                        thinking_buffer += token.get("content", "")
                        yield {"data": _sse_data(SSEThinking(**token))}
                        continue
                    if token_type == "media":
                        attachments.append({
                            "type": token.get("media_type", "image"),
                            "url": token.get("url", ""),
                            "mime_type": token.get("mime_type"),
                            "filename": token.get("filename"),
                        })
                        yield {"data": _sse_data(SSEMedia(**token))}
                        continue
                    if token_type == "followup_pending":
                        followup_id = token.get("followup_id")
                        if followup_id and followup_id not in followup_records:
                            followup_records[followup_id] = {
                                "followup_id": followup_id,
                                "content": token.get("content", ""),
                                "status": "pending",
                                "injected_tool": None,
                            }
                            followup_order.append(followup_id)
                        yield {"data": _sse_data(SSEFollowupPending(**token))}
                        continue
                    if token_type == "followup_injected":
                        followup_id = token.get("followup_id")
                        if followup_id:
                            record = followup_records.get(followup_id, {
                                "followup_id": followup_id,
                                "content": token.get("content", ""),
                                "status": "pending",
                                "injected_tool": None,
                            })
                            record["content"] = token.get("content", record.get("content", ""))
                            record["status"] = "injected"
                            record["injected_tool"] = token.get("injected_tool")
                            followup_records[followup_id] = record
                            if followup_id not in followup_order:
                                followup_order.append(followup_id)
                            timeline.append({"type": "followup", "ref": followup_id})
                        yield {"data": _sse_data(SSEFollowupInjected(**token))}
                        continue
                    if token_type == "chunk":
                        token_content = token.get("content", "")
                    else:
                        continue
                else:
                    token_content = str(token)

                full_response += token_content
                yield {"data": _sse_data(SSEChunk(content=token_content))}

        # 4. 保存 AI 回复
        if full_response:
            assistant_metadata = {
                "tool_calls": [tool_call_records[tool_id] for tool_id in tool_call_order],
                "followups": [followup_records[followup_id] for followup_id in followup_order],
                "context_stats": latest_context_stats,
                "attachments": attachments,
                "thinking": thinking_buffer or None,
                "timeline": timeline,
            }
            assistant_metadata = {k: v for k, v in assistant_metadata.items() if v not in (None, [], "")}

            await session_client.add_message(
                conversation_id=conversation_id,
                owner_type=owner_type,
                owner_id=owner_id,
                user_id=user_id,
                role="assistant",
                content=full_response,
                metadata=assistant_metadata,
            )

            # 5. 首轮对话自动生成标题（仅当标题仍为“新对话”时）
            try:
                conversation = await session_client.get_conversation(
                    conversation_id=conversation_id,
                    owner_type=owner_type,
                    owner_id=owner_id,
                )
                current_title = (conversation or {}).get("title")
                message_count = (conversation or {}).get("messageCount", 0)
                if current_title == "新对话" and message_count <= 2:
                    generated_title = await generate_title(message, full_response)
                    if generated_title:
                        await session_client.update_title(
                            conversation_id=conversation_id,
                            owner_type=owner_type,
                            owner_id=owner_id,
                            user_id=user_id,
                            title=generated_title,
                        )
            except Exception:
                logger.exception("[Chat] 自动生成标题失败: conv=%s", conversation_id)

        # 6. 发送完成事件
        yield {"data": _sse_data(SSEDone(conversation_id=conversation_id))}

    except Exception as exc:
        logger.exception(f"[Chat] Agent 执行异常: owner_type={owner_type}, owner_id={owner_id}, conv={conversation_id}")
        yield {"data": _sse_data(SSEError(message=str(exc)))}
    finally:
        # 确保 async generator 被正确关闭，避免 "generator didn't stop after athrow()" 警告
        if agent_stream is not None:
            try:
                await agent_stream.aclose()
            except Exception:
                pass


@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    x_context: str = Header(None, alias="X-Context"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_conv_id: str = Header(..., alias="X-Conv-Id"),
    x_agent_id: str = Header(None, alias="X-Agent-Id"),
):
    """
    SSE 流式对话接口。

    V5 重构：
    - 使用 X-Context 替代 X-Tenant-Id
    - X-Context 格式："personal" 或 "org:<orgCode>"
    """
    owner_type, owner_id = _parse_context(x_context, x_user_id)

    logger.info(
        "chat_stream: owner_type=%s, owner_id=%s, user=%s, conv=%s",
        owner_type,
        owner_id,
        x_user_id,
        x_conv_id,
    )

    # TODO: 从 agent_config 根据 agent_id 获取 max_context
    # 测试期间临时降低窗口，便于验证自动压缩
    max_context = 2000

    return EventSourceResponse(
        _chat_event_generator(
            owner_type=owner_type,
            owner_id=owner_id,
            user_id=x_user_id,
            conversation_id=x_conv_id,
            message=body.message,
            agent_id=x_agent_id,
            max_context=max_context,
        ),
        media_type="text/event-stream",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_non_stream(
    request: Request,
    body: ChatRequestNonStream,
    x_context: str = Header(None, alias="X-Context"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_conv_id: str = Header(None, alias="X-Conv-Id"),
):
    """
    非流式对话接口（用于 QQ 机器人等场景）。

    V5 重构：使用 X-Context 替代 X-Tenant-Id
    """
    owner_type, owner_id = _parse_context(x_context, x_user_id)
    conversation_id = body.conversation_id or x_conv_id or "default"

    logger.info(
        "chat_non_stream: owner_type=%s, owner_id=%s, user=%s, conv=%s",
        owner_type,
        owner_id,
        x_user_id,
        conversation_id,
    )

    try:
        # 保存用户消息
        session_client = get_session_client()
        await session_client.add_message(
            conversation_id=conversation_id,
            owner_type=owner_type,
            owner_id=owner_id,
            user_id=x_user_id,
            role="user",
            content=body.message,
        )

        # 执行 Agent
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await invoke_agent(
                graph=graph,
                owner_type=owner_type,
                owner_id=owner_id,
                user_id=x_user_id,
                conversation_id=conversation_id,
                message=body.message,
                max_context=128000,
            )

        # 保存 AI 回复
        await session_client.add_message(
            conversation_id=conversation_id,
            owner_type=owner_type,
            owner_id=owner_id,
            user_id=x_user_id,
            role="assistant",
            content=result,
        )

        return ChatResponse(
            conversation_id=conversation_id,
            content=result,
        )

    except Exception as exc:
        logger.exception(f"[Chat] Agent 执行异常: owner_type={owner_type}, owner_id={owner_id}, conv={conversation_id}")
        raise HTTPException(status_code=500, detail=str(exc))
