"""企业管理路由。

当前 schema（2026 改造后）：企业节点仅保留 `id` 和 `name` 两个属性，
分类归属通过 `(Company)-[:BELONGS_TO]->(Theme)` 关系承载（多主题）。

为什么用「产业主题」(Theme) 而不是「行业」(Industry)：
- 行业（GB/T 4754）按"经济活动"细分（如 C384 电池制造、D4415 风力发电），
  一个企业可能横跨多个行业；
- 主题按"产业视角"组织（如「新能源」「新能源汽车」），更贴合业务语义；
- 一个企业可属于 1~N 个主题（如比亚迪 → [新能源汽车, 新能源]）。
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import CompanyIn, CompanyOut, CompanyRef, CompanyUpdate, ThemeRef


router = APIRouter(prefix="/api/companies", tags=["companies"])


# ---------------------------- 内部工具 ----------------------------

def _themes_to_refs(themes: list[dict | None]) -> list[ThemeRef]:
    """把 Cypher 返回的 themes 列表（dict）转成 ThemeRef，丢弃空项。"""
    out: list[ThemeRef] = []
    for t in themes:
        if not t or not t.get("slug"):
            continue
        out.append(
            ThemeRef(
                slug=t["slug"],
                name=t.get("name") or t["slug"],
                icon=t.get("icon") or "",
                color=t.get("color") or "#3b82f6",
            )
        )
    return out


def _row_to_company(record: dict) -> CompanyOut:
    themes = record.get("themes") or []
    return CompanyOut(
        id=record["id"],
        name=record["name"],
        themes=_themes_to_refs(themes),
    )


async def _validate_theme_slugs(session, slugs: list[str]) -> None:
    """校验 theme_slugs 中每个 slug 在 Neo4j 中都存在；缺失则 400。"""
    if not slugs:
        return  # 允许空（创建时强制至少 1 个由 schema 校验）
    result = await session.run(
        "MATCH (t:Theme) WHERE t.slug IN $slugs RETURN t.slug AS slug",
        slugs=list(set(slugs)),
    )
    found = {r["slug"] async for r in result}
    missing = [s for s in slugs if s not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"以下主题不存在：{', '.join(missing)}",
        )


# ---------------------------- 列表 ----------------------------

@router.get("", response_model=list[CompanyOut])
async def list_companies(
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    theme_slug: Optional[str] = Query(None, description="按主题筛选（企业至少属于该主题）"),
    limit: int = Query(200, ge=1, le=2000),
) -> list[CompanyOut]:
    """列出企业。可按名称模糊、按主题过滤。"""
    session = await neo4j_manager.get_session()
    try:
        # 一个企业可有多个主题。这里先 collect 全部主题，
        # 然后判断是否包含目标 theme_slug；不在集合里说明没匹配，过滤掉。
        cypher = """
            MATCH (c:Company)
            WHERE $keyword IS NULL OR c.name CONTAINS $keyword
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(t:Theme)
            WITH c, collect(DISTINCT {
                slug: t.slug, name: t.name, icon: coalesce(t.icon, ''), color: coalesce(t.color, '#3b82f6')
            }) AS themes
            WITH c, themes
            WHERE $theme_slug IS NULL
               OR ANY(th IN themes WHERE th.slug = $theme_slug)
            RETURN c.id AS id, c.name AS name, themes
            ORDER BY c.name
            LIMIT $limit
        """
        result = await session.run(
            cypher,
            keyword=keyword,
            theme_slug=theme_slug,
            limit=limit,
        )
        records = [r.data() async for r in result]
    finally:
        await session.close()
    return [_row_to_company(r) for r in records]


# ---------------------------- 创建 ----------------------------

@router.post("", response_model=CompanyOut)
async def create_company(payload: CompanyIn) -> CompanyOut:
    """创建企业；同时建立 `(Company)-[:BELONGS_TO]->(Theme)` 关系（多主题）。"""
    if not payload.theme_slugs:
        raise HTTPException(status_code=400, detail="请至少选择 1 个产业主题")

    company_id = str(uuid.uuid4())
    session = await neo4j_manager.get_session()
    try:
        await _validate_theme_slugs(session, payload.theme_slugs)

        # 去重并按 slug 排序，确保关系建立是稳定的
        unique_slugs = sorted(set(payload.theme_slugs))
        result = await session.run(
            """
            CREATE (c:Company {id: $id, name: $name})
            WITH c
            UNWIND $slugs AS slug
            MATCH (t:Theme {slug: slug})
            MERGE (c)-[:BELONGS_TO]->(t)
            WITH c
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(t2:Theme)
            WITH c, collect(DISTINCT {
                slug: t2.slug, name: t2.name,
                icon: coalesce(t2.icon, ''), color: coalesce(t2.color, '#3b82f6')
            }) AS themes
            RETURN c.id AS id, c.name AS name, themes
            """,
            id=company_id,
            name=payload.name,
            slugs=unique_slugs,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=500, detail="创建企业失败")
    return _row_to_company(record)


# ---------------------------- 详情 ----------------------------

@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str) -> CompanyOut:
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company {id: $id})
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(t:Theme)
            WITH c, collect(DISTINCT {
                slug: t.slug, name: t.name,
                icon: coalesce(t.icon, ''), color: coalesce(t.color, '#3b82f6')
            }) AS themes
            RETURN c.id AS id, c.name AS name, themes
            """,
            id=company_id,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return _row_to_company(record)


