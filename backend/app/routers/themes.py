"""产业主题 (Theme) 管理路由。

数据模型（2026 改造后）：
    (:Company {id, name}) -[:BELONGS_TO]-> (:Theme {slug, name, icon, color, description})

Theme 是分类维度的"主节点"——企业直接挂主题，不再有 Industry 节点。
一个企业可挂多个主题；一个主题可包含多个企业。

API 设计：
- GET    /api/themes                  列出所有主题（含企业数）
- GET    /api/themes/{slug}           主题详情（含企业列表）
- POST   /api/themes                  创建主题（slug 唯一）
- PUT    /api/themes/{slug}           更新主题
- DELETE /api/themes/{slug}           删除主题（同时删除企业的 BELONGS_TO 关系）
- GET    /api/themes/{slug}/companies 主题下的企业列表
- GET    /api/themes/{slug}/graph     主题下的图谱（含 Theme 节点）
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import CompanyRef, ThemeDetail, ThemeIn, ThemeOut


router = APIRouter(prefix="/api/themes", tags=["themes"])


# ---------------------------- 列表 ----------------------------

@router.get("", response_model=list[ThemeOut])
async def list_themes() -> list[ThemeOut]:
    """列出所有主题，按 category 顺序（同 category 内按企业数倒序）。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (t:Theme)
            OPTIONAL MATCH (c:Company)-[:BELONGS_TO]->(t)
            WITH t, count(DISTINCT c) AS cc
            RETURN t.slug AS slug,
                   t.name AS name,
                   coalesce(t.icon, '') AS icon,
                   coalesce(t.color, '#3b82f6') AS color,
                   coalesce(t.category, 'emerging') AS category,
                   coalesce(t.description, '') AS description,
                   cc AS company_count
            ORDER BY
                CASE coalesce(t.category, 'emerging')
                    WHEN 'emerging' THEN 0
                    WHEN 'traditional' THEN 1
                    WHEN 'service' THEN 2
                    ELSE 3
                END,
                cc DESC, t.slug
            """
        )
        records = [r async for r in result]
    finally:
        await session.close()

    return [
        ThemeOut(
            slug=r["slug"],
            name=r["name"],
            icon=r["icon"],
            color=r["color"],
            category=r["category"],
            description=r["description"],
            company_count=r["company_count"],
        )
        for r in records
    ]


# ---------------------------- 详情 ----------------------------

@router.get("/{slug}", response_model=ThemeDetail)
async def get_theme(
    slug: str,
    company_limit: int = Query(500, ge=1, le=5000),
) -> ThemeDetail:
    """获取主题详情（含企业列表）。"""
    session = await neo4j_manager.get_session()
    try:
        theme_result = await session.run(
            """
            MATCH (t:Theme {slug: $slug})
            RETURN t.slug AS slug,
                   t.name AS name,
                   coalesce(t.icon, '') AS icon,
                   coalesce(t.color, '#3b82f6') AS color,
                   coalesce(t.category, 'emerging') AS category,
                   coalesce(t.description, '') AS description
            """,
            slug=slug,
        )
        record = await theme_result.single()
        if record is None:
            raise HTTPException(status_code=404, detail=f"主题不存在: {slug}")

        comp_result = await session.run(
            """
            MATCH (c:Company)-[:BELONGS_TO]->(t:Theme {slug: $slug})
            RETURN c.id AS id, c.name AS name
            ORDER BY c.name
            LIMIT $limit
            """,
            slug=slug,
            limit=company_limit,
        )
        companies = [CompanyRef(id=r["id"], name=r["name"]) async for r in comp_result]
    finally:
        await session.close()

    return ThemeDetail(
        slug=record["slug"],
        name=record["name"],
        icon=record["icon"],
        color=record["color"],
        category=record["category"],
        description=record["description"],
        company_count=len(companies),
        companies=companies,
    )


# ---------------------------- 创建 ----------------------------

@router.post("", response_model=ThemeOut)
async def create_theme(payload: ThemeIn) -> ThemeOut:
    """创建主题。slug 必须唯一。"""
    session = await neo4j_manager.get_session()
    try:
        existing = await session.run(
            "MATCH (t:Theme {slug: $slug}) RETURN t.slug AS slug LIMIT 1",
            slug=payload.slug,
        )
        if (await existing.single()) is not None:
            raise HTTPException(status_code=409, detail=f"主题 slug 已存在: {payload.slug}")

        result = await session.run(
            """
            CREATE (t:Theme {slug: $slug, name: $name, icon: $icon,
                            color: $color, category: $category, description: $description})
            RETURN t.slug AS slug,
                   t.name AS name,
                   t.icon AS icon,
                   t.color AS color,
                   t.category AS category,
                   t.description AS description
            """,
            slug=payload.slug,
            name=payload.name,
            icon=payload.icon,
            color=payload.color,
            category=payload.category,
            description=payload.description,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=500, detail="创建主题失败")
    return ThemeOut(
        slug=record["slug"],
        name=record["name"],
        icon=record["icon"] or "",
        color=record["color"] or "#3b82f6",
        category=record["category"] or "emerging",
        description=record["description"] or "",
        company_count=0,
    )


# ---------------------------- 更新 ----------------------------

@router.put("/{slug}", response_model=ThemeOut)
async def update_theme(slug: str, payload: ThemeIn) -> ThemeOut:
    """更新主题。slug 是主键，更新时 URL 中的 slug 必须与 body 中一致。"""
    if payload.slug != slug:
        raise HTTPException(
            status_code=400,
            detail=f"slug 不能修改（URL: {slug}, body: {payload.slug}）。如需改名请删除后重建。",
        )
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (t:Theme {slug: $slug})
            SET t.name = $name,
                t.icon = $icon,
                t.color = $color,
                t.category = $category,
                t.description = $description
            RETURN t.slug AS slug,
                   t.name AS name,
                   t.icon AS icon,
                   t.color AS color,
                   t.category AS category,
                   t.description AS description
            """,
            slug=slug,
            name=payload.name,
            icon=payload.icon,
            color=payload.color,
            category=payload.category,
            description=payload.description,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=404, detail=f"主题不存在: {slug}")

    # 取企业数
    session = await neo4j_manager.get_session()
    try:
        cc_result = await session.run(
            """
            MATCH (c:Company)-[:BELONGS_TO]->(t:Theme {slug: $slug})
            RETURN count(c) AS cc
            """,
            slug=slug,
        )
        cc_record = await cc_result.single()
    finally:
        await session.close()
    cc = cc_record["cc"] if cc_record else 0

    return ThemeOut(
        slug=record["slug"],
        name=record["name"],
        icon=record["icon"] or "",
        color=record["color"] or "#3b82f6",
        category=record["category"] or "emerging",
        description=record["description"] or "",
        company_count=cc,
    )


