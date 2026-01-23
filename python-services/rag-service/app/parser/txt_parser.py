"""
app/parser/txt_parser.py — TXT 解析器
"""
import logging
from pathlib import Path

from app.parser.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)


class TxtParser(BaseParser):
    """TXT 文档解析器"""
    
    def supports(self, file_path: str) -> bool:
        """支持文本文件"""
        return Path(file_path).suffix.lower() in ['.txt', '.md', '.json', '.xml', '.html']
    
    def parse(self, file_path: str) -> ParseResult:
        """解析文本文件"""
        try:
            # 检测编码
            encoding = self._detect_encoding(file_path)
            
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            # 提取标题（从文件名或第一行）
            title = Path(file_path).stem
            
            # 尝试从内容中提取标题（MD的第一个 # 标题）
            if Path(file_path).suffix == '.md':
                lines = content.split('\n')
                for line in lines:
                    if line.strip().startswith('# '):
                        title = line.strip()[2:]
                        break
            
            metadata = {
                "source_file": file_path,
                "file_type": "text",
                "encoding": encoding,
                "char_count": len(content)
            }
            
            return ParseResult(
                content=content,
                title=title,
                metadata=metadata,
                success=True
            )
            
        except Exception as e:
            logger.error(f"TXT parsing error: {e}")
            return ParseResult(
                content="",
                title=Path(file_path).stem,
                metadata={"file_type": "text"},
                success=False,
                error_message=str(e)
            )
    
    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
        
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    f.read(1024)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        
        return 'utf-8'  # 默认
