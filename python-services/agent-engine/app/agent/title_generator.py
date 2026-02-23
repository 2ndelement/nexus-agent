"""
对话标题生成器

根据首轮对话内容自动生成有意义的标题。
"""
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


async def generate_title(user_message: str, assistant_response: str) -> str | None:
    """
    根据首轮对话生成标题

    Args:
        user_message: 用户消息
        assistant_response: AI 回复

    Returns:
        生成的标题（10-20 字），失败返回 None
    """
    try:
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

        # 截取消息以避免过长
        user_msg_truncated = user_message[:200] if len(user_message) > 200 else user_message
        assistant_msg_truncated = assistant_response[:300] if len(assistant_response) > 300 else assistant_response

        prompt = f"""根据以下对话生成一个简短的中文标题（10-20字）：

用户: {user_msg_truncated}
助手: {assistant_msg_truncated}

要求：
1. 标题应概括对话主题
2. 简洁明了，不超过20个字
3. 只输出标题文字，不要有引号、标点或其他格式"""

        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.3,
        )

        title = response.choices[0].message.content.strip()

        # 清理标题：移除可能的引号
        title = title.strip('"\'""''')

        # 限制长度
        if len(title) > 30:
            title = title[:30]

        logger.info(f"[TitleGenerator] 生成标题: {title}")
        return title

    except Exception as e:
        logger.error(f"[TitleGenerator] 生成标题失败: {e}")
        return None
