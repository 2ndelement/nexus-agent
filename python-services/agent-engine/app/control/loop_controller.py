"""
app/control/loop_controller.py — Agent Loop 控制器

功能：
- 控制最大循环次数
- 达到上限后强制最终输出
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LoopConfig:
    """循环配置"""
    max_iterations: int = 30
    force_end_prompt: str = """
你已达到最大工具调用次数（{max_iterations}次）。
请基于之前的分析和工具调用结果，直接回答用户的问题。
不要调用任何新工具，给出最终答案。
"""


class LoopController:
    """
    Agent Loop 控制器
    
    用于：
    1. 跟踪迭代次数
    2. 判断是否强制结束
    3. 生成强制输出 Prompt
    """

    def __init__(self, max_iterations: int = 30):
        self.max_iterations = max_iterations
        self.force_end_prompt = LoopConfig.force_end_prompt

    def should_force_end(self, iteration: int) -> bool:
        """
        判断是否应该强制结束
        
        Args:
            iteration: 当前迭代次数（从1开始）
        
        Returns:
            是否强制结束
        """
        return iteration >= self.max_iterations

    def get_force_end_prompt(self) -> str:
        """
        获取强制结束 Prompt
        
        Returns:
            格式化后的强制结束提示
        """
        return self.force_end_prompt.format(max_iterations=self.max_iterations)

    def get_remaining_iterations(self, iteration: int) -> int:
        """
        获取剩余迭代次数
        
        Args:
            iteration: 当前迭代次数
        
        Returns:
            剩余可迭代次数
        """
        return max(0, self.max_iterations - iteration)


# 全局单例
_loop_controller: Optional[LoopController] = None


def get_loop_controller() -> LoopController:
    """获取 Loop 控制器"""
    global _loop_controller
    if _loop_controller is None:
        from app.config import settings
        _loop_controller = LoopController(
            max_iterations=getattr(settings, 'max_loop_iterations', 30)
        )
    return _loop_controller
