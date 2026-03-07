"""
sandbox — 沙箱代码执行工具

V5 更新：
- 支持会话隔离（不同用户/组织文件互不可见）
- 支持工作区持久化（同一会话内文件持续可用）

在隔离容器中执行 Python/Bash 代码，返回执行结果。

执行限制：
- 语言：python, bash
- 超时：默认 30s，最长 120s
- 内存：256MB
- 网络：完全隔离
"""
from typing import Any, Dict, Optional
import httpx


SANDBOX_URL = "http://localhost:8020/execute"
TIMEOUT = 130  # 略大于 sandbox 最大超时


async def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    owner_type: str = "PERSONAL",
    owner_id: str = "",
    conversation_id: str = "",
) -> Dict[str, Any]:
    """
    调用 sandbox-service 执行代码。

    Args:
        code: 要执行的代码
        language: 语言 (python | bash)
        timeout: 超时秒数
        owner_type: 所有者类型 (PERSONAL | ORGANIZATION)
        owner_id: 所有者 ID (user_id 或 org_code)
        conversation_id: 会话 ID

    Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "duration_ms": int,
            "error": str | None,
            "workspace_files": list[str],  # V5 新增
            "session_id": str | None  # V5 新增
        }
    """
    if timeout > 120:
        timeout = 120

    payload = {
        "code": code,
        "language": language,
        "timeout": timeout,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "conversation_id": conversation_id,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(SANDBOX_URL, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Sandbox service timeout",
            "exit_code": -1,
            "duration_ms": timeout * 1000,
            "error": "Timeout connecting to sandbox service",
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "duration_ms": 0,
            "error": f"Sandbox service error: {str(e)}",
        }


# OpenAI Function Calling Schema
TOOL_DEFINITION = {
    "name": "sandbox_execute",
    "description": (
        "在隔离沙箱中执行 Python 或 Bash 代码并返回执行结果。"
        "适用于需要运行代码完成的任务，如数据分析、文件处理、自动化脚本等。"
        "注意：代码在完全隔离的容器中运行，无法访问外部网络。"
        "工作区内的文件在同一会话内持续可用。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的代码内容",
            },
            "language": {
                "type": "string",
                "enum": ["python", "bash"],
                "default": "python",
                "description": "代码语言：python 或 bash",
            },
            "timeout": {
                "type": "integer",
                "default": 30,
                "description": "超时秒数，最大 120",
            },
        },
        "required": ["code"],
    },
}
