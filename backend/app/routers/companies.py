"""企业管理路由。

当前 schema 精简后，企业节点仅保留 `id` 和 `name` 两个属性，
行业归属通过 `(Company)-[:BELONGS_TO]->(Industry)` 关系承载。
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import CompanyIn, CompanyOut, CompanyUpdate


router = APIRouter(prefix="/api/companies", tags=["companies"])


# 仅返回 id / name / 行业（code + name）三组字段
_COMPANY_RETURN = (
    "c.id AS id, c.name AS name, "
    "i.code AS industry_code, i.name AS industry_name"
)


def _row_to_company(record: dict) -> CompanyOut:
    return CompanyOut(
        id=record["id"],
        name=record["name"],
        industry_code=record.get("industry_code"),
        industry_name=record.get("industry_name"),
    )


@router.get("", response_model=list[CompanyOut])
async def list_companies(
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    industry_code: Optional[str] = Query(None, description="按行业筛选"),
    limit: int = Query(200, ge=1, le=2000),
) -> list[CompanyOut]:
    session = await neo4j_manager.get_session()
    try:
        cypher = f"""
            MATCH (c:Company)
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(i:Industry)
            WHERE ($keyword IS NULL OR c.name CONTAINS $keyword)
              AND ($industry_code IS NULL OR i.code = $industry_code)
            RETURN {_COMPANY_RETURN}
            ORDER BY c.name
            LIMIT $limit
        """
        result = await session.run(
            cypher,
            keyword=keyword,
            industry_code=industry_code,
            limit=limit,
        )
        records = [r.data() async for r in result]
    finally:
        await session.close()
    return [_row_to_company(r) for r in records]


@router.post("", response_model=CompanyOut)
async def create_company(payload: CompanyIn) -> CompanyOut:
    company_id = str(uuid.uuid4())
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            f"""
            CREATE (c:Company {{id: $id, name: $name}})
            WITH c
            OPTIONAL MATCH (i:Industry {{code: $industry_code}})
            FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:BELONGS_TO]->(i)
            )
            RETURN {_COMPANY_RETURN}
            """,
            id=company_id,
            name=payload.name,
            industry_code=payload.industry_code,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=500, detail="创建企业失败")
    return _row_to_company(record)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str) -> CompanyOut:
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            f"""
            MATCH (c:Company {{id: $id}})
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(i:Industry)
            RETURN {_COMPANY_RETURN}
            """,
            id=company_id,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return _row_to_company(record)


@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(company_id: str, payload: CompanyUpdate) -> CompanyOut:
    """更新企业名称与行业归属。

    通过 `SET c = {id, name}` 把历史上残留的额外属性（如 description / scale 等）
    一并清理掉，让 Company 节点始终保持 `{id, name}` 两个属性。
    """
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company {id: $id})
            SET c.name = COALESCE($name, c.name)
            WITH c
            OPTIONAL MATCH (c)-[r:BELONGS_TO]->(:Industry)
            DELETE r
            WITH c
            OPTIONAL MATCH (i:Industry {code: $industry_code})
            FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:BELONGS_TO]->(i)
            )
            WITH c, i
            SET c = {id: c.id, name: c.name}
            RETURN c.id AS id, c.name AS name,
                   i.code AS industry_code, i.name AS industry_name
            """,
            id=company_id,
            name=payload.name,
            industry_code=payload.industry_code,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return _row_to_company(record)


@router.delete("/{company_id}")
async def delete_company(company_id: str, detach: bool = True) -> dict:
    session = await neo4j_manager.get_session()
    try:
        query = (
            "MATCH (c:Company {id: $id}) DETACH DELETE c"
            if detach
            else "MATCH (c:Company {id: $id}) DELETE c"
        )
        result = await session.run(query, id=company_id)
        summary = await result.consume()
    finally:
        await session.close()
    return {"deleted": summary.counters.nodes_deleted}