"""
tests/test_completions.py — /v1/chat/completions 接口测试

使用 unittest.mock 模拟 openai SDK，避免消耗真实 API 配额。
"""
from __future__ import annotations

import json
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─────────────────────── 辅助 Mock 工厂 ──────────────────────

def _make_usage(prompt=10, completion=5):
    u = MagicMock()
    u.prompt_tokens = prompt
    u.completion_tokens = completion
    u.total_tokens = prompt + completion
    return u


def _make_non_stream_response(content="你好！", model="MiniMax-M2.5-highspeed"):
    resp = MagicMock()
    resp.id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    resp.created = int(time.time())
    resp.model = model
    resp.usage = _make_usage()

    msg = MagicMock()
    msg.role = "assistant"
    msg.content = content

    choice = MagicMock()
    choice.index = 0
    choice.message = msg
    choice.finish_reason = "stop"

    resp.choices = [choice]
    return resp


async def _make_stream_chunks(content="你好"):
    """模拟 async for 流式 chunk 迭代器。"""
    for i, char in enumerate(content):
        delta = MagicMock()
        delta.role = "assistant" if i == 0 else None
        delta.content = char
        delta.tool_calls = None

        rc = MagicMock()
        rc.index = 0
        rc.delta = delta
        rc.finish_reason = None if i < len(content) - 1 else "stop"

        chunk = MagicMock()
        chunk.id = "chatcmpl-stream"
        chunk.created = int(time.time())
        chunk.model = "MiniMax-M2.5-highspeed"
        chunk.choices = [rc]
        chunk.usage = None
        yield chunk


# ─────────────────────────── 测试 ────────────────────────────

class TestNonStream:
    def test_basic_success(self, client):
        """正常非流式调用应返回 200 和标准 OpenAI 格式响应。"""
        mock_resp = _make_non_stream_response("你好！")

        with patch(
            "app.core.router.openai.AsyncOpenAI"
        ) as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_resp)
            instance.close = AsyncMock()

            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "MiniMax-M2.5-highspeed",
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": False,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "你好！"
        assert data["usage"]["total_tokens"] == 15

    def test_default_model_fallback(self, client):
        """未指定 model 时应使用默认模型。"""
        mock_resp = _make_non_stream_response()

        with patch("app.core.router.openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_resp)
            instance.close = AsyncMock()

            resp = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "test"}]},
            )

        assert resp.status_code == 200

    def test_empty_messages_returns_422(self, client):
        """消息列表为空应返回 422 校验错误。"""
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "MiniMax-M2.5-highspeed", "messages": []},
        )
        assert resp.status_code == 422

    def test_upstream_error_returns_502(self, client):
        """上游 LLM 调用失败应返回 502。"""
        with patch("app.core.router.openai.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(
                side_effect=Exception("upstream down")
            )
            instance.close = AsyncMock()

            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "MiniMax-M2.5-highspeed",
                    "messages": [{"role": "user", "content": "test"}],
                },
            )

        assert resp.status_code == 502


class TestStream:
    def test_stream_returns_event_stream(self, client):
        """流式请求应返回 text/event-stream 内容类型。"""
        async def _fake_stream_gen(req):
            from app.schemas import ChatCompletionStreamChunk, DeltaMessage, StreamChoice
            import time
            chunk = ChatCompletionStreamChunk(
                id="chatcmpl-test",
                created=int(time.time()),
                model=req.model,
                choices=[StreamChoice(delta=DeltaMessage(content="你"), finish_reason=None)],
            )
            yield chunk

        with patch("app.api.v1.completions.stream_chat_completion", side_effect=_fake_stream_gen):
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "MiniMax-M2.5-highspeed",
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": True,
                },
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_contains_data_lines(self, client):
        """流式响应内容应包含 `data:` 开头的行和 `[DONE]`。"""
        async def _fake_stream_gen(req):
            from app.schemas import ChatCompletionStreamChunk, DeltaMessage, StreamChoice
            import time
            for char in ["你", "好"]:
                yield ChatCompletionStreamChunk(
                    id="chatcmpl-test",
                    created=int(time.time()),
                    model=req.model,
                    choices=[StreamChoice(delta=DeltaMessage(content=char), finish_reason=None)],
                )

        with patch("app.api.v1.completions.stream_chat_completion", side_effect=_fake_stream_gen):
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "MiniMax-M2.5-highspeed",
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": True,
                },
            )

        body = resp.text
        assert "data:" in body
        assert "[DONE]" in body
