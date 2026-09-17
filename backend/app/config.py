"""应用配置（环境变量加载）。"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """从环境变量或 .env 文件读取应用级配置。"""

    app_name: str = "IndustrialMap API"
    app_version: str = "0.1.0"

    # SQLite 配置库路径（用于存储用户配置的 Neo4j 连接信息）
    settings_db_path: str = str(BASE_DIR / "data" / "industrialmap_settings.db")

    # CORS（前端开发服务器默认地址）
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]

    # 默认 Neo4j 配置（首次启动时如果 SQLite 中没有配置，会用这个）
    default_neo4j_uri: str = "bolt://localhost:7687"
    default_neo4j_user: str = "neo4j"
    default_neo4j_password: str = "neo4j"
    default_neo4j_database: str = "neo4j"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("model_",),
    )


settings = Settings()