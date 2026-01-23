"""
app/parser/__init__.py — 文档解析器模块
"""
from app.parser.base import BaseParser, ParseResult
from app.parser.pdf_parser import PDFParser
from app.parser.word_parser import WordParser
from app.parser.ppt_parser import PPTParser
from app.parser.txt_parser import TxtParser
from app.parser.document_parser import DocumentParser

__all__ = [
    "BaseParser",
    "ParseResult", 
    "PDFParser",
    "WordParser", 
    "PPTParser",
    "TxtParser",
    "DocumentParser",
]
