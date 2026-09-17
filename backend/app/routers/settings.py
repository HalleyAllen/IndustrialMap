"""数据库配置管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import neo4j_manager, settings_db
from ..schemas import (
    AISettingsIn,
    AISettingsOut,
    AITestResult,
    Neo4jSettingsIn,
    Neo4jSettingsOut,
    Neo4jTestResult,
)
from ..services import ai_service


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/neo4j", response_model=Neo4jSettingsOut)
async def get_neo4j_settings() -> Neo4jSettingsOut:
    """读取当前 Neo4j 配置（密码不回显）。"""
    cfg = settings_db.get_neo4j_settings()
    if cfg is None:
        raise HTTPException(status_code=404, detail="尚未配置 Neo4j 连接")
    return Neo4jSettingsOut(
        uri=cfg["uri"],
        user=cfg["user"],
        database=cfg["database"],
        updated_at=cfg["updated_at"],
        password_set=bool(cfg["password"]),
    )


@router.post("/neo4j", response_model=Neo4jSettingsOut)
async def save_neo4j_settings(payload: Neo4jSettingsIn) -> Neo4jSettingsOut:
    """保存 Neo4j 配置；写入后立即让现有 driver 失效。"""
    cfg = settings_db.save_neo4j_settings(
        payload.uri, payload.user, payload.password, payload.database
    )
    await neo4j_manager.reset()
    return Neo4jSettingsOut(
        uri=cfg["uri"],
        user=cfg["user"],
        database=cfg["database"],
        updated_at=cfg["updated_at"],
        password_set=bool(cfg["password"]),
    )


@router.post("/neo4j/test", response_model=Neo4jTestResult)
async def test_neo4j_settings(payload: Neo4jSettingsIn) -> Neo4jTestResult:
    """用给定的配置去尝试连接 Neo4j（不保存，不影响现状）。"""
    result = await neo4j_manager.test_connection(
        payload.uri, payload.user, payload.password, payload.database
    )
    return Neo4jTestResult(**result)


@router.get("/neo4j/status")
async def neo4j_status() -> dict:
    """返回当前 Neo4j 连接状态（未配置 / 已连接 / 失败）。"""
    cfg = settings_db.get_neo4j_settings()
    if cfg is None:
        return {"configured": False, "connected": False}
    try:
        async with await neo4j_manager.get_session() as session:
            result = await session.run("RETURN 1 AS ok")
            await result.single()
        return {"configured": True, "connected": True}
    except Exception as e:  # noqa: BLE001
        return {"configured": True, "connected": False, "error": str(e)}


# ---------------- AI 配置 ----------------

@router.get("/ai", response_model=AISettingsOut)
async def get_ai_settings() -> AISettingsOut:
    """读取 AI 配置（API Key 不回显）。"""
    cfg = settings_db.get_ai_settings()
    if cfg is None:
        raise HTTPException(status_code=404, detail="尚未配置 AI 服务")
    return AISettingsOut(
        provider=cfg["provider"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        temperature=cfg["temperature"],
        api_key_set=bool(cfg["api_key"]),
        extra=cfg.get("extra", {}),
        updated_at=cfg["updated_at"],
    )


@router.post("/ai", response_model=AISettingsOut)
async def save_ai_settings(payload: AISettingsIn) -> AISettingsOut:
    """保存 AI 配置；保存后立即可用于连通性测试等场景。"""
    cfg = settings_db.save_ai_settings(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        model=payload.model,
        temperature=payload.temperature,
        extra=payload.extra,
    )
    return AISettingsOut(
        provider=cfg["provider"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        temperature=cfg["temperature"],
        api_key_set=bool(cfg["api_key"]),
        extra=cfg.get("extra", {}),
        updated_at=cfg["updated_at"],
    )


@router.post("/ai/test", response_model=AITestResult)
async def test_ai_settings(payload: AISettingsIn) -> AITestResult:
    """用给定配置测试 AI 连通性（不保存）。"""
    result = await ai_service.test_connection(
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        model=payload.model,
        temperature=payload.temperature,
        extra=payload.extra,
    )
    return AITestResult(**result)


@router.get("/ai/status")
async def ai_status() -> dict:
    """返回 AI 配置状态（未配置 / 已配置）。"""
    cfg = settings_db.get_ai_settings()
    if cfg is None:
        return {"configured": False}
    return {
        "configured": True,
        "provider": cfg["provider"],
        "model": cfg["model"],
    }