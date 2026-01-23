"""
app/parser/document_parser.py — 统一文档解析器
"""
import logging
from pathlib import Path

from app.parser.base import BaseParser, ParseResult
from app.parser.pdf_parser import PDFParser
from app.parser.word_parser import WordParser
from app.parser.ppt_parser import PPTParser
from app.parser.txt_parser import TxtParser

logger = logging.getLogger(__name__)


class DocumentParser:
    """
    统一文档解析器
    
    自动识别文件类型并调用对应的解析器
    
    支持格式：
    - PDF (.pdf)
    - Word (.docx, .doc)
    - PPT (.pptx, .ppt)
    - 文本 (.txt, .md, .json, .xml, .html)
    """
    
    def __init__(self):
        self.parsers: list[BaseParser] = [
            PDFParser(),
            WordParser(),
            PPTParser(),
            TxtParser(),
        ]
    
    def parse(self, file_path: str) -> ParseResult:
        """
        解析文档（自动识别类型）
        
        Args:
            file_path: 文件路径
            
        Returns:
            ParseResult: 解析结果
        """
        # 查找支持该文件的解析器
        for parser in self.parsers:
            if parser.supports(file_path):
                logger.info(f"Using parser {parser.__class__.__name__} for {file_path}")
                return parser.parse(file_path)
        
        # 未找到支持的解析器
        return ParseResult(
            content="",
            title=Path(file_path).stem,
            metadata={"source_file": file_path},
            success=False,
            error_message=f"Unsupported file type: {Path(file_path).suffix}"
        )
    
    def parse_bytes(self, file_bytes: bytes, file_name: str) -> ParseResult:
        """
        从字节流解析文档
        
        Args:
            file_bytes: 文件字节内容
            file_name: 文件名（用于识别类型）
            
        Returns:
            ParseResult: 解析结果
        """
        import tempfile
        
        # 写入临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_name).suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        try:
            return self.parse(tmp_path)
        finally:
            # 清理临时文件
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass
