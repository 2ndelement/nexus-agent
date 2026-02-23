"""
app/agent/context_manager.py — Auto Compact Context Manager

实现三层压缩策略：
1. Micro Compact (Layer 1) - 每轮静默压缩旧 tool 结果
2. Auto Transcript (Layer 2) - 超阈值时保存转录 + LLM 摘要  
3. Halving Truncation (Layer 3) - 兜底截断

作者：帕托莉 🐱
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AutoCompactConfig:
    """Auto Compact 配置（动态阈值基于 max_context 计算）"""

    # 基础配置
    max_context: int = 128000  # 最大上下文token数（默认128k）

    # Layer 1: Micro Compact
    micro_compact_enabled: bool = True
    micro_compact_keep_recent: int = 3  # 保留最近 N 个 tool 结果

    # Layer 2: Auto Transcript
    use_auto_transcript: bool = True
    transcript_dir: str = "/tmp/nexus-transcripts"

    # Layer 3: Halving Truncation (兜底)
    use_halving_truncation: bool = True
    halving_keep_ratio: float = 0.5  # 截断后保留比例

    # LLM 摘要配置
    llm_model: str = "gpt-4o"
    summary_instruction: str = """基于对话历史，生成简洁摘要，包含：

1. **已完成任务**：完成了什么？使用了哪些工具？结果如何？

2. **当前状态**：当前状态如何？Agent 正在做什么？

3. **关键决策**：做了哪些重要决策？选择了什么方法/拒绝了什么方法？

4. **待办事项**：还有什么需要完成？有什么阻塞或依赖？

5. **重要上下文**：讨论了哪些重要事实、偏好或约束？

请用与对话相同的语言撰写摘要。保持简洁但保留关键细节。"""

    @property
    def transcript_threshold(self) -> int:
        """transcript_threshold = max_context * 0.625（约 80k for 128k context）"""
        return int(self.max_context * 0.625)

    @property
    def halving_threshold(self) -> int:
        """halving_threshold = max_context * 0.8（约 100k for 128k context）"""
        return int(self.max_context * 0.8)
    
    # LLM 摘要配置
    llm_model: str = "gpt-4o"
    summary_instruction: str = """基于对话历史，生成简洁摘要，包含：

1. **已完成任务**：完成了什么？使用了哪些工具？结果如何？

2. **当前状态**：当前状态如何？Agent 正在做什么？

3. **关键决策**：做了哪些重要决策？选择了什么方法/拒绝了什么方法？

4. **待办事项**：还有什么需要完成？有什么阻塞或依赖？

5. **重要上下文**：讨论了哪些重要事实、偏好或约束？

