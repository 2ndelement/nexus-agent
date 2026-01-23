"""
common/discovery.py — Nacos 服务发现
"""
import logging
import os
from typing import List, Optional

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ServiceInstance(BaseModel):
    """服务实例"""
    ip: str
    port: int
    healthy: bool = True
    weight: float = 1.0


class NacosDiscovery:
    """Nacos 服务发现"""

    def __init__(self, server_address: str = "127.0.0.1:8848", namespace: str = "", group: str = "DEFAULT_GROUP"):
        self.server_address = server_address
        self.namespace = namespace
        self.group = group

    @property
    def _base_url(self) -> str:
        return f"http://{self.server_address}/nacos/v1"

    def get_instances(self, service_name: str) -> List[ServiceInstance]:
        """获取服务实例列表"""
        url = f"{self._base_url}/ns/instance/list"
        
        params = {
            "serviceName": service_name,
            "namespaceId": self.namespace,
            "groupName": self.group,
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                hosts = data.get("hosts", [])
                return [
                    ServiceInstance(
                        ip=h.get("ip"),
                        port=h.get("port"),
                        healthy=h.get("healthy", True),
                        weight=h.get("weight", 1.0),
                    )
                    for h in hosts if h.get("healthy", True)
                ]
            return []
        except Exception as e:
            logger.error(f"[Nacos] 服务发现异常: {service_name} - {e}")
            return []

    def get_one_instance(self, service_name: str) -> Optional[ServiceInstance]:
        """获取一个健康的服务实例（加权随机）"""
        instances = self.get_instances(service_name)
        if not instances:
            return None
        
        # 加权随机
        total_weight = sum(i.weight for i in instances)
        import random
        r = random.uniform(0, total_weight)
        
        cumulative = 0
        for instance in instances:
            cumulative += instance.weight
            if r <= cumulative:
                return instance
        
        return instances[0]


# 全局发现实例
_discovery: Optional[NacosDiscovery] = None


def get_discovery() -> NacosDiscovery:
    """获取全局发现实例"""
    global _discovery
    if _discovery is None:
        _discovery = NacosDiscovery(
            server_address=os.getenv("NACOS_SERVER", "127.0.0.1:8848"),
            namespace=os.getenv("NACOS_NAMESPACE", ""),
            group=os.getenv("NACOS_GROUP", "DEFAULT_GROUP"),
        )
    return _discovery
