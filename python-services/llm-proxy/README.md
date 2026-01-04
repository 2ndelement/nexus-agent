# LLM Proxy

LLM 统一代理服务，端口 **8010**。

提供 OpenAI 兼容的 `/v1/chat/completions` 接口，支持多模型路由与 Token 统计。

---

## 功能特性

| 特性 | 说明 |
|------|------|
| **OpenAI 协议兼容** | 请求/响应格式与 OpenAI API 完全一致，上游服务无需改造 |
| **多模型路由** | 根据请求的 `model` 字段自动路由到不同 provider |
| **流式输出** | 支持 `stream: true` SSE 流式响应 |
| **Token 统计** | 记录每次请求的 prompt/completion/total tokens，按 model 聚合 |
| **健康检查** | `GET /health` 供 K8s/Docker 探针使用 |

---

## 目录结构

```
python-services/llm-proxy/
├── README.md
├── requirements.txt
├── main.py                        # FastAPI 入口，端口 8010
├── .env.dev                       # 本地开发环境变量（不提交到 Git）
├── app/
│   ├── __init__.py
│   ├── config.py                  # 配置（从环境变量读取）
│   ├── schemas.py                 # Pydantic v2 请求/响应模型（OpenAI 兼容）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── router.py              # 多模型路由逻辑
│   │   └── token_stats.py        # Token 统计存储（内存 + 可选 Redis）
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── completions.py     # POST /v1/chat/completions
│           └── stats.py          # GET /v1/stats
└── tests/
    ├── conftest.py
    ├── test_completions.py
    └── test_stats.py
```

---

## 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_DEFAULT_MODEL` | `MiniMax-M2.5-highspeed` | 默认模型（请求未指定时使用） |
| `LLM_DEFAULT_BASE_URL` | `https://copilot.lab.2ndelement.tech/v1` | 默认 Provider base_url |
| `LLM_DEFAULT_API_KEY` | *(必填)* | 默认 Provider API Key |
| `LLM_PROVIDERS_JSON` | `""` | JSON 格式多 Provider 配置，见下方说明 |
| `LLM_PROXY_PORT` | `8010` | 服务监听端口 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

### 多 Provider 配置（`LLM_PROVIDERS_JSON`）

```json
{
  "MiniMax-M2.5-highspeed": {
    "base_url": "https://copilot.lab.2ndelement.tech/v1",
    "api_key": "your-api-key",
    "model": "MiniMax-M2.5-highspeed"
  },
  "gpt-4o": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-xxx",
    "model": "gpt-4o"
  }
}
```

> **路由规则：** 请求体中的 `model` 字段作为路由 key，若匹配到 `LLM_PROVIDERS_JSON` 中的配置则使用对应 provider；否则回退到默认 provider 并使用请求中的 `model` 值。

---

## API 说明

### POST /v1/chat/completions

OpenAI 兼容的聊天补全接口。

**请求体：**
```json
{
  "model": "MiniMax-M2.5-highspeed",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你好"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1024
}
```

**非流式响应：**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "MiniMax-M2.5-highspeed",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "你好！"},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 5,
    "total_tokens": 25
  }
}
```

**流式响应（`stream: true`）：** `text/event-stream`，格式与 OpenAI streaming 完全一致。

---

### GET /v1/stats

查询 Token 统计数据。

**响应：**
```json
{
  "total_requests": 42,
  "total_tokens": 15320,
  "by_model": {
    "MiniMax-M2.5-highspeed": {
      "requests": 40,
      "prompt_tokens": 8000,
      "completion_tokens": 6000,
      "total_tokens": 14000
    }
  }
}
```

---

### GET /health

健康检查接口。

```json
{"status": "ok", "service": "llm-proxy"}
```

---

## 快速启动

```bash
cd python-services/llm-proxy

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.dev.example .env.dev
# 编辑 .env.dev，填写 LLM_DEFAULT_API_KEY

# 启动服务
python main.py
# 或
uvicorn main:app --port 8010 --reload
```

---

## 运行测试

```bash
cd python-services/llm-proxy
python -m pytest tests/ -v
```