# ---------------------------- 删除 ----------------------------

@router.delete("/{slug}")
async def delete_theme(
    slug: str,
    detach: bool = Query(True, description="是否同时删除企业的 BELONGS_TO 关系"),
) -> dict:
    """删除主题。默认 detach=true，会同时删除与企业之间的关联关系。"""
    session = await neo4j_manager.get_session()
    try:
        exists = await session.run(
            "MATCH (t:Theme {slug: $slug}) RETURN t.slug AS slug", slug=slug
        )
        if (await exists.single()) is None:
            raise HTTPException(status_code=404, detail=f"主题不存在: {slug}")

        query = (
            "MATCH (t:Theme {slug: $slug}) DETACH DELETE t"
            if detach
            else "MATCH (t:Theme {slug: $slug}) DELETE t"
        )
        result = await session.run(query, slug=slug)
        summary = await result.consume()
    finally:
        await session.close()
    return {
        "deleted_nodes": summary.counters.nodes_deleted,
        "deleted_relations": summary.counters.relationships_deleted,
    }


# ---------------------------- 主题下的企业 ----------------------------

@router.get("/{slug}/companies", response_model=list[CompanyRef])
async def list_companies_in_theme(
    slug: str,
    limit: int = Query(500, ge=1, le=5000),
) -> list[CompanyRef]:
    """列出该主题下的所有企业（精简引用 id+name）。"""
    session = await neo4j_manager.get_session()
    try:
        exists = await session.run(
            "MATCH (t:Theme {slug: $slug}) RETURN t.name AS name", slug=slug
        )
        if (await exists.single()) is None:
            raise HTTPException(status_code=404, detail=f"主题不存在: {slug}")

        result = await session.run(
            """
            MATCH (c:Company)-[:BELONGS_TO]->(t:Theme {slug: $slug})
            RETURN c.id AS id, c.name AS name
            ORDER BY c.name
            LIMIT $limit
            """,
            slug=slug,
            limit=limit,
        )
        companies = [CompanyRef(id=r["id"], name=r["name"]) async for r in result]
    finally:
        await session.close()
    return companies


