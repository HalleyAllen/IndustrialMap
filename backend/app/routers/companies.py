"""企业管理路由。"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import CompanyEnrichOut, CompanyIn, CompanyOut, CompanyUpdate
from ..services import ai_service


router = APIRouter(prefix="/api/companies", tags=["companies"])


def _row_to_company(record: dict) -> CompanyOut:
    extra_raw = record.get("extra")
    extra = None
    if extra_raw:
        if isinstance(extra_raw, dict):
            extra = extra_raw
        else:
            try:
                extra = json.loads(extra_raw)
            except (TypeError, json.JSONDecodeError):
                extra = None
    return CompanyOut(
        id=record["id"],
        name=record["name"],
        industry_code=record.get("industry_code"),
        industry_name=record.get("industry_name"),
        description=record.get("description"),
        address=record.get("address"),
        founded_year=record.get("founded_year"),
        scale=record.get("scale"),
        website=record.get("website"),
        extra=extra,
    )


@router.get("", response_model=list[CompanyOut])
async def list_companies(
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    industry_code: Optional[str] = Query(None, description="按行业筛选"),
    limit: int = Query(200, ge=1, le=2000),
) -> list[CompanyOut]:
    session = await neo4j_manager.get_session()
    try:
        cypher = """
            MATCH (c:Company)
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(i:Industry)
            WHERE ($keyword IS NULL OR c.name CONTAINS $keyword)
              AND ($industry_code IS NULL OR i.code = $industry_code)
            RETURN c.id AS id, c.name AS name, c.description AS description,
                   c.address AS address, c.founded_year AS founded_year,
                   c.scale AS scale, c.website AS website, c.extra AS extra,
                   i.code AS industry_code, i.name AS industry_name
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
            """
            CREATE (c:Company {
                id: $id,
                name: $name,
                description: $description,
                address: $address,
                founded_year: $founded_year,
                scale: $scale,
                website: $website,
                extra: $extra
            })
            WITH c
            OPTIONAL MATCH (i:Industry {code: $industry_code})
            FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:BELONGS_TO]->(i)
            )
            RETURN c.id AS id, c.name AS name, c.description AS description,
                   c.address AS address, c.founded_year AS founded_year,
                   c.scale AS scale, c.website AS website, c.extra AS extra,
                   i.code AS industry_code, i.name AS industry_name
            """,
            id=company_id,
            name=payload.name,
            description=payload.description,
            address=payload.address,
            founded_year=payload.founded_year,
            scale=payload.scale,
            website=payload.website,
            extra=json.dumps(payload.extra or {}, ensure_ascii=False),
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
            """
            MATCH (c:Company {id: $id})
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(i:Industry)
            RETURN c.id AS id, c.name AS name, c.description AS description,
                   c.address AS address, c.founded_year AS founded_year,
                   c.scale AS scale, c.website AS website, c.extra AS extra,
                   i.code AS industry_code, i.name AS industry_name
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
    """更新企业基础信息及行业归属。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company {id: $id})
            SET c.name = COALESCE($name, c.name),
                c.description = COALESCE($description, c.description),
                c.address = COALESCE($address, c.address),
                c.founded_year = COALESCE($founded_year, c.founded_year),
                c.scale = COALESCE($scale, c.scale),
                c.website = COALESCE($website, c.website)
            WITH c
            OPTIONAL MATCH (c)-[r:BELONGS_TO]->(:Industry)
            DELETE r
            WITH c
            OPTIONAL MATCH (i:Industry {code: $industry_code})
            FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:BELONGS_TO]->(i)
            )
            RETURN c.id AS id, c.name AS name, c.description AS description,
                   c.address AS address, c.founded_year AS founded_year,
                   c.scale AS scale, c.website AS website, c.extra AS extra,
                   i.code AS industry_code, i.name AS industry_name
            """,
            id=company_id,
            name=payload.name,
            description=payload.description,
            address=payload.address,
            founded_year=payload.founded_year,
            scale=payload.scale,
            website=payload.website,
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


@router.post("/{company_id}/enrich", response_model=CompanyEnrichOut)
async def enrich_company(
    company_id: str,
    write_back: bool = False,
    user_hint: Optional[str] = None,
) -> CompanyEnrichOut:
    """AI 信息补全。

    根据企业已有字段，调用管理员配置的 LLM 推断缺失字段。
    默认仅返回补全建议（不写回），前端可让用户确认后再写回；
    设置 ?write_back=true 则立即把非空字段写回 Neo4j。
    """
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company {id: $id})
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(i:Industry)
            RETURN c.id AS id, c.name AS name, c.description AS description,
                   c.address AS address, c.founded_year AS founded_year,
                   c.scale AS scale, c.website AS website,
                   i.name AS industry_name
            """,
            id=company_id,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在")

    suggestions = await ai_service.enrich_company(
        {
            "name": record["name"],
            "industry_name": record["industry_name"],
            "description": record["description"],
            "address": record["address"],
            "founded_year": record["founded_year"],
            "scale": record["scale"],
            "website": record["website"],
        },
        user_hint=user_hint,
    )

    if write_back:
        # 仅把当前为空的字段写入，避免覆盖人工数据
        update_fields: dict[str, object] = {}
        for f in ("description", "website", "address", "scale"):
            if not record.get(f) and suggestions.get(f):
                update_fields[f] = suggestions[f]
        if not record.get("founded_year") and suggestions.get("founded_year"):
            update_fields["founded_year"] = suggestions["founded_year"]
        if update_fields:
            async with await neo4j_manager.get_session() as session:
                await session.run(
                    """
                    MATCH (c:Company {id: $id})
                    SET c += $fields, c.ai_enriched_at = datetime()
                    """,
                    id=company_id,
                    fields=update_fields,
                )

    return CompanyEnrichOut(company_id=company_id, suggestions=suggestions)


@router.post("/{company_id}/enrich/apply")
async def apply_enrichment(company_id: str, payload: dict) -> dict:
    """把前端已经编辑过的补全结果写回 Neo4j。"""
    fields: dict[str, object] = {}
    for f in ("description", "website", "address", "scale"):
        v = payload.get(f)
        if v not in (None, ""):
            fields[f] = v
    y = payload.get("founded_year")
    if y not in (None, "", 0):
        try:
            fields["founded_year"] = int(y)
        except (TypeError, ValueError):
            pass
    if not fields:
        return {"written": 0}
    session = await neo4j_manager.get_session()
    try:
        await session.run(
            """
            MATCH (c:Company {id: $id})
            SET c += $fields, c.ai_enriched_at = datetime()
            """,
            id=company_id,
            fields=fields,
        )
    finally:
        await session.close()
    return {"written": len(fields)}