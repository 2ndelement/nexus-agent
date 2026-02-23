"""
app/agent/nodes.py — LangGraph 图节点函数

节点列表：
  1. call_llm_node   — 调用 LLM，可能返回 tool_calls
  2. tool_call_node  — 执行工具调用，将结果添加到 messages
  3. should_continue — 条件路由：有 tool_calls → 工具节点，无 → 结束

🐱 Auto Compact 集成：
  - call_llm_node 在调用 LLM 前执行上下文压缩
  - 支持 Micro Compact (每轮)、Auto Transcript (阈值触发)、Halving Truncation (兜底)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.state import AgentState
from app.agent.context_manager import AutoCompactConfig, ContextManager, estimate_message_tokens, get_token_breakdown
from app.config import settings

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════════
# 上下文管理器初始化
# ═══════════════════════════════════════════════════════════════════════════════════

# 全局上下文管理器实例（单例模式）
_context_manager: ContextManager | None = None


def get_context_manager(max_context: int = 2000) -> ContextManager:
    """获取上下文管理器实例

    Args:
        max_context: 最大上下文token数，基于此计算动态阈值
    """
    global _context_manager
    if _context_manager is None or _context_manager.config.max_context != max_context:
        config = AutoCompactConfig(
            max_context=max_context,
            micro_compact_enabled=True,
            micro_compact_keep_recent=3,
            use_auto_transcript=True,
            transcript_dir=settings.transcript_dir or "/tmp/nexus-transcripts",
            use_halving_truncation=True,
            llm_model=settings.llm_model,
        )
        _context_manager = ContextManager(config)
        logger.info(f"ContextManager initialized: max_context={max_context}, "
                    f"transcript_threshold={config.transcript_threshold}, "
                    f"halving_threshold={config.halving_threshold}")
    return _context_manager


# ═══════════════════════════════════════════════════════════════════════════════════
# 内置工具定义
# ═══════════════════════════════════════════════════════════════════════════════════

BUILTIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "执行数学表达式计算。支持 +, -, *, /, **, sqrt, log 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取实时信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_execute",
            "description": "在隔离沙箱中执行 Python 或 Bash 代码并返回结果。适用于数据分析、计算、文件处理等任务。\n\n重要规则：\n- 所有文件操作必须在 /workspace/ 目录下进行\n- 生成的图片、数据文件等必须保存到 /workspace/ 目录\n- 保存路径示例：/workspace/output.png（正确）、/tmp/output.png（错误，前端无法访问）\n- 代码执行后，/workspace/ 下新生成的文件会自动返回并可被前端访问",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的代码。注意：所有文件保存路径必须是 /workspace/xxx",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "bash"],
                        "default": "python",
                        "description": "代码语言",
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 60,
                        "minimum": 1,
                        "maximum": 3600,
                        "description": "超时秒数（1-3600）",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_browser",
            "description": "浏览和管理 Skill 技能文件。列出技能、读取 SKILL.md、读取技能文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "read", "read_file", "tree"],
                        "description": "操作类型",
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "技能名称",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_retrieve",
            "description": "从知识库检索相关信息。在回答需要特定领域知识、公司内部文档、产品说明等问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索查询词，描述你要查找的信息",
                    },
                    "knowledge_base_id": {
                        "type": "string",
                        "description": "知识库 ID（可选，不指定则搜索所有可用知识库）",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                        "description": "返回的最相关结果数量",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_send",
            "description": """发送图片、视频、音频等多媒体内容到聊天界面。

使用场景：
- 当需要向用户展示图表、数据可视化、生成的图片时
- 当需要播放音频/视频内容时
- 当需要提供文件下载时

URL 格式要求：
- 工作区相对路径：直接使用文件名如 "chart.png" 或 "output/data.csv"（推荐）
- 代理 URL：/api/v1/media/{owner_type}/{owner_id}/{conversation_id}/{filename}
- base64 data URI：data:{mime_type};base64,{base64_data}

禁止使用的 URL 格式：
- /tmp/xxx 或 /var/xxx 等非工作区路径（前端无法访问）
- file:// 协议（浏览器安全限制）
- 绝对路径如 /home/xxx（前端无法访问）