请用与对话相同的语言撰写摘要。保持简洁但保留关键细节。"""


# ═══════════════════════════════════════════════════════════════════════════════
# 消息工具函数
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_tokens(value: object) -> int:
    """估算任意消息片段的 token 数。

    当前先用稳定的近似值，统一覆盖文本、JSON、tool args/result。
    后续如果接入真实 tokenizer，可只替换这里。
    """
    total_chars = 0

    def add_text(inner: object) -> None:
        nonlocal total_chars
        if inner is None:
            return
        if isinstance(inner, str):
            total_chars += len(inner)
        elif isinstance(inner, (int, float, bool)):
            total_chars += len(str(inner))
        elif isinstance(inner, dict):
            for k, v in inner.items():
                total_chars += len(str(k))
                add_text(v)
        elif isinstance(inner, list):
            for item in inner:
                add_text(item)
        else:
            total_chars += len(str(inner))

    add_text(value)
    if total_chars <= 0:
        return 0
    return max(1, int(total_chars / 2.5))


def estimate_message_tokens(msg: BaseMessage) -> int:
    """估算单条消息 token。"""
    parts: list[object] = []
    if hasattr(msg, "content"):
        parts.append(msg.content)
    if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
        parts.append(msg.tool_calls)
    if isinstance(msg, ToolMessage):
        parts.append(getattr(msg, "tool_call_id", None))
    return estimate_tokens(parts)


def count_messages_tokens(messages: list[BaseMessage]) -> int:
    """估算消息列表 token 总数。"""
    return sum(estimate_message_tokens(msg) for msg in messages)


def get_token_breakdown(messages: list[BaseMessage], assistant_output: object | None = None) -> dict:
    """返回上下文/读写/当前消息 token 拆分。"""
    read_tokens = count_messages_tokens(messages)
    write_tokens = estimate_tokens(assistant_output) if assistant_output is not None else 0
    return {
        "token_count": read_tokens,
        "read_tokens": read_tokens,
        "write_tokens": write_tokens,
        "message_tokens": write_tokens,
    }


def get_message_token_counts(messages: list[BaseMessage]) -> list[int]:
    """返回每条消息的 token 估算。"""
    return [estimate_message_tokens(msg) for msg in messages]



def serialize_message(msg: BaseMessage) -> dict:
    """将消息序列化为字典（用于保存转录）"""
    result = {
        "type": type(msg).__name__,
        "content": msg.content if hasattr(msg, "content") else str(msg),
    }
    
    if isinstance(msg, AIMessage) and msg.tool_calls:
        result["tool_calls"] = [
            {"name": tc["name"], "args": tc["args"]}
            for tc in msg.tool_calls
        ]
    
    if isinstance(msg, ToolMessage):
        result["tool_call_id"] = msg.tool_call_id
    
    return result


def deserialize_message(data: dict) -> BaseMessage:
    """从字典反序列化消息"""
    msg_type = data.get("type", "HumanMessage")
    content = data.get("content", "")
    
    if msg_type == "AIMessage":
        return AIMessage(content=content)
    elif msg_type == "ToolMessage":
        return ToolMessage(content=content, tool_call_id=data.get("tool_call_id", ""))
    elif msg_type == "SystemMessage":
        return SystemMessage(content=content)
    else:
        return HumanMessage(content=content)


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 1: Micro Compact
# ═══════════════════════════════════════════════════════════════════════════════

def micro_compact(messages: list[BaseMessage], keep_recent: int = 3) -> list[BaseMessage]:
    """
    Micro Compact - 每轮静默压缩旧 tool 结果
    
    策略：将旧的冗长 tool 结果替换为简短引用，保留最近 N 个完整结果
    
    Args:
        messages: 消息列表
        keep_recent: 保留最近 N 个 tool 结果
        
    Returns:
        压缩后的消息列表
    """
    result = []
    tool_result_count = 0
    
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_result_count += 1
            
            # 保留最近的 tool 结果
            if tool_result_count > keep_recent:
                # 检查是否需要压缩
                content = msg.content
                if isinstance(content, str) and len(content) > 100:
                    # 尝试从 tool_call_id 获取工具名称
                    tool_name = f"tool_{msg.tool_call_id[:8]}" if msg.tool_call_id else "unknown"
                    # 替换为简短引用
                    result.append(ToolMessage(
                        content=f"[使用 {tool_name} 的结果，已压缩]",
                        tool_call_id=msg.tool_call_id,
                    ))
                    logger.debug(f"Micro compact: 压缩 tool 结果 {msg.tool_call_id[:8]}")
                    continue
        
        result.append(msg)
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 2: Auto Transcript Compress
# ═══════════════════════════════════════════════════════════════════════════════

class TranscriptCompressor:
    """转录压缩器 - 保存完整历史 + LLM 摘要"""
    
    def __init__(self, config: AutoCompactConfig):
        self.config = config
        self._ensure_dir()
    
    def _ensure_dir(self):
        """确保转录目录存在"""
        os.makedirs(self.config.transcript_dir, exist_ok=True)
    
    def save_transcript(
        self, 
        messages: list[BaseMessage], 
        tenant_id: str, 
        conversation_id: str
    ) -> str:
        """
        保存完整转录到文件
        
        Args:
            messages: 消息列表
            tenant_id: 租户 ID
            conversation_id: 会话 ID
            
        Returns:
            转录文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transcript_{tenant_id}_{conversation_id}_{timestamp}.jsonl"
        filepath = os.path.join(self.config.transcript_dir, filename)
        
        lines = []
        for msg in messages:
            lines.append(json.dumps(serialize_message(msg), ensure_ascii=False))
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        
        logger.info(f"转录已保存: {filepath} ({len(messages)} 条消息)")
        return filepath
    
    async def generate_summary(
        self, 
        messages: list[BaseMessage],
        tenant_id: str,
        conversation_id: str,
    ) -> str:
        """
        使用 LLM 生成摘要（需要外部调用）
        
        这个方法生成摘要提示，实际 LLM 调用由外部完成
        
        Returns:
            摘要提示文本
        """
        # 转换为可读文本
        conversation_text = self._messages_to_text(messages)
        
        # 构建摘要请求
        summary_request = f"""{self.config.summary_instruction}

对话内容:
---
{conversation_text[:self.config.transcript_threshold]}
---
"""
        
        return summary_request
    
    def _messages_to_text(self, messages: list[BaseMessage]) -> str:
        """将消息转换为可读文本"""
        lines = []
        for msg in messages:
            role = type(msg).__name__.replace("Message", "")
            content = msg.content if hasattr(msg, "content") else str(msg)
            
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_result":
                            text_parts.append(f"[工具结果]")
                content = "\n".join(text_parts)
            
            if isinstance(content, str) and len(content) > 500:
                content = content[:500] + "..."
            
            lines.append(f"[{role}] {content}")
        
        return "\n\n".join(lines)
    
    def build_compressed_messages(
        self,
        original_count: int,
        transcript_path: str,
        summary: str,
        recent_messages: list[BaseMessage],
        system_messages: list[BaseMessage],
    ) -> list[BaseMessage]:
        """
        构建压缩后的消息列表
        
        结构:
        1. System messages (保留)
        2. 压缩摘要消息
        3. 最近的 N 条消息
        """
        result = []
        
        # 保留系统消息
        result.extend(system_messages)
        
        # 添加压缩说明
        compression_notice = (
            f"[对话历史已压缩。完整转录: {transcript_path}]\n\n"
            f"原始消息数: {original_count}"
        )
        result.append(HumanMessage(content=compression_notice))
        
        # 添加摘要
        if summary:
            result.append(AIMessage(content=summary))
        
        # 添加最近的确认消息
        result.append(AIMessage(
            content="我已了解之前的对话摘要。如果需要查看完整历史，可访问上述转录文件。"
        ))
        
        # 添加最近的原始消息（保留最新上下文）
        result.extend(recent_messages)
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Layer 3: Halving Truncation
# ═══════════════════════════════════════════════════════════════════════════════

