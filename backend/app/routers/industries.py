"""行业管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import neo4j_manager
from ..schemas import IndustryIn, IndustryOut


router = APIRouter(prefix="/api/industries", tags=["industries"])


@router.get("", response_model=list[IndustryOut])
async def list_industries() -> list[IndustryOut]:
    """列出所有行业（含每个行业下的企业数）。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (i:Industry)
            OPTIONAL MATCH (c:Company)-[:BELONGS_TO]->(i)
            RETURN i.code AS code, i.name AS name, i.description AS description,
                   count(c) AS company_count
            ORDER BY i.code
            """
        )
        records = [r async for r in result]
    finally:
        await session.close()
    return [
        IndustryOut(
            code=r["code"],
            name=r["name"],
            description=r["description"],
            company_count=r["company_count"],
        )
        for r in records
    ]


@router.post("", response_model=IndustryOut)
async def create_industry(payload: IndustryIn) -> IndustryOut:
    """创建或更新行业（按 code 合并）。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MERGE (i:Industry {code: $code})
            SET i.name = $name, i.description = $description
            RETURN i.code AS code, i.name AS name, i.description AS description
            """,
            code=payload.code,
            name=payload.name,
            description=payload.description,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=500, detail="创建行业失败")
    return IndustryOut(
        code=record["code"],
        name=record["name"],
        description=record["description"],
        company_count=0,
    )


@router.delete("/{code}")
async def delete_industry(code: str, detach: bool = True) -> dict:
    """删除行业；detach=True 时同时删除与企业的关联。"""
    session = await neo4j_manager.get_session()
    try:
        query = (
            "MATCH (i:Industry {code: $code}) "
            "DETACH DELETE i"
            if detach
            else "MATCH (i:Industry {code: $code}) DELETE i"
        )
        result = await session.run(query, code=code)
        summary = await result.consume()
    finally:
        await session.close()
    return {"deleted": summary.counters.nodes_deleted}