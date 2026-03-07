"""
common/nacos.py — Nacos 服务注册与发现

功能：
- 服务注册
- 服务心跳
- 服务注销
- 服务发现（带负载均衡）
"""
import logging
import os
import random
import threading
import time
from typing import Dict, List, Optional, Tuple

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class NacosConfig(BaseModel):
    """Nacos 配置"""
    server_address: str = "127.0.0.1:8848"
    namespace: str = ""
    group: str = "DEFAULT_GROUP"
    heartbeat_interval: int = 5  # 秒


class ServiceInstance(BaseModel):
    """服务实例"""
    ip: str
    port: int
    weight: float = 1.0
    healthy: bool = True
    enabled: bool = True
    metadata: Dict[str, str] = {}

    @property
    def url(self) -> str:
        """返回 http://ip:port 格式"""
        return f"http://{self.ip}:{self.port}"


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


class NacosServiceDiscovery:
    """
    Nacos 服务发现客户端（带本地缓存和负载均衡）

    使用示例:
        discovery = NacosServiceDiscovery()
        url = discovery.get_service_url("nexus-sandbox-service")
        # url = "http://172.25.0.11:8020"
    """

    def __init__(self, config: Optional[NacosConfig] = None):
        self.config = config or NacosConfig(
            server_address=os.getenv("NACOS_SERVER", "127.0.0.1:8848"),
            namespace=os.getenv("NACOS_NAMESPACE", ""),
            group=os.getenv("NACOS_GROUP", "DEFAULT_GROUP"),
        )
        # 本地缓存: service_name -> (instances, last_update_time)
        self._cache: Dict[str, Tuple[List[ServiceInstance], float]] = {}
        self._cache_ttl = 10  # 缓存 10 秒
        self._lock = threading.Lock()

    @property
    def _base_url(self) -> str:
        return f"http://{self.config.server_address}/nacos/v1"

    def get_instances(self, service_name: str, healthy_only: bool = True) -> List[ServiceInstance]:
        """
        获取服务实例列表（带本地缓存）

        Args:
            service_name: 服务名称
            healthy_only: 是否只返回健康实例

        Returns:
            服务实例列表
        """
        with self._lock:
            # 检查缓存
            if service_name in self._cache:
                instances, last_update = self._cache[service_name]
                if time.time() - last_update < self._cache_ttl:
                    if healthy_only:
                        return [i for i in instances if i.healthy and i.enabled]
                    return instances

        # 从 Nacos 获取
        url = f"{self._base_url}/ns/instance/list"
        params = {
            "serviceName": service_name,
            "namespaceId": self.config.namespace,
            "groupName": self.config.group,
            "healthyOnly": healthy_only,
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                instances = []
                for host in data.get("hosts", []):
                    instances.append(ServiceInstance(
                        ip=host["ip"],
                        port=host["port"],
                        weight=host.get("weight", 1.0),
                        healthy=host.get("healthy", True),
                        enabled=host.get("enabled", True),
                        metadata=host.get("metadata", {}),
                    ))

                # 更新缓存
                with self._lock:
                    self._cache[service_name] = (instances, time.time())

                logger.debug(f"[Nacos] 发现服务 {service_name}: {len(instances)} 个实例")
                return instances
            else:
                logger.warning(f"[Nacos] 服务发现失败: {response.text}")
                return []
        except Exception as e:
            logger.error(f"[Nacos] 服务发现异常: {e}")
            # 返回缓存（如果有）
            with self._lock:
                if service_name in self._cache:
                    instances, _ = self._cache[service_name]
                    return instances
            return []

    def get_one_instance(self, service_name: str) -> Optional[ServiceInstance]:
        """
        获取一个服务实例（加权随机负载均衡）

        Args:
            service_name: 服务名称

        Returns:
            服务实例，如果没有可用实例返回 None
        """
        instances = self.get_instances(service_name, healthy_only=True)
        if not instances:
            return None

        # 加权随机选择
        total_weight = sum(i.weight for i in instances)
        if total_weight <= 0:
            return random.choice(instances)

        r = random.uniform(0, total_weight)
        current = 0
        for instance in instances:
            current += instance.weight
            if r <= current:
                return instance

        return instances[-1]

    def get_service_url(self, service_name: str, fallback: Optional[str] = None) -> Optional[str]:
        """
        获取服务 URL（负载均衡）

        Args:
            service_name: 服务名称
            fallback: 无可用实例时的降级地址

        Returns:
            http://ip:port 格式的 URL
        """
        instance = self.get_one_instance(service_name)
        if instance:
            return instance.url

        if fallback:
            logger.warning(f"[Nacos] 服务 {service_name} 无可用实例，使用降级地址: {fallback}")
            return fallback

        logger.error(f"[Nacos] 服务 {service_name} 无可用实例")
        return None

    def clear_cache(self, service_name: Optional[str] = None):
        """清除缓存"""
        with self._lock:
            if service_name:
                self._cache.pop(service_name, None)
            else:
                self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════════

_discovery: Optional[NacosServiceDiscovery] = None


def get_discovery() -> NacosServiceDiscovery:
    """获取服务发现客户端单例"""
    global _discovery
    if _discovery is None:
        _discovery = NacosServiceDiscovery()
    return _discovery


def discover_service(service_name: str, fallback: Optional[str] = None) -> Optional[str]:
    """
    快捷函数：发现服务并返回 URL

    使用示例:
        url = discover_service("nexus-sandbox-service", fallback="http://localhost:8020")
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{url}/execute", ...)
    """
    return get_discovery().get_service_url(service_name, fallback)


def create_registry(service_name: str, ip: str, port: int) -> NacosServiceRegistry:
    """从环境变量创建注册器"""
    config = NacosConfig(
        server_address=os.getenv("NACOS_SERVER", "127.0.0.1:8848"),
        namespace=os.getenv("NACOS_NAMESPACE", ""),
        group=os.getenv("NACOS_GROUP", "DEFAULT_GROUP"),
    )
    return NacosServiceRegistry(service_name, ip, port, config)