# ---------------------------- 更新 ----------------------------

@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(company_id: str, payload: CompanyUpdate) -> CompanyOut:
    """更新企业名称与所属主题。

    - `theme_slugs=None` 表示不动主题；
    - `theme_slugs=[]` 表示清空全部主题；
    - `theme_slugs=['xxx', 'yyy']` 表示替换为指定主题集合。
    """
    session = await neo4j_manager.get_session()
    try:
        # 仅在用户提供 theme_slugs 时校验
        if payload.theme_slugs is not None:
            await _validate_theme_slugs(session, payload.theme_slugs)

        # 用 `coalesce` 同时处理三种情况
        result = await session.run(
            """
            MATCH (c:Company {id: $id})
            SET c.name = coalesce($name, c.name)
            WITH c
            // 删除旧的主题关系
            OPTIONAL MATCH (c)-[r:BELONGS_TO]->(:Theme)
            DELETE r
            WITH c
            // 建立新的主题关系（仅在 theme_slugs 显式提供时执行）
            FOREACH (_ IN CASE WHEN $slugs IS NULL THEN [] ELSE [1] END |
                UNWIND $slugs AS slug
                MATCH (t:Theme {slug: slug})
                MERGE (c)-[:BELONGS_TO]->(t)
            )
            WITH c
            OPTIONAL MATCH (c)-[:BELONGS_TO]->(t2:Theme)
            WITH c, collect(DISTINCT {
                slug: t2.slug, name: t2.name,
                icon: coalesce(t2.icon, ''), color: coalesce(t2.color, '#3b82f6')
            }) AS themes
            // SET c = {id, name} 清理历史残留属性
            SET c = {id: c.id, name: c.name}
            RETURN c.id AS id, c.name AS name, themes
            """,
            id=company_id,
            name=payload.name,
            slugs=payload.theme_slugs if payload.theme_slugs is not None else None,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return _row_to_company(record)


# ---------------------------- 删除 ----------------------------

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


# ---------------------------- 主题下的企业（GET by-theme） ----------------------------
# 这里复用下方 `routers/themes.py` 的 `/api/themes/{slug}/companies`，
# 但提供一个从企业维度反向查询的便捷端点。

@router.get("/by-theme/{slug}", response_model=list[CompanyOut])
async def list_companies_by_theme(slug: str) -> list[CompanyOut]:
    """列出属于指定主题的所有企业。"""
    return await list_companies(theme_slug=slug, limit=2000)