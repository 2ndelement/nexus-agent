"""
app/parser/pdf_parser.py — PDF 解析器
"""
import logging
from pathlib import Path

from app.parser.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """PDF 文档解析器"""
    
    def supports(self, file_path: str) -> bool:
        """支持 PDF 文件"""
        return Path(file_path).suffix.lower() in ['.pdf']
    
    def parse(self, file_path: str) -> ParseResult:
        """解析 PDF 文档"""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            text_parts = []
            metadata = {
                "page_count": len(doc),
                "source_file": file_path,
                "file_type": "pdf"
            }
            
            # 提取标题（从 metadata 或第一行）
            title = doc.metadata.get("title") or Path(file_path).stem
            
            for page_num, page in enumerate(doc):
                # 提取文本
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(f"[第{page_num + 1}页]
{text}")
                
                # 尝试提取表格（简化版）
                tables = page.find_tables()
                for table in tables:
                    table_text = table.extract()
                    if table_text:
                        text_parts.append(self._format_table(table_text))
            
            doc.close()
            
            content = "\n".join(text_parts)
            
            return ParseResult(
                content=content,
                title=title,
                metadata=metadata,
                success=True
            )
            
        except ImportError:
            return ParseResult(
                content="",
                title=Path(file_path).stem,
                metadata={"file_type": "pdf"},
                success=False,
                error_message="PyMuPDF not installed: pip install pymupdf"
            )
        except Exception as e:
            logger.error(f"PDF parsing error: {e}")
            return ParseResult(
                content="",
                title=Path(file_path).stem,
                metadata={"file_type": "pdf"},
                success=False,
                error_message=str(e)
            )
    
    def _format_table(self, table) -> str:
        """格式化表格为文本"""
        lines = []
        for row in table:
            line = " | ".join(str(cell) if cell else "" for cell in row)
            lines.append(line)
        return "\n表格:\n" + "\n".join(lines)
