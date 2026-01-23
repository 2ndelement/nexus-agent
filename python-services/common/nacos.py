"""
common/nacos.py — Nacos 服务注册

功能：
- 服务注册
- 服务心跳
- 服务注销
"""
import logging
import os
import signal
import threading
import time
from typing import Optional

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class NacosConfig(BaseModel):
    """Nacos 配置"""
    server_address: str = "127.0.0.1:8848"
    namespace: str = ""
    group: str = "DEFAULT_GROUP"
    heartbeat_interval: int = 5  # 秒


class NacosServiceRegistry:
    """Nacos 服务注册器"""

    def __init__(self, service_name: str, ip: str, port: int, config: Optional[NacosConfig] = None):
        self.service_name = service_name
        self.ip = ip
        self.port = port
        self.config = config or NacosConfig()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def _base_url(self) -> str:
        return f"http://{self.config.server_address}/nacos/v1"

    def register(self) -> bool:
        """注册服务"""
        url = f"{self._base_url}/ns/instance"
        
        params = {
            "serviceName": self.service_name,
            "ip": self.ip,
            "port": self.port,
            "namespaceId": self.config.namespace,
            "groupName": self.config.group,
            "enabled": True,
            "healthy": True,
            "weight": 1.0,
        }

        try:
            response = requests.post(url, params=params, timeout=5)
            if response.status_code == 200:
                logger.info(f"[Nacos] 服务注册成功: {self.service_name} -> {self.ip}:{self.port}")
                return True
            else:
                logger.error(f"[Nacos] 服务注册失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"[Nacos] 服务注册异常: {e}")
            return False

    def deregister(self) -> bool:
        """注销服务"""
        url = f"{self._base_url}/ns/instance"
        
        params = {
            "serviceName": self.service_name,
            "ip": self.ip,
            "port": self.port,
            "namespaceId": self.config.namespace,
            "groupName": self.config.group,
        }

        try:
            response = requests.delete(url, params=params, timeout=5)
            if response.status_code == 200:
                logger.info(f"[Nacos] 服务注销成功: {self.service_name}")
                return True
            else:
                logger.error(f"[Nacos] 服务注销失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"[Nacos] 服务注销异常: {e}")
            return False

    def send_heartbeat(self) -> bool:
        """发送心跳"""
        url = f"{self._base_url}/ns/instance/beat"
        
        params = {
            "serviceName": self.service_name,
            "ip": self.ip,
            "port": self.port,
            "namespaceId": self.config.namespace,
            "groupName": self.config.group,
        }

        try:
            response = requests.put(url, params=params, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"[Nacos] 心跳异常: {e}")
            return False

    def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            success = self.send_heartbeat()
            if success:
                logger.debug(f"[Nacos] 心跳: {self.service_name}")
            else:
                logger.warning(f"[Nacos] 心跳失败: {self.service_name}")
            
            time.sleep(self.config.heartbeat_interval)

    def start(self):
        """启动注册（注册 + 启动心跳线程）"""
        # 注册服务
        if not self.register():
            logger.warning(f"[Nacos] 服务注册失败，将重试...")
        
        # 启动心跳线程
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"[Nacos] 服务注册完成: {self.service_name}")

    def stop(self):
        """停止（注销服务）"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        
        self.deregister()
        logger.info(f"[Nacos] 服务已注销: {self.service_name}")


def create_registry(service_name: str, ip: str, port: int) -> NacosServiceRegistry:
    """从环境变量创建注册器"""
    config = NacosConfig(
        server_address=os.getenv("NACOS_SERVER", "127.0.0.1:8848"),
        namespace=os.getenv("NACOS_NAMESPACE", ""),
        group=os.getenv("NACOS_GROUP", "DEFAULT_GROUP"),
    )
    return NacosServiceRegistry(service_name, ip, port, config)
