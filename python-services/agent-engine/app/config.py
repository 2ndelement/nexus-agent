"""
app/config.py — 从环境变量读取配置（无硬编码密码）
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有配置项皆来自环境变量或 .env 文件，严禁硬编码密码。"""

    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.7
    llm_timeout: float = 60.0

    # MySQL
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_db: str = "nexus_agent"
    mysql_user: str = "nexus"
    mysql_pass: str = ""

    @property
    def mysql_url(self) -> str:
        """返回 aiomysql 兼容的连接串"""
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_pass}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )

    # Redis（备用）
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379

    # 内部服务地址
    agent_engine_port: int = 8001
    tool_registry_url: str = "http://127.0.0.1:8011"
    sandbox_url: str = "http://127.0.0.1:8020"
    rag_service_url: str = "http://127.0.0.1:8013"
    memory_service_url: str = "http://127.0.0.1:8012"
    log_level: str = "INFO"

    # Tool Calling
    max_tool_iterations: int = 5

    # 服务发现
    service_name: str = "nexus-agent-engine"
    service_ip: str = ""
    nacos_enabled: bool = True
    nacos_server_addresses: str = "127.0.0.1:8848"
    nacos_namespace: str = ""
    nacos_group: str = "DEFAULT_GROUP"
    nacos_username: str = "nacos"
    nacos_password: str = "nacos"


# 单例
settings = Settings()