def halving_truncation(
    messages: list[BaseMessage], 
    keep_ratio: float = 0.5
) -> list[BaseMessage]:
    """
    折半截断 - 兜底策略
    
    当消息过长时，保留后半部分（最新部分）
    
    Args:
        messages: 消息列表
        keep_ratio: 保留比例
        
    Returns:
        截断后的消息列表
    """
    if len(messages) <= 4:
        return messages
    
    keep_count = max(2, int(len(messages) * keep_ratio))
    
    # 保留后半部分（最新消息）
    result = messages[-keep_count:]
    
    logger.info(f"Halving truncation: {len(messages)} -> {keep_count} 条消息")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 主压缩入口
# ═══════════════════════════════════════════════════════════════════════════════

class ContextManager:
    """
    上下文管理器 - 整合三层压缩策略
    
    使用方式:
    ```python
    manager = ContextManager(config)
    compressed = await manager.compact(messages, tenant_id, conversation_id)
    ```
    """
    
    def __init__(self, config: Optional[AutoCompactConfig] = None):
        self.config = config or AutoCompactConfig()
        self.transcript_compressor = TranscriptCompressor(self.config)
    
    async def compact(
        self,
        messages: list[BaseMessage],
        tenant_id: str,
        conversation_id: str,
    ) -> list[BaseMessage]:
        """
        执行上下文压缩
        
        按顺序执行三层策略：
        1. Micro Compact (每轮)
        2. Auto Transcript (超阈值)
        3. Halving Truncation (兜底)
        
        Args:
            messages: 消息列表
            tenant_id: 租户 ID
            conversation_id: 会话 ID
            
        Returns:
            压缩后的消息列表
        """
        original_count = len(messages)
        original_tokens = count_messages_tokens(messages)
        
        logger.info(
            f"ContextManager.compact: {original_count} 条消息, "
            f"约 {original_tokens} tokens"
        )
        
        result = messages
        
        # ─────────────────────────────────────────────────────────────────────
        # Layer 1: Micro Compact
        # ─────────────────────────────────────────────────────────────────────
        if self.config.micro_compact_enabled:
            result = micro_compact(result, self.config.micro_compact_keep_recent)
            logger.debug(f"After micro compact: {len(result)} 条消息")
        
        # ─────────────────────────────────────────────────────────────────────
        # Layer 2: Auto Transcript (需要 LLM 调用，这里标记为待实现)
        # ─────────────────────────────────────────────────────────────────────
        current_tokens = count_messages_tokens(result)
        
        if (self.config.use_auto_transcript and 
            current_tokens > self.config.transcript_threshold):
            
            # 保存转录
            transcript_path = self.transcript_compressor.save_transcript(
                messages, tenant_id, conversation_id
            )
            
            # 提取系统消息和最近消息
            system_messages = [m for m in result if isinstance(m, SystemMessage)]
            non_system = [m for m in result if not isinstance(m, SystemMessage)]
            
            # 保留最近 4 条（保持最新上下文）
            keep_recent = 4
            recent = non_system[-keep_recent:] if len(non_system) > keep_recent else non_system
            
            # 生成压缩消息列表
            result = self.transcript_compressor.build_compressed_messages(
                original_count=original_count,
                transcript_path=transcript_path,
                summary="[LLM 摘要待生成]",  # 实际由外部 LLM 调用填充
                recent_messages=recent,
                system_messages=system_messages,
            )
            
            logger.info(f"After transcript compress: {len(result)} 条消息")
        
        # ─────────────────────────────────────────────────────────────────────
        # Layer 3: Halving Truncation (兜底)
        # ─────────────────────────────────────────────────────────────────────
        current_tokens = count_messages_tokens(result)
        
        if self.config.use_halving_truncation and current_tokens > self.config.halving_threshold:
            result = halving_truncation(result, self.config.halving_keep_ratio)
            logger.info(f"After halving truncation: {len(result)} 条消息")
        
        final_tokens = count_messages_tokens(result)
        compression_ratio = len(result) / original_count if original_count > 0 else 1.0
        
        logger.info(
            f"Compression complete: {original_count} -> {len(result)} "
            f"({compression_ratio:.1%}), tokens: {original_tokens} -> {final_tokens}"
        )
        
        return result
    
    def get_stats(self, messages: list[BaseMessage]) -> dict:
        """获取消息统计"""
        token_count = count_messages_tokens(messages)
        return {
            "message_count": len(messages),
            "token_count": token_count,
            "max_context": self.config.max_context,
            "transcript_threshold": self.config.transcript_threshold,
            "halving_threshold": self.config.halving_threshold,
            "tool_result_count": sum(1 for m in messages if isinstance(m, ToolMessage)),
        }
