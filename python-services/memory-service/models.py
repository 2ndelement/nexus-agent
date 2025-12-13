"""
数据库模型定义（SQLAlchemy ORM）
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, Text, String, Float,
    DateTime, Index
)
from sqlalchemy.dialects.mysql import BIGINT as MYSQL_BIGINT
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Memory(Base):
    """记忆片段表"""
    __tablename__ = "memories"

    # 使用 Integer 作为 PK 类型，在 SQLite 中自动成为 ROWID（支持 autoincrement），
    # 在 MySQL 中通过 BigInteger 正常工作（SQLAlchemy 会选择最合适的类型）。
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, nullable=False, comment="租户ID，多租户隔离")
    user_id = Column(Integer, nullable=True, comment="用户ID，可为空（Agent级记忆）")
    agent_id = Column(Integer, nullable=True, comment="AgentID，可为空（用户级记忆）")
    content = Column(Text, nullable=False, comment="记忆内容")
    keywords = Column(Text, nullable=True, comment="关键词，逗号分隔，用于降级搜索")
    embedding = Column(Text, nullable=True, comment="向量序列化（逗号分隔浮点数）")
    source = Column(String(100), nullable=True, comment="来源标识，如 chat/tool/summary")
    importance = Column(Float, default=1.0, comment="重要性权重 0-10")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_memories_tenant_user", "tenant_id", "user_id"),
        Index("idx_memories_tenant_agent", "tenant_id", "agent_id"),
    )
