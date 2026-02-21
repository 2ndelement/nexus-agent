"""
app/skill_manager.py — Skill 管理器

核心设计：
1. 租户 OSS 存储 Skill 文件
2. Agent 渐进式读取（description → content → scripts）
3. 沙箱执行时挂载 OSS（只读）
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillConfig:
    """Skill 配置（租户级别）"""
    tenant_id: str
    bucket: str
    endpoint: str
    access_key: str
    secret_key: str
    region: str
    skills_path: str = "skills"


@dataclass
class SkillManifest:
    """Skill 清单（name + description）"""
    name: str
    description: str
    path: str


@dataclass
class SkillContent:
    """Skill 完整内容"""
    name: str
    description: str
    content: str  # SKILL.md 内容
    scripts: dict  # {"path": "content base64}
    references: list[str]  # 参考文件列表


class SkillManager:
    """
    Skill 管理器
    
    核心职责：
    1. 获取 Skill 清单（name + description）
    2. 读取 Skill 内容（SKILL.md）
    3. 准备沙箱挂载参数
    """

    def __init__(self):
        self._oss_clients: dict[str, OSSClient] = {}
        self._skill_configs: dict[str, SkillConfig] = {}

    async def get_skill_manifests(
        self,
        agent_id: int,
        tenant_id: str,
    ) -> list[SkillManifest]:
        """
        获取 Agent 绑定的 Skill 清单
        仅返回 name + description，供 LLM 发现
        """
        # 1. 获取租户 OSS 配置
        config = await self._get_skill_config(tenant_id)
        
        # 2. 读取 skills/ 目录
        manifests = []
        skill_names = await self._list_skill_dirs(config)
        
        for skill_name in skill_names:
            # 3. 读取 SKILL.md 获取 description
            skill_path = f"{config.skills_path}/{skill_name}/SKILL.md"
            description = await self._read_file(config, skill_path)
            
            manifests.append(SkillManifest(
                name=skill_name,
                description=self._extract_description(description),
                path=f"{config.skills_path}/{skill_name}"
            ))
        
        return manifests

    async def get_skill_content(
        self,
        skill_name: str,
        tenant_id: str,
    ) -> SkillContent:
        """
        获取 Skill 完整内容
        """
        config = await self._get_skill_config(tenant_id)
        
        skill_dir = f"{config.skills_path}/{skill_name}"
        
        # 读取 SKILL.md
        skill_md = await self._read_file(config, f"{skill_dir}/SKILL.md")
        
        # 读取 scripts/ 目录
        scripts = await self._read_scripts(config, skill_dir)
        
        # 读取 references/ 目录
        references = await self._list_references(config, skill_dir)
        
        return SkillContent(
            name=skill_name,
            description=self._extract_description(skill_md),
            content=skill_md,
            scripts=scripts,
            references=references
        )

    def get_sandbox_mount(self, config: SkillConfig) -> dict:
        """
        获取沙箱挂载参数（只读）
        
        Returns:
            {
                "mounts": [
                    {
                        "path": "/skills",
                        "oss": {
                            "bucket": "xxx",
                            "prefix": "skills/",
                            "readonly": True
                        }
                    }
                ]
            }
        """
        return {
            "mounts": [
                {
                    "path": "/skills",
                    "oss": {
                        "bucket": config.bucket,
                        "endpoint": config.endpoint,
                        "access_key": config.access_key,
                        "secret_key": config.secret_key,
                        "prefix": f"{config.skills_path}/",
                        "readonly": True  # 只读隔离
                    }
                }
            ]
        }

    # ==================== 内部方法 ====================
    
    async def _get_skill_config(self, tenant_id: str) -> SkillConfig:
        """获取租户 Skill 配置（从数据库/缓存）"""
        # TODO: 从数据库或缓存获取
        pass

    async def _list_skill_dirs(self, config: SkillConfig) -> list[str]:
        """列出 Skill 目录"""
        # TODO: 调用 OSS 列出目录
        return ["pdf-processing", "data-analysis"]

    async def _read_file(self, config: SkillConfig, path: str) -> str:
        """读取文件内容"""
        # TODO: OSS 读取
        return ""

    async def _read_scripts(self, config: SkillConfig, skill_dir: str) -> dict:
        """读取 scripts 目录"""
        return {}

    async def _list_references(self, config: SkillConfig, skill_dir: str) -> list[str]:
        """列出 references 目录"""
        return []

    def _extract_description(self, content: str) -> str:
        """从 SKILL.md 提取 description（frontmatter）"""
        # 简单实现：取第一段描述
        if content.startswith("---"):
n            # YAML frontmatter 格式
            parts = content.split("---")
            if len(parts) >= 2:
                # description: 在 YAML frontmatter 中
                for line in parts[1].split("\n"):
                    if line.startswith("description:"):
                        return line.split(":", 1)[1].strip()
        return ""


class OSSClient:
    """OSS 客户端（简化）"""
    
    def __init__(self, config: SkillConfig):
        self.config = config
        # TODO: 初始化 OSS 客户端
    
    async def list_dirs(self, prefix: str) -> list[str]:
        """列出目录"""
        return []
    
    async def read_file(self, path: str) -> str:
        """读取文件"""
        return ""