# ---------------------------- 主题下的图谱（含 Theme 节点） ----------------------------

@router.get("/{slug}/graph")
async def theme_graph(
    slug: str,
    company_limit: int = Query(300, ge=1, le=2000),
    include_relations: bool = Query(True, description="是否包含企业之间的关系边"),
) -> dict:
    """返回主题下的子图：Theme 节点 + Company 节点 + 必要的关系边。"""
    session = await neo4j_manager.get_session()
    try:
        tr_run = await session.run(
            """
            MATCH (t:Theme {slug: $slug})
            RETURN t.slug AS slug,
                   t.name AS name,
                   coalesce(t.icon, '') AS icon,
                   coalesce(t.color, '#3b82f6') AS color,
                   coalesce(t.description, '') AS description
            """,
            slug=slug,
        )
        theme_record = await tr_run.single()
        if theme_record is None:
            raise HTTPException(status_code=404, detail=f"主题不存在: {slug}")

        nodes: list[dict] = [
            {
                "id": f"theme:{slug}",
                "label": "Theme",
                "name": theme_record["name"],
                "slug": theme_record["slug"],
                "icon": theme_record["icon"],
                "color": theme_record["color"],
                "description": theme_record["description"],
            }
        ]
        edges: list[dict] = []

        comp_result = await session.run(
            """
            MATCH (c:Company)-[:BELONGS_TO]->(t:Theme {slug: $slug})
            RETURN c.id AS id, c.name AS name
            ORDER BY c.name
            LIMIT $limit
            """,
            slug=slug,
            limit=company_limit,
        )
        companies = [r async for r in comp_result]
        for c in companies:
            nodes.append({"id": c["id"], "label": "Company", "name": c["name"]})
            edges.append(
                {
                    "id": f"belongs_to:{c['id']}:{slug}",
                    "source": c["id"],
                    "target": f"theme:{slug}",
                    "type": "BELONGS_TO",
                }
            )

        if include_relations and companies:
            ids = [c["id"] for c in companies]
            rel_result = await session.run(
                """
                MATCH (a:Company)-[r]->(b:Company)
                WHERE a.id IN $ids AND b.id IN $ids
                  AND type(r) <> 'BELONGS_TO'
                RETURN a.id AS a, b.id AS b, type(r) AS t
                """,
                ids=ids,
            )
            async for r in rel_result:
                edges.append(
                    {
                        "id": f"rel:{r['a']}:{r['b']}:{r['t']}",
                        "source": r["a"],
                        "target": r["b"],
                        "type": r["t"],
                    }
                )
    finally:
        await session.close()

    return {
        "theme": {
            "slug": theme_record["slug"],
            "name": theme_record["name"],
            "icon": theme_record["icon"],
            "color": theme_record["color"],
            "description": theme_record["description"],
        },
        "nodes": nodes,
        "edges": edges,
    }