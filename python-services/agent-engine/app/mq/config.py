"""
app/mq/config.py — RabbitMQ 配置
"""
from pydantic_settings import BaseSettings
from typing import Optional


class RabbitMQSettings(BaseSettings):
    """RabbitMQ 连接配置"""

    host: str = "127.0.0.1"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    virtual_host: str = "/"

    # Exchange & Queue
    exchange: str = "nexus.platform.events"
    inbound_queue: str = "nexus.platform.inbound"
    inbound_routing_key: str = "platform.message.inbound"
    outbound_queue: str = "nexus.platform.outbound"
    outbound_routing_key: str = "platform.message.outbound"
    
    # 死信队列
    dlx_exchange: str = "nexus.platform.events.dlx"
    dlq_queue: str = "nexus.platform.inbound.dlq"
    dlq_routing_key: str = "dead-letter"
    
    # 消费配置
    prefetch_count: int = 10
    retry_attempts: int = 3
    retry_delay: int = 5000  # 毫秒

    class Config:
        env_prefix = "RABBITMQ_"


mq_settings = RabbitMQSettings()
