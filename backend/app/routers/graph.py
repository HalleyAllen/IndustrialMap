"""图谱查询路由：返回前端图谱可视化所需的节点和边。

数据模型（2026 二次改造后）：
- 节点：Company（产业主题作为其 Neo4j 标签）+ Theme（仅配置注册表）
- 企业关系：(Company)-[SUPPLIES / PARTNER_OF / ...]->(Company)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import neo4j_manager
from ..schemas import GraphData, GraphEdge, GraphNode, GraphStats, ThemeRef
from ..theme_labels import (
    load_theme_registry,
    refs_from_labels,
    theme_label_filter_expr,
)


router = APIRouter(prefix="/api/graph", tags=["graph"])


# ---------------------------- 内部辅助 ----------------------------

async def _themes_for(session, company_ids: list[str]) -> dict[str, list[ThemeRef]]:
    """批量获取企业主题：企业标签 ∩ 主题注册表。返回 {company_id: [ThemeRef]}。"""
    if not company_ids:
        return {}
    registry = await load_theme_registry(session)
    result = await session.run(
        f"""
        MATCH (c:Company)
        WHERE c.id IN $ids
        RETURN c.id AS cid, {theme_label_filter_expr()} AS themeLabels
        """,
        ids=company_ids,
        themeLabels=list(registry.keys()),
    )
    out: dict[str, list[ThemeRef]] = {}
    async for r in result:
        out[r["cid"]] = refs_from_labels(r["themeLabels"], registry)
    return out


# ---------------------------- 统计 ----------------------------

@router.get("/stats", response_model=GraphStats)
async def graph_stats() -> GraphStats:
    """返回企业 / 主题 / 关系总数 + 产业链/环节统计。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            """
            OPTIONAL MATCH (c:Company) WITH count(c) AS cc
            OPTIONAL MATCH (t:Theme) WITH cc, count(t) AS tc
            OPTIONAL MATCH ()-[r]->() WHERE type(r) <> 'BELONGS_TO'
                AND type(r) <> 'HAS_STAGE'
                AND type(r) <> 'UPSTREAM_OF'
                AND type(r) <> 'IN_STAGE'
            WITH cc, tc, count(r) AS rc
            OPTIONAL MATCH (ch:Chain) WITH cc, tc, rc, count(ch) AS chc
            OPTIONAL MATCH (s:Stage) WITH cc, tc, rc, chc, count(s) AS sc
            RETURN cc AS company_count,
                   tc AS theme_count,
                   rc AS relation_count,
                   chc AS chain_count,
                   sc AS stage_count
            """
        )
        record = await result.single()
    finally:
        await session.close()
    if record is None:
        return GraphStats()
    return GraphStats(
        company_count=record["company_count"],
        theme_count=record["theme_count"],
        relation_count=record["relation_count"],
        chain_count=record["chain_count"],
        stage_count=record["stage_count"],
    )


# ---------------------------- 全图 / 按主题过滤 ----------------------------

