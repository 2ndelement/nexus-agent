"""
skill_browser.py — Skill 浏览器工具

支持两种存储类型：
1. oss: 阿里云 OSS
2. local: 本地文件系统

工具参数：
- action: list/read/read_file/tree
- tenant_id: 租户ID
- skill_name: 技能名称
- file_path: 文件路径
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseStorage(ABC):
    """存储抽象基类"""
    
    @abstractmethod
    def list_skills(self, tenant_id: str) -> list[str]:
        """列出租户的所有 Skills"""
        pass
    
    @abstractmethod
    def read_skill_md(self, tenant_id: str, skill_name: str) -> str:
        """读取 SKILL.md 内容"""
        pass
    
    @abstractmethod
    def read_file(self, tenant_id: str, skill_name: str, file_path: str) -> str:
        """读取文件内容"""
        pass
    
    @abstractmethod
    def list_files(self, tenant_id: str, skill_name: str, sub_path: str = "") -> list[dict]:
        """列出技能目录下的文件"""
        pass


class OSSStorage(BaseStorage):
    """阿里云 OSS 存储"""
    
    def __init__(self, bucket: str, region: str, ak: str = None, sk: str = None):
        self.bucket = bucket
        self.region = region
        self.ak = ak or os.getenv("OSS_AK")
        self.sk = sk or os.getenv("OSS_SK")
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            try:
                import oss2
                auth = oss2.Auth(self.ak, self.sk)
                self._client = oss2.Bucket(
                    auth,
                    f"{self.bucket}.oss-{self.region}.aliyuncs.com"
                )
            except ImportError:
                logger.error("请安装 oss2: pip install oss2")
                raise ImportError("oss2 未安装")
        return self._client
    
    def _skill_prefix(self, tenant_id: str) -> str:
        return f"skills/{tenant_id}/"
    
    def list_skills(self, tenant_id: str) -> list[str]:
        client = self._get_client()
        prefix = self._skill_prefix(tenant_id)
        
        skills = set()
        try:
            for obj in oss2.ObjectIterator(client, prefix=prefix, delimiter="/"):
                if obj.key.endswith("/SKILL.md"):
                    # 提取 skill 名称
                    key = obj.key[len(prefix):]
                    skill_name = key.rstrip("/").split("/")[0]
                    if skill_name:
                        skills.add(skill_name)
        except Exception as e:
            logger.error(f"OSS list_skills 失败: {e}")
        
        return sorted(list(skills))
    
    def read_skill_md(self, tenant_id: str, skill_name: str) -> str:
        key = f"skills/{tenant_id}/skills/{skill_name}/SKILL.md"
        client = self._get_client()
        try:
            content = client.get_object(key).read().decode("utf-8")
            return content
        except Exception as e:
            logger.error(f"OSS read_skill_md 失败: {e}")
            return f"读取失败: {e}"
    
    def read_file(self, tenant_id: str, skill_name: str, file_path: str) -> str:
        key = f"skills/{tenant_id}/skills/{skill_name}/{file_path}"
        client = self._get_client()
        try:
            return client.get_object(key).read().decode("utf-8")
        except Exception as e:
            logger.error(f"OSS read_file 失败: {e}")
            return f"读取失败: {e}"
    
    def list_files(self, tenant_id: str, skill_name: str, sub_path: str = "") -> list[dict]:
        prefix = f"skills/{tenant_id}/skills/{skill_name}/{sub_path}"
        client = self._get_client()
        files = []
        try:
            for obj in oss2.ObjectIterator(client, prefix=prefix):
                rel_path = obj.key[len(f"skills/{tenant_id}/skills/{skill_name}/"):]
                files.append({
                    "path": rel_path,
                    "size": obj.size,
                    "is_dir": obj.is_prefix(),
                })
        except Exception as e:
            logger.error(f"OSS list_files 失败: {e}")
        return files


class LocalStorage(BaseStorage):
    """本地文件系统存储"""
    
    def __init__(self, base_path: str = "/data/skills"):
        self.base_path = base_path
    
    def _skill_path(self, tenant_id: str) -> str:
        return os.path.join(self.base_path, tenant_id, "skills")
    
    def list_skills(self, tenant_id: str) -> list[str]:
        skill_root = self._skill_path(tenant_id)
        if not os.path.exists(skill_root):
            return []
        
        skills = []
        try:
            for name in os.listdir(skill_root):
                skill_dir = os.path.join(skill_root, name)
                if os.path.isdir(skill_dir):
                    skills.append(name)
        except Exception as e:
            logger.error(f"Local list_skills 失败: {e}")
        
        return sorted(skills)
    
    def read_skill_md(self, tenant_id: str, skill_name: str) -> str:
        md_path = os.path.join(self._skill_path(tenant_id), skill_name, "SKILL.md")
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "SKILL.md 不存在"
        except Exception as e:
            logger.error(f"Local read_skill_md 失败: {e}")
            return f"读取失败: {e}"
    
    def read_file(self, tenant_id: str, skill_name: str, file_path: str) -> str:
        file_full = os.path.join(self._skill_path(tenant_id), skill_name, file_path)
        try:
            with open(file_full, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "文件不存在"
        except Exception as e:
            logger.error(f"Local read_file 失败: {e}")
            return f"读取失败: {e}"
    
    def list_files(self, tenant_id: str, skill_name: str, sub_path: str = "") -> list[dict]:
        skill_dir = os.path.join(self._skill_path(tenant_id), skill_name, sub_path)
        if not os.path.exists(skill_dir):
            return []
        
        files = []
        for root, dirs, filenames in os.walk(skill_dir):
            for name in filenames:
                rel_path = os.path.relpath(
                    os.path.join(root, name),
                    self._skill_path(tenant_id)
                )
                files.append({
                    "path": rel_path,
                    "is_dir": False,
                })
            for name in dirs:
                rel_path = os.path.relpath(
                    os.path.join(root, name),
                    self._skill_path(tenant_id)
                )
                files.append({
                    "path": rel_path + "/",
                    "is_dir": True,
                })
        return files


def create_storage(storage_type: str = None, **kwargs) -> BaseStorage:
    """工厂方法创建存储实例"""
    storage_type = storage_type or os.getenv("SKILL_STORAGE_TYPE", "local")
    
    if storage_type == "oss":
        return OSSStorage(
            bucket=kwargs.get("bucket"),
            region=kwargs.get("region"),
        )
    else:
        return LocalStorage(
            base_path=kwargs.get("base_path", "/data/skills")
        )


async def skill_browser(
    action: str,
    tenant_id: str,
    skill_name: str = None,
    file_path: str = None,
    storage_type: str = None,
    **kwargs
) -> dict:
    """
    Skill 浏览器工具
    
    参数：
    - action: list/read/read_file/tree
    - tenant_id: 租户ID
    - skill_name: 技能名称
    - file_path: 文件路径
    """
    storage = create_storage(storage_type, **kwargs)
    
    if action == "list":
        skills = storage.list_skills(tenant_id)
        return {"skills": skills}
    
    elif action == "read":
        if not skill_name:
            return {"error": "skill_name 必填"}
        content = storage.read_skill_md(tenant_id, skill_name)
        return {
            "skill_name": skill_name,
            "content": content
        }
    
    elif action == "read_file":
        if not skill_name or not file_path:
            return {"error": "skill_name 和 file_path 必填"}
        content = storage.read_file(tenant_id, skill_name, file_path)
        return {
            "skill_name": skill_name,
            "file_path": file_path,
            "content": content
        }
    
    elif action == "tree":
        if not skill_name:
            return {"error": "skill_name 必填"}
        files = storage.list_files(tenant_id, skill_name)
        return {
            "skill_name": skill_name,
            "files": files
        }
    
    else:
        return {"error": f"未知 action: {action}"}


# Tool Schema
SKILL_BROWSER_TOOL = {
    "name": "skill_browser",
    "description": "浏览和管理 Skill 技能文件。支持列出技能列表、读取 SKILL.md 内容、读取技能文件。",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "read_file", "tree"],
                "description": "操作类型：list=列出租户所有技能，read=读取 SKILL.md，read_file=读取文件，tree=列出文件树"
            },
            "skill_name": {
                "type": "string",
                "description": "技能名称"
            },
            "file_path": {
                "type": "string",
                "description": "文件路径"
            }
        },
        "required": ["action", "tenant_id"]
    }
}
