# Memory Service

会话记忆服务，管理 Agent 的长期记忆。

## 功能

- 记忆存储 (PostgreSQL)
- 记忆检索 (向量相似度)
- 记忆总结 (LLM)

## 架构

```
Memory Service
  ├── Short-term: Redis (会话级)
  └── Long-term: PostgreSQL (持久化)
```

## API

```bash
# 存储记忆
POST /api/memory
{
  "tenant_id": "xxx",
  "conversation_id": "xxx",
  "content": "用户说...",
  "importance": 5
}

# 检索记忆
GET /api/memory/search?query=用户之前提到&top_k=5
```
