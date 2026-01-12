# NexusPlatform 开发指南

## 适配器概览

当前实现两个适配器：
- **WebChat**：Web 网页聊天（Vue3 前端）
- **QQ 机器人**：QQ 官方机器人（基于 QQ Open API v2）

---

## QQ 机器人适配器开发文档

### 快速开始

#### 1. 接入凭证

| 字段 | 说明 |
|------|------|
| AppID | 机器人 ID，开放平台获取 |
| AppSecret | 机器人密钥 |
| AccessToken | 调用 API 的凭证，有效期 7200 秒 |

获取方式：
```bash
# 获取 AccessToken
curl -X POST 'https://bots.qq.com/app/getAppAccessToken' \
  -H 'Content-Type: application/json' \
  -d '{"appId": "YOUR_APP_ID", "clientSecret": "YOUR_CLIENT_SECRET"}'
```

#### 2. 事件接收方式

支持两种方式：
- **Webhook**：HTTP 回调，需配置回调地址（端口 80/443/8080/8443）
- **WebSocket**：长连接，需实现 Gateway 协议

推荐 WebSocket 方式，更稳定。

#### 3. WebSocket 接入流程

```
Step 1: 获取 Gateway 地址
  GET https://api.sgroup.qq.com/gateway/bot
  
Step 2: 建立 WSS 长连接
  wss://api.sgroup.qq.com/websocket/
  
Step 3: 收到 Hello (op=10)，记录 heartbeat_interval
  
Step 4: 鉴权 (op=2)
  {
    "op": 2,
    "d": {
      "token": "QQBot YOUR_ACCESS_TOKEN",
      "intents": 513,  // 需订阅的事件
      "shard": [0, 1],
      "properties": {...}
    }
  }
  
Step 5: 收到 Ready (op=0, t="READY")，连接成功

Step 6: 定时心跳 (op=1)
```

### 核心 API

#### 发送消息

| 场景 | HTTP URL | 说明 |
|------|----------|------|
| 单聊 | POST /v2/users/{openid}/messages | 发送给用户 |
| 群聊 | POST /v2/groups/{group_openid}/messages | 发送给群 |
| 子频道 | POST /channels/{channel_id}/messages | 频道消息 |
| 频道私信 | POST /dms/{guild_id}/messages | 频道私信 |

请求参数：
```json
{
  "msg_type": 0,        // 0=文本, 2=markdown, 3=ark, 4=embed, 7=media
  "content": "消息内容",
  "markdown": {...},    // 可选，markdown 消息
  "keyboard": {...},    // 可选，按钮消息
  "ark": {...}          // 可选，卡片消息
}
```

### Intents 事件订阅

| 事件 | intents 值 | 说明 |
|------|-----------|------|
| GUILDS | 1 << 0 | 频道事件 |
| GUILD_MEMBERS | 1 << 1 | 成员事件 |
| GUILD_MESSAGES | 1 << 9 | 频道消息（私域） |
| DIRECT_MESSAGE | 1 << 12 | 私信消息 |
| GROUP_AND_C2C_EVENT | 1 << 25 | 群聊/单聊事件 |
| INTERACTION | 1 << 26 | 互动事件 |
| PUBLIC_GUILD_MESSAGES | 1 << 30 | 公域频道消息 |

常用组合：
- 接收@机器人消息：`1 << 30` = 1073741824
- 接收群聊@消息：`1 << 25` = 33554432
- 接收用户私信：`1 << 12` = 4096

### 消息类型

| msg_type | 类型 | 说明 |
|----------|------|------|
| 0 | text | 纯文本 |
| 2 | markdown | Markdown 格式 |
| 3 | ark | JSON 结构化消息 |
| 4 | embed | 嵌入消息 |
| 7 | media | 富媒体 |

### 错误码

| code | message | 说明 |
|------|---------|------|
| 22009 | msg limit exceed | 消息发送超频 |
| 304082 | upload media info fail | 富媒体上传失败 |
| 304083 | convert media info fail | 富媒体转换失败 |

### SDK 参考

官方 SDK：
- Go: [botgo](https://github.com/tencent-connect/botgo)
- Python: [botpy](https://github.com/tencent-connect/botpy)
- NodeJS: [bot-node-sdk](https://github.com/tencent-connect/bot-node-sdk)

---

## 开发约定

### 目录结构

```
nexus-platform/
├── src/main/java/tech/nexus/platform/
│   ├── NexusPlatformApplication.java
│   ├── adapter/
│   │   ├── webchat/          # WebChat 适配器
│   │   │   ├── controller/
│   │   │   ├── handler/
│   │   │   └── config/
│   │   └── qq/               # QQ 机器人适配器
│   │       ├── controller/   # Webhook 回调
│   │       ├── client/       # WebSocket 客户端
│   │       ├── handler/      # 事件处理器
│   │       ├── service/      # 消息发送服务
│   │       └── config/
│   └── common/               # 通用组件
└── src/main/resources/
    └── application.yml
```

### 配置项

```yaml
nexus:
  platform:
    qq:
      enabled: true
      app-id: ${QQ_APP_ID}
      app-secret: ${QQ_APP_SECRET}
      intents: 33554432  # GROUP_AND_C2C_EVENT
    webchat:
      enabled: true
```

### 消息流程

```
用户消息 -> QQ/QQ频道/Web
    ↓
WebSocket/HTTP Webhook
    ↓
消息事件处理器 (MessageHandler)
    ↓
转换为统一消息格式 (PlatformMessage)
    ↓
发送到消息队列 (RabbitMQ)
    ↓
agent-engine 消费并处理
    ↓
返回结果
    ↓
通过对应平台适配器发送回复
```

---

## 参考文档

- [QQ 机器人官方文档](https://bot.q.qq.com/wiki/develop/api-v2/)
- [接口调用与鉴权](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/api-use.html)
- [事件订阅](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html)
- [发送消息](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/send.html)
