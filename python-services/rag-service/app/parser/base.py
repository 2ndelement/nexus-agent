"""
app/parser/base.py — 解析器基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParseResult:
    """解析结果"""
    content: str                    # 提取的文本内容
    title: str                     # 文档标题
    metadata: dict                 # 元数据（页码、格式等）
    success: bool = True           # 是否成功
    error_message: Optional[str] = None  # 错误信息


class BaseParser(ABC):
    """文档解析器基类"""
    
    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """
        解析文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            ParseResult: 解析结果
        """
        pass
    
    @abstractmethod
    def supports(self, file_path: str) -> bool:
        """
        是否支持该文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否支持
        """
        pass
