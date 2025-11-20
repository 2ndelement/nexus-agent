"""
app/core/config.py — Settings（从 app.config re-export）

保持 app/core/config.py 路径约定，实现在 app/config.py。
"""
from app.config import Settings, settings  # noqa: F401

__all__ = ["Settings", "settings"]
