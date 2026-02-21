"""
e2b_client.py — e2b API 封装

支持：
1. 沙箱创建/销毁
2. 命令执行
3. 文件上传/下载
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FileUpload:
    """上传文件"""
    path: str
    content: str  # base64 编码

    def decode(self) -> bytes:
        return base64.b64decode(self.content)

    def write(self, path: str = None):
        path = path or self.path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.decode())


@dataclass
class CommandResult:
    """命令执行结果"""
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: int


class E2BClient:
    """
    e2b API 客户端
    
    环境变量：
    - E2B_API_KEY: API Key
    - E2B_TEMPLATE: 沙箱模板
    - E2B_TIMEOUT: 超时时间（秒）
    """
    
    BASE_URL = "https://api.aita.moe/v1"

    def __init__(self, api_key: str = None, template: str = None):
        self.api_key = api_key or os.getenv("E2B_API_KEY")
        self.template = template or os.getenv("E2B_TEMPLATE", "python")
        self.timeout = int(os.getenv("E2B_TIMEOUT", "300"))
        self._base_url = "https://api.e2b.dev/v1"
        
    async def create_sandbox(self) -> str:
        """创建沙箱，返回 sandbox_id"""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/sandboxes",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"template": self.template},
                timeout=30
            )
            data = resp.json()
            return data["sandbox_id"]

    async def destroy_sandbox(self, sandbox_id: str):
        """销毁沙箱"""
        import httpx
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{self._base_url}/sandboxes/{sandbox_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )

    async def execute_command(
        self,
        sandbox_id: str,
        cmd: str,
        cwd: str = "/home/user"
    ) -> CommandResult:
        """执行命令"""
        import httpx
        start = time.time()
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/sandboxes/{sandbox_id}/commands",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"cmd": cmd, "cwd": cwd},
                timeout=self.timeout
            )
            data = resp.json()
            
            # 轮询结果
            cmd_id = data["command_id"]
            while True:
                result_resp = await client.get(
                    f"{self._base_url}/sandboxes/{sandbox_id}/commands/{cmd_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
                result = result_resp.json()
                if result.get("status") == "success":
                    elapsed = int((time.time() - start) * 1000)
                    return CommandResult(
                        stdout=result.get("stdout", ""),
                        stderr=result.get("stderr", ""),
                        exit_code=result.get("exit_code", 0),
                        elapsed_ms=elapsed
                    )
                await asyncio.sleep(0.5)

    async def upload_file(
        self,
        sandbox_id: str,
        path: str,
        content: bytes
    ) -> bool:
        """上传文件到沙箱"""
        import httpx
        b64 = base64.b64encode(content).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/sandboxes/{sandbox_id}/files",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"path": path, "content": b64},
                timeout=60
            )
            return resp.status_code == 200

    async def download_file(
        self,
        sandbox_id: str,
        path: str
    ) -> bytes:
        """下载沙箱文件"""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/sandboxes/{sandbox_id}/files/{path.lstrip('/')}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=60
            )
            data = resp.json()
            return base64.b64decode(data["content"])


class E2BPoolManager:
    """e2b 沙箱池管理器"""
    
    def __init__(self):
        self._pools: dict[str, str] = {}  # tenant_id -> sandbox_id
        self._client = E2BClient()
    
    async def get_sandbox(self, tenant_id: str) -> str:
        """获取租户的沙箱"""
        if tenant_id in self._pools:
            return self._pools[tenant_id]
        
        sandbox_id = await self._client.create_sandbox()
        self._pools[tenant_id] = sandbox_id
        return sandbox_id
    
    async def execute(
        self,
        tenant_id: str,
        cmd: str,
        cwd: str = "/home/user"
    ) -> CommandResult:
        sandbox_id = await self.get_sandbox(tenant_id)
        return await self._client.execute_command(sandbox_id, cmd, cwd)
    
    async def upload(
        self,
        tenant_id: str,
        path: str,
        content: bytes
    ) -> bool:
        sandbox_id = await self.get_sandbox(tenant_id)
        return await self._client.upload_file(sandbox_id, path, content)
    
    async def download(
        self,
        tenant_id: str,
        path: str
    ) -> bytes:
        sandbox_id = await self.get_sandbox(tenant_id)
        return await self._client.download_file(sandbox_id, path)
    
    async def destroy(self, tenant_id: str):
        """销毁租户沙箱"""
        if tenant_id in self._pools:
            await self._client.destroy_sandbox(self._pools[tenant_id])
            del self._pools[tenant_id]
