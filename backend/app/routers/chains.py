"""产业链 (Chain / Stage) 管理路由。

数据模型：
    (:Chain {slug, name, icon, color, description})
      -[:HAS_STAGE {order}]->  (:Stage {chain_slug, code, name, description, level, order})
                                  ^
                                  |  (:Stage)-[:UPSTREAM_OF]->(:Stage)
                                  |
    (:Company)-[:IN_STAGE {note}]->(:Stage)         # 企业位于某环节
    (:Company)-[:SUPPLIES_TO {product, strength}]->(:Company)  # 企业间供货（已存在）

API 设计：
- GET    /api/chains                          列出所有链（含环节数/企业数）
- GET    /api/chains/{slug}                   链详情（含环节 + 上下游关系）
- GET    /api/chains/{slug}/graph             按层布局的图谱数据（前端 dagre 布局）
- GET    /api/chains/{slug}/stage/{code}      环节详情（含上下游企业清单，断链分析用）
- GET    /api/chains/{slug}/stage/{code}/upstream   上游环节及企业
- GET    /api/chains/{slug}/stage/{code}/downstream 下游环节及企业
- POST   /api/chains/{slug}/stage/{code}/companies/{company_id}    挂企业到环节
- DELETE /api/chains/{slug}/stage/{code}/companies/{company_id}    解绑
- GET    /api/companies/{id}/chains          查企业所在的产业链及环节
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import (
    ChainDetail,
    ChainGraphData,
    ChainGraphEdge,
    ChainGraphNode,
    ChainOut,
    CompanyChainOut,
    CompanyRef,
    StageOut,
    StageRef,
    UpDownStreamResult,
)
from ..theme_labels import load_theme_registry, refs_from_labels, theme_label_filter_expr


router = APIRouter(prefix="/api", tags=["chains"])


# ---------------------------- 内部辅助 ----------------------------

def _row_to_chain_out(record: dict) -> ChainOut:
    return ChainOut(
        slug=record["slug"],
        name=record["name"],
        icon=record.get("icon") or "",
        color=record.get("color") or "#0ea5e9",
        description=record.get("description") or "",
        stage_count=record.get("stage_count", 0),
        company_count=record.get("company_count", 0),
    )


async def _stage_out(session, chain_slug: str, stage_code: str) -> StageOut:
    """获取环节完整信息（含上下游 + 企业数）。"""
    result = await session.run(
        """
        MATCH (s:Stage {chain_slug: $chain_slug, code: $code})
        OPTIONAL MATCH (up:Stage)-[:UPSTREAM_OF]->(s)
        OPTIONAL MATCH (s)-[:UPSTREAM_OF]->(down:Stage)
        OPTIONAL MATCH (c:Company)-[:IN_STAGE]->(s)
        WITH s,
             collect(DISTINCT up.code) AS up_codes,
             collect(DISTINCT down.code) AS down_codes,
             count(DISTINCT c) AS cc
        RETURN s.code AS code,
               s.name AS name,
               coalesce(s.description, '') AS description,
               coalesce(s.order, 0) AS order,
               coalesce(s.level, 'middle') AS level,
               up_codes,
               down_codes,
               cc
        """,
        chain_slug=chain_slug,
        code=stage_code,
    )
    rec = await result.single()
    if rec is None:
        raise HTTPException(
            status_code=404,
            detail=f"环节不存在: {chain_slug}/{stage_code}",
        )
    return StageOut(
        code=rec["code"],
        name=rec["name"],
        description=rec["description"],
        order=rec["order"],
        level=rec["level"],
        upstream_codes=[k for k in rec["up_codes"] if k],
        downstream_codes=[k for k in rec["down_codes"] if k],
        company_count=rec["cc"],
    )


# ---------------------------- 链列表 ----------------------------

@router.get("/chains", response_model=list[ChainOut])
async def list_chains() -> list[ChainOut]:
    """列出所有产业链（含环节数、企业数）。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (ch:Chain)
            OPTIONAL MATCH (ch)-[:HAS_STAGE]->(s:Stage)
            WITH ch, count(DISTINCT s) AS stage_count
            OPTIONAL MATCH (c:Company)-[:IN_STAGE]->(s2:Stage)<-[:HAS_STAGE]-(ch)
            WITH ch, stage_count, count(DISTINCT c) AS company_count
            RETURN ch.slug AS slug,
                   ch.name AS name,
                   coalesce(ch.icon, '') AS icon,
                   coalesce(ch.color, '#0ea5e9') AS color,
                   coalesce(ch.description, '') AS description,
                   stage_count,
                   company_count
            ORDER BY ch.slug
            """
        )
        records = [r async for r in result]
    finally:
        await session.close()
    return [_row_to_chain_out(r) for r in records]


# ---------------------------- 链详情 ----------------------------

@router.get("/chains/{slug}", response_model=ChainDetail)
async def get_chain(slug: str) -> ChainDetail:
    """获取产业链详情（含全部环节，按 order 排序）。"""
    session = await neo4j_manager.get_session()
    try:
        ch_run = await session.run(
            """
            MATCH (ch:Chain {slug: $slug})
            RETURN ch.slug AS slug, ch.name AS name,
                   coalesce(ch.icon, '') AS icon,
                   coalesce(ch.color, '#0ea5e9') AS color,
                   coalesce(ch.description, '') AS description
            """,
            slug=slug,
        )
        ch = await ch_run.single()
        if ch is None:
            raise HTTPException(status_code=404, detail=f"产业链不存在: {slug}")

        stages = [
            await _stage_out(session, slug, stage_code)
            for stage_code in _stage_codes_in_order(session, slug)
        ]
    finally:
        await session.close()

    return ChainDetail(
        slug=ch["slug"],
        name=ch["name"],
        icon=ch["icon"],
        color=ch["color"],
        description=ch["description"],
        stages=stages,
    )


async def _stage_codes_in_order(session, slug: str) -> list[str]:
    """返回某链下所有环节 code，按 order 排序。"""
    result = await session.run(
        """
        MATCH (:Chain {slug: $slug})-[:HAS_STAGE]->(s:Stage)
        RETURN s.code AS code
        ORDER BY s.order, s.code
        """,
        slug=slug,
    )
    return [r["code"] async for r in result]


# ---------------------------- 链下图谱（按层布局） ----------------------------

@router.get("/chains/{slug}/graph", response_model=ChainGraphData)
async def chain_graph(slug: str) -> ChainGraphData:
    """返回该产业链的分层图谱数据。

    节点：
        - 1 个 Chain 根节点（链头）
        - N 个 Stage 节点（按 order 分层）
        - M 个 Company 节点（挂在对应 Stage 下）

    边：
        - Chain -[HAS_STAGE]-> Stage
        - Stage -[UPSTREAM_OF]-> Stage（上下游）
        - Company -[IN_STAGE]-> Stage
    """
    session = await neo4j_manager.get_session()
    try:
        ch_run = await session.run(
            """
            MATCH (ch:Chain {slug: $slug})
            RETURN ch.slug AS slug, ch.name AS name,
                   coalesce(ch.icon, '') AS icon,
                   coalesce(ch.color, '#0ea5e9') AS color,
                   coalesce(ch.description, '') AS description
            """,
            slug=slug,
        )
        ch = await ch_run.single()
        if ch is None:
            raise HTTPException(status_code=404, detail=f"产业链不存在: {slug}")

        nodes: list[ChainGraphNode] = []
        edges: list[ChainGraphEdge] = []

        # Chain 根节点
        nodes.append(
            ChainGraphNode(
                id=f"chain:{slug}",
                label="Chain",
                name=ch["name"],
                level=0,
            )
        )

        # Stage 节点
        st_run = await session.run(
            """
            MATCH (:Chain {slug: $slug})-[:HAS_STAGE]->(s:Stage)
            RETURN s.code AS code, s.name AS name,
                   coalesce(s.level, 'middle') AS level,
                   coalesce(s.order, 1) AS order
            ORDER BY s.order
            """,
            slug=slug,
        )
        stages = [r async for r in st_run]
        for s in stages:
            sid = f"stage:{slug}:{s['code']}"
            nodes.append(
                ChainGraphNode(
                    id=sid,
                    label="Stage",
                    name=s["name"],
                    level=s["order"],
                    stage_code=s["code"],
                )
            )
            edges.append(
                ChainGraphEdge(
                    id=f"has_stage:{slug}:{s['code']}",
                    source=f"chain:{slug}",
                    target=sid,
                    type="HAS_STAGE",
                    label="包含",
                )
            )

        # UPSTREAM_OF
        up_run = await session.run(
            """
            MATCH (a:Stage)-[:UPSTREAM_OF]->(b:Stage)
            WHERE a.chain_slug = $slug AND b.chain_slug = $slug
            RETURN a.code AS a, b.code AS b
            """,
            slug=slug,
        )
        async for r in up_run:
            edges.append(
                ChainGraphEdge(
                    id=f"upstream:{r['a']}:{r['b']}",
                    source=f"stage:{slug}:{r['a']}",
                    target=f"stage:{slug}:{r['b']}",
                    type="UPSTREAM_OF",
                    label="→",
                )
            )

        # Company 节点 + IN_STAGE 边（主题 = 企业标签 ∩ 注册表）
        registry = await load_theme_registry(session)
        comp_run = await session.run(
            f"""
            MATCH (c:Company)-[:IN_STAGE]->(s:Stage {{chain_slug: $slug}})
            WITH c, s, {theme_label_filter_expr()} AS themeLabels
            RETURN c.id AS id, c.name AS name, s.code AS stage_code,
                   s.order AS stage_order, themeLabels
            ORDER BY c.name
            """,
            slug=slug,
            themeLabels=list(registry.keys()),
        )
        async for r in comp_run:
            themes = refs_from_labels(r["themeLabels"], registry)
            nodes.append(
                ChainGraphNode(
                    id=r["id"],
                    label="Company",
                    name=r["name"],
                    level=r["stage_order"] + 0.5,  # 介于 stage 节点层 +1
                    stage_code=r["stage_code"],
                    themes=themes,
                )
            )
            edges.append(
                ChainGraphEdge(
                    id=f"in_stage:{r['id']}:{r['stage_code']}",
                    source=r["id"],
                    target=f"stage:{slug}:{r['stage_code']}",
                    type="IN_STAGE",
                    label="归属",
                )
            )
    finally:
        await session.close()

    return ChainGraphData(
        chain={
            "slug": ch["slug"],
            "name": ch["name"],
            "icon": ch["icon"],
            "color": ch["color"],
            "description": ch["description"],
        },
        nodes=nodes,
        edges=edges,
    )


# ---------------------------- 环节详情（含上下游企业） ----------------------------

@router.get(
    "/chains/{slug}/stage/{code}",
    response_model=UpDownStreamResult,
)
async def get_stage_detail(slug: str, code: str) -> UpDownStreamResult:
    """获取环节详情 + 直接上下游企业清单（用于断链分析）。"""
    session = await neo4j_manager.get_session()
    try:
        stage = await _stage_out(session, slug, code)

        # 上游环节（含公司）
        up_stages_run = await session.run(
            """
            MATCH (up:Stage)-[:UPSTREAM_OF]->(s:Stage {chain_slug: $slug, code: $code})
            OPTIONAL MATCH (c:Company)-[:IN_STAGE]->(up)
            WITH up, collect({id: c.id, name: c.name}) AS comps
            RETURN up.code AS code, up.name AS name, up.order AS order, comps
            ORDER BY up.order
            """,
            slug=slug,
            code=code,
        )
        upstream_stages: list[StageRef] = []
        upstream_companies: list[CompanyRef] = []
        async for r in up_stages_run:
            upstream_stages.append(
                StageRef(code=r["code"], name=r["name"], order=r["order"])
            )
            for c in r["comps"]:
                if c and c.get("id"):
                    upstream_companies.append(
                        CompanyRef(id=c["id"], name=c.get("name") or "")
                    )

        # 下游环节
        down_stages_run = await session.run(
            """
            MATCH (s:Stage {chain_slug: $slug, code: $code})-[:UPSTREAM_OF]->(down:Stage)
            OPTIONAL MATCH (c:Company)-[:IN_STAGE]->(down)
            WITH down, collect({id: c.id, name: c.name}) AS comps
            RETURN down.code AS code, down.name AS name, down.order AS order, comps
            ORDER BY down.order
            """,
            slug=slug,
            code=code,
        )
        downstream_stages: list[StageRef] = []
        downstream_companies: list[CompanyRef] = []
        async for r in down_stages_run:
            downstream_stages.append(
                StageRef(code=r["code"], name=r["name"], order=r["order"])
            )
            for c in r["comps"]:
                if c and c.get("id"):
                    downstream_companies.append(
                        CompanyRef(id=c["id"], name=c.get("name") or "")
                    )
    finally:
        await session.close()

    return UpDownStreamResult(
        stage=stage,
        upstream_stages=upstream_stages,
        downstream_stages=downstream_stages,
        upstream_companies=upstream_companies,
        downstream_companies=downstream_companies,
    )


@router.get(
    "/chains/{slug}/stage/{code}/upstream",
    response_model=UpDownStreamResult,
)
async def get_upstream(slug: str, code: str) -> UpDownStreamResult:
    """只取上游环节及企业。"""
    full = await get_stage_detail(slug, code)
    return UpDownStreamResult(
        stage=full.stage,
        upstream_stages=full.upstream_stages,
        downstream_stages=[],
        upstream_companies=full.upstream_companies,
        downstream_companies=[],
    )


@router.get(
    "/chains/{slug}/stage/{code}/downstream",
    response_model=UpDownStreamResult,
)
async def get_downstream(slug: str, code: str) -> UpDownStreamResult:
    """只取下游环节及企业。"""
    full = await get_stage_detail(slug, code)
    return UpDownStreamResult(
        stage=full.stage,
        upstream_stages=[],
        downstream_stages=full.downstream_stages,
        upstream_companies=[],
        downstream_companies=full.downstream_companies,
    )


# ---------------------------- 企业挂环节 ----------------------------

@router.post("/chains/{slug}/stage/{code}/companies/{company_id}")
async def attach_company(
    slug: str,
    code: str,
    company_id: str,
    note: str = Query("", description="备注"),
) -> dict:
    """把企业挂到该环节。会自动解绑该企业在该链上的其他环节（一个企业在一链中只能处于一个环节）。"""
    session = await neo4j_manager.get_session()
    try:
        # 检查 stage 存在
        st = await session.run(
            "MATCH (s:Stage {chain_slug: $slug, code: $code}) RETURN s.code AS code LIMIT 1",
            slug=slug, code=code,
        )
        if (await st.single()) is None:
            raise HTTPException(status_code=404, detail=f"环节不存在: {slug}/{code}")

        # 检查 company 存在
        co = await session.run(
            "MATCH (c:Company {id: $id}) RETURN c.id AS id LIMIT 1",
            id=company_id,
        )
        if (await co.single()) is None:
            raise HTTPException(status_code=404, detail=f"企业不存在: {company_id}")

        # 删除该企业在该链上的旧 IN_STAGE，再建新的
        result = await session.run(
            """
            MATCH (c:Company {id: $company_id})-[old:IN_STAGE]->(s:Stage {chain_slug: $slug})
            DELETE old
            WITH c, $slug AS slug, $code AS code, $note AS note
            MATCH (s2:Stage {chain_slug: slug, code: code})
            MERGE (c)-[:IN_STAGE {note: note}]->(s2)
            RETURN s2.code AS attached_to
            """,
            company_id=company_id,
            slug=slug,
            code=code,
            note=note,
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        raise HTTPException(status_code=500, detail="挂载失败")
    return {"attached_to": record["attached_to"]}


@router.delete("/chains/{slug}/stage/{code}/companies/{company_id}")
async def detach_company(slug: str, code: str, company_id: str) -> dict:
    """解除企业在该环节的归属。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company {id: $company_id})-[r:IN_STAGE]->(s:Stage {chain_slug: $slug, code: $code})
            DELETE r
            RETURN count(r) AS deleted
            """,
            company_id=company_id, slug=slug, code=code,
        )
        record = await result.single()
    finally:
        await session.close()
    return {"deleted": record["deleted"] if record else 0}


# ---------------------------- 企业所在产业链 ----------------------------

@router.get(
    "/companies/{company_id}/chains",
    response_model=list[CompanyChainOut],
)
async def get_company_chains(company_id: str) -> list[CompanyChainOut]:
    """查询企业所在的产业链及环节（一个企业可同时在多个链的不同环节）。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            MATCH (c:Company {id: $company_id})-[:IN_STAGE]->(s:Stage)
            MATCH (ch:Chain)-[:HAS_STAGE]->(s)
            RETURN c.id AS company_id, c.name AS company_name,
                   ch.slug AS chain_slug, ch.name AS chain_name,
                   coalesce(ch.color, '#0ea5e9') AS chain_color,
                   s.code AS stage_code, s.name AS stage_name,
                   coalesce(s.order, 0) AS stage_order
            ORDER BY ch.slug, s.order
            """,
            company_id=company_id,
        )
        records = [r async for r in result]
    finally:
        await session.close()
    if not records:
        # 检查 company 是否存在
        session2 = await neo4j_manager.get_session()
        try:
            ex = await session2.run(
                "MATCH (c:Company {id: $id}) RETURN c.id LIMIT 1", id=company_id,
            )
            if (await ex.single()) is None:
                raise HTTPException(status_code=404, detail=f"企业不存在: {company_id}")
        finally:
            await session2.close()
        return []
    return [
        CompanyChainOut(
            company_id=r["company_id"],
            company_name=r["company_name"],
            chain_slug=r["chain_slug"],
            chain_name=r["chain_name"],
            chain_color=r["chain_color"],
            stage_code=r["stage_code"],
            stage_name=r["stage_name"],
            stage_order=r["stage_order"],
        )
        for r in records
    ]