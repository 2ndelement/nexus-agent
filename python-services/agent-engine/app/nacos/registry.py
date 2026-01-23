"""
app/nacos.py — Nacos 服务注册

支持：
- 服务注册
- 服务心跳保活
- 服务下线
"""
import logging
import threading
import time
from typing import Optional

from nacos import NacosClient

logger = logging.getLogger(__name__)


class NacosServiceRegistry:
    """Nacos 服务注册器"""
    
    _instance: Optional['NacosServiceRegistry'] = None
    _lock = threading.Lock()
    
    def __init__(
        self,
        server_addresses: str,
        namespace: str = "",
        group: str = "DEFAULT_GROUP",
        username: str = "",
        password: str = "",
    ):
        self.server_addresses = server_addresses
        self.namespace = namespace
        self.group = group
        
        # 初始化 Nacos 客户端
        self.client = NacosClient(
            server_addresses=server_addresses,
            namespace=namespace,
            username=username,
            password=password,
        )
        
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        
        logger.info(
            f"[Nacos] 初始化成功: server={server_addresses}, "
            f"namespace={namespace}, group={group}"
        )
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'NacosServiceRegistry':
        """单例模式获取实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(**kwargs)
            return cls._instance
    
    def register(
        self,
        service_name: str,
        port: int,
        ip: str = "127.0.0.1",
        metadata: dict = None,
    ) -> bool:
        """
        注册服务
        
        Args:
            service_name: 服务名称
            port: 端口
            ip: IP 地址
            metadata: 元数据
            
        Returns:
            是否注册成功
        """
        try:
            self.client.add_naming_instance(
                service_name=service_name,
                ip=ip,
                port=port,
                group_name=self.group,
                metadata=metadata or {},
            )
            logger.info(f"[Nacos] 服务注册成功: {service_name}:{port}")
            return True
        except Exception as e:
            logger.error(f"[Nacos] 服务注册失败: {service_name}, error: {e}")
            return False
    
    def deregister(self, service_name: str, ip: str, port: int) -> bool:
        """注销服务"""
        try:
            self.client.remove_naming_instance(
                service_name=service_name,
                ip=ip,
                port=port,
                group_name=self.group,
            )
            logger.info(f"[Nacos] 服务注销: {service_name}:{port}")
            return True
        except Exception as e:
            logger.error(f"[Nacos] 服务注销失败: {service_name}, error: {e}")
            return False
    
    def send_heartbeat(
        self,
        service_name: str,
        ip: str,
        port: int,
        interval: int = 30,
    ):
        """发送心跳保活"""
        while self._running:
            try:
                self.client.send_heartbeat(
                    service_name=service_name,
                    ip=ip,
                    port=port,
                    group_name=self.group,
                )
                logger.debug(f"[Nacos] 发送心跳: {service_name}:{port}")
            except Exception as e:
                logger.warning(f"[Nacos] 发送心跳失败: {service_name}, error: {e}")
            time.sleep(interval)
    
    def start_heartbeat(
        self,
        service_name: str,
        ip: str,
        port: int,
        interval: int = 30,
    ):
        """启动心跳线程"""
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self.send_heartbeat,
            args=(service_name, ip, port, interval),
            daemon=True,
            name=f"nacos-heartbeat-{service_name}",
        )
        self._heartbeat_thread.start()
        logger.info(f"[Nacos] 心跳线程已启动: {service_name}")
    
    def stop(self):
        """停止心跳"""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        logger.info("[Nacos] 心跳已停止")
    
    def get_service_instances(self, service_name: str) -> list:
        """获取服务实例列表"""
        try:
            instances = self.client.list_naming_instances(
                service_name=service_name,
                group_name=self.group,
            )
            return instances or []
        except Exception as e:
            logger.error(f"[Nacos] 获取服务实例失败: {service_name}, error: {e}")
            return []
    
    def get_one_healthy_instance(self, service_name: str) -> Optional[dict]:
        """获取一个健康的实例"""
        instances = self.get_service_instances(service_name)
        for instance in instances:
            if instance.get('healthy', False):
                return instance
        return instances[0] if instances else None


# ==================== 便捷函数 ====================

def get_registry() -> NacosServiceRegistry:
    """获取注册器实例（从环境变量初始化）"""
    import os
    
    server_addresses = os.getenv("NACOS_SERVER_ADDRESSES", "127.0.0.1:8848")
    namespace = os.getenv("NACOS_NAMESPACE", "")
    group = os.getenv("NACOS_GROUP", "DEFAULT_GROUP")
    username = os.getenv("NACOS_USERNAME", "nacos")
    password = os.getenv("NACOS_PASSWORD", "nacos")
    
    return NacosServiceRegistry.get_instance(
        server_addresses=server_addresses,
        namespace=namespace,
        group=group,
        username=username,
        password=password,
    )
