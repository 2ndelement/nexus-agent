"""
app/config.py — sandbox-service 配置
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8020

    # Docker 配置
    docker_image: str = "python:3.11-slim"
    container_pool_size: int = 4          # 容器池大小
    container_max_memory: str = "256m"    # 最大内存
    container_cpu_limit: float = 0.5      # CPU 限制（0.5 核）
    default_timeout: int = 30             # 默认超时秒数
    max_timeout: int = 120                # 最大超时

    # 工作目录（在容器内）
    work_dir: str = "/workspace"

    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
