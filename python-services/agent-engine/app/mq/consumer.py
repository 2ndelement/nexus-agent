"""
app/mq/consumer.py — RabbitMQ 消费者

监听 nexus.platform.inbound 队列，消费平台消息，
调用 Agent 非流式接口处理，然后发布到 nexus.platform.outbound 队列。

支持：
- 死信队列（DLQ）处理失败消息
- 消息去重
- 优雅关闭
"""
import asyncio
import json
import logging
import os
import signal
import sys
import threading
from typing import Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError

from app.agent.graph import build_graph, invoke_agent
from app.checkpointer import get_mysql_checkpointer
from app.mq.config import mq_settings
from app.schemas import ChatResponse

logger = logging.getLogger(__name__)


class InboundMessageConsumer:
    """RabbitMQ 消费者 - 处理入站消息"""

    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self._running = False
        self._processed_messages = set()  # 消息去重
        self._lock = threading.Lock()

    def connect(self):
        """建立 RabbitMQ 连接"""
        credentials = pika.PlainCredentials(
            mq_settings.username,
            mq_settings.password
        )
        parameters = pika.ConnectionParameters(
            host=mq_settings.host,
            port=mq_settings.port,
            virtual_host=mq_settings.virtual_host,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=300,
        )
        
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # 声明交换机
        self.channel.exchange_declare(
            exchange=mq_settings.exchange,
            exchange_type="topic",
            durable=True
        )

        # 声明入站队列
        self.channel.queue_declare(
            queue=mq_settings.inbound_queue,
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{mq_settings.exchange}.dlx",
                "x-dead-letter-routing-key": "dead-letter",
            }
        )

        # 声明死信队列
        self.channel.queue_declare(
            queue=f"{mq_settings.inbound_queue}.dlq",
            durable=True,
        )
        
        # 绑定死信队列
        self.channel.queue_bind(
            queue=f"{mq_settings.inbound_queue}.dlq",
            exchange=f"{mq_settings.exchange}.dlx",
            routing_key="dead-letter",
        )

        # 声明出站队列
        self.channel.queue_declare(
            queue=mq_settings.outbound_queue,
            durable=True,
        )

        logger.info(
            "[MQ] 消费者已连接，监听队列: %s (DLQ: %s)",
            mq_settings.inbound_queue,
            f"{mq_settings.inbound_queue}.dlq"
        )

    def _is_duplicate(self, message_id: str) -> bool:
        """检查消息是否重复"""
        with self._lock:
            if message_id in self._processed_messages:
                return True
            self._processed_messages.add(message_id)
            # 保持集合大小，防止内存泄漏
            if len(self._processed_messages) > 10000:
                self._processed_messages.clear()
            return False

    def process_message(self, ch, method, properties, body):
        """处理入站消息"""
        message_id = properties.message_id if properties.message_id else "unknown"
        
        # 去重检查
        if self._is_duplicate(message_id):
            logger.info("[MQ] 消息重复，跳过: %s", message_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            message_data = json.loads(body)
            logger.info(
                "[MQ] 收到入站消息: id=%s, platform=%s, chatId=%s",
                message_id,
                message_data.get("platform"),
                message_data.get("chatId"),
            )

            # 提取必要字段
            platform = message_data.get("platform")
            chat_id = message_data.get("chatId")
            sender_id = message_data.get("senderId")
            tenant_id = message_data.get("tenantId", "default")
            user_content = message_data.get("content", "")

            if not user_content:
                logger.warn("[MQ] 消息内容为空，跳过处理")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # 异步调用 Agent
            response = asyncio.run(
                self._invoke_agent_async(tenant_id, sender_id, chat_id, user_content)
            )

            # 构建出站消息
            outbound_message = {
                "messageId": f"{message_id}_response",
                "platform": platform,
                "chatId": chat_id,
                "senderId": sender_id,
                "content": response,
                "tenantId": tenant_id,
            }

            # 发布到出站队列
            self.channel.basic_publish(
                exchange=mq_settings.exchange,
                routing_key=mq_settings.outbound_routing_key,
                body=json.dumps(outbound_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 持久化
                    message_id=f"{message_id}_response",
                )
            )
            logger.info(
                "[MQ] 出站消息已发布: platform=%s, chatId=%s",
                platform,
                chat_id
            )

            # 确认消息
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logger.error("[MQ] 处理消息失败: %s", str(e), exc_info=True)
            # 拒绝消息，发送到死信队列
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    async def _invoke_agent_async(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        message: str,
    ) -> str:
        """异步调用 Agent"""
        async with get_mysql_checkpointer() as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            result = await invoke_agent(
                graph=graph,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
            )
        return result

    def start_consuming(self):
        """开始消费"""
        self._running = True
        self.channel.basic_qos(prefetch_count=10)
        self.channel.basic_consume(
            queue=mq_settings.inbound_queue,
            on_message_callback=self.process_message,
        )
        logger.info("[MQ] 开始消费消息...")
        
        while self._running:
            try:
                self.channel.connection.process_data_events(time_limit=1)
            except Exception as e:
                if self._running:
                    logger.error("[MQ] 消费异常: %s", e)
                    # 尝试重连
                    self._reconnect()

    def _reconnect(self):
        """重连机制"""
        max_retries = 5
        for i in range(max_retries):
            try:
                logger.info(f"[MQ] 尝试重连 ({i+1}/{max_retries})...")
                self.connect()
                logger.info("[MQ] 重连成功")
                return
            except AMQPConnectionError:
                import time
                time.sleep(2 ** i)  # 指数退避
        
        logger.error("[MQ] 重连失败，退出")
        self._running = False

    def stop(self):
        """优雅关闭"""
        logger.info("[MQ] 收到关闭信号...")
        self._running = False
        if self.channel and self.channel.is_open:
            self.channel.stop_consuming()
        self.close()

    def close(self):
        """关闭连接"""
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
            if self.connection and self.connection.is_open:
                self.connection.close()
            logger.info("[MQ] 消费者已关闭")
        except Exception as e:
            logger.error("[MQ] 关闭连接异常: %s", e)


def run_consumer():
    """运行消费者（独立进程入口）"""
    consumer = InboundMessageConsumer()
    
    # 注册信号处理
    def signal_handler(signum, frame):
        logger.info(f"[MQ] 收到信号: {signum}")
        consumer.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        consumer.connect()
        consumer.start_consuming()
    except KeyboardInterrupt:
        logger.info("[MQ] 收到中断信号，关闭消费者...")
    finally:
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_consumer()
