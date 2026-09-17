"""SQLite 配置库：存储用户配置的 Neo4j 连接信息。

使用 SQLAlchemy Core（不引入 ORM 模型，简单）创建单表 `neo4j_settings`，
只有一行 id=1，存储管理员配置的 Neo4j 连接地址、账号、密码、默认数据库。
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.engine import Engine

from .config import settings


def _ensure_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """惰性创建 SQLite 引擎。"""
    global _engine
    if _engine is None:
        _ensure_dir(settings.settings_db_path)
        _engine = create_engine(
            f"sqlite:///{settings.settings_db_path}",
            connect_args={"check_same_thread": False},
        )
        _init_schema(_engine)
    return _engine


def _init_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            sql_text(
                """
                CREATE TABLE IF NOT EXISTS neo4j_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    uri TEXT NOT NULL,
                    user TEXT NOT NULL,
                    password TEXT NOT NULL,
                    database TEXT NOT NULL DEFAULT 'neo4j',
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            sql_text(
                """
                CREATE TABLE IF NOT EXISTS ai_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    provider TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    model TEXT NOT NULL,
                    temperature REAL NOT NULL DEFAULT 0.3,
                    extra TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                )
                """
            )
        )


@contextmanager
def _connect():
    engine = get_engine()
    with engine.connect() as conn:
        yield conn


def get_neo4j_settings() -> Optional[dict]:
    """读取管理员填写的 Neo4j 配置；若无配置返回 None。"""
    with _connect() as conn:
        row = conn.execute(
            sql_text(
                "SELECT uri, user, password, database, updated_at "
                "FROM neo4j_settings WHERE id = 1"
            )
        ).first()
    if row is None:
        return None
    return {
        "uri": row[0],
        "user": row[1],
        "password": row[2],
        "database": row[3],
        "updated_at": row[4],
    }


def save_neo4j_settings(uri: str, user: str, password: str, database: str) -> dict:
    """写入或覆盖管理员填写的 Neo4j 配置。"""
    from datetime import datetime

    with get_engine().begin() as conn:
        conn.execute(
            sql_text(
                """
                INSERT INTO neo4j_settings (id, uri, user, password, database, updated_at)
                VALUES (1, :uri, :user, :password, :database, :updated_at)
                ON CONFLICT(id) DO UPDATE SET
                    uri = excluded.uri,
                    user = excluded.user,
                    password = excluded.password,
                    database = excluded.database,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "uri": uri,
                "user": user,
                "password": password,
                "database": database,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
    return get_neo4j_settings()  # type: ignore[return-value]


# ---------------- AI 配置 ----------------

def get_ai_settings() -> Optional[dict]:
    """读取管理员填写的 AI 配置；若无配置返回 None。"""
    with _connect() as conn:
        row = conn.execute(
            sql_text(
                "SELECT provider, base_url, api_key, model, temperature, extra, updated_at "
                "FROM ai_settings WHERE id = 1"
            )
        ).first()
    if row is None:
        return None
    import json

    try:
        extra = json.loads(row[5]) if row[5] else {}
    except (TypeError, json.JSONDecodeError):
        extra = {}
    return {
        "provider": row[0],
        "base_url": row[1],
        "api_key": row[2],
        "model": row[3],
        "temperature": row[4],
        "extra": extra,
        "updated_at": row[6],
    }


def save_ai_settings(
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.3,
    extra: Optional[dict] = None,
) -> dict:
    """写入或覆盖 AI 配置。extra 字段保留非通用参数（如 max_tokens、top_p）。"""
    import json
    from datetime import datetime

    payload_extra = json.dumps(extra or {}, ensure_ascii=False)
    with get_engine().begin() as conn:
        conn.execute(
            sql_text(
                """
                INSERT INTO ai_settings
                    (id, provider, base_url, api_key, model, temperature, extra, updated_at)
                VALUES
                    (1, :provider, :base_url, :api_key, :model, :temperature, :extra, :updated_at)
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    base_url = excluded.base_url,
                    api_key = excluded.api_key,
                    model = excluded.model,
                    temperature = excluded.temperature,
                    extra = excluded.extra,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "provider": provider,
                "base_url": base_url,
                "api_key": api_key,
                "model": model,
                "temperature": temperature,
                "extra": payload_extra,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
    return get_ai_settings()  # type: ignore[return-value]