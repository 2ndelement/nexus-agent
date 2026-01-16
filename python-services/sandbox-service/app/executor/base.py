"""
app/executor/base.py — 沙箱执行器基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: str | None = None


class BaseExecutor(ABC):
    """执行器抽象基类"""
    
    @abstractmethod
    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
    ) -> ExecutionResult:
        """
        执行代码并返回结果。
        
        Args:
            code: 要执行的代码
            language: 语言 (python | bash)
            timeout: 超时秒数
            
        Returns:
            ExecutionResult: 执行结果
        """
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        ...
