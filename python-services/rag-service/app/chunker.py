"""
app/chunker.py — 智能语义分块器

三层分块策略：
- 第一层：基于文档结构（章节标题、段落边界）规则切分
- 第二层：检查相邻chunk的语义连贯性，过短合并、跨页拼接
- 第三层：控制长度平衡，配合chunk overlap保持连续性
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """单个文档片段"""
    chunk_id: str          # 全局唯一 ID: sha256(doc_id + chunk_index)
    doc_id: str            # 来源文档 ID
    chunk_index: int       # 在文档内的序号（0-based）
    content: str           # 文本内容
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def make_chunk_id(cls, doc_id: str, chunk_index: int) -> str:
        raw = f"{doc_id}::{chunk_index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class TextSection:
    """文本段落/章节"""
    level: int           # 0=正文, 1=一级标题, 2=二级标题, etc.
    title: Optional[str] # 标题（正文为None）
    content: str         # 内容
    char_count: int      # 字符数


class SemanticChunker:
    """
    语义分块器 - 三层策略
    """

    def __init__(
        self,
        chunk_size: int = 1000,        # 目标 chunk 大小
        chunk_overlap: int = 150,      # 重叠字符数
        min_chunk_size: int = 200,     # 最小 chunk 大小（过短合并）
        max_chunk_size: int = 1500,   # 最大 chunk 大小（强制截断）
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk(
        self,
        doc_id: str,
        content: str,
        sections: list = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """
        执行三层分块策略
        """
        if metadata is None:
            metadata = {}

        if not content.strip():
            return [self._create_chunk(doc_id, 0, content, metadata)]

        # ========== 第一层：结构化切分 ==========
        structured_chunks = self._layer1_structural_split(content, sections)
        logger.debug(f"[Chunker] 第一层结构切分: {len(structured_chunks)} 块")

        # ========== 第二层：语义连贯性处理 ==========
        merged_chunks = self._layer2_semantic_merge(structured_chunks)
        logger.debug(f"[Chunker] 第二层语义合并: {len(merged_chunks)} 块")

        # ========== 第三层：长度平衡 ==========
        final_chunks = self._layer3_length_balance(merged_chunks)
        logger.debug(f"[Chunker] 第三层长度平衡: {len(final_chunks)} 块")

        # 转换为 Chunk 对象
        return [
            self._create_chunk(doc_id, i, chunk.content, metadata, chunk.title)
            for i, chunk in enumerate(final_chunks)
        ]

    def _layer1_structural_split(self, content: str, sections: list = None) -> list[TextSection]:
        """
        第一层：基于文档结构规则切分
        
        规则：
        - 按标题层级切分
        - 段落边界（空行）作为软分割
        - 表格和代码块保持完整
        """
        if sections and len(sections) > 0:
            # 如果有章节信息，按章节切分
            result = []
            for section in sections:
                if section.level > 0 and section.content:
                    # 标题后面的内容单独成块
                    result.append(TextSection(
                        level=section.level,
                        title=section.title,
                        content=section.content,
                        char_count=len(section.content),
                    ))
                elif section.content:
                    result.append(TextSection(
                        level=0,
                        title=None,
                        content=section.content,
                        char_count=len(section.content),
                    ))
            return result if result else self._split_by_paragraphs(content)

        # 没有章节信息，按段落切分
        return self._split_by_paragraphs(content)

    def _split_by_paragraphs(self, content: str) -> list[TextSection]:
        """按段落切分"""
        # 统一换行符
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        
        # 按空行分割段落
        paragraphs = re.split(r"\n\n+", content)
        
        result = []
        for para in paragraphs:
            para = para.strip()
            if para:
                # 检测是否为标题
                match = re.match(r"^(#{1,6})\s+(.+)$", para)
                if match:
                    level = len(match.group(1))
                    title = match.group(2).strip()
                    result.append(TextSection(level=level, title=title, content=para, char_count=len(para)))
                else:
                    result.append(TextSection(level=0, title=None, content=para, char_count=len(para)))
        
        return result if result else [TextSection(level=0, title=None, content=content, char_count=len(content))]

    def _layer2_semantic_merge(self, chunks: list[TextSection]) -> list[TextSection]:
        """
        第二层：语义连贯性处理
        
        规则：
        - 过短合并：小于 min_chunk_size，与相邻块合并
        - 上下文衔接：检查是否需要跨段落拼接
        """
        if not chunks:
            return chunks

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            current = chunks[i]
            previous = result[-1]

            # 计算合并后的长度
            merged_length = previous.char_count + current.char_count

            # 规则1：过短合并
            if previous.char_count < self.min_chunk_size:
                # 与前一块合并
                merged_content = previous.content + "\n\n" + current.content
                result[-1] = TextSection(
                    level=min(previous.level, current.level),
                    title=previous.title,
                    content=merged_content,
                    char_count=len(merged_content),
                )
                continue

            # 规则2：检查语义连贯性
            # 如果两个块主题相关，可以合并
            if self._is_semantically_related(previous.content, current.content):
                if merged_length <= self.chunk_size * 1.2:  # 允许20%弹性
                    merged_content = previous.content + "\n\n" + current.content
                    result[-1] = TextSection(
                        level=min(previous.level, current.level),
                        title=previous.title,
                        content=merged_content,
                        char_count=len(merged_content),
                    )
                    continue

            # 不合并，添加新块
            result.append(current)

        return result

    def _is_semantically_related(self, text1: str, text2: str) -> bool:
        """
        检查两段文本是否语义相关
        
        简单规则：
        - 有相同关键词
        - 上一段以冒号/引号结尾（未完句）
        """
        # 规则1：未完句（以冒号、引号结尾）
        if text1.strip().endswith((":","：",""","'","《","【","[")):
            return True

        # 规则2：共享关键词（简单实现：提取名词）
        # 简化：检查是否有连续相同的3个字
        text1_set = set(text1[i:i+3] for i in range(len(text1)-2))
        text2_set = set(text2[i:i+3] for i in range(len(text2)-2))
        
        if text1_set & text2_set:
            return True

        return False

    def _layer3_length_balance(self, chunks: list[TextSection]) -> list[TextSection]:
        """
        第三层：长度平衡 + overlap
        
        规则：
        - 超过 max_chunk_size 强制截断
        - 目标大小：chunk_size ± 20%
        - 添加 overlap 保持上下文连续
        """
        result = []
        buffer = ""  # overlap 缓冲区

        for chunk in chunks:
            content = chunk.content
            
            # 如果内容太长，强制截断
            while len(content) > self.max_chunk_size:
                # 找到合适截断点（句号、逗号、段落）
                breakpoint = self._find_breakpoint(content[:self.max_chunk_size])
                
                result.append(TextSection(
                    level=chunk.level,
                    title=chunk.title,
                    content=content[:breakpoint],
                    char_count=breakpoint,
                ))
                
                # overlap 部分
                buffer = content[breakpoint - self.chunk_overlap:breakpoint]
                content = content[breakpoint:]

            # 处理剩余内容
            if buffer:
                content = buffer + "\n\n" + content
                buffer = ""

            # 检查是否需要与下一块合并
            if len(content) < self.min_chunk_size:
                buffer = content  # 暂存，与下一块合并
            else:
                result.append(TextSection(
                    level=chunk.level,
                    title=chunk.title,
                    content=content,
                    char_count=len(content),
                ))

        # 处理最后剩余的 buffer
        if buffer:
            if result:
                # 合并到最后一块
                last = result[-1]
                result[-1] = TextSection(
                    level=last.level,
                    title=last.title,
                    content=last.content + "\n\n" + buffer,
                    char_count=last.char_count + len(buffer),
                )
            else:
                result.append(TextSection(level=0, title=None, content=buffer, char_count=len(buffer)))

        return result

    def _find_breakpoint(self, text: str) -> int:
        """找到合适的截断点"""
        # 优先按句子切分
        # 句号、问号、感叹号、分号
        for punct in ["。", "！", "？", "；", "\. ", "! ", "? ", "; "]:
            pos = text.rfind(punct)
            if pos > self.chunk_size * 0.5:  # 至少50%才切
                return pos + len(punct)

        # 按逗号切分
        for punct in [", ", "，"]:
            pos = text.rfind(punct)
            if pos > self.chunk_size * 0.5:
                return pos + len(punct)

        # 按行切分
        pos = text.rfind("\n")
        if pos > self.chunk_size * 0.5:
            return pos + 1

        # 强制截断
        return len(text)

    def _create_chunk(
        self,
        doc_id: str,
        index: int,
        content: str,
        metadata: dict,
        title: str = None,
    ) -> Chunk:
        """创建 Chunk 对象"""
        chunk_metadata = dict(metadata)
        if title:
            chunk_metadata["section_title"] = title
        
        return Chunk(
            chunk_id=Chunk.make_chunk_id(doc_id, index),
            doc_id=doc_id,
            chunk_index=index,
            content=content,
            metadata=chunk_metadata,
        )


# 兼容旧接口
def chunk_document(
    doc_id: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[Chunk]:
    """
    文档分块（兼容旧接口）
    
    使用语义分块器，支持三层策略
    """
    chunker = SemanticChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return chunker.chunk(doc_id, content, metadata=metadata)
