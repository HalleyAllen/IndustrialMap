"""Neo4j 连接管理：单例 driver，支持热重载（管理员改完配置后无需重启）。

使用 neo4j 官方 Python 驱动（bolt 协议 + async session）。
"""
from __future__ import annotations

import threading
from typing import Optional

from neo4j import AsyncGraphDatabase, AsyncDriver, exceptions as neo4j_exc

from . import settings_db


_lock = threading.Lock()
_driver: Optional[AsyncDriver] = None
_current_uri: Optional[str] = None


async def _close_driver() -> None:
    """关闭并清空当前 driver。"""
    global _driver, _current_uri
    if _driver is not None:
        try:
            await _driver.close()
        except Exception:
            pass
    _driver = None
    _current_uri = None


async def get_driver() -> Optional[AsyncDriver]:
    """获取当前 driver；若配置变更过，会重新创建。

    返回 None 表示尚未配置（前端应引导管理员先去配置页填表）。
    """
    global _driver, _current_uri

    cfg = settings_db.get_neo4j_settings()
    if cfg is None:
        return None

    with _lock:
        # 仅在 driver 不存在或 URI 变化时重建
        if _driver is None or _current_uri != cfg["uri"]:
            if _driver is not None:
                try:
                    await _driver.close()
                except Exception:
                    pass
                _driver = None
            _driver = AsyncGraphDatabase.driver(
                cfg["uri"],
                auth=(cfg["user"], cfg["password"]),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
            _current_uri = cfg["uri"]
    return _driver


async def get_session():
    """获取一个 session；要求管理员已经配置好 Neo4j。"""
    driver = await get_driver()
    if driver is None:
        raise RuntimeError("Neo4j 尚未配置，请先在「数据库配置」页填写连接信息")
    cfg = settings_db.get_neo4j_settings()
    return driver.session(database=cfg["database"])  # type: ignore[union-attr]


async def test_connection(uri: str, user: str, password: str, database: str) -> dict:
    """测试给定配置能否连通 Neo4j；不修改当前 driver。"""
    test_driver = AsyncGraphDatabase.driver(
        uri, auth=(user, password), connection_acquisition_timeout=10
    )
    try:
        await test_driver.verify_connectivity()
        async with test_driver.session(database=database) as session:
            result = await session.run("CALL dbms.components() YIELD name, versions, edition")
            record = await result.single()
        return {
            "ok": True,
            "name": record["name"],
            "versions": list(record["versions"]),
            "edition": record["edition"],
        }
    except neo4j_exc.AuthError as e:
        return {"ok": False, "error": f"认证失败: {e.message}"}
    except neo4j_exc.ServiceUnavailable as e:
        return {"ok": False, "error": f"无法连接 Neo4j 服务: {e.message}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        try:
            await test_driver.close()
        except Exception:
            pass


async def reset() -> None:
    """让当前 driver 失效，下次调用 get_driver 时会重新加载配置。"""
    await _close_driver()