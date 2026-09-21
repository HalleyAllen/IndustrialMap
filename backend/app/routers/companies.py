"""企业管理路由。

当前 schema（2026 二次改造后）：企业节点仅保留 `id` 和 `name` 两个属性，
所属**产业主题直接作为企业节点的 Neo4j 标签**（如 `(:Company:新能源 {id, name})`）。
Theme 节点仅作为配置注册表（slug / name / icon / color），企业不再与其建关系。
标签必须来自注册表白名单，拼接前经反引号转义（见 `theme_labels.py`）。

为什么用「产业主题」(Theme) 而不是「行业」(Industry)：
- 行业（GB/T 4754）按"经济活动"细分（如 C384 电池制造、D4415 风力发电），
  一个企业可能横跨多个行业；
- 主题按"产业视角"组织（如「新能源」「新能源汽车」），更贴合业务语义；
- 一个企业可属于 0~N 个主题（如比亚迪 → [新能源汽车, 新能源]）。
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import (
    CompanyIn,
    CompanyOut,
    CompanyRef,
    CompanyUpdate,
    IndustryCategoryRef,
    ThemeRef,
)
from ..theme_labels import (
    label_remove_clause,
    label_set_clause,
    load_theme_registry,
    refs_from_labels,
    theme_label_filter_expr,
    validate_slugs,
)
from .industries import descendant_codes, validate_industry_codes


router = APIRouter(prefix="/api/companies", tags=["companies"])


# ---------------------------- 内部工具 ----------------------------

def _industries_to_refs(items: list[dict | None]) -> list[IndustryCategoryRef]:
    """把 Cypher 返回的 industries 列表（dict）转成 IndustryCategoryRef。"""
    out: list[IndustryCategoryRef] = []
    for it in items:
        if not it or not it.get("code"):
            continue
        out.append(
            IndustryCategoryRef(
                code=it["code"],
                name=it.get("name") or it["code"],
                level=it.get("level") or 4,
                level_name=it.get("level_name") or "",
            )
        )
    return out


def _row_to_company(record: dict, registry: dict[str, ThemeRef]) -> CompanyOut:
    return CompanyOut(
        id=record["id"],
        name=record["name"],
        themes=refs_from_labels(record.get("themeLabels") or [], registry),
        industries=_industries_to_refs(record.get("industries") or []),
    )


async def _validate_theme_slugs(
    session, registry: dict[str, ThemeRef], slugs: list[str]
) -> list[str]:
    """白名单校验（注册表来自 Theme 节点）；返回去重排序后的 slug。"""
    return validate_slugs(registry, slugs)


# ---------------------------- 列表 ----------------------------

@router.get("", response_model=list[CompanyOut])
async def list_companies(
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    theme_slug: Optional[str] = Query(None, description="按主题筛选（企业至少属于该主题）"),
    industry_code: Optional[str] = Query(
        None, description="按行业分类筛选（含子分类，如传大类 13 会带出其下小类企业）"
    ),
    limit: int = Query(200, ge=1, le=2000),
) -> list[CompanyOut]:
    """列出企业。可按名称模糊、按主题、按行业分类（含子级）过滤。"""
    # 行业分类要先展开子级；用静态目录在应用层算，避免 Cypher 过于复杂
    industry_codes = descendant_codes(industry_code) if industry_code else None

    session = await neo4j_manager.get_session()
    try:
        registry = await load_theme_registry(session)
        # 一个企业可有多个主题标签。先取标签再判断，避免多值匹配把行数撑开。
        cypher = f"""
            MATCH (c:Company)
            WHERE ($keyword IS NULL OR c.name CONTAINS $keyword)
              AND ($theme_slug IS NULL OR $theme_slug IN labels(c))
            WITH c, {theme_label_filter_expr()} AS themeLabels
            OPTIONAL MATCH (c)-[:IN_INDUSTRY]->(n:IndustryCategory)
            WITH c, themeLabels, collect(DISTINCT {{
                code: n.code, name: n.name,
                level: coalesce(n.level, 4), level_name: coalesce(n.level_name, '')
            }}) AS industries
            WITH c, themeLabels, industries
            WHERE $industry_codes IS NULL
               OR ANY(i IN industries WHERE i.code IN $industry_codes)
            RETURN c.id AS id, c.name AS name, themeLabels, industries
            ORDER BY c.name
            LIMIT $limit
        """
        result = await session.run(
            cypher,
            keyword=keyword,
            theme_slug=theme_slug,
            themeLabels=list(registry.keys()),
            industry_codes=industry_codes,
            limit=limit,
        )
        records = [r.data() async for r in result]
    finally:
        await session.close()
    return [_row_to_company(r, registry) for r in records]


# ---------------------------- 创建 ----------------------------

@router.post("", response_model=CompanyOut)
async def create_company(payload: CompanyIn) -> CompanyOut:
    """创建企业；产业主题直接作为企业节点的 Neo4j 标签（0~N 个）。"""
    company_id = str(uuid.uuid4())
    session = await neo4j_manager.get_session()
    try:
        registry = await load_theme_registry(session)
        unique_slugs = await _validate_theme_slugs(session, registry, payload.theme_slugs)
        await validate_industry_codes(session, payload.industry_codes)

        unique_codes = sorted(set(payload.industry_codes))
        # 标签不能用参数传，只能在白名单校验后拼接（label_set_clause 内含转义）
        result = await session.run(
            f"""
            CREATE (c:Company {{id: $id, name: $name}}){label_set_clause(unique_slugs)}
            WITH c
            UNWIND (CASE WHEN size($codes) = 0 THEN [null] ELSE $codes END) AS icode
            OPTIONAL MATCH (n:IndustryCategory {{code: icode}})
            FOREACH (_ IN CASE WHEN n IS NULL THEN [] ELSE [1] END |
                MERGE (c)-[:IN_INDUSTRY]->(n)
            )
            WITH DISTINCT c
            OPTIONAL MATCH (c)-[:IN_INDUSTRY]->(n2:IndustryCategory)
            RETURN c.id AS id, c.name AS name, labels(c) AS themeLabels,
                   collect(DISTINCT {{
                       code: n2.code, name: n2.name,
                       level: coalesce(n2.level, 4), level_name: coalesce(n2.level_name, '')
                   }}) AS industries
            """,
            id=company_id,
            name=payload.name,
            codes=unique_codes,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=500, detail="创建企业失败")
    return _row_to_company(record.data(), registry)


# ---------------------------- 详情 ----------------------------

@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str) -> CompanyOut:
    session = await neo4j_manager.get_session()
    try:
        registry = await load_theme_registry(session)
        result = await session.run(
            f"""
            MATCH (c:Company {{id: $id}})
            WITH c, {theme_label_filter_expr()} AS themeLabels
            OPTIONAL MATCH (c)-[:IN_INDUSTRY]->(n:IndustryCategory)
            RETURN c.id AS id, c.name AS name, themeLabels,
                   collect(DISTINCT {{
                       code: n.code, name: n.name,
                       level: coalesce(n.level, 4), level_name: coalesce(n.level_name, '')
                   }}) AS industries
            """,
            id=company_id,
            themeLabels=list(registry.keys()),
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return _row_to_company(record.data(), registry)


# ---------------------------- 更新 ----------------------------

@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(company_id: str, payload: CompanyUpdate) -> CompanyOut:
    """更新企业名称、所属主题与行业分类。

    三个字段都是三态语义（`theme_slugs` / `industry_codes` 相同）：
    - `None`   表示不动该维度；
    - `[]`     表示清空该维度的全部关联；
    - `[a, b]` 表示替换为指定集合。
    """
    session = await neo4j_manager.get_session()
    try:
        exists = await session.run(
            "MATCH (c:Company {id: $id}) RETURN c.id AS id", id=company_id
        )
        if (await exists.single()) is None:
            raise HTTPException(status_code=404, detail="企业不存在")

        registry = await load_theme_registry(session)

        # 仅在用户显式提供时校验
        if payload.theme_slugs is not None:
            unique_slugs = validate_slugs(registry, payload.theme_slugs)
        if payload.industry_codes is not None:
            await validate_industry_codes(session, payload.industry_codes)

        if payload.name is not None:
            await session.run(
                "MATCH (c:Company {id: $id}) SET c.name = $name",
                id=company_id,
                name=payload.name,
            )

        # ---- 主题标签：None 不动 / [] 清空 / [..] 替换 ----
        # 先 REMOVE 注册表内的全部主题标签（没有该标签时 REMOVE 是空操作），
        # 再 SET 新标签。标签经白名单校验 + 反引号转义后拼接。
        if payload.theme_slugs is not None:
            clause = label_remove_clause(list(registry.keys()))
            if unique_slugs:
                clause += label_set_clause(unique_slugs)
            if clause:
                await session.run(
                    f"MATCH (c:Company {{id: $id}}){clause}",
                    id=company_id,
                )

        # ---- 行业分类：同样的三态语义 ----
        if payload.industry_codes is not None:
            await session.run(
                "MATCH (c:Company {id: $id})-[r:IN_INDUSTRY]->(:IndustryCategory) DELETE r",
                id=company_id,
            )
            if payload.industry_codes:
                await session.run(
                    """
                    MATCH (c:Company {id: $id})
                    UNWIND $codes AS code
                    MATCH (n:IndustryCategory {code: code})
                    MERGE (c)-[:IN_INDUSTRY]->(n)
                    """,
                    id=company_id,
                    codes=sorted(set(payload.industry_codes)),
                )

        result = await session.run(
            f"""
            MATCH (c:Company {{id: $id}})
            // 重置属性为 id/name，清理历史残留字段
            SET c = {{id: c.id, name: c.name}}
            WITH c, {theme_label_filter_expr()} AS themeLabels
            OPTIONAL MATCH (c)-[:IN_INDUSTRY]->(n:IndustryCategory)
            RETURN c.id AS id, c.name AS name, themeLabels,
                   collect(DISTINCT {{
                       code: n.code, name: n.name,
                       level: coalesce(n.level, 4), level_name: coalesce(n.level_name, '')
                   }}) AS industries
            """,
            id=company_id,
            themeLabels=list(registry.keys()),
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    return _row_to_company(record.data(), registry)


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