# Tool Registry

工具注册服务，管理 Agent 可用的工具。

## 内置工具

| 工具 | 功能 | 实现方式 |
|------|------|----------|
| web_search | 网页搜索 | Tavily API |
| calculator | 数学计算 | Python eval |
| weather | 天气查询 | 第三方 API |

## 架构

```
Tool Registry
  ├── Tool Definition (name, description, parameters)
  ├── Tool Executor (sandbox execution)
  └── Tool Cache (Redis)
```

## API

```bash
# 列出可用工具
GET /api/tools

# 执行工具
POST /api/tools/execute
{
  "tool_name": "calculator",
  "parameters": {"expression": "2+2"}
}
```