示例：
- 正确：{"url": "chart.png"} 或 {"url": "/api/v1/media/PERSONAL/17/conv123/chart.png"}
- 错误：{"url": "/tmp/chart.png"} 或 {"url": "file:///tmp/chart.png"}""",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "媒体文件路径或 URL。推荐使用相对路径如 \"chart.png\"",
                    },
                    "base64": {
                        "type": "string",
                        "description": "Base64编码数据（可选，与 url 二选一）",
                    },
                    "media_type": {
                        "type": "string",
                        "enum": ["image", "video", "audio", "file"],
                        "description": "媒体类型",
                    },
                    "mime_type": {
                        "type": "string",
                        "description": "MIME类型，如 image/png, video/mp4",
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名（可选）",
                    },
                },
                "required": ["media_type"],
            },
        },
    },
]

# ═══════════════════════════════════════════════════════════════════════════════════
# 工具执行
# ═══════════════════════════════════════════════════════════════════════════════════

async def _execute_tool(tool_name: str, arguments: dict) -> str:
    """执行工具"""
    if tool_name == "skill_browser":
        return await _execute_skill_browser(arguments)
    elif tool_name == "calculator":
        return _execute_calculator(arguments)
    elif tool_name == "sandbox_execute":
        return await _execute_sandbox(arguments)
    elif tool_name == "web_search":
        return await _execute_search(arguments)
    elif tool_name in ("knowledge_retrieve", "knowledge_search"):
        return await _execute_rag_retrieve(arguments)
    elif tool_name == "media_send":
        return await _execute_media_send(arguments)
    else:
        return f"未知工具: {tool_name}"


async def _execute_rag_retrieve(arguments: dict) -> str:
    """RAG 知识库检索"""
    try:
        from app.tools.rag_tool import knowledge_retrieve
        result = await knowledge_retrieve(
            tenant_id=arguments.get("tenant_id", ""),
            knowledge_base_id=arguments.get("knowledge_base_id", ""),
            query=arguments.get("query", ""),
            top_k=arguments.get("top_k", 5),
        )
        if result.get("success"):
            return result.get("context", "未找到相关内容")
        else:
            return f"知识库检索失败: {result.get('error', '未知错误')}"
    except Exception as e:
        logger.error(f"RAG 检索执行失败: {e}")
        return f"知识库检索失败: {e}"


async def _execute_skill_browser(arguments: dict) -> str:
    """执行 Skill 浏览器工具"""
    try:
        from app.tools.skill_browser import skill_browser as skill_browser_func
        result = await skill_browser_func(
            action=arguments.get("action"),
            tenant_id=arguments.get("tenant_id", ""),
            skill_name=arguments.get("skill_name"),
            file_path=arguments.get("file_path"),
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"skill_browser 执行失败: {e}")
        return f"skill_browser 执行失败: {e}"


def _execute_calculator(arguments: dict) -> str:
    """计算器"""
    try:
        expression = arguments.get("expression", "")
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"


async def _execute_sandbox(arguments: dict) -> str:
    """沙箱执行 - V5 支持会话隔离，通过 Nacos 服务发现"""
    import httpx
    from common.nacos import discover_service

    # 通过 Nacos 发现 sandbox 服务，降级使用配置的地址
    base_url = discover_service("nexus-sandbox-service", fallback=settings.sandbox_url)
    if not base_url:
        return "执行失败: sandbox 服务不可用"

    url = f"{base_url}/execute"
    try:
        # 构建请求 payload，包含 V5 会话上下文
        payload = {
            "code": arguments.get("code"),
            "language": arguments.get("language", "python"),
            "timeout": arguments.get("timeout", 60),
            # V5 会话上下文（从 tool_args 中获取，由 tool_node 注入）
            "owner_type": arguments.get("owner_type", "PERSONAL"),
            "owner_id": arguments.get("owner_id", ""),
            "conversation_id": arguments.get("conversation_id", ""),
        }

        async with httpx.AsyncClient(timeout=arguments.get("timeout", 60)) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                result = resp.json()

                # 处理工作区文件，构造可访问的代理 URL
                workspace_files = result.get("workspace_files", [])
                if workspace_files:
                    # 构建文件访问 URL
                    owner_type = arguments.get("owner_type", "PERSONAL")
                    owner_id = arguments.get("owner_id", "")
                    conversation_id = arguments.get("conversation_id", "")

                    file_urls = []
                    for f in workspace_files:
                        # 使用 Agent-Engine 的代理端点
                        file_url = f"/api/v1/media/{owner_type}/{owner_id}/{conversation_id}/{f['name']}"
                        file_urls.append({
                            "name": f["name"],
                            "size": f["size"],
                            "mime_type": f["mime_type"],
                            "url": file_url,
                        })

                    # 在返回结果中附加文件 URL 信息
                    result["_workspace_file_urls"] = file_urls

                return json.dumps(result, ensure_ascii=False)
            else:
                return f"执行失败: {resp.status_code}"
    except Exception as e:
        return f"执行失败: {e}"


async def _execute_search(arguments: dict) -> str:
    """网络搜索"""
    return "搜索功能开发中"


async def _execute_media_send(arguments: dict) -> str:
    """发送多媒体内容到聊天"""
    import json
    import re

    url = arguments.get("url")
    base64_data = arguments.get("base64")
    media_type = arguments.get("media_type", "image")
    mime_type = arguments.get("mime_type")
    filename = arguments.get("filename")

    # 获取会话上下文用于构建代理 URL
    owner_type = arguments.get("owner_type", "PERSONAL")
    owner_id = arguments.get("owner_id", "")
    conversation_id = arguments.get("conversation_id", "")

    # 如果提供的是 base64 而非 URL，转换为 data URI
    if base64_data and not url:
        if not mime_type:
            if base64_data.startswith("/9j"):
                mime_type = "image/png"
            elif base64_data.startswith("iVBOR"):
                mime_type = "image/png"
            elif base64_data.startswith("R0lGO"):
                mime_type = "image/gif"
            elif base64_data.startswith("JVBER"):
                mime_type = "application/pdf"
            else:
                mime_type = f"{media_type}/generic"
        url = f"data:{mime_type};base64,{base64_data}"

    if not url:
        return json.dumps({"success": False, "error": "必须提供 url 或 base64 参数"})

    # URL 格式校验和转换
    if not url.startswith("data:"):
        # 检查是否是禁止的路径格式
        forbidden_patterns = [
            r'^/tmp/',           # /tmp/ 目录
            r'^/var/',           # /var/ 目录
            r'^/home/',          # /home/ 目录
            r'^file://',         # file:// 协议
            r'^/[^a]',           # 非 /api 开头的绝对路径
        ]

        for pattern in forbidden_patterns:
            if re.match(pattern, url):
                return json.dumps({
                    "success": False,
                    "error": f"无效的文件路径: {url}。请使用工作区相对路径（如 'chart.png'）或代理 URL（如 '/api/v1/media/...'）。生成的文件必须保存在 /workspace/ 目录。"
                })

        # 如果是相对路径（如 "chart.png" 或 "output/data.csv"），转换为代理 URL
        if not url.startswith('/') and not url.startswith('http'):
            if owner_id and conversation_id:
                url = f"/api/v1/media/{owner_type}/{owner_id}/{conversation_id}/{url}"
            else:
                return json.dumps({
                    "success": False,
                    "error": "无法构建媒体 URL：缺少会话上下文。请使用完整路径或 base64 数据。"
                })

        # 如果是绝对路径但不在工作区内，报错
        if url.startswith('/') and not url.startswith('/api/v1/media/'):
            return json.dumps({
                "success": False,
                "error": f"路径不在工作区内: {url}。请使用工作区相对路径（如 'chart.png'）。"
            })

    # 返回特殊的 media 类型结果
    result = {
        "success": True,
        "type": "media",
        "media_type": media_type,
        "url": url,
        "mime_type": mime_type or f"{media_type}/generic",
        "filename": filename,
    }
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════════════
# 节点函数
# ═══════════════════════════════════════════════════════════════════════════════════

async def call_llm_node(state: AgentState) -> dict:
    """
    LLM 调用节点。

    🐱 Auto Compact 集成：
    在调用 LLM 前执行上下文压缩，减少 token 消耗

    📝 System Prompt 注入：
    从 AgentState 获取 system_prompt，作为 SystemMessage 注入到消息列表开头
    """
    from langchain_openai import ChatOpenAI

    # ─────────────────────────────────────────────────────────────────────────
    # 🐱 Auto Compact: 在 LLM 调用前压缩上下文
    # ─────────────────────────────────────────────────────────────────────────
    messages = state["messages"]
    # V5: 使用 owner_type + owner_id 构建 context_id
    owner_type = state.get("owner_type", "")
    owner_id = state.get("owner_id", "")
    context_id = f"{owner_type}:{owner_id}" if owner_type else "default"
    conversation_id = state.get("conversation_id", "default")
    system_prompt = state.get("system_prompt", "")

    # 获取消息统计
    max_context = state.get("max_context", 2000)
    ctx_manager = get_context_manager(max_context)
    stats_before = ctx_manager.get_stats(messages)
    logger.debug(
        f"Before compact: {stats_before['message_count']} messages, "
        f"~{stats_before['token_count']} tokens"
    )

    # 执行上下文压缩
    compressed_messages = await ctx_manager.compact(
        messages, context_id, conversation_id
    )

    stats_after = ctx_manager.get_stats(compressed_messages)
    if stats_before['token_count'] != stats_after['token_count']:
        logger.info(
            f"Context compressed: {stats_before['token_count']} -> "
            f"{stats_after['token_count']} tokens "
            f"({stats_before['message_count']} -> {stats_after['message_count']} messages)"
        )

    # 使用压缩后的消息
    messages = compressed_messages

    # ─────────────────────────────────────────────────────────────────────────
    # 📝 System Prompt 注入：在消息列表开头插入 SystemMessage
    # ─────────────────────────────────────────────────────────────────────────
    llm_messages = []
    if system_prompt:
        llm_messages.append(SystemMessage(content=system_prompt))
        logger.info(f"[LLM] 注入系统提示词: {len(system_prompt)} 字符")
    llm_messages.extend(messages)
    # ─────────────────────────────────────────────────────────────────────────

    # 使用 state 中的模型配置，如果没有则使用默认配置
    model_id = state.get("model") or settings.llm_model
    temperature = state.get("temperature") if state.get("temperature") is not None else settings.llm_temperature
    logger.info(f"[LLM] 使用模型: {model_id}, 温度: {temperature}")

    llm = ChatOpenAI(
        model=model_id,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=temperature,
        streaming=True,
    ).bind_tools(BUILTIN_TOOLS)

    try:
        response = await asyncio.wait_for(
            llm.ainvoke(llm_messages),
            timeout=settings.llm_timeout,
        )
    except asyncio.TimeoutError:
        timeout_message = AIMessage(content="请求超时")
        timeout_tokens = estimate_message_tokens(timeout_message)
        return {
            "messages": [timeout_message],
            "context_stats": {
                "token_count": stats_before["token_count"],
                "max_context": max_context,
                "compressed": False,
                "read_tokens": stats_before["token_count"],
                "write_tokens": timeout_tokens,
                "message_tokens": timeout_tokens,
            }
        }

    current_stats = ctx_manager.get_stats(messages)
    breakdown = get_token_breakdown(messages, response.content)
    was_compressed = stats_before["token_count"] != current_stats["token_count"]
    return {
        "messages": [response],
        "context_stats": {
            "token_count": current_stats["token_count"],
            "max_context": max_context,
            "compressed": was_compressed,
            "read_tokens": breakdown["read_tokens"],
            "write_tokens": breakdown["write_tokens"],
            "message_tokens": breakdown["message_tokens"],
        }
    }


async def tool_call_node(state: AgentState) -> dict:
    """工具执行节点。

    V5: 支持 Follow-up 消息注入
    """
    messages = state["messages"]
    # V5: 使用 owner_type + owner_id 构建 context_id
    owner_type = state.get("owner_type", "PERSONAL")
    owner_id = state.get("owner_id", "")
    conversation_id = state.get("conversation_id", "")
    context_id = f"{owner_type}:{owner_id}" if owner_type else ""

    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            last_ai_msg = msg
            break

    if not last_ai_msg or not last_ai_msg.tool_calls:
        return {"messages": []}

    tool_messages = []
    for tool_call in last_ai_msg.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"].copy()  # 复制以避免修改原数据
        tool_id = tool_call["id"]

        # 注入 context_id 到 arguments（用于空间隔离显示/审计）
        # tenant_id 继续传纯 owner_id，避免 RAG/知识库链路把 PERSONAL:25 当成真实租户ID
        tool_args["context_id"] = context_id
        tool_args["tenant_id"] = owner_id

        # V5: 注入会话上下文（用于 sandbox 等需要工作区隔离的工具）
        tool_args["owner_type"] = owner_type
        tool_args["owner_id"] = owner_id
        tool_args["conversation_id"] = conversation_id

        # Agent 绑定的知识库白名单：只允许访问分配给当前 Agent 的知识库
        if tool_name in ("knowledge_retrieve", "knowledge_search"):
            allowed_kb_ids = [str(x) for x in (state.get("knowledge_base_ids") or []) if str(x).strip()]
            requested_kb_id = str(tool_args.get("knowledge_base_id") or "").strip()
            if not allowed_kb_ids:
                result = "知识库检索失败: 当前 Agent 未分配任何知识库"
                tool_messages.append(ToolMessage(content=result, tool_call_id=tool_id))
                continue
            if not requested_kb_id:
                tool_args["knowledge_base_id"] = allowed_kb_ids[0]
            elif requested_kb_id not in allowed_kb_ids:
                result = f"知识库检索失败: 无权访问知识库 {requested_kb_id}"
                tool_messages.append(ToolMessage(content=result, tool_call_id=tool_id))
                continue

        logger.info("执行工具: %s, context_id: %s", tool_name, context_id)

        result = await _execute_tool(tool_name, tool_args)

        tool_messages.append(ToolMessage(
            content=result,
            tool_call_id=tool_id,
        ))

    # V5: 检查并注入 follow-up 消息
    injected_followups: list[dict] = []  # 记录注入的 follow-up 信息
    if tool_messages:
        try:
            from app.control.followup_queue import get_followup_queue
            followup_queue = await get_followup_queue()
            pending = await followup_queue.get_pending(conversation_id)

            if pending:
                # 获取最后一个工具的名称
                last_tool_name = None
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        last_tool_call = msg.tool_calls[-1]
                        last_tool_name = last_tool_call.get("name", "unknown")
                        break

                # 构建 follow-up 提示文本
                followup_text = "\n\n[SYSTEM NOTICE] 用户在工具执行期间发送了新消息，请优先处理这些指令：\n"
                for i, f in enumerate(pending, 1):
                    followup_text += f"{i}. {f.content}\n"

                # 附加到最后一个工具结果
                last_msg = tool_messages[-1]
                tool_messages[-1] = ToolMessage(
                    content=last_msg.content + followup_text,
                    tool_call_id=last_msg.tool_call_id,
                )

                # 标记已注入并获取注入信息
                injected_msgs = await followup_queue.mark_all_injected(conversation_id, last_tool_name)
                injected_followups = [
                    {
                        "followup_id": m.followup_id,
                        "content": m.content,
                        "injected_tool": m.injected_tool,
                        "injected_at": m.injected_at,
                    }
                    for m in injected_msgs
                ]

                logger.info("[Followup] 注入了 %d 条 follow-up 消息到工具 %s", len(pending), last_tool_name)
        except Exception as e:
            logger.warning(f"[Followup] 注入 follow-up 失败: {e}")

    return {"messages": tool_messages, "followup_injected": injected_followups}


def should_continue(state: AgentState) -> Literal["tool_call", "end"]:
    """条件路由"""
    messages = state["messages"]
    last_msg = messages[-1] if messages else None
    
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_call"
    return "end"