@router.get("/full", response_model=GraphData)
async def full_graph(
    theme_slug: Optional[str] = Query(
        None, description="按主题筛选（仅显示属于该主题的企业及其一跳关系）"
    ),
    limit: int = Query(300, ge=1, le=2000),
) -> GraphData:
    """返回完整图谱（或按主题过滤后的一跳子图）。"""
    session = await neo4j_manager.get_session()
    try:
        if theme_slug:
            # 按主题过滤：先找出属于该主题的企业（主题 = 企业标签），再查它们之间的关系
            companies_result = await session.run(
                """
                MATCH (c:Company)
                WHERE $slug IN labels(c)
                RETURN c.id AS id, c.name AS name
                ORDER BY c.name
                """,
                slug=theme_slug,
            )
            companies = [r async for r in companies_result]
            if not companies:
                return GraphData(nodes=[], edges=[])

            node_ids = [c["id"] for c in companies]
            # 一跳关系
            rel_result = await session.run(
                """
                MATCH (a:Company)-[r]->(b:Company)
                WHERE a.id IN $ids AND b.id IN $ids
                  AND type(r) <> 'BELONGS_TO'
                RETURN a.id AS src, b.id AS tgt, type(r) AS t
                """,
                ids=node_ids,
            )
            edges = [
                GraphEdge(
                    id=f"{r['src']}-{r['t']}-{r['tgt']}",
                    source=r["src"],
                    target=r["tgt"],
                    type=r["t"],
                )
                async for r in rel_result
            ]

            # 节点（含主题信息）
            themes_by_cid = await _themes_for(session, node_ids)
            nodes: list[GraphNode] = [
                GraphNode(
                    id=c["id"],
                    name=c["name"],
                    themes=themes_by_cid.get(c["id"], []),
                )
                for c in companies
            ]
            return GraphData(nodes=nodes, edges=edges)

        # 全图（按 limit 取前 N 个 + 它们之间的关系）
        result = await session.run(
            """
            MATCH (c:Company)
            RETURN c.id AS id, c.name AS name
            ORDER BY c.name
            LIMIT $limit
            """,
            limit=limit,
        )
        rows = [r async for r in result]
        if not rows:
            return GraphData(nodes=[], edges=[])
        node_ids = [r["id"] for r in rows]

        # 一次性收集所有节点的主题（标签 ∩ 注册表）
        themes_by_cid = await _themes_for(session, node_ids)

        nodes = [
            GraphNode(id=r["id"], name=r["name"], themes=themes_by_cid.get(r["id"], []))
            for r in rows
        ]

        # 企业之间的关系（排除 BELONGS_TO）
        rel_result = await session.run(
            """
            MATCH (a:Company)-[r]->(b:Company)
            WHERE a.id IN $ids AND b.id IN $ids
              AND type(r) <> 'BELONGS_TO'
            RETURN a.id AS src, b.id AS tgt, type(r) AS t
            """,
            ids=node_ids,
        )
        edges = [
            GraphEdge(
                id=f"{r['src']}-{r['t']}-{r['tgt']}",
                source=r["src"],
                target=r["tgt"],
                type=r["t"],
            )
            async for r in rel_result
        ]
        return GraphData(nodes=nodes, edges=edges)
    finally:
        await session.close()


# ---------------------------- 单企业 N 跳邻居 ----------------------------

@router.get("/company/{company_id}", response_model=GraphData)
async def company_neighborhood(
    company_id: str,
    depth: int = Query(1, ge=1, le=3, description="向外扩展几跳"),
) -> GraphData:
    """返回某企业周边 N 跳的子图（仅 Company 节点 + 它们之间的关系）。"""
    session = await neo4j_manager.get_session()
    try:
        result = await session.run(
            f"""
            MATCH path = (c:Company {{id: $id}})-[*1..{depth}]-(n)
            WHERE n:Company
            WITH collect(DISTINCT n) + collect(DISTINCT c) AS ns
            UNWIND ns AS node
            WITH collect(DISTINCT node) AS nodes
            UNWIND nodes AS a
            OPTIONAL MATCH (a)-[r]->(b)
            WHERE b IN nodes AND type(r) <> 'BELONGS_TO'
            RETURN a, b, type(r) AS t
            """,
            id=company_id,
        )
        records = [r async for r in result]
    finally:
        await session.close()
    if not records:
        raise HTTPException(status_code=404, detail="未找到该企业或无邻居")

    # 收集所有出现过的 Company id
    cids: set[str] = set()
    for r in records:
        if r["a"] is not None and "id" in r["a"]:
            cids.add(r["a"]["id"])
        if r["b"] is not None and "id" in r["b"]:
            cids.add(r["b"]["id"])
    cids.discard(None)  # type: ignore[arg-type]

    # 一次性批量取主题（标签 ∩ 注册表）；上面 session 已关闭，这里新开一个
    themes_by_cid: dict[str, list[ThemeRef]] = {}
    if cids:
        session2 = await neo4j_manager.get_session()
        try:
            themes_by_cid = await _themes_for(session2, list(cids))
        finally:
            await session2.close()

    node_set: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    for r in records:
        a = r["a"]
        b = r["b"]
        for node in (a, b):
            if node is None or "id" not in node:
                continue
            nid = node["id"]
            if nid not in node_set:
                node_set[nid] = GraphNode(
                    id=nid,
                    name=node.get("name", ""),
                    themes=themes_by_cid.get(nid, []),
                )
        if b is not None and r["t"]:
            edges.append(
                GraphEdge(
                    id=f"{a['id']}-{r['t']}-{b['id']}",
                    source=a["id"],
                    target=b["id"],
                    type=r["t"],
                )
            )
    return GraphData(nodes=list(node_set.values()), edges=edges)