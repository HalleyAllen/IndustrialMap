"""企业关系管理路由。"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from .. import neo4j_manager
from ..schemas import RelationIn


router = APIRouter(prefix="/api/relations", tags=["relations"])


# Neo4j 关系类型只允许字母、数字、下划线；禁止任意 Cypher 注入
_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_TYPES = {
    "SUPPLIES",          # 供货
    "PURCHASES_FROM",    # 采购
    "COMPETES_WITH",     # 竞争
    "PARTNER_OF",        # 合作
    "SUBSIDIARY_OF",     # 子公司
    "INVESTED_BY",       # 投资
    "CUSTOMER_OF",       # 客户
}


@router.post("")
async def create_relation(payload: RelationIn) -> dict:
    rel_type = payload.type.strip().upper()
    if not _TYPE_RE.match(rel_type):
        raise HTTPException(status_code=400, detail="关系类型非法（仅允许字母数字下划线）")
    if rel_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的关系类型 {rel_type}，可选: {sorted(_ALLOWED_TYPES)}",
        )
    if payload.from_id == payload.to_id:
        raise HTTPException(status_code=400, detail="关系两端不能是同一个企业")

    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            f"""
            MATCH (a:Company {{id: $from_id}}), (b:Company {{id: $to_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            RETURN a.id AS from_id, b.id AS to_id, type(r) AS type
            """,
            from_id=payload.from_id,
            to_id=payload.to_id,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在，无法创建关系")
    return {"from_id": record["from_id"], "to_id": record["to_id"], "type": record["type"]}


@router.delete("")
async def delete_relation(payload: RelationIn) -> dict:
    rel_type = payload.type.strip().upper()
    if not _TYPE_RE.match(rel_type):
        raise HTTPException(status_code=400, detail="关系类型非法")

    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            f"""
            MATCH (a:Company {{id: $from_id}})-[r:{rel_type}]->(b:Company {{id: $to_id}})
            DELETE r
            RETURN count(r) AS deleted
            """,
            from_id=payload.from_id,
            to_id=payload.to_id,
        )
        record = await result.single()
    finally:
        await session.close()
    return {"deleted": record["deleted"] if record else 0}


@router.get("/types")
async def list_relation_types() -> list[str]:
    """前端用来渲染关系类型下拉框。"""
    return sorted(_ALLOWED_TYPES)